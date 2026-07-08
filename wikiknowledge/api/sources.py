"""Knowledge Sources Configuration API endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(tags=["sources"])

class SourcePathUpdateRequest(BaseModel):
    path: str


class ArticleMetadataUpdateRequest(BaseModel):
    tags: list[str] = []
    categories: list[str] = []


@router.get("/sources")
async def get_sources(request: Request) -> list[dict[str, Any]]:
    """Get all configured sources and their status."""
    source_manager = request.app.state.source_manager
    return source_manager.get_status()


@router.put("/sources/{source_id}/path")
async def update_source_path(request: Request, source_id: str, body: SourcePathUpdateRequest):
    """Update the local override path for a source."""
    source_manager = request.app.state.source_manager
    try:
        source_manager.update_source_path(source_id, body.path)
        return {"status": "ok", "source_id": source_id, "path": body.path}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/sources/{source_id}/articles/{article_id:path}/metadata")
async def update_article_metadata(
    request: Request,
    source_id: str,
    article_id: str,
    body: ArticleMetadataUpdateRequest,
):
    """
    Update tags/categories for a Google Drive virtual article.
    Changes are persisted locally and pushed to Drive on next sync
    (only effective when bidirectional=true for the source).
    """
    from wikiknowledge.core.plugins.google_drive import GoogleDrivePlugin

    source_manager = request.app.state.source_manager
    index = request.app.state.index

    plugin = source_manager.plugins.get(source_id)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found")
    if not isinstance(plugin, GoogleDrivePlugin):
        raise HTTPException(status_code=400, detail="Metadata updates only supported for Google Drive sources")
    if not plugin.config.get("bidirectional"):
        raise HTTPException(status_code=400, detail=f"Source '{source_id}' is not configured as bidirectional")

    try:
        plugin.update_article_metadata(article_id, body.tags, body.categories)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Article '{article_id}' not found")

    # Update in-memory index so the change is immediately visible
    meta = index.get_meta(article_id)
    if meta:
        from wikiknowledge.storage.models import ArticleMeta
        updated_meta = ArticleMeta(
            id=meta.id,
            title=meta.title,
            type=meta.type,
            tags=body.tags,
            categories=body.categories,
            created=meta.created,
            modified=meta.modified,
        )
        index._all_meta[article_id] = updated_meta

    return {"status": "ok", "article_id": article_id, "tags": body.tags, "categories": body.categories}


@router.post("/sources/rescan")
async def rescan_sources(request: Request):
    """Re-initialize sources, run sync on Drive sources, and rebuild the index."""
    source_manager = request.app.state.source_manager
    storage = request.app.state.storage
    index = request.app.state.index

    # Re-initialize to pick up any config changes
    await source_manager.initialize()

    # Run sync on all Google Drive plugins (fetches new/changed docs)
    sync_results = await source_manager.sync_all()

    # Rebuild in-memory index
    from wikiknowledge.core.index import rebuild_full_index
    virtual_count = await rebuild_full_index(index, storage, source_manager)

    return {
        "status": "ok",
        "virtual_articles_discovered": virtual_count,
        "sync_results": sync_results,
    }