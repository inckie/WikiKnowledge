"""FastAPI router for AI integration settings and model fetching."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/ai", tags=["AI Integration"])


class AISettingsModel(BaseModel):
    """Pydantic model for AI configuration settings."""

    url: str = Field(default="https://ollama.com/v1", description="OpenAI API compatible base URL")
    api_key: str = Field(default="", description="API Key for authentication")
    model: str = Field(default="", description="Selected model ID")
    enabled: bool = Field(default=True, description="Whether AI integration is enabled")


class FetchModelsRequest(BaseModel):
    """Pydantic model for fetching models from a remote OpenAI API endpoint."""

    url: str = Field(..., description="OpenAI API compatible base URL")
    api_key: str = Field(default="", description="API Key for authentication")


@router.get("/settings", response_model=AISettingsModel)
async def get_ai_settings(request: Request):
    """Retrieve current AI configuration settings."""
    ai_service = getattr(request.app.state, "ai_service", None)
    if not ai_service:
        raise HTTPException(status_code=500, detail="AI Service not initialized.")

    settings = ai_service.load_settings()
    return AISettingsModel(**settings)


@router.post("/settings")
async def save_ai_settings(settings: AISettingsModel, request: Request):
    """Save AI configuration settings and update environment variables."""
    ai_service = getattr(request.app.state, "ai_service", None)
    if not ai_service:
        raise HTTPException(status_code=500, detail="AI Service not initialized.")

    try:
        updated = ai_service.save_settings(
            url=settings.url,
            api_key=settings.api_key,
            model=settings.model,
            enabled=settings.enabled,
        )
        return {"status": "success", "settings": updated}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/models")
async def fetch_available_models(body: FetchModelsRequest, request: Request):
    """Fetch available models from the remote OpenAI API endpoint."""
    ai_service = getattr(request.app.state, "ai_service", None)
    if not ai_service:
        raise HTTPException(status_code=500, detail="AI Service not initialized.")

    try:
        models = ai_service.fetch_available_models(url=body.url, api_key=body.api_key)
        return {"models": models}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class ChatRequest(BaseModel):
    """Pydantic model for AI chat request."""

    prompt: str = Field(..., description="User prompt for the AI model")


@router.post("/chat")
async def chat_with_ai(body: ChatRequest, request: Request):
    """Invoke the remote AI model with MCP tool binding."""
    ai_service = getattr(request.app.state, "ai_service", None)
    mcp_server = getattr(request.app.state, "mcp_server", None)
    if not ai_service or not mcp_server:
        raise HTTPException(status_code=500, detail="AI Service or MCP Server not initialized.")

    try:
        result = await ai_service.invoke_remote_model_with_tools(body.prompt, mcp_server)
        if isinstance(result, str):
            return {"reply": result, "stats": None}
        return {"reply": result.get("content", ""), "stats": result.get("stats")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

