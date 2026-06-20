"""Graph data API endpoints for D3.js visualization."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["graph"])


@router.get("/graph")
async def get_full_graph(request: Request) -> dict[str, list[dict[str, Any]]]:
    """Get the full knowledge graph (nodes + links) for D3.js."""
    graph = request.app.state.graph
    return graph.get_full_graph()


@router.get("/graph/categories")
async def get_category_tree(request: Request) -> list[dict[str, Any]]:
    """Get the hierarchical category tree."""
    graph = request.app.state.graph
    return graph.get_category_tree()


@router.get("/graph/{article_id}")
async def get_subgraph(
    request: Request,
    article_id: str,
    depth: int = 2,
) -> dict[str, list[dict[str, Any]]]:
    """Get a subgraph centered on an article."""
    graph = request.app.state.graph
    index = request.app.state.index

    if index.get_meta(article_id) is None:
        raise HTTPException(
            status_code=404, detail=f"Article '{article_id}' not found"
        )

    return graph.get_subgraph(article_id, depth=depth)
