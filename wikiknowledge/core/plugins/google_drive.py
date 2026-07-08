"""
Google Drive Knowledge Source Plugin.
:wk-id: wk/google-drive-plugin
:wk-tags: google-drive, plugin, knowledge-source, sync, cache
:wk-categories: knowledge-sources

Connects to one or more Google Drive folders via service account credentials,
discovers Google Docs, exports their content as markdown, and serves them as
virtual articles in the knowledge graph. Supports optional bi-directional
metadata sync via Google Drive appProperties.

Links to: [[knowledge-sources]], [[src:wikiknowledge/wk/index-engine]]
"""

from __future__ import annotations

import fnmatch
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from wikiknowledge.core.parser import extract_wiki_links
from wikiknowledge.core.plugins.base import KnowledgeSourcePlugin
from wikiknowledge.storage.models import ArticleMeta, ArticleType, WikiLink

logger = logging.getLogger(__name__)

# Google API scopes
SCOPES_READONLY = ["https://www.googleapis.com/auth/drive.readonly"]
SCOPES_READWRITE = ["https://www.googleapis.com/auth/drive"]

# Supported include MIME types
GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
GOOGLE_FOLDER_MIME = "application/vnd.google-apps.folder"


class GoogleDrivePlugin(KnowledgeSourcePlugin):
    """
    Knowledge Source plugin that reads Google Docs from a Drive folder.

    Discovers Google Docs within a configured folder tree, exports them
    as markdown, and caches locally in .index/<source-name>/. Supports
    optional bidirectional metadata via Google Drive appProperties.
    """

    def __init__(self, source_name: str, kb_name: str = "default", kb_dir: Optional[Path] = None):
        self.source_name = source_name
        self.kb_name = kb_name
        self._kb_dir: Optional[Path] = kb_dir
        self.config: dict = {}
        self._drive_service: Any = None
        self._available = False

        # In-memory article stores (populated from cache or sync)
        self._articles_meta: dict[str, ArticleMeta] = {}
        self._articles_content: dict[str, str] = {}
        self._links: dict[str, list[WikiLink]] = {}

    # ------------------------------------------------------------------
    # KnowledgeSourcePlugin interface
    # ------------------------------------------------------------------

    async def initialize(self, config: dict) -> None:
        """Load credentials, connect to Drive, load local cache."""
        self.config = config

        credentials_file = config.get("credentials_file")
        if not credentials_file:
            logger.warning(
                "[%s] No credentials_file configured — source unavailable.", self.source_name
            )
            self._available = False
            return

        if not Path(credentials_file).exists():
            logger.warning(
                "[%s] credentials_file '%s' not found — source unavailable.",
                self.source_name,
                credentials_file,
            )
            self._available = False
            return

        # Build Drive service
        try:
            self._drive_service = self._build_drive_service(credentials_file)
        except Exception as exc:
            logger.error("[%s] Failed to build Drive service: %s", self.source_name, exc)
            self._available = False
            return

        # Validate folder access
        folder_id = config.get("folder_id")
        if not folder_id:
            logger.warning("[%s] No folder_id configured — source unavailable.", self.source_name)
            self._available = False
            return

        try:
            self._drive_service.files().get(
                fileId=folder_id, fields="id,name,mimeType"
            ).execute()
        except Exception as exc:
            logger.error(
                "[%s] Cannot access folder '%s': %s", self.source_name, folder_id, exc
            )
            self._available = False
            return

        self._available = True

        # Load local cache (may be empty on first run)
        cache_loaded = self._load_cache()

        # Auto-sync on first launch if configured
        if not cache_loaded and config.get("auto_sync", False):
            logger.info("[%s] auto_sync=true — running initial sync.", self.source_name)
            await self.sync()

    def is_available(self) -> bool:
        return self._available

    async def discover_articles(self) -> list[ArticleMeta]:
        """Return articles from local cache (no API calls)."""
        return list(self._articles_meta.values())

    async def get_article_content(self, article_id: str) -> str:
        """Return cached markdown content for a virtual article."""
        if article_id in self._articles_content:
            return self._articles_content[article_id]

        # Fallback: try reading from disk cache
        doc_id = article_id.removeprefix("gdrive:")
        cache_file = self._cache_dir / "articles" / f"{doc_id}.md"
        if cache_file.exists():
            content = cache_file.read_text(encoding="utf-8")
            self._articles_content[article_id] = content
            return content

        raise KeyError(f"Article '{article_id}' not found in Drive source '{self.source_name}'")

    async def get_links(self) -> dict[str, list[WikiLink]]:
        return self._links

    def has_article(self, article_id: str) -> bool:
        """Check if this plugin owns the given article ID."""
        return article_id in self._articles_meta

    # ------------------------------------------------------------------
    # Sync (on-demand — called by SourceManager on rescan)
    # ------------------------------------------------------------------

    async def sync(self) -> dict:
        """
        Perform a delta sync against Google Drive.
        Returns a status dict with counts of new/updated/deleted docs.
        """
        if not self._available or self._drive_service is None:
            return {"error": "Source not available"}

        folder_id = self.config.get("folder_id")
        recursive = self.config.get("recursive", True)
        include_mime_types = self.config.get(
            "include_mime_types", [GOOGLE_DOC_MIME]
        )
        bidirectional = self.config.get("bidirectional", False)

        logger.info("[%s] Starting sync from folder '%s'.", self.source_name, folder_id)

        stats = {"new": 0, "updated": 0, "deleted": 0, "failed": 0, "unchanged": 0}

        try:
            # List all remote files
            remote_files = self._list_folder_recursive(folder_id, "", recursive, include_mime_types)
        except Exception as exc:
            logger.error("[%s] Failed to list folder: %s", self.source_name, exc)
            return {"error": str(exc)}

        # Load existing manifest for delta comparison
        manifest = self._read_manifest()
        cached_entries: dict[str, dict] = manifest.get("articles", {})

        remote_ids = {f["id"] for f in remote_files}

        # Process remote files: new and updated
        for file_info in remote_files:
            doc_id = file_info["id"]
            article_id = f"gdrive:{doc_id}"
            drive_modified = file_info.get("modifiedTime", "")

            cached = cached_entries.get(doc_id)
            if cached and cached.get("drive_modified") == drive_modified:
                # Unchanged — load from cache
                stats["unchanged"] += 1
                self._load_article_from_cache(doc_id, cached)
                continue

            # New or modified — export from Drive
            try:
                content = self._export_doc(
                    doc_id=doc_id,
                    title=file_info.get("name", doc_id),
                    web_view_link=file_info.get("webViewLink", ""),
                )
            except Exception as exc:
                logger.warning("[%s] Failed to export doc '%s': %s", self.source_name, doc_id, exc)
                stats["failed"] += 1
                continue

            # Read properties for bidirectional metadata (fallback to appProperties for legacy)
            tags: list[str] = []
            categories: list[str] = []
            if bidirectional:
                props = file_info.get("properties", {}) or {}
                app_props = file_info.get("appProperties", {}) or {}
                
                raw_tags = props.get("wk_tags")
                if raw_tags is None:
                    raw_tags = app_props.get("wk_tags", "")
                    
                raw_cats = props.get("wk_categories")
                if raw_cats is None:
                    raw_cats = app_props.get("wk_categories", "")
                    
                tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
                categories = [c.strip() for c in raw_cats.split(",") if c.strip()]

            # Build metadata
            created_str = file_info.get("createdTime", "")
            modified_str = drive_modified

            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                created = datetime.now(timezone.utc)

            try:
                modified = datetime.fromisoformat(modified_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                modified = datetime.now(timezone.utc)

            meta = ArticleMeta(
                id=article_id,
                title=file_info.get("name", doc_id),
                type=ArticleType.LEAF,
                tags=tags,
                categories=categories,
                created=created,
                modified=modified,
            )

            # Save to disk cache
            cache_file = self._cache_dir / "articles" / f"{doc_id}.md"
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(content, encoding="utf-8")

            # Update in-memory state
            self._articles_meta[article_id] = meta
            self._articles_content[article_id] = content
            self._links[article_id] = extract_wiki_links(article_id, content)

            # Update manifest entry
            cached_entries[doc_id] = {
                "title": meta.title,
                "drive_modified": drive_modified,
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "drive_created": created_str,
                "mime_type": file_info.get("mimeType", GOOGLE_DOC_MIME),
                "drive_path": file_info.get("_path", ""),
                "web_view_link": file_info.get("webViewLink", ""),
                "tags": tags,
                "categories": categories,
                "metadata_dirty": False,
                "size_bytes": len(content.encode("utf-8")),
            }

            if cached:
                stats["updated"] += 1
            else:
                stats["new"] += 1

        # Remove deleted docs
        deleted_ids = set(cached_entries.keys()) - remote_ids
        for doc_id in deleted_ids:
            article_id = f"gdrive:{doc_id}"
            self._articles_meta.pop(article_id, None)
            self._articles_content.pop(article_id, None)
            self._links.pop(article_id, None)
            del cached_entries[doc_id]

            cache_file = self._cache_dir / "articles" / f"{doc_id}.md"
            if cache_file.exists():
                cache_file.unlink()

            stats["deleted"] += 1

        # Push dirty metadata back to Drive (bidirectional)
        if bidirectional:
            self._push_dirty_metadata(cached_entries)

        # Save updated manifest
        new_manifest = {
            "source_name": self.source_name,
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "folder_id": folder_id,
            "sync_status": "partial" if stats["failed"] > 0 else "success",
            "articles": cached_entries,
        }
        self._write_manifest(new_manifest)

        logger.info(
            "[%s] Sync complete — new:%d updated:%d deleted:%d failed:%d unchanged:%d",
            self.source_name, stats["new"], stats["updated"],
            stats["deleted"], stats["failed"], stats["unchanged"],
        )
        return stats

    # ------------------------------------------------------------------
    # Bidirectional metadata
    # ------------------------------------------------------------------

    def update_article_metadata(
        self, article_id: str, tags: list[str], categories: list[str]
    ) -> None:
        """
        Update tags/categories for a Google Drive article locally,
        and push immediately to Google Drive if bidirectional is true.
        """
        if article_id not in self._articles_meta:
            raise KeyError(f"Article '{article_id}' not found")

        meta = self._articles_meta[article_id]
        # Rebuild with updated values
        self._articles_meta[article_id] = ArticleMeta(
            id=meta.id,
            title=meta.title,
            type=meta.type,
            tags=tags,
            categories=categories,
            created=meta.created,
            modified=meta.modified,
        )

        doc_id = article_id.removeprefix("gdrive:")
        bidirectional = self.config.get("bidirectional", False)
        pushed = False

        if bidirectional and self._available and self._drive_service:
            tags_str = ",".join(tags)
            cats_str = ",".join(categories)
            try:
                self._drive_service.files().update(
                    fileId=doc_id,
                    body={
                        "properties": {
                            "wk_tags": tags_str[:124],
                            "wk_categories": cats_str[:124],
                        }
                    },
                    fields="id,properties",
                ).execute()
                pushed = True
                logger.info("[%s] Immediately pushed metadata for doc '%s'.", self.source_name, doc_id)
            except Exception as exc:
                logger.error("[%s] Failed to push metadata immediately for doc '%s': %s", self.source_name, doc_id, exc)

        # Update in manifest
        manifest = self._read_manifest()
        if doc_id in manifest.get("articles", {}):
            manifest["articles"][doc_id]["tags"] = tags
            manifest["articles"][doc_id]["categories"] = categories
            manifest["articles"][doc_id]["metadata_dirty"] = not pushed
            manifest["articles"][doc_id]["metadata_modified_locally"] = (
                datetime.now(timezone.utc).isoformat()
            )
            self._write_manifest(manifest)

    def _push_dirty_metadata(self, entries: dict[str, dict]) -> None:
        """Push locally-modified metadata to Drive via custom file properties."""
        for doc_id, entry in entries.items():
            if not entry.get("metadata_dirty"):
                continue

            tags = entry.get("tags", [])
            categories = entry.get("categories", [])

            tags_str = ",".join(tags)
            cats_str = ",".join(categories)

            # Warn if over properties value limit (~120 chars)
            if len(tags_str) > 120:
                logger.warning(
                    "[%s] Tags for doc '%s' exceed 120 chars — will be truncated by Drive API.",
                    self.source_name, doc_id,
                )
            if len(cats_str) > 120:
                logger.warning(
                    "[%s] Categories for doc '%s' exceed 120 chars — will be truncated by Drive API.",
                    self.source_name, doc_id,
                )

            try:
                self._drive_service.files().update(
                    fileId=doc_id,
                    body={
                        "properties": {
                            "wk_tags": tags_str[:124],
                            "wk_categories": cats_str[:124],
                        }
                    },
                    fields="id,properties",
                ).execute()
                entry["metadata_dirty"] = False
                logger.info(
                    "[%s] Pushed metadata for doc '%s'.", self.source_name, doc_id
                )
            except Exception as exc:
                logger.error(
                    "[%s] Failed to push metadata for doc '%s': %s",
                    self.source_name, doc_id, exc,
                )

    # ------------------------------------------------------------------
    # Private helpers — Drive API
    # ------------------------------------------------------------------

    def _build_drive_service(self, credentials_file: str) -> Any:
        """Build and return a Google Drive API service client."""
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        bidirectional = self.config.get("bidirectional", False)
        scopes = SCOPES_READWRITE if bidirectional else SCOPES_READONLY

        creds = service_account.Credentials.from_service_account_file(
            credentials_file, scopes=scopes
        )
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    def _list_folder_recursive(
        self,
        folder_id: str,
        current_path: str,
        recursive: bool,
        include_mime_types: list[str],
    ) -> list[dict]:
        """
        List all matching files under folder_id, optionally recursing.
        Returns a list of file metadata dicts with an extra '_path' field.
        """
        exclude_patterns = self.config.get("exclude_patterns", [])
        results: list[dict] = []
        subfolders: list[tuple[str, str]] = []  # (id, path)

        # We need properties too for bidirectional read
        fields = (
            "nextPageToken, files(id,name,mimeType,modifiedTime,createdTime,"
            "webViewLink,properties,appProperties)"
        )
        page_token = None

        while True:
            try:
                resp = self._drive_service.files().list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    fields=fields,
                    pageSize=1000,
                    pageToken=page_token,
                ).execute()
            except Exception as exc:
                # Retry once on transient errors
                logger.warning(
                    "[%s] Drive list error (retrying): %s", self.source_name, exc
                )
                time.sleep(1)
                resp = self._drive_service.files().list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    fields=fields,
                    pageSize=1000,
                    pageToken=page_token,
                ).execute()

            for file_info in resp.get("files", []):
                mime = file_info.get("mimeType", "")
                name = file_info.get("name", "")
                file_path = f"{current_path}/{name}".lstrip("/")

                # Check exclude patterns
                if self._is_excluded(file_path, exclude_patterns):
                    continue

                if mime == GOOGLE_FOLDER_MIME:
                    if recursive:
                        subfolders.append((file_info["id"], file_path))
                elif mime in include_mime_types:
                    file_info["_path"] = file_path
                    results.append(file_info)

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        # Recurse into subfolders
        for sub_id, sub_path in subfolders:
            results.extend(
                self._list_folder_recursive(sub_id, sub_path, recursive, include_mime_types)
            )

        return results

    def _is_excluded(self, path: str, patterns: list[str]) -> bool:
        """Return True if the given path matches any exclude pattern."""
        for pattern in patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
        return False

    def _export_doc(self, doc_id: str, title: str, web_view_link: str) -> str:
        """
        Export a Google Doc as markdown. Falls back to HTML+markdownify
        if the markdown export is empty or suspiciously short.
        """
        # Try markdown export first
        try:
            content = self._drive_service.files().export(
                fileId=doc_id,
                mimeType="text/markdown",
            ).execute()
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="replace")
        except Exception as exc:
            logger.debug(
                "[%s] Markdown export failed for '%s', trying HTML: %s",
                self.source_name, doc_id, exc,
            )
            content = ""

        # Fall back to HTML + markdownify if result looks empty/broken
        if not content or len(content.strip()) < 20:
            try:
                html_bytes = self._drive_service.files().export(
                    fileId=doc_id,
                    mimeType="text/html",
                ).execute()
                if isinstance(html_bytes, bytes):
                    html_bytes = html_bytes.decode("utf-8", errors="replace")
                import markdownify  # type: ignore[import-untyped]
                content = markdownify.markdownify(html_bytes, heading_style="ATX")
            except Exception as exc2:
                logger.error(
                    "[%s] Both markdown and HTML export failed for '%s': %s",
                    self.source_name, doc_id, exc2,
                )
                content = f"*Content could not be exported from Google Drive.*"

        content = self._post_process_content(content, title, doc_id, web_view_link)
        return content

    def _post_process_content(
        self, content: str, title: str, doc_id: str, web_view_link: str
    ) -> str:
        """Normalize heading, strip metadata markers, append Drive footer."""
        lines = content.strip().split("\n")

        # Ensure first content line is an H1 matching the doc title
        if not lines or not lines[0].startswith("# "):
            lines.insert(0, f"# {title}")
        elif lines[0].strip("# ").strip() != title:
            # First heading exists but differs — prepend canonical title
            lines.insert(0, f"# {title}")

        content = "\n".join(lines)

        # Append Google Drive source link footer
        if web_view_link:
            footer = f"\n\n---\n🔌 **Source**: [View in Google Drive]({web_view_link})"
        else:
            footer = f"\n\n---\n🔌 **Source**: Google Drive (doc id: `{doc_id}`)"

        return content + footer

    # ------------------------------------------------------------------
    # Private helpers — local cache
    # ------------------------------------------------------------------

    @property
    def _cache_dir(self) -> Path:
        """Return the per-source cache directory path."""
        if self._kb_dir is None:
            raise RuntimeError("kb_dir not set on GoogleDrivePlugin")
        return self._kb_dir / ".index" / self.source_name

    def _read_manifest(self) -> dict:
        """Read manifest.json from the cache directory, or return an empty manifest."""
        manifest_path = self._cache_dir / "manifest.json"
        if not manifest_path.exists():
            return {"articles": {}}
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning(
                "[%s] Failed to read manifest, starting fresh: %s", self.source_name, exc
            )
            return {"articles": {}}

    def _write_manifest(self, manifest: dict) -> None:
        """Write manifest.json atomically using temp-file + rename."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self._cache_dir / "manifest.json"
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=self._cache_dir, prefix="manifest_", suffix=".json.tmp"
            )
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, manifest_path)
        except Exception as exc:
            logger.error("[%s] Failed to write manifest: %s", self.source_name, exc)

    def _load_cache(self) -> bool:
        """
        Load all cached articles from disk into memory.
        Returns True if cache existed and was loaded, False if empty/missing.
        """
        manifest = self._read_manifest()
        entries = manifest.get("articles", {})
        if not entries:
            return False

        articles_dir = self._cache_dir / "articles"
        loaded = 0

        for doc_id, entry in entries.items():
            article_id = f"gdrive:{doc_id}"

            # Parse timestamps
            try:
                created = datetime.fromisoformat(
                    entry.get("drive_created", "").replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                created = datetime.now(timezone.utc)

            try:
                modified = datetime.fromisoformat(
                    entry.get("drive_modified", "").replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                modified = datetime.now(timezone.utc)

            meta = ArticleMeta(
                id=article_id,
                title=entry.get("title", doc_id),
                type=ArticleType.LEAF,
                tags=entry.get("tags", []),
                categories=entry.get("categories", []),
                created=created,
                modified=modified,
            )
            self._articles_meta[article_id] = meta

            # Lazy-load content — only load if file exists, defer actual read
            cache_file = articles_dir / f"{doc_id}.md"
            if cache_file.exists():
                try:
                    content = cache_file.read_text(encoding="utf-8")
                    self._articles_content[article_id] = content
                    self._links[article_id] = extract_wiki_links(article_id, content)
                    loaded += 1
                except Exception as exc:
                    logger.warning(
                        "[%s] Failed to read cached article '%s': %s",
                        self.source_name, doc_id, exc,
                    )

        logger.info("[%s] Loaded %d articles from cache.", self.source_name, loaded)
        return loaded > 0

    def _load_article_from_cache(self, doc_id: str, entry: dict) -> None:
        """
        Restore a single unchanged article from a manifest entry into memory.
        Called during sync for docs that haven't changed since last sync.
        """
        article_id = f"gdrive:{doc_id}"
        if article_id in self._articles_meta:
            return  # Already loaded

        try:
            created = datetime.fromisoformat(
                entry.get("drive_created", "").replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            created = datetime.now(timezone.utc)

        try:
            modified = datetime.fromisoformat(
                entry.get("drive_modified", "").replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            modified = datetime.now(timezone.utc)

        meta = ArticleMeta(
            id=article_id,
            title=entry.get("title", doc_id),
            type=ArticleType.LEAF,
            tags=entry.get("tags", []),
            categories=entry.get("categories", []),
            created=created,
            modified=modified,
        )
        self._articles_meta[article_id] = meta

        cache_file = self._cache_dir / "articles" / f"{doc_id}.md"
        if cache_file.exists():
            try:
                content = cache_file.read_text(encoding="utf-8")
                self._articles_content[article_id] = content
                self._links[article_id] = extract_wiki_links(article_id, content)
            except Exception as exc:
                logger.warning(
                    "[%s] Failed to read cached article '%s': %s",
                    self.source_name, doc_id, exc,
                )
