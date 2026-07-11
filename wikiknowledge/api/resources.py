"""Resource CRUD API endpoints for binary/media files."""
# Trigger uvicorn hot-reload for resource ID update

from __future__ import annotations

import mimetypes
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from wikiknowledge.storage.models import ResourceMeta

router = APIRouter(tags=["resources"])


# --- Request/Response schemas ---

class ResourceMoveRequest(BaseModel):
    """Request body for moving/renaming an existing resource."""
    new_id: str
    update_references: bool = True


class ResourceMetaResponse(BaseModel):
    """Resource metadata response."""
    id: str
    title: str
    filename: str
    mime_type: str
    tags: list[str]
    categories: list[str]
    related: list[str]
    description: str
    created: str
    modified: str


def _meta_to_response(meta: ResourceMeta) -> ResourceMetaResponse:
    """Convert ResourceMeta to API response."""
    return ResourceMetaResponse(
        id=meta.id,
        title=meta.title,
        filename=meta.filename,
        mime_type=meta.mime_type,
        tags=meta.tags,
        categories=meta.categories,
        related=meta.related,
        description=meta.description,
        created=meta.created.isoformat(),
        modified=meta.modified.isoformat(),
    )


# --- Endpoints ---


@router.get("/resources", response_model=list[ResourceMetaResponse])
async def list_resources(request: Request):
    """List all resource metadata."""
    storage = request.app.state.storage
    metas = await storage.list_resources()
    return [_meta_to_response(m) for m in metas]


# NOTE: This route MUST be defined before the `/resources/{resource_id:path}` route below.
# Because `{resource_id:path}` matches any path including slashes, it would intercept 
# requests ending in `/file` if it were defined first, causing 404 errors.
@router.get("/resources/{resource_id:path}/file")
async def get_resource_file(request: Request, resource_id: str):
    """Download the actual binary file for a resource."""
    storage = request.app.state.storage
    try:
        resource = await storage.get_resource(resource_id)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Resource '{resource_id}' not found"
        )

    encoded_filename = urllib.parse.quote(resource.meta.filename)
    return Response(
        content=resource.data,
        media_type=resource.meta.mime_type,
        headers={
            "Content-Disposition": f"inline; filename*=utf-8''{encoded_filename}",
        },
    )


@router.get("/resources/{resource_id:path}", response_model=ResourceMetaResponse)
async def get_resource_meta(request: Request, resource_id: str):
    """Get metadata for a single resource."""
    storage = request.app.state.storage
    try:
        meta = await storage.get_resource_meta(resource_id)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Resource '{resource_id}' not found"
        )
    return _meta_to_response(meta)


@router.post("/resources", response_model=ResourceMetaResponse, status_code=201)
async def upload_resource(
    request: Request,
    file: UploadFile = File(...),
    resource_id: str = Form(...),
    title: str = Form(...),
    tags: str = Form(""),
    categories: str = Form(""),
    related: str = Form(""),
    description: str = Form(""),
):
    """Upload a new resource (multipart form: file + metadata fields).

    Tags, categories, and related are comma-separated strings.
    """
    storage = request.app.state.storage
    index = request.app.state.index

    # Check for duplicate
    if resource_id in storage._resource_meta_cache:
        raise HTTPException(
            status_code=409,
            detail=f"Resource '{resource_id}' already exists",
        )

    # Read file data
    data = await file.read()

    # Parse comma-separated lists
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    cat_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else []
    rel_list = [r.strip() for r in related.split(",") if r.strip()] if related else []

    # Determine MIME type
    mime_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"

    now = datetime.now(timezone.utc)
    meta = ResourceMeta(
        id=resource_id,
        title=title,
        filename=file.filename or f"{resource_id}.bin",
        mime_type=mime_type,
        tags=tag_list,
        categories=cat_list,
        related=rel_list,
        description=description,
        created=now,
        modified=now,
    )

    saved_meta = await storage.save_resource(resource_id, data, meta)

    # Update index
    index.rebuild_resource(resource_id, saved_meta)

    return _meta_to_response(saved_meta)


@router.delete("/resources/{resource_id}", status_code=204)
async def delete_resource(request: Request, resource_id: str):
    """Delete a resource."""
    storage = request.app.state.storage
    index = request.app.state.index

    try:
        await storage.delete_resource(resource_id)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Resource '{resource_id}' not found"
        )

    index.remove_resource(resource_id)
