"""
Unit tests for GoogleDrivePlugin.

Tests use unittest.mock to avoid any real Google API calls.
Run with: uv run pytest tests/ -v
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wikiknowledge.core.plugins.google_drive import GoogleDrivePlugin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_drive_file(
    doc_id: str,
    name: str = "Test Doc",
    modified: str = "2026-01-01T12:00:00.000Z",
    created: str = "2026-01-01T00:00:00.000Z",
    mime: str = "application/vnd.google-apps.document",
    app_props: dict | None = None,
) -> dict:
    return {
        "id": doc_id,
        "name": name,
        "mimeType": mime,
        "modifiedTime": modified,
        "createdTime": created,
        "webViewLink": f"https://docs.google.com/document/d/{doc_id}/edit",
        "appProperties": app_props or {},
        "_path": name,
    }


def _make_plugin(tmp_path: Path, config: dict | None = None) -> GoogleDrivePlugin:
    """Create a plugin with kb_dir pointing to tmp_path."""
    plugin = GoogleDrivePlugin("test-source", "default", kb_dir=tmp_path)
    plugin._drive_service = MagicMock()  # Pre-wire mock service
    plugin._available = True
    if config:
        plugin.config = config
    else:
        plugin.config = {
            "folder_id": "folder-abc",
            "bidirectional": False,
            "auto_sync": False,
            "recursive": True,
            "include_mime_types": ["application/vnd.google-apps.document"],
            "exclude_patterns": [],
        }
    return plugin


# ---------------------------------------------------------------------------
# Cache: load and write
# ---------------------------------------------------------------------------

class TestCacheLoadSave:
    def test_cache_dir_path(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        assert plugin._cache_dir == tmp_path / ".index" / "test-source"

    def test_load_cache_empty_returns_false(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        result = plugin._load_cache()
        assert result is False
        assert plugin._articles_meta == {}

    def test_write_and_read_manifest(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        manifest = {
            "source_name": "test-source",
            "last_sync": "2026-01-01T00:00:00+00:00",
            "folder_id": "folder-abc",
            "sync_status": "success",
            "articles": {
                "doc-001": {
                    "title": "Hello",
                    "drive_modified": "2026-01-01T12:00:00.000Z",
                    "cached_at": "2026-01-01T12:01:00+00:00",
                    "drive_created": "2026-01-01T00:00:00.000Z",
                    "mime_type": "application/vnd.google-apps.document",
                    "drive_path": "Hello",
                    "web_view_link": "https://docs.google.com/document/d/doc-001/edit",
                    "tags": ["tag1"],
                    "categories": ["cat1"],
                    "metadata_dirty": False,
                    "size_bytes": 100,
                }
            },
        }
        plugin._write_manifest(manifest)

        # Manifest file should exist
        assert (plugin._cache_dir / "manifest.json").exists()

        # Read it back
        loaded = plugin._read_manifest()
        assert loaded["source_name"] == "test-source"
        assert "doc-001" in loaded["articles"]
        assert loaded["articles"]["doc-001"]["title"] == "Hello"

    def test_load_cache_populates_articles(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)

        # Write a manifest + article file
        articles_dir = plugin._cache_dir / "articles"
        articles_dir.mkdir(parents=True)
        (articles_dir / "doc-001.md").write_text("# Hello\n\nContent.", encoding="utf-8")

        manifest = {
            "articles": {
                "doc-001": {
                    "title": "Hello",
                    "drive_modified": "2026-01-01T12:00:00.000Z",
                    "cached_at": "2026-01-01T12:01:00+00:00",
                    "drive_created": "2026-01-01T00:00:00.000Z",
                    "mime_type": "application/vnd.google-apps.document",
                    "drive_path": "Hello",
                    "web_view_link": "",
                    "tags": [],
                    "categories": [],
                    "metadata_dirty": False,
                    "size_bytes": 0,
                }
            }
        }
        plugin._write_manifest(manifest)

        result = plugin._load_cache()
        assert result is True
        assert "gdrive:doc-001" in plugin._articles_meta
        assert plugin._articles_meta["gdrive:doc-001"].title == "Hello"
        assert "gdrive:doc-001" in plugin._articles_content
        assert "Hello" in plugin._articles_content["gdrive:doc-001"]


# ---------------------------------------------------------------------------
# Content retrieval
# ---------------------------------------------------------------------------

class TestGetArticleContent:
    async def test_returns_content_from_memory(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        plugin._articles_content["gdrive:doc-001"] = "# My Doc\n\nBody."

        content = await plugin.get_article_content("gdrive:doc-001")
        assert content == "# My Doc\n\nBody."

    async def test_falls_back_to_disk(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        articles_dir = plugin._cache_dir / "articles"
        articles_dir.mkdir(parents=True)
        (articles_dir / "doc-002.md").write_text("# Disk Doc\n\nFrom disk.", encoding="utf-8")

        content = await plugin.get_article_content("gdrive:doc-002")
        assert "Disk Doc" in content

    async def test_raises_key_error_for_missing(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        with pytest.raises(KeyError):
            await plugin.get_article_content("gdrive:nonexistent")


# ---------------------------------------------------------------------------
# Export doc: markdown / fallback
# ---------------------------------------------------------------------------

class TestExportDoc:
    def test_markdown_export_used_when_valid(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        plugin._drive_service.files.return_value.export.return_value.execute.return_value = (
            b"# Title\n\nThis is some content that is long enough."
        )

        result = plugin._export_doc("doc-001", "Title", "https://example.com/doc")
        assert "# Title" in result
        assert "View in Google Drive" in result

    def test_fallback_to_html_when_markdown_empty(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)

        # First call (markdown) returns empty, second call (HTML) returns content
        execute_mock = MagicMock()
        execute_mock.side_effect = [
            b"",  # markdown empty
            b"<h1>Title</h1><p>Content from HTML</p>",  # HTML response
        ]
        plugin._drive_service.files.return_value.export.return_value.execute = execute_mock

        result = plugin._export_doc("doc-001", "Title", "https://example.com/doc")
        assert "Title" in result
        assert "Content from HTML" in result

    def test_fallback_when_markdown_throws(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)

        execute_mock = MagicMock()
        execute_mock.side_effect = [
            Exception("Export failed"),  # markdown throws
            b"<h1>Title</h1><p>Fallback content</p>",  # HTML succeeds
        ]
        plugin._drive_service.files.return_value.export.return_value.execute = execute_mock

        result = plugin._export_doc("doc-001", "Title", "")
        assert "Title" in result

    def test_post_process_adds_h1_if_missing(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        result = plugin._post_process_content("No heading here.", "My Title", "doc-001", "")
        assert result.startswith("# My Title")

    def test_post_process_appends_footer_link(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        result = plugin._post_process_content("# My Title\n\nBody", "My Title", "doc-001", "https://link")
        assert "View in Google Drive" in result
        assert "https://link" in result

    def test_post_process_footer_without_link_uses_doc_id(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        result = plugin._post_process_content("# My Title\n\nBody", "My Title", "doc-abc", "")
        assert "doc-abc" in result


# ---------------------------------------------------------------------------
# List folder recursive
# ---------------------------------------------------------------------------

class TestListFolderRecursive:
    def _make_list_response(self, files: list, next_page_token: str | None = None) -> dict:
        resp = {"files": files}
        if next_page_token:
            resp["nextPageToken"] = next_page_token
        return resp

    def test_lists_docs_in_folder(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        doc = _make_drive_file("doc-001", "Doc One")
        plugin._drive_service.files.return_value.list.return_value.execute.return_value = (
            self._make_list_response([doc])
        )

        results = plugin._list_folder_recursive(
            "folder-abc", "", recursive=False, include_mime_types=["application/vnd.google-apps.document"]
        )
        assert len(results) == 1
        assert results[0]["id"] == "doc-001"

    def test_excludes_folders_when_not_recursive(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        folder = _make_drive_file("subfolder-1", "Subfolder", mime="application/vnd.google-apps.folder")
        doc = _make_drive_file("doc-001", "Doc One")
        plugin._drive_service.files.return_value.list.return_value.execute.return_value = (
            self._make_list_response([folder, doc])
        )

        results = plugin._list_folder_recursive(
            "folder-abc", "", recursive=False, include_mime_types=["application/vnd.google-apps.document"]
        )
        assert len(results) == 1
        assert results[0]["id"] == "doc-001"

    def test_applies_exclude_patterns(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        plugin.config["exclude_patterns"] = ["Archive/*"]

        doc_include = _make_drive_file("doc-001", "Normal Doc")
        doc_exclude = _make_drive_file("doc-002", "Archive Doc")

        # Simulate: "Archive" folder contents (current_path="Archive")
        # So the plugin will build: "Archive/Archive Doc" and "Archive/Normal Doc"
        # We want doc-002 excluded when it's inside Archive, doc-001 included.
        plugin._drive_service.files.return_value.list.return_value.execute.return_value = (
            self._make_list_response([doc_include, doc_exclude])
        )

        # Call with current_path="Archive" so paths are "Archive/Normal Doc" and "Archive/Archive Doc"
        # Only "Archive/Archive Doc" matches the "Archive/*" pattern, so only doc_include survives.
        # But "Archive/Normal Doc" also matches "Archive/*"! So use a more specific pattern.
        plugin.config["exclude_patterns"] = ["Archive/Archive*"]

        results = plugin._list_folder_recursive(
            "folder-abc", "Archive", recursive=False, include_mime_types=["application/vnd.google-apps.document"]
        )
        ids = [r["id"] for r in results]
        assert "doc-001" in ids
        assert "doc-002" not in ids


    def test_is_excluded_patterns(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        assert plugin._is_excluded("Archive/old-doc", ["Archive/*"]) is True
        assert plugin._is_excluded("Design/new-doc", ["Archive/*"]) is False
        assert plugin._is_excluded("temp.tmp", ["*.tmp"]) is True


# ---------------------------------------------------------------------------
# Delta sync
# ---------------------------------------------------------------------------

class TestSync:
    async def test_sync_new_doc_added_to_cache(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        doc = _make_drive_file("doc-001", "New Doc", modified="2026-01-02T12:00:00.000Z")

        # Mock folder listing
        plugin._drive_service.files.return_value.list.return_value.execute.return_value = {
            "files": [doc]
        }
        # Mock export
        plugin._drive_service.files.return_value.export.return_value.execute.return_value = (
            b"# New Doc\n\nSome content here that is long enough to pass the check."
        )

        stats = await plugin.sync()

        assert stats["new"] == 1
        assert stats["updated"] == 0
        assert stats["deleted"] == 0
        assert "gdrive:doc-001" in plugin._articles_meta
        assert plugin._articles_meta["gdrive:doc-001"].title == "New Doc"

        # Check cache file written
        cache_file = plugin._cache_dir / "articles" / "doc-001.md"
        assert cache_file.exists()

    async def test_sync_unchanged_doc_skipped(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        mod_time = "2026-01-01T12:00:00.000Z"
        doc = _make_drive_file("doc-001", "Doc", modified=mod_time)

        # Pre-populate manifest with same modifiedTime
        manifest = {
            "articles": {
                "doc-001": {
                    "title": "Doc",
                    "drive_modified": mod_time,
                    "cached_at": "2026-01-01T12:01:00+00:00",
                    "drive_created": "2026-01-01T00:00:00.000Z",
                    "mime_type": "application/vnd.google-apps.document",
                    "drive_path": "Doc",
                    "web_view_link": "",
                    "tags": [],
                    "categories": [],
                    "metadata_dirty": False,
                    "size_bytes": 50,
                }
            }
        }
        plugin._cache_dir.mkdir(parents=True)
        plugin._write_manifest(manifest)
        (plugin._cache_dir / "articles").mkdir(parents=True)
        (plugin._cache_dir / "articles" / "doc-001.md").write_text("# Doc\n\nCached.", encoding="utf-8")

        plugin._drive_service.files.return_value.list.return_value.execute.return_value = {
            "files": [doc]
        }

        stats = await plugin.sync()

        assert stats["unchanged"] == 1
        assert stats["new"] == 0
        # Export should NOT have been called for unchanged docs
        plugin._drive_service.files.return_value.export.assert_not_called()

    async def test_sync_deleted_doc_removed(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)

        # Pre-populate manifest with a doc
        plugin._cache_dir.mkdir(parents=True)
        (plugin._cache_dir / "articles").mkdir(parents=True)
        (plugin._cache_dir / "articles" / "doc-old.md").write_text("# Old", encoding="utf-8")
        plugin._write_manifest({
            "articles": {
                "doc-old": {
                    "title": "Old Doc",
                    "drive_modified": "2026-01-01T00:00:00.000Z",
                    "cached_at": "",
                    "drive_created": "",
                    "mime_type": "application/vnd.google-apps.document",
                    "drive_path": "Old Doc",
                    "web_view_link": "",
                    "tags": [],
                    "categories": [],
                    "metadata_dirty": False,
                    "size_bytes": 0,
                }
            }
        })

        # Remote returns NO docs (doc was deleted from Drive)
        plugin._drive_service.files.return_value.list.return_value.execute.return_value = {
            "files": []
        }

        stats = await plugin.sync()

        assert stats["deleted"] == 1
        assert "gdrive:doc-old" not in plugin._articles_meta
        assert not (plugin._cache_dir / "articles" / "doc-old.md").exists()

    async def test_sync_updated_doc_re_exported(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        old_mod = "2026-01-01T12:00:00.000Z"
        new_mod = "2026-01-02T12:00:00.000Z"

        # Pre-populate manifest with old modified time
        plugin._cache_dir.mkdir(parents=True)
        (plugin._cache_dir / "articles").mkdir(parents=True)
        (plugin._cache_dir / "articles" / "doc-001.md").write_text("# Old Content", encoding="utf-8")
        plugin._write_manifest({
            "articles": {
                "doc-001": {
                    "title": "Doc",
                    "drive_modified": old_mod,
                    "cached_at": "",
                    "drive_created": "",
                    "mime_type": "application/vnd.google-apps.document",
                    "drive_path": "Doc",
                    "web_view_link": "",
                    "tags": [],
                    "categories": [],
                    "metadata_dirty": False,
                    "size_bytes": 0,
                }
            }
        })

        # Remote has a newer modifiedTime
        doc = _make_drive_file("doc-001", "Doc", modified=new_mod)
        plugin._drive_service.files.return_value.list.return_value.execute.return_value = {
            "files": [doc]
        }
        plugin._drive_service.files.return_value.export.return_value.execute.return_value = (
            b"# Doc\n\nUpdated content is definitely long enough to pass the validation check."
        )

        stats = await plugin.sync()

        assert stats["updated"] == 1
        assert stats["new"] == 0

    async def test_sync_returns_error_on_api_failure(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        plugin._drive_service.files.return_value.list.return_value.execute.side_effect = (
            Exception("API rate limit exceeded")
        )

        stats = await plugin.sync()
        assert "error" in stats


# ---------------------------------------------------------------------------
# Bidirectional metadata
# ---------------------------------------------------------------------------

class TestBidirectionalMetadata:
    async def test_update_article_metadata_sets_dirty(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        plugin.config["bidirectional"] = True

        # Pre-populate article
        plugin._cache_dir.mkdir(parents=True)
        plugin._write_manifest({
            "articles": {
                "doc-001": {
                    "title": "Doc",
                    "drive_modified": "2026-01-01T12:00:00.000Z",
                    "cached_at": "",
                    "drive_created": "",
                    "mime_type": "application/vnd.google-apps.document",
                    "drive_path": "Doc",
                    "web_view_link": "",
                    "tags": [],
                    "categories": [],
                    "metadata_dirty": False,
                    "size_bytes": 0,
                }
            }
        })
        (plugin._cache_dir / "articles").mkdir(parents=True)
        (plugin._cache_dir / "articles" / "doc-001.md").write_text("# Doc", encoding="utf-8")
        plugin._load_cache()

        plugin.update_article_metadata("gdrive:doc-001", tags=["new-tag"], categories=["cat-a"])

        # Metadata updated in memory
        assert plugin._articles_meta["gdrive:doc-001"].tags == ["new-tag"]
        assert plugin._articles_meta["gdrive:doc-001"].categories == ["cat-a"]

        # Manifest dirty flag set
        manifest = plugin._read_manifest()
        assert manifest["articles"]["doc-001"]["metadata_dirty"] is True
        assert manifest["articles"]["doc-001"]["tags"] == ["new-tag"]

    async def test_update_metadata_raises_for_unknown_article(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        with pytest.raises(KeyError):
            plugin.update_article_metadata("gdrive:nonexistent", tags=[], categories=[])

    async def test_push_dirty_metadata_calls_drive_api(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        plugin.config["bidirectional"] = True

        entries = {
            "doc-001": {
                "metadata_dirty": True,
                "tags": ["architecture"],
                "categories": ["system"],
            }
        }
        plugin._drive_service.files.return_value.update.return_value.execute.return_value = {
            "id": "doc-001"
        }

        plugin._push_dirty_metadata(entries)

        # Drive files.update() should have been called
        plugin._drive_service.files.return_value.update.assert_called_once()
        # Dirty flag cleared
        assert entries["doc-001"]["metadata_dirty"] is False

    async def test_push_skips_clean_entries(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        entries = {
            "doc-001": {"metadata_dirty": False, "tags": [], "categories": []},
        }
        plugin._push_dirty_metadata(entries)
        plugin._drive_service.files.return_value.update.assert_not_called()


# ---------------------------------------------------------------------------
# has_article
# ---------------------------------------------------------------------------

class TestHasArticle:
    def test_returns_true_when_present(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        plugin._articles_meta["gdrive:doc-001"] = MagicMock()
        assert plugin.has_article("gdrive:doc-001") is True

    def test_returns_false_when_absent(self, tmp_path: Path):
        plugin = _make_plugin(tmp_path)
        assert plugin.has_article("gdrive:unknown") is False


# ---------------------------------------------------------------------------
# initialize — graceful degradation
# ---------------------------------------------------------------------------

class TestInitialize:
    async def test_unavailable_when_no_credentials(self, tmp_path: Path):
        plugin = GoogleDrivePlugin("test", "default", kb_dir=tmp_path)
        await plugin.initialize({"folder_id": "folder-abc"})  # no credentials_file
        assert plugin.is_available() is False

    async def test_unavailable_when_credentials_file_missing(self, tmp_path: Path):
        plugin = GoogleDrivePlugin("test", "default", kb_dir=tmp_path)
        await plugin.initialize({
            "folder_id": "folder-abc",
            "credentials_file": "/nonexistent/path/key.json",
        })
        assert plugin.is_available() is False

    async def test_unavailable_when_no_folder_id(self, tmp_path: Path):
        # Create a dummy credentials file
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")

        plugin = GoogleDrivePlugin("test", "default", kb_dir=tmp_path)
        with patch("wikiknowledge.core.plugins.google_drive.GoogleDrivePlugin._build_drive_service"):
            await plugin.initialize({
                "credentials_file": str(creds_file),
                # no folder_id
            })
        assert plugin.is_available() is False
