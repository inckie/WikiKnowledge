"""Markdown file storage backend."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import frontmatter

from wikiknowledge.core.parser import extract_wiki_links
from wikiknowledge.storage.base import StorageBackend
from wikiknowledge.storage.models import (
    Article,
    ArticleMeta,
    ArticleType,
    WikiLink,
)


class MarkdownStorageBackend(StorageBackend):
    """Storage backend using markdown files with YAML frontmatter.

    Directory structure:
        knowledge_dir/
        ├── articles/    # leaf articles
        └── categories/  # category/superstructure articles

    File naming: {article_id}.md
    """

    def __init__(self, knowledge_dir: str | Path) -> None:
        self.knowledge_dir = Path(knowledge_dir)
        self.articles_dir = self.knowledge_dir / "articles"
        self.categories_dir = self.knowledge_dir / "categories"

        # Ensure directories exist
        self.articles_dir.mkdir(parents=True, exist_ok=True)
        self.categories_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache: article_id → ArticleMeta
        self._meta_cache: dict[str, ArticleMeta] = {}
        # In-memory cache: article_id → list of outgoing WikiLinks
        self._links_cache: dict[str, list[WikiLink]] = {}

    # --- Initialization ---

    async def initialize(self) -> None:
        """Scan all markdown files and populate caches."""
        self._meta_cache.clear()
        self._links_cache.clear()

        for directory in [self.articles_dir, self.categories_dir]:
            if not directory.exists():
                continue
            for md_file in sorted(directory.glob("*.md")):
                try:
                    article = self._read_file(md_file)
                    self._meta_cache[article.meta.id] = article.meta
                    links = extract_wiki_links(article.meta.id, article.content)
                    self._links_cache[article.meta.id] = links
                except Exception as e:
                    print(f"Warning: Failed to parse {md_file}: {e}")

        print(
            f"Loaded {len(self._meta_cache)} articles "
            f"({sum(len(v) for v in self._links_cache.values())} wiki links)"
        )

    # --- CRUD ---

    async def get_article(self, article_id: str) -> Article:
        """Read a full article from disk."""
        path = self._id_to_path(article_id)
        if not path.exists():
            raise KeyError(f"Article '{article_id}' not found")
        return self._read_file(path)

    async def list_articles(
        self, article_type: Optional[ArticleType] = None
    ) -> list[ArticleMeta]:
        """List article metadata from cache."""
        metas = list(self._meta_cache.values())
        if article_type is not None:
            metas = [m for m in metas if m.type == article_type]
        return sorted(metas, key=lambda m: m.title)

    async def save_article(self, article: Article) -> ArticleMeta:
        """Write an article to disk and update caches."""
        # Update modified timestamp
        article.meta.modified = datetime.now(timezone.utc)

        # Determine the target directory based on type
        target_dir = self._type_to_dir(article.meta.type)
        target_path = target_dir / f"{article.meta.id}.md"

        # If article type changed, remove from old location
        old_meta = self._meta_cache.get(article.meta.id)
        if old_meta and old_meta.type != article.meta.type:
            old_path = self._type_to_dir(old_meta.type) / f"{article.meta.id}.md"
            if old_path.exists():
                old_path.unlink()

        # Atomic write: write to temp file, then rename
        self._write_file_atomic(target_path, article)

        # Update caches
        self._meta_cache[article.meta.id] = article.meta
        self._links_cache[article.meta.id] = extract_wiki_links(
            article.meta.id, article.content
        )

        return article.meta

    async def delete_article(self, article_id: str) -> None:
        """Delete an article from disk and caches."""
        path = self._id_to_path(article_id)
        if not path.exists():
            raise KeyError(f"Article '{article_id}' not found")

        path.unlink()
        self._meta_cache.pop(article_id, None)
        self._links_cache.pop(article_id, None)

    # --- Queries ---

    async def get_by_tag(self, tag: str) -> list[ArticleMeta]:
        """Find articles with the given tag."""
        return sorted(
            [m for m in self._meta_cache.values() if tag in m.tags],
            key=lambda m: m.title,
        )

    async def get_by_category(self, category_id: str) -> list[ArticleMeta]:
        """Find articles in the given category."""
        return sorted(
            [
                m
                for m in self._meta_cache.values()
                if category_id in m.categories
            ],
            key=lambda m: m.title,
        )

    async def get_all_tags(self) -> dict[str, int]:
        """Return all tags with counts."""
        tag_counts: dict[str, int] = {}
        for meta in self._meta_cache.values():
            for tag in meta.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        return dict(sorted(tag_counts.items()))

    async def get_all_categories(self) -> list[ArticleMeta]:
        """Return all category-type articles."""
        return await self.list_articles(ArticleType.CATEGORY)

    async def get_backlinks(self, article_id: str) -> list[WikiLink]:
        """Find all links pointing to the given article."""
        backlinks: list[WikiLink] = []
        for source_id, links in self._links_cache.items():
            for link in links:
                if link.target_id == article_id:
                    backlinks.append(link)
        return backlinks

    async def search(self, query: str) -> list[ArticleMeta]:
        """Simple case-insensitive search across titles and content."""
        query_lower = query.lower()
        results: list[ArticleMeta] = []

        for article_id, meta in self._meta_cache.items():
            # Check title
            if query_lower in meta.title.lower():
                results.append(meta)
                continue
            # Check tags
            if any(query_lower in tag.lower() for tag in meta.tags):
                results.append(meta)
                continue
            # Check content (lazy load from disk)
            try:
                path = self._id_to_path(article_id)
                if path.exists():
                    text = path.read_text(encoding="utf-8").lower()
                    if query_lower in text:
                        results.append(meta)
            except Exception:
                pass

        return sorted(results, key=lambda m: m.title)

    # --- Link access for index building ---

    def get_all_links(self) -> dict[str, list[WikiLink]]:
        """Return the full forward-links cache (used by KnowledgeIndex)."""
        return dict(self._links_cache)

    # --- Internal helpers ---

    def _type_to_dir(self, article_type: ArticleType) -> Path:
        """Map article type to directory."""
        if article_type == ArticleType.CATEGORY:
            return self.categories_dir
        return self.articles_dir

    def _id_to_path(self, article_id: str) -> Path:
        """Find the file path for an article ID (checks both directories)."""
        # Check cache first for type info
        meta = self._meta_cache.get(article_id)
        if meta:
            return self._type_to_dir(meta.type) / f"{article_id}.md"

        # Fall back to checking both directories
        for directory in [self.articles_dir, self.categories_dir]:
            path = directory / f"{article_id}.md"
            if path.exists():
                return path

        # Default to articles directory
        return self.articles_dir / f"{article_id}.md"

    def _read_file(self, path: Path) -> Article:
        """Parse a markdown file into an Article object."""
        post = frontmatter.load(str(path))

        meta = ArticleMeta(
            id=post.get("id", path.stem),
            title=post.get("title", path.stem),
            type=ArticleType(post.get("type", "leaf")),
            tags=post.get("tags", []),
            categories=post.get("categories", []),
            created=post.get("created", datetime.now(timezone.utc)),
            modified=post.get("modified", datetime.now(timezone.utc)),
        )

        return Article(meta=meta, content=post.content)

    def _write_file_atomic(self, path: Path, article: Article) -> None:
        """Write an article to disk atomically (temp file + rename)."""
        post = frontmatter.Post(
            content=article.content,
            **{
                "id": article.meta.id,
                "title": article.meta.title,
                "type": article.meta.type.value,
                "tags": article.meta.tags,
                "categories": article.meta.categories,
                "created": article.meta.created.isoformat(),
                "modified": article.meta.modified.isoformat(),
            },
        )

        serialized = frontmatter.dumps(post)

        # Write to temp file in same directory, then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent), suffix=".md.tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(serialized)
            # Atomic rename (works on same filesystem)
            os.replace(tmp_path, str(path))
        except Exception:
            # Clean up temp file on failure
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
