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
    match_type: Optional[str] = None
    score: Optional[float] = None
    snippet: Optional[str] = None


class EmbeddingSettingsRequest(BaseModel):
    """Payload to toggle embedding search."""
    enabled: bool


class EmbeddingStatusResponse(BaseModel):
    """Status details for embedding search."""
    enabled: bool
    status: str
    article_count: int
    chunk_count: int
    last_indexed: Optional[str] = None
    last_error: Optional[str] = None
    model_name: str


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


@router.get("/search/embedding/settings", response_model=EmbeddingStatusResponse)
async def get_embedding_settings(request: Request):
    """Retrieve current embedding search settings and index status."""
    service = getattr(request.app.state, "embedding_service", None)
    if not service:
        return EmbeddingStatusResponse(
            enabled=False, status="disabled", article_count=0, chunk_count=0, model_name=""
        )
    return EmbeddingStatusResponse(**service.get_status())


@router.post("/search/embedding/settings", response_model=EmbeddingStatusResponse)
async def update_embedding_settings(request: Request, body: EmbeddingSettingsRequest):
    """Enable or disable embedding search and trigger initial indexing if needed."""
    service = getattr(request.app.state, "embedding_service", None)
    if not service:
        return EmbeddingStatusResponse(
            enabled=False, status="disabled", article_count=0, chunk_count=0, model_name=""
        )
    service.save_settings(enabled=body.enabled)
    if body.enabled and service.status != "ready":
        import asyncio
        storage = request.app.state.storage
        index = request.app.state.index
        source_manager = request.app.state.source_manager
        asyncio.create_task(service.start_background_indexing(storage, index, source_manager))
    return EmbeddingStatusResponse(**service.get_status())


@router.post("/search/embedding/rebuild", response_model=EmbeddingStatusResponse)
async def rebuild_embedding_index(request: Request):
    """Trigger background re-indexing of reachable wiki articles."""
    service = getattr(request.app.state, "embedding_service", None)
    if not service:
        return EmbeddingStatusResponse(
            enabled=False, status="disabled", article_count=0, chunk_count=0, model_name=""
        )
    import asyncio
    storage = request.app.state.storage
    index = request.app.state.index
    source_manager = request.app.state.source_manager
    asyncio.create_task(service.start_background_indexing(storage, index, source_manager))
    return EmbeddingStatusResponse(**service.get_status())


@router.get("/search", response_model=list[SearchResultResponse])
async def search_articles(request: Request, q: str = ""):
    """Full-text and semantic search across articles."""
    query = q.strip()
    if not query:
        return []

    storage = request.app.state.storage
    index = request.app.state.index
    service = getattr(request.app.state, "embedding_service", None)

    # 1. Lexical search across storage and in-memory index
    storage_results = await storage.search(query)
    index_results = index.search(query)

    seen_lexical = set()
    lexical_items = []
    for m in storage_results:
        if m.id not in seen_lexical:
            lexical_items.append(m)
            seen_lexical.add(m.id)
    for m in index_results:
        if m.id not in seen_lexical:
            lexical_items.append(m)
            seen_lexical.add(m.id)

    # If embedding search is disabled or not ready, return standard lexical results
    if not service or not service.enabled or service.status != "ready":
        lexical_items.sort(key=lambda m: m.title)
        return [
            SearchResultResponse(
                id=m.id,
                title=m.title,
                type=m.type.value if hasattr(m.type, "value") else str(m.type),
                tags=m.tags,
                match_type="lexical",
            )
            for m in lexical_items
        ]

    # 2. Semantic search using pre-computed Model2Vec embeddings
    semantic_results = service.search(query)
    semantic_dict = {item["id"]: item for item in semantic_results}

    # 3. Hybrid ranking: combine and score
    combined: dict[str, dict] = {}

    for m in lexical_items:
        aid = m.id
        sem = semantic_dict.get(aid)
        sem_score = sem["score"] if sem else 0.0
        match_type = "hybrid" if sem else "lexical"
        combined[aid] = {
            "id": aid,
            "title": m.title,
            "type": m.type.value if hasattr(m.type, "value") else str(m.type),
            "tags": m.tags,
            "match_type": match_type,
            "score": 1.0 + sem_score,  # Keyword matches boosted by semantic relevance
            "snippet": sem.get("snippet") if sem else None,
        }

    for sem in semantic_results:
        aid = sem["id"]
        if aid not in combined:
            combined[aid] = {
                "id": aid,
                "title": sem["title"],
                "type": sem["type"],
                "tags": sem["tags"],
                "match_type": "semantic",
                "score": sem["score"],
                "snippet": sem.get("snippet"),
            }

    # Sort descending by composite score; tie-break on title alphabetically
    sorted_results = sorted(combined.values(), key=lambda x: (-x["score"], x["title"].lower()))

    return [SearchResultResponse(**item) for item in sorted_results]
