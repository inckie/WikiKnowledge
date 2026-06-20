---
id: "fastapi-backend"
title: "FastAPI Backend"
type: "leaf"
tags: ["architecture", "api", "fastapi", "python", "rest"]
categories: ["system-architecture"]
created: "2026-06-19T21:00:00Z"
modified: "2026-06-19T21:00:00Z"
---

# FastAPI Backend

The WikiKnowledge web interface is powered by a FastAPI application that serves both the REST API and the static frontend files. FastAPI was chosen for its async support, automatic OpenAPI documentation, and Pydantic integration for request/response validation.

## Architecture

```
Request → FastAPI Router → Service Layer → Storage Backend → Filesystem
                                         → In-Memory Index
```

The API layer is intentionally thin. Route handlers validate input, call into the [[storage-abstraction]] or [[in-memory-index]], and return serialized responses. Business logic (e.g., update cascading, summarization triggers) lives in the service layer.

## Startup Lifecycle

On application startup (via FastAPI's lifespan context manager):

1. Initialize the `MarkdownStorageBackend` with the `knowledge/` directory path
2. Scan and parse all markdown files
3. Build the [[in-memory-index]] from the parsed data
4. Mount the static frontend files
5. Register all API routers

## API Endpoints

### Articles

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/articles` | List all articles. Query params: `type` (leaf/category), `tag`, `category` |
| `GET` | `/api/articles/{id}` | Get a single article with full content and metadata |
| `POST` | `/api/articles` | Create a new article. Body: `{id, title, type, tags, categories, content}` |
| `PUT` | `/api/articles/{id}` | Update an existing article. Body: same as POST |
| `DELETE` | `/api/articles/{id}` | Delete an article and remove it from the index |
| `GET` | `/api/articles/{id}/backlinks` | "What links here" — returns articles that link to this one |

### Search and Discovery

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/tags` | List all tags with usage counts |
| `GET` | `/api/categories` | List all category articles |
| `GET` | `/api/search?q=...` | Full-text search across article titles and content |

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
