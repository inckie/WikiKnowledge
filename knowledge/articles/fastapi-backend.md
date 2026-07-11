---
categories:
- system-architecture
created: '2026-06-19T21:00:00+00:00'
id: fastapi-backend
modified: '2026-07-11T22:38:43.608933+00:00'
tags:
- architecture
- api
- fastapi
- python
- rest
title: FastAPI Backend
type: leaf
---

# FastAPI Backend

The WikiKnowledge web interface is powered by a FastAPI application that serves both the REST API and the static frontend files. FastAPI was chosen for its async support, automatic OpenAPI documentation, and Pydantic integration for request/response validation.

## Architecture

> Request → [[src:wikiknowledge/wk/frontend-app|FastAPI Router]] → [[src:wikiknowledge/wk/ai-service|Service Layer]] → [[src:wikiknowledge/wk/storage-contract|Storage Backend]] → Filesystem
                                         → [[src:wikiknowledge/wk/index-engine|In-Memory Index]]

The API layer is intentionally thin. Route handlers validate input, call into the [[storage-abstraction]] or [[in-memory-index]], and return serialized responses. Business logic (e.g., update cascading, summarization triggers) lives in the service layer.

## Startup Lifecycle

On application startup (via FastAPI's lifespan context manager):

1. Initialize the `MarkdownStorageBackend` with the `knowledge/` directory path
2. Scan and parse all markdown files
3. Build the [[in-memory-index]] from the parsed data
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