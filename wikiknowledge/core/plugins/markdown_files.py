"""Markdown Files Plugin

:wk-id: markdown-files-plugin
:wk-tags: knowledge-sources, markdown, plugin, hierarchy
:wk-categories: knowledge-sources

Imports a plain markdown documentation tree (Docusaurus/MkDocs style) as virtual articles.

Folders become category articles, files become leaf articles, and relative markdown
links are rewritten into [[wiki-links]] on serving, since WikiKnowledge has a flat ID space.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, quote

import frontmatter

from wikiknowledge.core.parser import extract_wiki_links
from wikiknowledge.core.plugins.base import KnowledgeSourcePlugin
from wikiknowledge.storage.models import ArticleMeta, ArticleType, WikiLink

# [text](target) and ![alt](target "title")
MD_LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(\s*<?([^)<>\s]+)>?(\s+\"[^\"]*\"|\s+'[^']*')?\s*\)")
CODE_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
EXTERNAL_RE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|#)", re.IGNORECASE)


def slugify(value: str) -> str:
    """Turn an arbitrary path segment into a lowercase dash-separated slug."""
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value)
    return re.sub(r"-{2,}", "-", value).strip("-").lower()


class MarkdownFilesPlugin(KnowledgeSourcePlugin):
    """Exposes a hierarchy of markdown files as virtual wiki articles."""

    MD_EXTENSIONS = (".md", ".mdx", ".markdown")
    INDEX_NAMES = ("index", "readme", "_index", "_category_")

    def __init__(self, source_name: str, kb_name: str = "default"):
        self.source_name = source_name
        self.kb_name = kb_name
        self.config: dict = {}
        self.root_path: Path = Path(".")
        self._articles_meta: dict[str, ArticleMeta] = {}
        self._articles_content: dict[str, str] = {}
        self._links: dict[str, list[WikiLink]] = {}
        # resolved absolute posix path -> article id (files and folders)
        self._path_to_id: dict[str, str] = {}
        self._available = False

    # --- Lifecycle ---

    async def initialize(self, config: dict) -> None:
        self.config = config
        path_str = config.get("path")
        if not path_str:
            self._available = False
            return

        self.root_path = Path(path_str).resolve()
        self._available = self.root_path.exists() and self.root_path.is_dir()

    def is_available(self) -> bool:
        return self._available

    # --- Config accessors ---

    @property
    def _include(self) -> list[str]:
        return self.config.get("include") or ["**/*.md"]

    @property
    def _exclude(self) -> list[str]:
        return self.config.get("exclude") or []

    @property
    def _folders_as_categories(self) -> bool:
        return self.config.get("folders_as_categories", True)

    @property
    def _root_id(self) -> str:
        return self.config.get("root_id") or slugify(self.source_name)

    @property
    def _root_categories(self) -> list[str]:
        """KB categories the top level of the imported tree is attached to."""
        return self.config.get("categories") or []

    @property
    def _extra_tags(self) -> list[str]:
        return self.config.get("tags") or []

    # --- Discovery ---

    async def discover_articles(self) -> list[ArticleMeta]:
        if not self.is_available():
            return []

        self._articles_meta.clear()
        self._articles_content.clear()
        self._links.clear()
        self._path_to_id.clear()

        files = self._collect_files()
        if not files:
            return []

        folders = self._collect_folders(files)
        index_files = self._map_index_files(files, folders)

        # Register IDs first so links between files can be resolved in any order.
        claimed: dict[str, Path] = {}
        for folder in folders:
            article_id = self._folder_article_id(folder)
            claimed[article_id] = folder
            self._path_to_id[folder.as_posix()] = article_id

        for file_path in files:
            folder = index_files.get(file_path)
            if folder is not None:
                self._path_to_id[file_path.as_posix()] = self._folder_article_id(folder)
                continue

            article_id = self._file_article_id(file_path)
            if article_id in claimed:
                print(
                    f"Markdown source '{self.source_name}': ID collision '{article_id}' "
                    f"between {claimed[article_id]} and {file_path}"
                )
                suffix = 2
                while f"{article_id}-{suffix}" in claimed:
                    suffix += 1
                article_id = f"{article_id}-{suffix}"
            claimed[article_id] = file_path
            self._path_to_id[file_path.as_posix()] = article_id

        # Folder categories (may be overwritten below by their own index file).
        if self._folders_as_categories:
            for folder in folders:
                self._build_folder_category(folder)

        for file_path in files:
            try:
                self._parse_file(file_path, is_category=file_path in index_files)
            except Exception as exc:
                print(f"Error parsing {file_path}: {exc}")

        self._append_category_contents(folders)

        for article_id, content in self._articles_content.items():
            self._links[article_id] = extract_wiki_links(article_id, content)

        return list(self._articles_meta.values())

    async def get_article_content(self, article_id: str) -> str:
        if article_id not in self._articles_content:
            raise KeyError(f"Article '{article_id}' not found in source '{self.source_name}'")
        return self._articles_content[article_id]

    async def get_links(self) -> dict[str, list[WikiLink]]:
        return self._links

    def resolve_asset(self, rel_path: str) -> Path | None:
        """Resolve a relative asset path inside the source root, or None if unsafe/missing."""
        if not self.is_available():
            return None
        candidate = (self.root_path / unquote(rel_path)).resolve()
        if not candidate.is_file():
            return None
        if self.root_path not in candidate.parents:
            return None
        return candidate

    # --- File collection ---

    def _collect_files(self) -> list[Path]:
        matched: set[Path] = set()
        for pattern in self._include:
            for path in self.root_path.glob(pattern):
                if path.is_file() and path.suffix.lower() in self.MD_EXTENSIONS:
                    matched.add(path.resolve())

        for pattern in self._exclude:
            matched -= {p.resolve() for p in self.root_path.glob(pattern)}
            
        respect_gitignore = self.config.get("respect_gitignore", False)
        if respect_gitignore:
            from wikiknowledge.core.plugins.base import is_path_ignored
            gitignore_cache = {}
            filtered_files = set()
            for file_path in matched:
                if not is_path_ignored(file_path, self.root_path, gitignore_cache):
                    filtered_files.add(file_path)
            matched = filtered_files

        return sorted(matched)

    def _collect_folders(self, files: list[Path]) -> list[Path]:
        """All folders between the root and any included file (root excluded)."""
        folders: set[Path] = set()
        for file_path in files:
            parent = file_path.parent
            while parent != self.root_path and self.root_path in parent.parents:
                folders.add(parent)
                parent = parent.parent
        return sorted(folders)

    def _map_index_files(self, files: list[Path], folders: list[Path]) -> dict[Path, Path]:
        """Map files that represent a folder (index.md, or same name as a sibling folder)."""
        folder_set = set(folders)
        mapping: dict[Path, Path] = {}
        for file_path in files:
            parent = file_path.parent
            stem = file_path.stem.lower()
            if stem in self.INDEX_NAMES and parent in folder_set:
                mapping[file_path] = parent
                continue
            # `guide.md` next to a `guide/` folder describes that folder
            twin = parent / file_path.stem
            if twin in folder_set:
                mapping[file_path] = twin
        return mapping

    # --- ID helpers ---

    def _rel_parts(self, path: Path) -> list[str]:
        return list(PurePosixPath(path.relative_to(self.root_path).as_posix()).parts)

    def _local_id(self, parts: list[str]) -> str:
        slug = "-".join(s for s in (slugify(p) for p in parts) if s)
        return slug or self._root_id

    def _file_article_id(self, path: Path) -> str:
        parts = self._rel_parts(path)
        parts[-1] = Path(parts[-1]).stem
        return f"src:{self.source_name}/{self._local_id(parts)}"

    def _folder_article_id(self, path: Path) -> str:
        return f"src:{self.source_name}/{self._local_id(self._rel_parts(path))}"

    def _parent_categories(self, path: Path) -> list[str]:
        """Category IDs for the folder containing `path` (or the KB roots at top level)."""
        if not self._folders_as_categories:
            return list(self._root_categories)
        parent = path.parent
        if parent == self.root_path:
            return list(self._root_categories)
        return [self._folder_article_id(parent)]

    # --- Article building ---

    def _build_folder_category(self, folder: Path) -> None:
        article_id = self._folder_article_id(folder)
        modified = datetime.fromtimestamp(folder.stat().st_mtime, tz=timezone.utc)
        title = folder.name.replace("-", " ").replace("_", " ").strip().title()

        self._articles_meta[article_id] = ArticleMeta(
            id=article_id,
            title=title,
            type=ArticleType.CATEGORY,
            tags=list(self._extra_tags),
            categories=self._parent_categories(folder),
            created=modified,
            modified=modified,
        )
        self._articles_content[article_id] = f"# {title}\n"

    def _parse_file(self, file_path: Path, is_category: bool) -> None:
        raw = file_path.read_text(encoding="utf-8")
        post = frontmatter.loads(raw)
        body = post.content
        meta_dict = post.metadata or {}

        article_id = self._path_to_id[file_path.as_posix()]

        title = (
            str(meta_dict.get("title") or meta_dict.get("sidebar_label") or "").strip()
            or self._title_from_body(body)
            or file_path.stem.replace("-", " ").replace("_", " ").title()
        )

        tags = self._normalize_list(meta_dict.get("tags") or meta_dict.get("keywords"))
        tags.extend(t for t in self._extra_tags if t not in tags)

        categories = self._normalize_list(meta_dict.get("wk-categories") or meta_dict.get("categories"))
        # Folder hierarchy always applies; frontmatter categories are additive.
        anchor = file_path.parent if is_category else file_path
        for cat in self._parent_categories(anchor):
            if cat not in categories:
                categories.append(cat)

        content = self._convert_links(body, file_path)
        if not H1_RE.search(content):
            content = f"# {title}\n\n{content.lstrip()}"

        rel_path = file_path.relative_to(self.root_path).as_posix()
        content = content.rstrip() + (
            f"\n\n---\n📄 **Source File**: "
            f'<a href="file:///{file_path.as_posix()}">{rel_path}</a>'
        )

        stat = file_path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

        self._articles_meta[article_id] = ArticleMeta(
            id=article_id,
            title=title,
            type=ArticleType.CATEGORY if is_category else ArticleType.LEAF,
            tags=tags,
            categories=categories,
            created=datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc),
            modified=modified,
        )
        self._articles_content[article_id] = content

    def _append_category_contents(self, folders: list[Path]) -> None:
        """Add a generated contents list to every folder category."""
        if not self._folders_as_categories:
            return

        for folder in folders:
            article_id = self._folder_article_id(folder)
            if article_id not in self._articles_content:
                continue

            children: list[tuple[str, str]] = []
            for child_id, meta in self._articles_meta.items():
                if child_id != article_id and article_id in meta.categories:
                    children.append((meta.title, child_id))

            if not children:
                continue

            lines = ["", "## Contents", ""]
            lines += [f"- [[{cid}|{title}]]" for title, cid in sorted(children)]
            content = self._articles_content[article_id]
            self._articles_content[article_id] = content.rstrip() + "\n" + "\n".join(lines) + "\n"

    @staticmethod
    def _title_from_body(body: str) -> str | None:
        match = H1_RE.search(body)
        return match.group(1).strip() if match else None

    @staticmethod
    def _normalize_list(value) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return [str(v).strip() for v in value if str(v).strip()]

    # --- Link conversion ---

    def _convert_links(self, body: str, file_path: Path) -> str:
        out_lines: list[str] = []
        in_code_block = False
        fence_char: str | None = None

        for line in body.splitlines():
            fence = CODE_FENCE_RE.match(line)
            if fence:
                token = fence.group(1)
                if not in_code_block:
                    in_code_block, fence_char = True, token[0]
                elif token[0] == fence_char:
                    in_code_block, fence_char = False, None
                out_lines.append(line)
                continue

            if in_code_block:
                out_lines.append(line)
                continue

            out_lines.append(
                MD_LINK_RE.sub(lambda m: self._convert_link(m, file_path), line)
            )

        return "\n".join(out_lines)

    def _convert_link(self, match: re.Match, file_path: Path) -> str:
        bang, text, target, title = match.group(1), match.group(2), match.group(3), match.group(4) or ""

        if EXTERNAL_RE.match(target):
            return match.group(0)

        path_part, _, anchor = target.partition("#")
        if not path_part:
            return match.group(0)

        resolved = self._resolve_target(path_part, file_path)
        if resolved is None:
            return match.group(0)

        article_id = self._path_to_id.get(resolved.as_posix())
        if article_id and not bang:
            display = text.strip() or article_id
            return f"[[{article_id}|{display}]]"

        # Not an article (image or other asset) — serve it through the API.
        rel = resolved.relative_to(self.root_path).as_posix()
        url = f"/api/sources/{quote(self.source_name)}/assets/{quote(rel)}"
        if anchor:
            url = f"{url}#{anchor}"
        return f"{bang}[{text}]({url}{title})"

    def _resolve_target(self, path_part: str, file_path: Path) -> Path | None:
        """Resolve a relative link target to an existing file inside the source root."""
        raw = unquote(path_part)
        base = self.root_path if raw.startswith("/") else file_path.parent
        candidate = (base / raw.lstrip("/")).resolve()

        if self.root_path not in candidate.parents and candidate != self.root_path:
            return None

        if candidate.is_file():
            return candidate

        # Extension-less links (Docusaurus slugs) and folder links
        for ext in self.MD_EXTENSIONS:
            with_ext = candidate.with_name(candidate.name + ext)
            if with_ext.is_file():
                return with_ext

        if candidate.is_dir():
            if candidate.as_posix() in self._path_to_id:
                return candidate
            for name in self.INDEX_NAMES:
                for ext in self.MD_EXTENSIONS:
                    index_file = candidate / f"{name}{ext}"
                    if index_file.is_file():
                        return index_file

        return None
