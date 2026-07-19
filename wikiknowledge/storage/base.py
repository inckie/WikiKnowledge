"""Storage Abstraction Layer

:wk-id: storage-abstraction
:wk-tags: architecture, storage, abstraction, backend, python
:wk-categories: system-architecture

The storage abstraction layer provides a uniform interface for reading, writing, and querying articles regardless of the underlying storage mechanism. The initial implementation uses markdown files on disk, but the abstraction is designed so that alternative backends (e.g., MongoDB, SQLite) can be swapped in without changing the rest of the system.

## Abstract Interface

The `StorageBackend` base class defines the contract:

### CRUD Operations

| Method | Description |
|--------|-------------|
| `get_article(id)` | Retrieve a single article by its unique ID |
| `list_articles(type?)` | List all articles, optionally filtered by [[markdown-frontmatter|type]] (leaf or category) |
| `save_article(article)` | Create or update an article, writing both frontmatter and content |
| `delete_article(id)` | Remove an article from storage |

### Query Operations

| Method | Description |
|--------|-------------|
| `get_by_tag(tag)` | Find all articles with a given tag |
| `get_by_category(category_id)` | Find all articles in a given category |
| `get_all_tags()` | List every unique tag across all articles |
| `get_all_categories()` | List all category-type articles |
| `get_backlinks(id)` | Find all articles that link to the given article via [[wiki-link-syntax|wiki links]] |

### Resource CRUD Operations

| Method | Description |
|--------|-------------|
| `get_resource(id)` | Retrieve a full resource (metadata + binary data) by its unique ID |
| `get_resource_meta(id)` | Retrieve only the metadata (`ResourceMeta`) for a resource |
| `list_resources()` | List metadata for all binary/media resources |
| `save_resource(id, data, meta)` | Create or update a resource file and its YAML `.meta` sidecar |
| `delete_resource(id)` | Remove a resource file and its sidecar from storage |

## Markdown Backend

The `MarkdownStorageBackend` is the first concrete implementation. It maps directly to the filesystem:

```
knowledge/
├── articles/          # type: "leaf"
│   ├── article-one.md
│   └── article-two.md
├── categories/        # type: "category"
│   ├── cat-one.md
│   └── cat-two.md
└── media/             # binary resources + sidecars
    ├── my-image.png
    └── my-image.png.meta
```

### File ↔ Article / Resource Mapping

- The **filename** (without `.md`) must match the article's `id` field in [[markdown-frontmatter|frontmatter]]
- **Leaf articles** live in `knowledge/articles/`
- **Category articles** live in `knowledge/categories/`
- The `type` field in frontmatter determines which directory an article is written to
- **Media resources** live in `knowledge/media/` as raw binary files (`.png`, `.svg`, `.mp3`) alongside YAML sidecar metadata files (`.meta` appended after the full extension, e.g., `my-image.png.meta`). The `id` property inside the sidecar explicitly retains the full filename extension (e.g., `id: my-image.png`) to avoid collisions between different file types sharing the same base name and to match standard wiki link formats (`[[file:my-image.png]]`).

### Startup Behavior

On application startup, the markdown backend:

1. Scans both directories for `.md` files
2. Parses frontmatter from each file using `python-frontmatter`
3. Extracts [[wiki-link-syntax|wiki links]] from the body content
4. Populates an in-memory cache of `ArticleMeta` objects
5. Hands the extracted link data to the [[src:wikiknowledge/in-memory-index|in-memory-index]] for graph construction

### Write Path

When an article is saved:

1. The `modified` timestamp is updated to the current time
2. Frontmatter is serialized back to YAML
3. The full file (frontmatter + body) is written atomically (write to temp file, then rename)
4. The in-memory cache is updated
5. The [[src:wikiknowledge/in-memory-index|in-memory-index]] is notified to rebuild the affected article's links

## Design Principles

- **Files are the source of truth** — the in-memory cache is always rebuildable from disk
- **Atomic writes** — prevent corruption if the process crashes mid-save
- **Lazy content loading** — `list_articles()` returns only metadata; full content is loaded only by `get_article()`
- **No external dependencies** — the markdown backend requires only `python-frontmatter` and the standard library

## Future Backends

The abstraction is designed to support:

- **MongoDB** — frontmatter fields become document fields, content stored as a text field, categories and tags become indexed arrays
- **SQLite** — lightweight embedded database for single-user deployments
- **Git-backed** — wraps the markdown backend with automatic git commits on every save
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from wikiknowledge.storage.models import (
    Article,
    ArticleMeta,
    ArticleType,
    Resource,
    ResourceMeta,
    WikiLink,
)


class StorageBackend(ABC):
    """Abstract interface for article storage and retrieval.

    All storage backends must implement these methods. The interface
    supports CRUD operations, tag/category queries, and reverse-link
    lookups ("what links here").
    """

    # --- Article CRUD ---

    @abstractmethod
    async def get_article(self, article_id: str) -> Article:
        """Retrieve a single article by ID.

        Raises:
            KeyError: If the article does not exist.
        """

    @abstractmethod
    async def list_articles(
        self, article_type: Optional[ArticleType] = None
    ) -> list[ArticleMeta]:
        """List all article metadata, optionally filtered by type."""

    @abstractmethod
    async def save_article(self, article: Article) -> ArticleMeta:
        """Create or update an article. Returns updated metadata."""

    @abstractmethod
    async def delete_article(self, article_id: str) -> None:
        """Delete an article by ID.

        Raises:
            KeyError: If the article does not exist.
        """

    # --- Article Queries ---

    @abstractmethod
    async def get_by_tag(self, tag: str) -> list[ArticleMeta]:
        """Find all articles with a given tag."""

    @abstractmethod
    async def get_by_category(self, category_id: str) -> list[ArticleMeta]:
        """Find all articles belonging to a category."""

    @abstractmethod
    async def get_all_tags(self) -> dict[str, int]:
        """Return all tags with their usage counts."""

    @abstractmethod
    async def get_all_categories(self) -> list[ArticleMeta]:
        """Return metadata for all category-type articles."""

    # --- Reverse links ---

    @abstractmethod
    async def get_backlinks(self, article_id: str) -> list[WikiLink]:
        """Find all wiki links pointing to the given article."""

    # --- Full-text search ---

    @abstractmethod
    async def search(self, query: str) -> list[ArticleMeta]:
        """Full-text search across article titles and content."""

    # --- Resource CRUD ---

    @abstractmethod
    async def get_resource(self, resource_id: str) -> Resource:
        """Retrieve a resource (metadata + binary data) by ID.

        Raises:
            KeyError: If the resource does not exist.
        """

    @abstractmethod
    async def get_resource_meta(self, resource_id: str) -> ResourceMeta:
        """Retrieve resource metadata only.

        Raises:
            KeyError: If the resource does not exist.
        """

    @abstractmethod
    async def list_resources(self) -> list[ResourceMeta]:
        """List all resource metadata."""

    @abstractmethod
    async def save_resource(
        self, resource_id: str, data: bytes, meta: ResourceMeta
    ) -> ResourceMeta:
        """Create or update a resource. Returns updated metadata."""

    @abstractmethod
    async def delete_resource(self, resource_id: str) -> None:
        """Delete a resource by ID.

        Raises:
            KeyError: If the resource does not exist.
        """

