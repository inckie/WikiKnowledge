---
id: ai-settings-and-mcp-binding
title: AI Settings and MCP Binding
type: leaf
tags: ['ai', 'mcp', 'settings', 'openapi', 'configuration']
categories: ['ai-integration']
created: 2026-06-24T04:15:00+00:00
modified: 2026-06-24T04:15:00+00:00
---

# AI Settings and MCP Binding

WikiKnowledge features an optional AI integration architecture built upon the OpenAPI protocol. This allows remote AI models (such as those hosted via Ollama, OpenAI, or compatible endpoints) to seamlessly interact with the knowledge graph, assist in generating hierarchical category overviews, and bind directly to the application's embedded Model Context Protocol (MCP) server tools.

## Configuration & Environment Injection

### Storage Location
To maintain portability while separating configuration from article content, AI settings are stored within a dedicated directory in the knowledge base path:
```
knowledge/
├── .settings/
│   └── ai_config.json
├── articles/
└── categories/
```

### Startup Lifecycle & Environment Injection
During application startup (managed by `AIService` within the FastAPI lifespan context), the system inspects `ai_config.json`. If configuration is present and enabled, the settings are automatically injected into `os.environ` similar to command-line arguments.

Key environment variables injected include:
- `WIKIKNOWLEDGE_AI_URL` / `OPENAI_API_BASE`
- `WIKIKNOWLEDGE_AI_API_KEY` / `OPENAI_API_KEY`
- `WIKIKNOWLEDGE_AI_MODEL` / `OPENAI_MODEL`

This enables any underlying service or client library to instantly locate and authenticate against the remote AI model without requiring hardcoded configuration or manual environment setup.

## Web UI Settings Page

The WikiKnowledge web interface includes a dedicated **Settings** page accessible via the sidebar navigation (`#/settings`).

```
┌────────────────────────────────────────────────────────┐
│ ⚙️ AI Integration Settings                             │
├────────────────────────────────────────────────────────┤
│  OpenAPI Base URL:  [ https://ollama.com/v1         ]  │
│  API Key:           [ ***************************** ]  │
│                                                        │
│  [ 🔄 Fetch Available Models ]                         │
│                                                        │
│  Select Model:      [ Default Model ▾               ]  │
│                                                        │
│  ☑ Enable AI Integration & MCP Tool Binding            │
│                                                        │
│                                   [ 💾 Save Settings ] │
└────────────────────────────────────────────────────────┘
```

### Dynamic Model Discovery
When a user enters an OpenAPI Base URL (e.g., `https://ollama.com/v1`) and an API Key, the **Fetch Available Models** button becomes active. Clicking this button triggers a backend request (`POST /api/ai/models`) which establishes a secure connection to the remote endpoint's `/models` route, parses the available models, and populates the selection dropdown in real-time.

## Remote MCP Tool Binding

The core objective of the AI integration is to establish an autonomous feedback loop between the remote AI model and the embedded WikiKnowledge MCP server (`wikiknowledge/mcp_server.py`).

```
┌──────────────────────┐             ┌──────────────────────┐
│  Remote OpenAPI AI   │ ◄─────────► │ WikiKnowledge MCP    │
│  (Ollama / OpenAI)   │  Tool Call  │ Server (FastMCP)     │
└──────────────────────┘             └──────────────────────┘
```

### Next Step Integration
In the next phase of the project, `AIService` will leverage the saved configuration to expose our internal MCP tools (`get_article`, `list_articles`, `save_article`, `search`, etc.) directly to the remote model. This will allow the web UI to bind these tools dynamically, empowering the remote AI to autonomously inspect dirty category trees, trace backlinks, and maintain the knowledge graph.
