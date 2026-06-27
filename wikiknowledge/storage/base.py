"""Abstract base class for storage backends."""

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

