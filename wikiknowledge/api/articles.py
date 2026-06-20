"""Article CRUD API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from wikiknowledge.storage.models import Article, ArticleMeta, ArticleType

router = APIRouter(tags=["articles"])


# --- Request/Response schemas ---

class ArticleCreateRequest(BaseModel):
    """Request body for creating a new article."""
    id: str
    title: str
    type: str = "leaf"
    tags: list[str] = []
    categories: list[str] = []
    content: str = ""


class ArticleUpdateRequest(BaseModel):
    """Request body for updating an existing article."""
    title: Optional[str] = None
    type: Optional[str] = None
    tags: Optional[list[str]] = None
    categories: Optional[list[str]] = None
    content: Optional[str] = None


class ArticleResponse(BaseModel):
    """Full article response."""
    id: str
    title: str
    type: str
    tags: list[str]
    categories: list[str]
    created: str
    modified: str
    content: str


class ArticleMetaResponse(BaseModel):
    """Article metadata response (no content)."""
    id: str
    title: str
    type: str
    tags: list[str]
    categories: list[str]
    created: str
    modified: str


class BacklinkResponse(BaseModel):
    """A single backlink entry."""
    source_id: str
    target_id: str
    display_text: Optional[str] = None
    line_number: int = 0
    source_title: Optional[str] = None


def _meta_to_response(meta: ArticleMeta) -> ArticleMetaResponse:
    """Convert ArticleMeta to API response."""
    return ArticleMetaResponse(
        id=meta.id,
        title=meta.title,
        type=meta.type.value,
        tags=meta.tags,
        categories=meta.categories,
        created=meta.created.isoformat(),
        modified=meta.modified.isoformat(),
    )


def _article_to_response(article: Article) -> ArticleResponse:
    """Convert Article to API response."""
    return ArticleResponse(
        id=article.meta.id,
        title=article.meta.title,
        type=article.meta.type.value,
        tags=article.meta.tags,
        categories=article.meta.categories,
        created=article.meta.created.isoformat(),
        modified=article.meta.modified.isoformat(),
        content=article.content,
    )


# --- Endpoints ---

@router.get("/articles", response_model=list[ArticleMetaResponse])
async def list_articles(
    request: Request,
    type: Optional[str] = None,
    tag: Optional[str] = None,
    category: Optional[str] = None,
):
    """List all articles, optionally filtered by type, tag, or category."""
    storage = request.app.state.storage

    if tag:
        metas = await storage.get_by_tag(tag)
    elif category:
        metas = await storage.get_by_category(category)
    else:
        article_type = ArticleType(type) if type else None
        metas = await storage.list_articles(article_type)

    return [_meta_to_response(m) for m in metas]


@router.get("/articles/{article_id}", response_model=ArticleResponse)
async def get_article(request: Request, article_id: str):
    """Get a single article with full content."""
    storage = request.app.state.storage
    try:
        article = await storage.get_article(article_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Article '{article_id}' not found")
    return _article_to_response(article)


@router.post("/articles", response_model=ArticleMetaResponse, status_code=201)
async def create_article(request: Request, body: ArticleCreateRequest):
    """Create a new article."""
    storage = request.app.state.storage
    index = request.app.state.index

    # Check for duplicate
    existing = storage._meta_cache.get(body.id)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Article '{body.id}' already exists",
        )

    now = datetime.now(timezone.utc)
    article = Article(
        meta=ArticleMeta(
            id=body.id,
            title=body.title,
            type=ArticleType(body.type),
            tags=body.tags,
            categories=body.categories,
            created=now,
            modified=now,
        ),
        content=body.content,
    )

    meta = await storage.save_article(article)

    # Update index
    index.rebuild_article(article.meta.id, meta, article.content)

    return _meta_to_response(meta)


@router.put("/articles/{article_id}", response_model=ArticleMetaResponse)
async def update_article(
    request: Request, article_id: str, body: ArticleUpdateRequest
):
    """Update an existing article."""
    storage = request.app.state.storage
    index = request.app.state.index

    try:
        existing = await storage.get_article(article_id)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Article '{article_id}' not found"
        )

    # Apply updates
    if body.title is not None:
        existing.meta.title = body.title
    if body.type is not None:
        existing.meta.type = ArticleType(body.type)
    if body.tags is not None:
        existing.meta.tags = body.tags
    if body.categories is not None:
        existing.meta.categories = body.categories
    if body.content is not None:
        existing.content = body.content

    meta = await storage.save_article(existing)

    # Update index
    index.rebuild_article(article_id, meta, existing.content)

    return _meta_to_response(meta)


@router.delete("/articles/{article_id}", status_code=204)
async def delete_article(request: Request, article_id: str):
    """Delete an article."""
    storage = request.app.state.storage
    index = request.app.state.index

    try:
        await storage.delete_article(article_id)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Article '{article_id}' not found"
        )

    index.remove_article(article_id)


@router.get(
    "/articles/{article_id}/backlinks",
    response_model=list[BacklinkResponse],
)
async def get_backlinks(request: Request, article_id: str):
    """Get all articles that link to this one ('What links here')."""
    storage = request.app.state.storage
    index = request.app.state.index

    backlinks = index.what_links_here(article_id)
    result = []
    for bl in backlinks:
        source_meta = index.get_meta(bl.source_id)
        result.append(
            BacklinkResponse(
                source_id=bl.source_id,
                target_id=bl.target_id,
                display_text=bl.display_text,
                line_number=bl.line_number,
                source_title=source_meta.title if source_meta else None,
            )
        )
    return result
