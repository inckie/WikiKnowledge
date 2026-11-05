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
    native_count = sum(1 for aid in all_articles if not aid.startswith("src:") and not aid.startswith("gdrive:"))
    external_count = sum(1 for aid in all_articles if aid.startswith("src:") or aid.startswith("gdrive:"))

    all_resources = index._all_resource_meta
    all_known_ids = set(all_articles.keys()) | set(all_resources.keys())

    # Total links
    total_links = sum(len(links) for links in index.forward_links.values())

    # Broken links
    broken_raw = []
    for links in index.forward_links.values():
        for link in links:
            target_base = link.target_id.split("#")[0].strip()
            if target_base not in all_known_ids:
                broken_raw.append(link)

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
