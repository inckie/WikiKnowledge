"""
FastAPI Backend Application
:wk-id: wk/frontend-app
:wk-tags: python, fast-api, backend, setup
:wk-categories: system-architecture

This module sets up the FastAPI application, mounts the static frontend, configures CORS, and registers all API routers. It also defines the lifespan context manager that initializes the storage backend and source plugins on startup.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from wikiknowledge.api.ai import router as ai_router
from wikiknowledge.api.articles import router as articles_router
from wikiknowledge.api.graph import router as graph_router
from wikiknowledge.api.resources import router as resources_router
from wikiknowledge.api.search import router as search_router
from wikiknowledge.api.sources import router as sources_router
from wikiknowledge.api.sse import create_sse_server
from wikiknowledge.core.ai_service import AIService
from wikiknowledge.core.graph import KnowledgeGraph
from wikiknowledge.core.index import KnowledgeIndex
from wikiknowledge.core.plugins.manager import SourceManager
from wikiknowledge.mcp_server import create_mcp_server
from wikiknowledge.storage.markdown_backend import MarkdownStorageBackend

# Resolve paths relative to the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
env_kb_dir = os.environ.get("WIKIKNOWLEDGE_KB_DIR")
KNOWLEDGE_DIR = Path(env_kb_dir) if env_kb_dir else PROJECT_ROOT / "knowledge"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# Create shared instances that will be initialized in the lifespan
storage = MarkdownStorageBackend(KNOWLEDGE_DIR)
index = KnowledgeIndex()
graph = KnowledgeGraph(index)
source_manager = SourceManager(KNOWLEDGE_DIR)
mcp_server = create_mcp_server(storage, index, graph, source_manager)
ai_service = AIService(KNOWLEDGE_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize storage and index on startup."""
    # Initialize storage backend
    await storage.initialize()
    
    # Initialize knowledge sources
    await source_manager.initialize()
    virtual_articles = await source_manager.discover_all_articles()
    virtual_meta = {a.id: a for a in virtual_articles}
    virtual_links = await source_manager.get_all_links()

    # Merge physical and virtual articles
    all_meta = dict(storage._meta_cache)
    all_meta.update(virtual_meta)
    
    all_links = storage.get_all_links()
    all_links.update(virtual_links)

    # Build in-memory index (articles + resources)
    index.build(
        all_meta=all_meta,
        all_links=all_links,
        all_resource_meta=dict(storage._resource_meta_cache),
        all_resource_links=storage.get_all_resource_links(),
    )

    # Store on app state for access from other routes
    app.state.storage = storage
    app.state.index = index
    app.state.graph = graph
    app.state.ai_service = ai_service
    app.state.mcp_server = mcp_server
    app.state.source_manager = source_manager

    # Inject AI configuration into environment on launch
    ai_service.inject_environment()
    print("Storage, index, graph, and AI service initialized.")

    yield

    # Cleanup (if needed)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="WikiKnowledge",
        description="Knowledge Graph Construction and Question Answering System",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS for development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount the Starlette SSE server onto the FastAPI app
    app.mount("/mcp", create_sse_server(mcp_server))

    # API routes
    app.include_router(articles_router, prefix="/api")
    app.include_router(resources_router, prefix="/api")
    app.include_router(search_router, prefix="/api")
    app.include_router(graph_router, prefix="/api")
    app.include_router(ai_router, prefix="/api")
    app.include_router(sources_router, prefix="/api")

    # Static frontend files (mounted last as a catch-all)
    if FRONTEND_DIR.exists():
        app.mount(
            "/",
            StaticFiles(directory=str(FRONTEND_DIR), html=True),
            name="frontend",
        )

    return app


# Module-level app instance (used by uvicorn)
app = create_app()


def main():
    """Run the server (entry point for pyproject.toml scripts)."""
    import argparse
    import os
    import uvicorn

    parser = argparse.ArgumentParser(description="Run WikiKnowledge server.")
    parser.add_argument(
        "--kb-dir",
        type=str,
        help="Path to the knowledge base directory containing articles/ and categories/",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the server on",
    )
    args, _ = parser.parse_known_args()

    if args.kb_dir:
        os.environ["WIKIKNOWLEDGE_KB_DIR"] = os.path.abspath(args.kb_dir)

    uvicorn.run(
        "wikiknowledge.api.app:app",
        host="0.0.0.0",
        port=args.port,
        reload=True,
        reload_dirs=[str(PROJECT_ROOT / "wikiknowledge")],
    )