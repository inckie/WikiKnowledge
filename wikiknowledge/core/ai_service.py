"""AI Service & MCP Architecture

:wk-id: ai-service-architecture
:wk-tags: architecture, mcp, backend, api
:wk-categories: system-architecture

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
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional


class AIService:
    """Manages AI integration settings, OpenAI API model fetching, and future MCP binding."""

    def __init__(self, kb_dir: Path | str):
        """Initialize the AI service with the knowledge base directory path."""
        self.kb_dir = Path(kb_dir)
        self.settings_dir = self.kb_dir / ".settings"
        self.config_path = self.settings_dir / "ai_config.json"

    def load_settings(self) -> Dict[str, Any]:
        """Load AI configuration settings from disk.

        Returns default settings if the file does not exist.
        """
        defaults = {
            "url": "https://ollama.com/v1",
            "api_key": "",
            "model": "",
            "enabled": False,
        }

        if not self.config_path.exists():
            return defaults

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults.update(data)
        except Exception as e:
            print(f"Error reading AI config: {e}")

        return defaults

    def save_settings(
        self, url: str, api_key: str, model: str, enabled: bool = True
    ) -> Dict[str, Any]:
        """Save AI configuration settings to disk and update the environment."""
        self.settings_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "url": url.strip(),
            "api_key": api_key.strip(),
            "model": model.strip(),
            "enabled": enabled,
        }

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving AI config: {e}")
            raise RuntimeError(f"Failed to save AI settings: {e}")

        # Inject settings into environment immediately upon saving
        self.inject_environment()
        return data

    def inject_environment(self) -> bool:
        """Inject AI configuration settings into os.environ similar to command-line arguments.

        Returns True if integration is present and enabled, False otherwise.
        """
        if not self.config_path.exists():
            return False

        settings = self.load_settings()
        if not settings.get("enabled") and (not settings.get("url") or not settings.get("api_key")):
            return False

        url = settings.get("url", "")
        api_key = settings.get("api_key", "")
        model = settings.get("model", "")

        if url:
            os.environ["WIKIKNOWLEDGE_AI_URL"] = url
            os.environ["OPENAI_API_BASE"] = url
        if api_key:
            os.environ["WIKIKNOWLEDGE_AI_API_KEY"] = api_key
            os.environ["OPENAI_API_KEY"] = api_key
        if model:
            os.environ["WIKIKNOWLEDGE_AI_MODEL"] = model
            os.environ["OPENAI_MODEL"] = model

        print(f"AI integration enabled. Environment configured for URL: {url}")
        return True

    def fetch_available_models(self, url: str, api_key: str) -> List[str]:
        """Fetch available models from a remote OpenAI API / OpenAI-compatible endpoint.

        Args:
            url: Base URL (e.g., https://ollama.com/v1)
            api_key: API Key for authorization

        Returns:
            List of model ID strings.
        """
        endpoint = f"{url.rstrip('/')}/models"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        req = urllib.request.Request(endpoint, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                body = response.read().decode("utf-8")
                data = json.loads(body)

                # OpenAI API protocol typically returns {"data": [{"id": "model_name", ...}]}
                models_list = data.get("data") or data.get("models") or []
                if isinstance(models_list, list):
                    return [
                        m.get("id", str(m)) for m in models_list if isinstance(m, dict) and "id" in m
                    ]
                return []
        except urllib.error.URLError as e:
            raise RuntimeError(f"Failed to connect to AI endpoint ({endpoint}): {e}")
        except Exception as e:
            raise RuntimeError(f"Error parsing models from AI endpoint: {e}")

    # --- MCP Binding & OpenAI API Tool Loop ---

    async def initialize_mcp_binding(self, mcp_server: Any) -> Any:
        """Initialize and verify binding of FastMCP server tools to the remote AI model."""
        settings = self.load_settings()
        if not settings.get("enabled"):
            raise RuntimeError("AI Integration is not enabled in settings.")

        tools = await mcp_server.list_tools()
        print(f"Verified MCP binding with {len(tools)} tools to remote model.")
        return {"status": "bound", "bound_tools_count": len(tools)}

    async def invoke_remote_model_with_tools(self, prompt: str, mcp_server: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Invoke the remote model with an active MCP tool calling loop.

        Allows the remote OpenAI API model to inspect, call, and receive results
        from our embedded FastMCP tools until a final response is generated.
        """
        settings = self.load_settings()
        if not settings.get("enabled"):
            raise RuntimeError("AI Integration is not enabled in settings.")

        url = settings.get("url", "").rstrip("/")
        api_key = settings.get("api_key", "")
        model = settings.get("model", "")

        if not url or not model:
            raise RuntimeError("AI Base URL or Model is not configured in settings.")

        endpoint = f"{url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Convert FastMCP tools to OpenAI API tool definitions
        openapi_tools = []
        try:
            mcp_tools = await mcp_server.list_tools()
            for t in mcp_tools:
                params = t.inputSchema if getattr(t, "inputSchema", None) else {"type": "object", "properties": {}}
                openapi_tools.append({
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description or f"Execute {t.name}",
                        "parameters": params,
                    },
                })
        except Exception as e:
            print(f"Error listing MCP tools: {e}")

        full_prompt = prompt
        if context:
            ctx_str = f"User is currently viewing the '{context.get('current_view', 'unknown')}' page"
            if context.get('current_article_id'):
                ctx_str += f" for article ID '{context.get('current_article_id')}'"
            full_prompt += f"\n\n[System Context: {ctx_str}]"

        messages = [{"role": "user", "content": full_prompt}]
        max_iterations = 10
        start_time = time.time()

        for _ in range(max_iterations):
            payload = {
                "model": model,
                "messages": messages,
            }
            if openapi_tools:
                payload["tools"] = openapi_tools

            data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(endpoint, data=data_bytes, headers=headers, method="POST")

            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    body = response.read().decode("utf-8")
                    resp_data = json.loads(body)
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                raise RuntimeError(f"AI endpoint HTTPError {e.code}: {err_body}")
            except Exception as e:
                raise RuntimeError(f"Failed to communicate with AI endpoint: {e}")

            choices = resp_data.get("choices", [])
            if not choices:
                raise RuntimeError("No choices returned in AI response.")

            message = choices[0].get("message", {})
            tool_calls = message.get("tool_calls")

            if not tool_calls:
                # No tool calls requested, return final content
                end_time = time.time()
                elapsed = end_time - start_time
                usage = resp_data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                tps = completion_tokens / elapsed if elapsed > 0 else 0
                
                return {
                    "content": message.get("content") or "",
                    "stats": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "time_s": round(elapsed, 2),
                        "tps": round(tps, 1)
                    }
                }

            # Model requested tool call(s), append assistant message to history
            messages.append(message)

            for tc in tool_calls:
                tc_id = tc.get("id")
                func = tc.get("function", {})
                func_name = func.get("name")
                func_args_str = func.get("arguments", "{}")

                try:
                    func_args = json.loads(func_args_str) if func_args_str else {}
                    content_list, _ = await mcp_server.call_tool(func_name, func_args)
                    tool_result = "\n".join([getattr(c, "text", str(c)) for c in content_list])
                except Exception as e:
                    tool_result = f"Error executing tool '{func_name}': {e}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": func_name,
                    "content": tool_result,
                })

        return {
            "content": "Error: Exceeded maximum tool execution iterations.",
            "stats": None
        }
