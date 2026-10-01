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


class ResourceMetaUpdateRequest(BaseModel):
    """Request body for updating resource metadata."""
    title: Optional[str] = None
    tags: Optional[list[str]] = None
    categories: Optional[list[str]] = None
    related: Optional[list[str]] = None
    description: Optional[str] = None


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


# NOTE: The sub-path routes below (/file, /metadata) MUST be defined before
# the generic `/resources/{resource_id:path}` route. Because `{resource_id:path}`
# matches any path including slashes, it would intercept requests ending in
# `/file` or `/metadata` if it were defined first, causing 404/method errors.
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


@router.put("/resources/{resource_id:path}/file", response_model=ResourceMetaResponse)
async def replace_resource_file(request: Request, resource_id: str):
    """Replace only the binary file for an existing resource without altering other metadata."""
    storage = request.app.state.storage
    index = request.app.state.index

    try:
        resource = await storage.get_resource(resource_id)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Resource '{resource_id}' not found"
        )

    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        upload_file = form.get("file")
        if not upload_file or not hasattr(upload_file, "read"):
            raise HTTPException(status_code=400, detail="Missing 'file' field in multipart form data")
        data = await upload_file.read()
        file_mime = upload_file.content_type or mimetypes.guess_type(upload_file.filename or "")[0]
        if file_mime:
            resource.meta.mime_type = file_mime
    else:
        data = await request.body()
        if not data:
            raise HTTPException(status_code=400, detail="Request body cannot be empty")
        clean_content_type = content_type.split(";")[0].strip()
        if clean_content_type and clean_content_type != "application/octet-stream":
            resource.meta.mime_type = clean_content_type

    resource.meta.modified = datetime.now(timezone.utc)
    saved_meta = await storage.save_resource(resource_id, data, resource.meta)
    index.rebuild_resource(resource_id, saved_meta)

    return _meta_to_response(saved_meta)


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


@router.put("/resources/{resource_id:path}/metadata", response_model=ResourceMetaResponse)
async def update_resource_metadata(
    request: Request, resource_id: str, payload: ResourceMetaUpdateRequest
):
    """Update metadata for an existing resource."""
    storage = request.app.state.storage
    index = request.app.state.index

    try:
        resource = await storage.get_resource(resource_id)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Resource '{resource_id}' not found"
        )

    meta = resource.meta
    
    if payload.title is not None:
        meta.title = payload.title
    if payload.tags is not None:
        meta.tags = payload.tags
    if payload.categories is not None:
        meta.categories = payload.categories
    if payload.related is not None:
        meta.related = payload.related
    if payload.description is not None:
        meta.description = payload.description
        
    meta.modified = datetime.now(timezone.utc)

    saved_meta = await storage.save_resource(resource_id, resource.data, meta)
    
    # Update index
    index.rebuild_resource(resource_id, saved_meta)

    return _meta_to_response(saved_meta)


@router.put("/resources/{resource_id:path}", response_model=ResourceMetaResponse)
async def replace_resource(
    request: Request,
    resource_id: str,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    categories: Optional[str] = Form(None),
    related: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
):
    """Replace an existing resource's binary file and optionally update its metadata."""
    storage = request.app.state.storage
    index = request.app.state.index

    try:
        resource = await storage.get_resource(resource_id)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Resource '{resource_id}' not found"
        )

    data = await file.read()
    meta = resource.meta

    if title is not None:
        meta.title = title
    if tags is not None:
        meta.tags = [t.strip() for t in tags.split(",") if t.strip()]
    if categories is not None:
        meta.categories = [c.strip() for c in categories.split(",") if c.strip()]
    if related is not None:
        meta.related = [r.strip() for r in related.split(",") if r.strip()]
    if description is not None:
        meta.description = description

    meta.mime_type = file.content_type or mimetypes.guess_type(file.filename or meta.filename)[0] or meta.mime_type
    meta.modified = datetime.now(timezone.utc)

    saved_meta = await storage.save_resource(resource_id, data, meta)
    index.rebuild_resource(resource_id, saved_meta)

    return _meta_to_response(saved_meta)


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
    replace: bool = Form(False),
):
    """Upload a new resource (multipart form: file + metadata fields).

    Tags, categories, and related are comma-separated strings.
    If replace is True, allows overwriting an existing resource.
    """
    storage = request.app.state.storage
    index = request.app.state.index

    now = datetime.now(timezone.utc)
    created = now

    # Check for duplicate
    if resource_id in storage._resource_meta_cache:
        if not replace:
            raise HTTPException(
                status_code=409,
                detail=f"Resource '{resource_id}' already exists",
            )
        existing = storage._resource_meta_cache[resource_id]
        created = existing.created

    # Read file data
    data = await file.read()

    # Parse comma-separated lists
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    cat_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else []
    rel_list = [r.strip() for r in related.split(",") if r.strip()] if related else []

    # Determine MIME type
    mime_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"

    meta = ResourceMeta(
        id=resource_id,
        title=title,
        filename=file.filename or f"{resource_id}.bin",
        mime_type=mime_type,
        tags=tag_list,
        categories=cat_list,
        related=rel_list,
        description=description,
        created=created,
        modified=now,
    )

    saved_meta = await storage.save_resource(resource_id, data, meta)

    # Update index
    index.rebuild_resource(resource_id, saved_meta)

    return _meta_to_response(saved_meta)


@router.delete("/resources/{resource_id:path}", status_code=204)
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
