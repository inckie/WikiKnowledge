# WikiKnowledge Codebase Context

Quick-reference summary of the WikiKnowledge architecture for any AI agent picking up this work. Read this if you need to understand the codebase before making changes.

## Project Location

`d:\Work\Tools\AI\WikiKnowledge`

## Tech Stack

- **Backend**: Python 3.12+, FastAPI, Pydantic, `python-frontmatter`, `diff-match-patch`
- **Frontend**: Vanilla HTML/CSS/JS, D3.js (CDN), Marked.js (CDN), Mermaid (CDN)
- **MCP**: FastMCP library, mounted on FastAPI at `/mcp`
- **Package management**: `uv` (pyproject.toml + uv.lock)

## Directory Structure

```
WikiKnowledge/
├── .agents/                      # Agent-specific working notes (this folder)
├── frontend/
│   ├── index.html                # SPA entry point
│   ├── css/                      # Stylesheets
│   └── js/
│       ├── app.js                # Main controller, routing, sidebar
│       ├── api.js                # REST API client
│       ├── viewer.js             # Markdown rendering with wiki-link resolution
│       ├── editor.js             # Split-pane article editor
│       ├── graph.js              # D3.js force-directed graph
│       ├── metadata.js           # Tag/category chip controls
│       ├── chat.js               # AI chat interface
│       ├── settings.js           # Settings panel (AI config)
│       └── utils.js              # Shared utilities
├── knowledge/
│   ├── articles/                 # Leaf article .md files
│   ├── categories/               # Category article .md files
│   └── media/                    # Binary resources + .meta sidecars
├── wikiknowledge/
│   ├── __init__.py
│   ├── mcp_server.py             # MCP server factory (17 tools)
│   ├── api/
│   │   ├── app.py                # FastAPI factory + lifespan
│   │   ├── articles.py           # Article CRUD routes
│   │   ├── resources.py          # Resource CRUD routes
│   │   ├── search.py             # Search endpoint
│   │   ├── graph.py              # Graph data endpoint
│   │   ├── ai.py                 # AI chat/summarization routes
│   │   └── sse.py                # SSE transport for MCP
│   ├── core/
│   │   ├── index.py              # KnowledgeIndex (in-memory inverted index)
│   │   ├── parser.py             # Wiki-link + content block parser
│   │   ├── graph.py              # KnowledgeGraph (D3 data builder)
│   │   ├── refactor.py           # Rename with global link updates
│   │   └── ai_service.py         # AI config, model fetching, tool loop
│   └── storage/
│       ├── base.py               # StorageBackend ABC
│       ├── models.py             # Pydantic data models
│       └── markdown_backend.py   # File-system implementation
├── config.json                   # Multi-KB manager configuration
├── kb_manager.py                 # Tkinter multi-KB launcher GUI
├── run.py                        # Server entry point
├── main.py                       # Alternative entry point
└── pyproject.toml                # Package metadata + dependencies
```

## Architecture Summary

### Data Flow

```
Markdown files on disk
  → MarkdownStorageBackend (parse frontmatter, extract links, cache in memory)
  → KnowledgeIndex (build forward/back links, tag index, category index)
  → KnowledgeGraph (produce D3.js node/link data)
  → FastAPI API routes (REST endpoints)
  → Frontend SPA (render, edit, visualize)

MCP Server (parallel path)
  → 17 tools wrapping storage + index operations
  → AI agents access via MCP protocol
```

### Key Design Patterns

1. **Files are source of truth** — the index is always rebuildable from `.md` files
2. **Incremental index updates** — single-article changes don't require full rebuild
3. **Human/AI content separation** — `<!-- human:start/end -->` / `<!-- ai:start/end -->` markers
4. **Dirty category detection** — category is "dirty" when member articles are newer
5. **Many-to-many categories** — articles can belong to multiple categories (vs. file-system folders)
6. **Atomic writes** — temp file + rename pattern prevents corruption

### Data Models (from `storage/models.py`)

- `ArticleMeta`: id, title, type (leaf/category), tags[], categories[], created, modified
- `Article`: ArticleMeta + content string
- `WikiLink`: source_id, target_id, display_text, line_number, is_file_link
- `ResourceMeta`: id, title, filename, mime_type, tags[], categories[], related[], description
- `Resource`: ResourceMeta + bytes data
- `ContentBlock`: content, block_type (human/ai/unmarked), start_line, end_line

### Current Article Inventory (15 articles)

**Categories**: system-architecture, markup-conventions, ai-integration  
**Leaves**: overview, fastapi-backend, in-memory-index, storage-abstraction, local-setup-and-mcp, markdown-frontmatter, wiki-link-syntax, human-protected-blocks, category-features, mermaid-diagrams, ai-interaction-guide, ai-settings-and-mcp-binding  
**Resources**: wikiknowledge-logo.svg

## MCP Access

All article/resource operations are available via the `mcp-host-http` MCP server with `wikiknowledge_*` tool names:
- `wikiknowledge_get_article`, `wikiknowledge_list_articles`, `wikiknowledge_save_article`
- `wikiknowledge_update_article`, `wikiknowledge_delete_article`, `wikiknowledge_move_article`
- `wikiknowledge_get_backlinks`, `wikiknowledge_get_category_members`, `wikiknowledge_get_category_status`
- `wikiknowledge_search`, `wikiknowledge_get_all_tags`, `wikiknowledge_rebuild_index`
- `wikiknowledge_get_resource`, `wikiknowledge_list_resources`, `wikiknowledge_upload_resource`, `wikiknowledge_delete_resource`
- `wikiknowledge_move_resource`

## Running the Server

```bash
# From project root
uv run python run.py --port=8001

# Or via kb_manager.py for multi-KB management
uv run python kb_manager.py
```
