"""Knowledge Sources Configuration API endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(tags=["sources"])

class SourcePathUpdateRequest(BaseModel):
    path: str


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


@router.post("/sources/rescan")
async def rescan_sources(request: Request):
    """Re-initialize sources and rebuild the index."""
    source_manager = request.app.state.source_manager
    storage = request.app.state.storage
    index = request.app.state.index

    # Re-initialize the sources
    await source_manager.initialize()
    virtual_articles = await source_manager.discover_all_articles()
    virtual_meta = {a.id: a for a in virtual_articles}
    virtual_links = await source_manager.get_all_links()

    # Merge physical and virtual articles
    all_meta = dict(storage._meta_cache)
    all_meta.update(virtual_meta)
    
    all_links = storage.get_all_links()
    all_links.update(virtual_links)

    # Rebuild in-memory index
    index.build(
        all_meta=all_meta,
        all_links=all_links,
        all_resource_meta=dict(storage._resource_meta_cache),
        all_resource_links=storage.get_all_resource_links(),
    )

    return {"status": "ok", "virtual_articles_discovered": len(virtual_articles)}