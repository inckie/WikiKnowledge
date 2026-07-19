"""Data Models

:wk-id: data-models
:wk-tags: python, pydantic, models, core
:wk-categories: system-architecture

Data models for WikiKnowledge articles and links.

Pydantic data model foundation: Article, ArticleMeta, WikiLink, Resource, ResourceMeta, ContentBlock.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ArticleType(str, Enum):
    """Type of article in the knowledge base."""
    LEAF = "leaf"
    CATEGORY = "category"


class ArticleMeta(BaseModel):
    """Metadata extracted from article YAML frontmatter."""
    id: str
    title: str
    type: ArticleType = ArticleType.LEAF
    tags: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    modified: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Article(BaseModel):
    """Full article: metadata + markdown body content."""
    meta: ArticleMeta
    content: str = ""

    @property
    def id(self) -> str:
        return self.meta.id

    @property
    def title(self) -> str:
        return self.meta.title


class WikiLink(BaseModel):
    """A single wiki link extracted from article content."""
    source_id: str
    target_id: str
    display_text: Optional[str] = None
    line_number: int = 0
    is_file_link: bool = False  # True for [[file:...]] links to media resources


class ResourceMeta(BaseModel):
    """Metadata for a binary/media resource (stored in .meta sidecar files)."""
    id: str
    title: str
    filename: str  # actual file on disk, e.g. "logo.svg"
    mime_type: str = "application/octet-stream"
    tags: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)  # outgoing links (like [[]] in articles)
    description: str = ""  # alt-text / content description for non-multimodal LLMs
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    modified: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Resource(BaseModel):
    """Full resource: metadata + optional binary data."""
    meta: ResourceMeta
    data: Optional[bytes] = None

    @property
    def id(self) -> str:
        return self.meta.id

    @property
    def title(self) -> str:
        return self.meta.title


class ContentBlock(BaseModel):
    """A block of content with authorship information."""
    content: str
    block_type: str = "unmarked"  # "human", "ai", or "unmarked"
    start_line: int = 0
    end_line: int = 0
