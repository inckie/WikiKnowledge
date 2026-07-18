---
categories:
- system-architecture
created: '2026-07-18T06:38:41.093152+00:00'
id: ai-service-architecture
modified: '2026-07-18T06:38:41.093168+00:00'
tags:
- architecture
- mcp
- backend
- api
title: AI Service & MCP Architecture
type: leaf
---

# AI Service & MCP Architecture

This article outlines the backend implementation details of WikiKnowledge's AI integration, detailing how the `AIService` hooks into the FastAPI lifecycle and establishes the execution loop for the Model Context Protocol (MCP).

## Configuration & Environment Injection

### Startup Lifecycle
During application startup (managed by `AIService` within the FastAPI lifespan context), the system inspects `knowledge/.settings/ai_config.json`. If configuration is present and enabled, the settings are automatically injected into `os.environ` similar to command-line arguments.

Key environment variables injected include:
- `WIKIKNOWLEDGE_AI_URL` / `OPENAI_API_BASE`
- `WIKIKNOWLEDGE_AI_API_KEY` / `OPENAI_API_KEY`
- `WIKIKNOWLEDGE_AI_MODEL` / `OPENAI_MODEL`

This enables any underlying service or client library to instantly locate and authenticate against the remote AI model without requiring hardcoded configuration or manual environment setup.

## Remote MCP Tool Binding & Active Execution Loop

The core objective of the AI backend is to establish an autonomous feedback loop between the remote AI model and the embedded WikiKnowledge MCP server (`wikiknowledge/mcp_server.py`).

```
┌──────────────────────┐   tool_calls    ┌──────────────────────┐
│  Remote OpenAI API   │ ◄─────────────► │ WikiKnowledge MCP    │
│  (Ollama / OpenAI)   │  tool_results   │ Server (FastMCP)     │
└──────────────────────┘                 └──────────────────────┘
```

### Active Tool Calling Architecture
Through `AIService.invoke_remote_model_with_tools`, the system implements a fully automated OpenAI API tool execution loop:
1. **Tool Inspection**: `AIService` extracts the available FastMCP tools (`list_articles`, `get_article`, `search`, `save_article`, etc.) and converts their JSON schemas into OpenAI API function definitions.
2. **Execution Loop**: When a user prompt is sent to `/api/ai/chat`, the remote model receives the prompt along with the tool definitions. If the model responds with `tool_calls`, `AIService` intercepts them, executes the corresponding FastMCP tools locally in Python, appends the `tool` result messages to the conversation history, and calls the model again until a final text response is produced.