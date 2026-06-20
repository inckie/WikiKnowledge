"""Data models for WikiKnowledge articles and links."""

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


class ContentBlock(BaseModel):
    """A block of content with authorship information."""
    content: str
    block_type: str = "unmarked"  # "human", "ai", or "unmarked"
    start_line: int = 0
    end_line: int = 0
