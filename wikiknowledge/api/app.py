"""FastAPI Backend

:wk-id: fastapi-backend
:wk-tags: architecture, api, fastapi, python, rest
:wk-categories: system-architecture

The WikiKnowledge web interface is powered by a FastAPI application that serves both the REST API and the static frontend files. FastAPI was chosen for its async support, automatic OpenAPI documentation, and Pydantic integration for request/response validation.

## Architecture

> Request → [[src:wikiknowledge/wk/frontend-app|FastAPI Router]] → [[src:wikiknowledge/wk/ai-service|Service Layer]] → [[src:wikiknowledge/wk/storage-contract|Storage Backend]] → Filesystem
                                         → [[src:wikiknowledge/wk/index-engine|In-Memory Index]]

The API layer is intentionally thin. Route handlers validate input, call into the [[src:wikiknowledge/storage-abstraction|storage-abstraction]] or [[src:wikiknowledge/in-memory-index|in-memory-index]], and return serialized responses. Business logic (e.g., update cascading, summarization triggers) lives in the service layer.

## Startup Lifecycle

On application startup (via FastAPI's lifespan context manager):

1. Initialize the `MarkdownStorageBackend` with the `knowledge/` directory path
2. Scan and parse all markdown files
3. Build the [[src:wikiknowledge/in-memory-index|in-memory-index]] from the parsed data
4. Initialize `AIService`, load `.settings/ai_config.json`, and inject environment variables
5. Mount the static frontend files
6. Register all API routers

## API Endpoints

### Articles

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/articles` | List all articles. Query params: `type` (leaf/category), `tag`, `category` |
| `GET` | `/api/articles/{id}` | Get a single article with full content and metadata |
| `POST` | `/api/articles` | Create a new article. Body: `{id, title, type, tags, categories, content}` |
| `POST` | `/api/articles/{id}/move` | Rename/move an article. Body: `{new_id, update_links, title, type, tags, categories, content, content_patches}` |
| `PUT` | `/api/articles/{id}` | Update an existing article. Body: optional `{title, type, tags, categories, content, content_patches}` (supports `diff-match-patch`) |
| `DELETE` | `/api/articles/{id}` | Delete an article and remove it from the index |
| `GET` | `/api/articles/{id}/backlinks` | "What links here" — returns articles that link to this one |

### Resources

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/resources` | List metadata for all media/binary resources |
| `GET` | `/api/resources/{id}` | Get metadata for a single resource |
| `GET` | `/api/resources/{id}/file` | Download the raw binary file for a resource |
| `POST` | `/api/resources` | Upload a new resource (multipart/form-data with file and metadata fields) |
| `POST` | `/api/resources/{id}/move` | Rename/move a resource. Body: `{new_id, update_references}` |
| `DELETE` | `/api/resources/{id}` | Delete a resource and its sidecar file |

### Search and Discovery

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/tags` | List all tags with usage counts |
| `GET` | `/api/categories` | List all category articles |
| `GET` | `/api/search?q=...` | Full-text search across article titles and content |

### AI Integration

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/ai/settings` | Retrieve current AI configuration settings |
| `POST` | `/api/ai/settings` | Save AI settings to `.settings/ai_config.json` and inject environment |
| `POST` | `/api/ai/models` | Query remote OpenAI API endpoint for available model IDs |

### Graph

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/graph` | Full graph data (nodes + links) for D3.js visualization |
| `GET` | `/api/graph/{id}` | Subgraph centered on a specific article, with configurable depth |
| `GET` | `/api/graph/categories` | Hierarchical category tree structure |

## Static File Serving

The frontend is a plain HTML/CSS/JS application (no build step) served from the `frontend/` directory. FastAPI's `StaticFiles` middleware mounts it at the root path `/`. The `index.html` acts as the SPA entry point, with hash-based routing handled client-side.

```python
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
```

API routes are registered *before* the static mount so they take priority over file serving.

## Error Handling

The API uses standard HTTP status codes:

- `404` — Article not found
- `409` — Conflict (e.g., creating an article with an ID that already exists)
- `422` — Validation error (invalid frontmatter, missing required fields)
- `500` — Internal server error

All error responses follow a consistent JSON shape:

```json
{
  "detail": "Article 'nonexistent-id' not found"
}
```

## Development

The server is started with:

```bash
python run.py
```

This runs Uvicorn with auto-reload enabled, so changes to Python files are picked up automatically. The frontend files are also served fresh on each request (no caching in dev mode).

The auto-generated OpenAPI documentation is available at `/docs` (Swagger UI) and `/redoc` (ReDoc), providing interactive API exploration and testing.
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
    from wikiknowledge.core.index import rebuild_full_index
    await rebuild_full_index(index, storage, source_manager)

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