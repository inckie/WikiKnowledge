---
id: "local-setup-and-mcp"
title: "Local Setup and MCP Configuration"
type: "leaf"
tags: ["setup", "deployment", "mcp", "config"]
categories: ["system-architecture"]
created: "2026-06-20T02:14:00Z"
modified: "2026-06-20T02:14:00Z"
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
The application can run in two modes: **Standard Mode** for the web interface and API, and **MCP-Only Mode** for AI tool integration.

#### Standard Mode (Web + API)
This mode serves the web UI and the REST API.
```bash
uvicorn wikiknowledge.api.app:app --reload
```
Once running, the following services are active:
- **Web Interface (SPA)**: [http://localhost:8000/](http://localhost:8000/) — Explore articles, hierarchical category trees, tag clouds, interactive knowledge graphs, and edit markdown files directly.
- **REST API Endpoint**: [http://localhost:8000/api](http://localhost:8000/api) — Direct JSON interface for articles, tags, and graph nodes.
- **OpenAPI / Swagger Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs) — Browse, test, and run HTTP request scripts against API endpoints.

#### MCP-Only Mode (for AI Tools)
This mode is required for connecting AI assistants like LM Studio or Cursor. It exposes the MCP server endpoints.
```bash
# On Windows (Command Prompt)
set MCP_ONLY=1
uvicorn wikiknowledge.api.app:app --reload

# On macOS/Linux
MCP_ONLY=1 uvicorn wikiknowledge.api.app:app --reload
```
When running in this mode, the server will only expose the MCP endpoints at `http://localhost:8000/mcp` and `http://localhost:8000/mcp/sse`. The web UI and API will be disabled.

---

## 2. Model Context Protocol (MCP) Integration

Model Context Protocol allows AI agents to directly view, query, and modify the knowledge base. The WikiKnowledge server uses `FastMCP` to provide this functionality. To avoid routing conflicts with the main web application, the MCP server runs in a separate, dedicated mode.

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

> [!IMPORTANT]
> Ensure you are running the server in **MCP-Only Mode** before attempting to connect from an MCP client. If you are running in standard mode, the connection will fail with a `404 Not Found` error.

---

## 3. Available MCP Tools

Once configured, the AI agent gains access to the following functions:
- `get_article(article_id)`: Read a full article with its YAML frontmatter metadata and markdown content.
- `list_articles(article_type, tag, category)`: Query, search, and filter matching articles.
- `save_article(article_id, title, article_type, tags, categories, content)`: Create or update articles programmatically.
- `delete_article(article_id)`: Delete articles.
- `get_backlinks(article_id)`: Retrieve a list of all articles linking to the requested ID.
- `get_category_members(category_id)`: List all articles nested within a given category.
- `search(query)`: Run full-text search across titles, tags, and contents.
- `get_all_tags()`: Fetch all tags along with their usage counts.