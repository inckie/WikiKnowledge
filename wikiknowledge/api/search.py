"""Search and discovery API endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request

from wikiknowledge.core.article_content import is_virtual
from wikiknowledge.core.text_search import lexical_search
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
    source_type: str = "native"
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


class BrokenLinkInfo(BaseModel):
    """Details for a broken wiki-link."""
    source_id: str
    target_id: str
    display_text: Optional[str] = None
    line_number: Optional[int] = None


class OrphanPageInfo(BaseModel):
    """An article or resource with no incoming links."""
    id: str
    title: str
    type: str
    source_type: str = "native"
    has_outgoing: bool = False
    outgoing_count: int = 0


class KnowledgeBaseStatsResponse(BaseModel):
    """Comprehensive knowledge base health and graph metrics."""
    total_articles: int
    native_articles: int
    external_articles: int
    total_resources: int
    total_categories: int
    total_tags: int
    total_links: int
    broken_links: list[BrokenLinkInfo]
    broken_links_count: int
    orphaned_pages: list[OrphanPageInfo]
    orphaned_pages_count: int


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


@router.get("/stats", response_model=KnowledgeBaseStatsResponse)
async def get_stats(request: Request):
    """Retrieve comprehensive knowledge base health and statistics."""
    index = request.app.state.index
    storage = request.app.state.storage

    all_articles = index._all_meta
    native_count = sum(1 for aid in all_articles if not is_virtual(aid))
    external_count = sum(1 for aid in all_articles if is_virtual(aid))

    all_resources = index._all_resource_meta

    # Total links
    total_links = sum(len(links) for links in index.forward_links.values())

    broken_raw = index.get_broken_links()
    broken_links = [
        BrokenLinkInfo(
            source_id=l.source_id,
            target_id=l.target_id,
            display_text=l.display_text,
            line_number=l.line_number,
        )
        for l in broken_raw
    ]

    # Orphaned pages (no incoming links, excluding the root "overview" category)
    orphaned_pages: list[OrphanPageInfo] = []
    for aid, meta in sorted(all_articles.items(), key=lambda x: x[0]):
        if aid == "overview":
            continue
        incoming = index.back_links.get(aid, [])
        if not incoming:
            outgoing = index.forward_links.get(aid, [])
            orphaned_pages.append(
                OrphanPageInfo(
                    id=aid,
                    title=meta.title or aid,
                    type=meta.type.value if hasattr(meta.type, "value") else str(meta.type),
                    source_type=meta.source_type.value if hasattr(meta.source_type, "value") else str(meta.source_type),
                    has_outgoing=bool(outgoing),
                    outgoing_count=len(outgoing),
                )
            )

    for rid, rmeta in sorted(all_resources.items(), key=lambda x: x[0]):
        incoming = index.back_links.get(rid, [])
        if not incoming:
            orphaned_pages.append(
                OrphanPageInfo(
                    id=rid,
                    title=rmeta.title or rid,
                    type="resource",
                    has_outgoing=False,
                    outgoing_count=0,
                )
            )

    categories = await storage.get_all_categories()

    return KnowledgeBaseStatsResponse(
        total_articles=len(all_articles),
        native_articles=native_count,
        external_articles=external_count,
        total_resources=len(all_resources),
        total_categories=len(categories),
        total_tags=len(index.tag_index),
        total_links=total_links,
        broken_links=broken_links,
        broken_links_count=len(broken_links),
        orphaned_pages=orphaned_pages,
        orphaned_pages_count=len(orphaned_pages),
    )


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

    # 1. Ranked lexical search (same as the MCP search tool)
    hits, _partial = await lexical_search(query, storage, index, request.app.state.source_manager)

    def type_str(m):
        return m.type.value if hasattr(m.type, "value") else str(m.type)

    def source_type_str(m):
        return m.source_type.value if hasattr(m.source_type, "value") else str(m.source_type)

    # If embedding search is disabled or not ready, return the lexical ranking
    if not service or not service.enabled or service.status != "ready":
        return [
            SearchResultResponse(
                id=h.meta.id,
                title=h.meta.title,
                type=type_str(h.meta),
                source_type=source_type_str(h.meta),
                tags=h.meta.tags,
                match_type="lexical",
                score=h.score,
                snippet=h.snippet or None,
            )
            for h in hits
        ]

    # 2. Semantic search using pre-computed Model2Vec embeddings
    semantic_results = service.search(query)
    semantic_dict = {item["id"]: item for item in semantic_results}

    # 3. Hybrid ranking: combine and score
    combined: dict[str, dict] = {}

    top = hits[0].score if hits else 1.0
    for h in hits:
        m = h.meta
        sem = semantic_dict.get(m.id)
        sem_score = sem["score"] if sem else 0.0
        combined[m.id] = {
            "id": m.id,
            "title": m.title,
            "type": type_str(m),
            "source_type": source_type_str(m),
            "tags": m.tags,
            "match_type": "hybrid" if sem else "lexical",
            # Keyword matches stay above semantic-only ones; lexical rank (0..1) and semantic relevance order them
            "score": 1.0 + h.score / top + sem_score,
            "snippet": h.snippet or (sem.get("snippet") if sem else None),
        }

    for sem in semantic_results:
        aid = sem["id"]
        if aid not in combined:
            meta = index.get_meta(aid)
            combined[aid] = {
                "id": aid,
                "title": sem["title"],
                "type": sem["type"],
                "source_type": source_type_str(meta) if meta else "native",
                "tags": sem["tags"],
                "match_type": "semantic",
                "score": sem["score"],
                "snippet": sem.get("snippet"),
            }

    # Sort descending by composite score; tie-break on title alphabetically
    sorted_results = sorted(combined.values(), key=lambda x: (-x["score"], x["title"].lower()))

    return [SearchResultResponse(**item) for item in sorted_results]
