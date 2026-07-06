"""Search and discovery API endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(tags=["search"])


class TagResponse(BaseModel):
    """A tag with its usage count."""
    name: str
    count: int


class CategoryResponse(BaseModel):
    """A category summary."""
    id: str
    title: str
    member_count: int


class SearchResultResponse(BaseModel):
    """A search result entry."""
    id: str
    title: str
    type: str
    tags: list[str]


@router.get("/tags", response_model=list[TagResponse])
async def list_tags(request: Request):
    """List all tags with usage counts."""
    index = request.app.state.index
    return [
        TagResponse(name=name, count=len(item_ids))
        for name, item_ids in sorted(index.tag_index.items())
    ]


@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(request: Request):
    """List all category articles with member counts."""
    storage = request.app.state.storage
    index = request.app.state.index

    categories = await storage.get_all_categories()
    return [
        CategoryResponse(
            id=cat.id,
            title=cat.title,
            member_count=len(index.articles_in_category(cat.id)),
        )
        for cat in categories
    ]


@router.get("/search", response_model=list[SearchResultResponse])
async def search_articles(request: Request, q: str = ""):
    """Full-text search across articles."""
    if not q.strip():
        return []

    storage = request.app.state.storage
    results = await storage.search(q)
    return [
        SearchResultResponse(
            id=m.id,
            title=m.title,
            type=m.type.value,
            tags=m.tags,
        )
        for m in results
    ]
