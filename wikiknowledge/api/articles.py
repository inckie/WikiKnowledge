"""Article CRUD API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Union

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
import diff_match_patch as dmp_module

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
    content_patches: Optional[str] = None

class ArticleMoveRequest(ArticleUpdateRequest):
    """Request body for moving/renaming an existing article."""
    new_id: str
    update_links: bool = True


class ArticleMetaResponse(BaseModel):
    """Article metadata response (no content)."""
    id: str
    title: str
    type: str
    tags: list[str]
    categories: list[str]
    created: str
    modified: str
    is_unmentioned: bool = False
    is_newer: bool = False


class ArticleResponse(BaseModel):
    """Full article response for a leaf article."""
    id: str
    title: str
    type: str
    tags: list[str]
    categories: list[str]
    created: str
    modified: str
    content: str


class CategoryArticleResponse(ArticleResponse):
    """Full article response for a category article."""
    sub_articles: list[ArticleMetaResponse] = Field(default_factory=list)
    is_dirty: bool = False


class BacklinkResponse(BaseModel):
    """A single backlink entry."""
    source_id: str
    target_id: str
    display_text: Optional[str] = None
    line_number: int = 0
    source_title: Optional[str] = None


def _meta_to_response(meta: ArticleMeta, is_unmentioned: bool = False, is_newer: bool = False) -> ArticleMetaResponse:
    """Convert ArticleMeta to API response."""
    return ArticleMetaResponse(
        id=meta.id,
        title=meta.title,
        type=meta.type.value,
        tags=meta.tags,
        categories=meta.categories,
        created=meta.created.isoformat(),
        modified=meta.modified.isoformat(),
        is_unmentioned=is_unmentioned,
        is_newer=is_newer,
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


@router.get("/articles/{article_id}", response_model=Union[CategoryArticleResponse, ArticleResponse])
async def get_article(request: Request, article_id: str):
    """Get a single article with full content."""
    storage = request.app.state.storage
    index = request.app.state.index
    try:
        article = await storage.get_article(article_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Article '{article_id}' not found")

    if article.meta.type == ArticleType.CATEGORY:
        sub_article_metas = index.get_sub_articles(article_id)
        
        # Determine which sub-articles are unmentioned and newer
        sub_articles_with_mention_status = [
            _meta_to_response(
                meta=sub_meta,
                is_unmentioned=f"[[{sub_meta.id}" not in article.content,
                is_newer=sub_meta.modified > article.meta.modified
            )
            for sub_meta in sub_article_metas
        ]

        return CategoryArticleResponse(
            id=article.meta.id,
            title=article.meta.title,
            type=article.meta.type.value,
            tags=article.meta.tags,
            categories=article.meta.categories,
            created=article.meta.created.isoformat(),
            modified=article.meta.modified.isoformat(),
            content=article.content,
            sub_articles=sub_articles_with_mention_status,
            is_dirty=index.is_dirty(article_id),
        )
    else:
        return _article_to_response(article)


@router.post("/articles", response_model=ArticleMetaResponse, status_code=201)
async def create_article(request: Request, body: ArticleCreateRequest):
    """Create a new article."""
    storage = request.app.state.storage
    index = request.app.state.index

    # Check for duplicate
    if body.id in storage._meta_cache:
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
    """Update an existing article (partial metadata update, full content replacement, and/or diff-match-patch patches)."""
    storage = request.app.state.storage
    index = request.app.state.index

    try:
        existing = await storage.get_article(article_id)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Article '{article_id}' not found"
        )

    # Apply metadata updates
    if body.title is not None:
        existing.meta.title = body.title
    if body.type is not None:
        existing.meta.type = ArticleType(body.type)
    if body.tags is not None:
        existing.meta.tags = body.tags
    if body.categories is not None:
        existing.meta.categories = body.categories

    # Apply content updates
    if body.content is not None:
        existing.content = body.content
    elif body.content_patches is not None:
        dmp = dmp_module.diff_match_patch()
        try:
            patches = dmp.patch_fromText(body.content_patches)
            new_text, results = dmp.patch_apply(patches, existing.content)
            if not all(results):
                raise HTTPException(
                    status_code=400, 
                    detail="Some patches could not be applied cleanly."
                )
            existing.content = new_text
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to parse or apply patches: {e}"
            )

    meta = await storage.save_article(existing)

    # Update index
    index.rebuild_article(article_id, meta, existing.content)

    return _meta_to_response(meta)


@router.post("/articles/{article_id}/move", response_model=ArticleMetaResponse)
async def move_article(
    request: Request, article_id: str, body: ArticleMoveRequest
):
    """Rename an article and update all references to it."""
    storage = request.app.state.storage
    index = request.app.state.index
    from wikiknowledge.core.refactor import rename_article

    try:
        updates = body.model_dump(exclude_unset=True, exclude={"new_id", "update_links"})
        meta = await rename_article(
            storage, index, article_id, body.new_id, updates, body.update_links
        )
        return _meta_to_response(meta)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Article '{article_id}' not found"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=409, detail=str(e)
        )


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