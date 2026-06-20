"""FastAPI application factory and configuration."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from wikiknowledge.api.articles import router as articles_router
from wikiknowledge.api.graph import router as graph_router
from wikiknowledge.api.search import router as search_router
from wikiknowledge.core.graph import KnowledgeGraph
from wikiknowledge.core.index import KnowledgeIndex
from wikiknowledge.mcp_server import create_mcp_server
from wikiknowledge.storage.markdown_backend import MarkdownStorageBackend

# Resolve paths relative to the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# Create shared instances that will be initialized in the lifespan
storage = MarkdownStorageBackend(KNOWLEDGE_DIR)
index = KnowledgeIndex()
graph = KnowledgeGraph(index)
mcp_server = create_mcp_server(storage, index, graph)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize storage and index on startup."""
    # Initialize storage backend
    await storage.initialize()

    # Build in-memory index
    index.build(
        all_meta=dict(storage._meta_cache),
        all_links=storage.get_all_links(),
    )

    # Store on app state for access from other routes
    app.state.storage = storage
    app.state.index = index
    app.state.graph = graph
    print("Storage, index, and graph initialized.")

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

    # Conditionally mount routes based on environment variable
    if os.environ.get("MCP_ONLY"):
        print("Running in MCP_ONLY mode for IDE integration.")
        # Mount MCP server components
        try:
            # The methods return ASGI applications, so we must call them.
            # We mount both at the root; their internal routing handles the specific paths.
            app.mount("/", mcp_server.sse_app())
            app.mount("/", mcp_server.streamable_http_app())
            print("MCP server apps mounted at /")
        except Exception as e:
            print(f"Warning: MCP server failed to mount: {e}")
    else:
        print("Running in standard web + API mode.")
        # API routes
        app.include_router(articles_router, prefix="/api")
        app.include_router(search_router, prefix="/api")
        app.include_router(graph_router, prefix="/api")

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
    import uvicorn

    uvicorn.run(
        "wikiknowledge.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(PROJECT_ROOT / "wikiknowledge")],
    )
