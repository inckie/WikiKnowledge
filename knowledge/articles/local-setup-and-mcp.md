---
categories:
- system-architecture
created: '2026-06-20T02:14:00+00:00'
id: local-setup-and-mcp
modified: '2026-06-24T02:24:42.561450+00:00'
tags:
- setup
- deployment
- mcp
- config
title: Local Setup and MCP Configuration
type: leaf
---

# Local Setup and MCP Configuration

This guide provides instructions on how to set up the WikiKnowledge system on your local development machine, run the application backend and frontend, and configure Model Context Protocol (MCP) clients to enable AI assistants to read, update, and search your articles.

---

## 1. Local Setup & Launching

WikiKnowledge is built as a Python package utilizing FastAPI and is managed using the modern package manager `uv`.

### Prerequisites
- Python 3.13 or newer.
- `uv` installed on your machine (`pip install uv` or via standalone installer).

### Installation
Clone the repository and install all dependencies:
```bash
# Clone the repository
git clone <repository-url>
cd WikiKnowledge

# Sync environment and install dependencies
uv sync
```

### Running the Server
The application serves the web UI, a REST API, and the MCP server simultaneously. You can launch it using the Python script.

You can pass command-line arguments to specify a custom knowledge base directory and port:
```bash
uv run python run.py --kb-dir "D:/Path/To/Your/KnowledgeBase" --port 8000
```
Once running, the following services are active:
- **Web Interface (SPA)**: [http://localhost:8000/](http://localhost:8000/) — Explore articles, hierarchical category trees, tag clouds, interactive knowledge graphs, edit markdown files, and configure AI settings.
- **REST API Endpoint**: [http://localhost:8000/api](http://localhost:8000/api) — Direct JSON interface for articles, tags, graph nodes, and AI configuration.
- **OpenAPI / Swagger Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs) — Browse, test, and run HTTP request scripts against API endpoints.
- **MCP Server**: `http://localhost:8000/mcp` — Endpoints for AI tool integration.

### Optional AI Integration & Configuration
WikiKnowledge provides optional AI integration via the OpenAI API protocol. You can configure this directly from the web UI by navigating to the **Settings** page in the sidebar.
- **Configuration Storage**: Settings are saved in `[kb_dir]/.settings/ai_config.json`.
- **Environment Injection**: On launch, if `ai_config.json` is present, the system automatically injects the configured URL, API key, and model ID into `os.environ` (e.g., `WIKIKNOWLEDGE_AI_URL`, `OPENAI_API_BASE`), enabling seamless integration across the backend services.

---

## 2. Model Context Protocol (MCP) Integration

Model Context Protocol allows AI agents to directly view, query, and modify the knowledge base. The WikiKnowledge server uses `FastMCP` to provide this functionality, which runs alongside the main web application.

### Configuring MCP Clients

#### Option A: Cursor IDE
Cursor supports connecting to external MCP servers using the SSE transport protocol:
1. Open Cursor settings (`Ctrl+,` or `Cmd+,`).
2. Go to **Features** → **MCP**.
3. Click the **+ Add New MCP Server** button.
4. Configure the form:
   - **Name**: `WikiKnowledge`
   - **Type**: `sse`
   - **URL**: `http://localhost:8000/mcp/sse`
5. Click **Save**. The status indicator should turn green, indicating the IDE has successfully loaded the WikiKnowledge tools.

#### Option B: LM Studio
LM Studio supports connecting to external HTTP/SSE MCP servers.
To add the WikiKnowledge tools to LM Studio:
1. Open the **Tools / MCP** panel in LM Studio.
2. Select **SSE** (or HTTP/SSE) as the connection type.
3. Set the Endpoint URL to the explicit Server-Sent Events route:
   `http://localhost:8000/mcp/sse`
4. Click **Connect** to load the server.

---

## 3. Available MCP Tools

Once configured, the AI agent gains access to the following functions:
- `get_article(article_id)`: Read a full article with its YAML frontmatter metadata and markdown content.
- `list_articles(article_type, tag, category)`: Query, search, and filter matching articles.
- `save_article(article_id, title, article_type, tags, categories, content)`: Create or update articles programmatically.
- `delete_article(article_id)`: Delete articles.
- `get_backlinks(article_id)`: Retrieve a list of all articles linking to the requested ID.
- `get_category_members(category_id)`: List all articles nested within a given category.
- `get_category_status(category_id)`: Check if a category article's summary is outdated ('dirty') relative to its members.
- `search(query)`: Run full-text search across titles, tags, and contents.
- `get_all_tags()`: Fetch all tags along with their usage counts.
- `rebuild_index()`: Rebuild the knowledge index from the storage backend.