"""AI Service managing configuration, environment injection, OpenAPI model fetching, and MCP binding foundations."""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional


class AIService:
    """Manages AI integration settings, OpenAPI model fetching, and future MCP binding."""

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
        """Fetch available models from a remote OpenAPI / OpenAI-compatible endpoint.

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

                # OpenAPI / OpenAI protocol typically returns {"data": [{"id": "model_name", ...}]}
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

    # --- Future MCP Binding Foundations ---

    def initialize_mcp_binding(self, mcp_server: Any) -> Any:
        """Lay the foundation for binding our own MCP tools to the remote AI model.

        In the next step, this method will establish the client connection loop
        between the FastMCP server tools (wikiknowledge/mcp_server.py) and the
        remote OpenAPI model configured in os.environ.
        """
        settings = self.load_settings()
        if not settings.get("enabled"):
            raise RuntimeError("AI Integration is not enabled in settings.")

        # Foundation placeholder for next step MCP binding initialization
        print("Initializing MCP binding to remote model...")
        return {"status": "ready", "bound_tools_count": len(mcp_server._tools)}

    async def invoke_remote_model_with_tools(self, prompt: str, mcp_server: Any) -> str:
        """Foundation stub for invoking the remote model with an active MCP tool calling loop.

        This will be implemented in the next step to allow the remote model
        to inspect, call, and receive results from our embedded MCP tools.
        """
        # Placeholder for next step implementation
        return f"Remote model invoked with tools for prompt: {prompt}"
