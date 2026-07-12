"""
AI Engine Configuration Router

API endpoints for managing AI model configurations:
- List available models
- Test model connectivity
- Set default model
- Configure API keys
- Update model settings
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from ..services.ai_engine_config import get_ai_engine_config, AIEngineConfigService, AIEngineConfigError
from ..models.config import ModelConfig, AIProvider

router = APIRouter(tags=["AI Engine Configuration"])

# Request/Response models
class ModelConfigRequest(BaseModel):
    model_id: str = Field(..., description="Unique model identifier")
    name: str = Field(..., description="Human-readable model name")
    provider: str = Field(..., description="AI provider (ollama, ibm_bob, google_gemma, nvidia_nim)")
    endpoint_url: Optional[str] = None
    api_key_env: Optional[str] = Field(None, description="Environment variable name for API key (optional)")
    context_window: int = 4096
    temperature: float = 0.7
    max_tokens: int = 2048
    provider_config: Dict[str, Any] = Field(default_factory=dict)
    config_note: Optional[str] = Field(None, description="Configuration notes for user reference")

class UpdateModelRequest(BaseModel):
    """Request model for updating an existing model's configuration"""
    model_id: str = Field(..., description="Model ID to update")
    name: Optional[str] = None
    endpoint_url: Optional[str] = None
    api_key_env: Optional[str] = Field(None, description="Custom environment variable name (optional)")
    context_window: Optional[int] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    provider_config: Optional[Dict[str, Any]] = None
    config_note: Optional[str] = None

class TestConnectionRequest(BaseModel):
    model_id: str = Field(..., description="Model ID to test")

class SetDefaultModelRequest(BaseModel):
    model_id: str = Field(..., description="Model ID to set as default")

class SetApiKeyRequest(BaseModel):
    model_id: str = Field(..., description="Model ID")
    api_key: str = Field(..., description="API key to set")

class UpdateConfigRequest(BaseModel):
    timeout_seconds: Optional[int] = None
    max_retries: Optional[int] = None
    enable_fallback: Optional[bool] = None
    enable_caching: Optional[bool] = None

# GET /api/ai-engine/config
@router.get("/config", response_model=Dict[str, Any])
async def get_ai_config(
    config: AIEngineConfigService = Depends(get_ai_engine_config)
):
    """
    Get current AI engine configuration.
    
    Returns default provider, default model, and list of all available models with their status.
    """
    return config.get_config_for_ui()

# GET /api/ai-engine/provider-models
@router.get("/provider-models", response_model=Dict[str, Any])
async def get_provider_models(
    provider: Optional[str] = None,
    config: AIEngineConfigService = Depends(get_ai_engine_config)
) -> Dict[str, Any]:
    """Return a list of models available from the selected provider.
    The UI uses this endpoint to populate the "Add Model" dialog.
    """
    # Resolve provider identifier to enum, accepting common aliases
    if provider:
        normalized = provider.lower().replace("-", "_")
        alias_map = {
            "nvidia": "nvidia_nim",
            "google": "google_gemma",
            "ibm": "ibm_bob",
            "openrouter": "openrouter",
            "anthropic": "anthropic",
            "openai": "openai",
            "ollama": "ollama",
        }
        normalized = alias_map.get(normalized, normalized)
        try:
            prov_enum = AIProvider(normalized)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Unsupported provider '{provider}'") from exc
    else:
        prov_enum = config.config.default_provider
    try:
        models = config.list_provider_models(prov_enum)
        return {"models": models}
    except AIEngineConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# GET /api/ai-engine/logs
@router.get("/logs", response_model=Dict[str, Any])
async def get_logs(
    tail: int = 1048576,  # 1MiB by default
) -> Dict[str, Any]:
    """Return the last *tail* bytes of the backend log file.

    This supports the UI "tail logs" feature. If the log file cannot be read we return
    an empty string.
    """
    import os
    log_path = os.path.abspath("backend.log")
    try:
        size = os.path.getsize(log_path)
        with open(log_path, "rb") as f:
            if size > tail:
                f.seek(-tail, os.SEEK_END)
            content = f.read().decode(errors="replace")
    except Exception:
        content = ""
    return {"logs": content}


# GET /api/ai-engine/models
@router.get("/models", response_model=List[Dict[str, Any]])
async def list_models(
    config: AIEngineConfigService = Depends(get_ai_engine_config)
):
    """
    List all configured AI models.
    
    Includes provider, name, default status, and API key status for each model.
    """
    return config.list_available_models()

# POST /api/ai-engine/test-connection
@router.post("/test-connection")
async def test_model_connection(
    request: TestConnectionRequest,
    config: AIEngineConfigService = Depends(get_ai_engine_config)
):
    """
    Test connection to a specific AI model.
    
    Returns success status and message with connection details.
    """
    result = config.test_connection(request.model_id)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    
    return result

# POST /api/ai-engine/set-default
@router.post("/set-default")
async def set_default_model(
    request: SetDefaultModelRequest,
    config: AIEngineConfigService = Depends(get_ai_engine_config)
):
    """
    Set the default AI model for the engine.
    
    This model will be used for all AI operations unless explicitly overridden.
    """
    try:
        config.set_default_model(request.model_id)
        return {"success": True, "message": f"Default model set to {request.model_id}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# POST /api/ai-engine/set-api-key
@router.post("/set-api-key")
async def set_api_key(
    request: SetApiKeyRequest,
    config: AIEngineConfigService = Depends(get_ai_engine_config)
):
    """
    Set API key for a specific model.
    
    The key is stored in the environment variable associated with the model.
    For production, use a secure secrets manager.
    """
    try:
        config.set_api_key(request.model_id, request.api_key)
        return {"success": True, "message": f"API key set for {request.model_id}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# POST /api/ai-engine/set-provider-api-key
class SetProviderApiKeyRequest(BaseModel):
    provider_id: str = Field(..., description="Provider identifier (e.g., 'nvidia_nim')")
    api_key: str = Field(..., description="API key to set for all models of this provider")

@router.post("/set-provider-api-key")
async def set_provider_api_key(
    request: SetProviderApiKeyRequest,
    config: AIEngineConfigService = Depends(get_ai_engine_config)
):
    """
    Set a single API key for all models belonging to a provider.
    This updates the environment variable used by each model (or creates a default one).
    """
    # Normalize provider identifiers to match AIProvider enum values.
    # Accept common aliases like "nvidia", "nvidia_nim", "google", "google_gemma", etc.
    normalized = request.provider_id.lower().replace("-", "_")
    alias_map = {
        "nvidia": "nvidia_nim",
        "nvidia_nim": "nvidia_nim",
        "google": "google_gemma",
        "google_gemma": "google_gemma",
        "ibm": "ibm_bob",
        "ibm_bob": "ibm_bob",
        "ollama": "ollama",
        "openai": "openai",
        "anthropic": "anthropic",
    }
    provider_key = alias_map.get(normalized)
    if not provider_key:
        raise HTTPException(status_code=400, detail=f"Unknown provider '{request.provider_id}'")
    try:
        config.set_provider_api_key(provider_key, request.api_key)
        return {"success": True, "message": f"API key set for provider {provider_key}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
# POST /api/ai-engine/add-model
@router.post("/add-model")
async def add_model(
    request: ModelConfigRequest,
    config: AIEngineConfigService = Depends(get_ai_engine_config)
):
    """
    Add a new AI model configuration.
    
    Supports custom models from any provider (Ollama, IBM Bob, Google Gemma, NVIDIA NIM).
    You can customize the environment variable name for API keys.
    """
    try:
        # Map string provider to enum
        provider = AIProvider(request.provider)
        
        # Use custom api_key_env or generate default
        api_key_env = request.api_key_env
        if not api_key_env and provider != AIProvider.OLLAMA:
            api_key_env = f"{provider.value.upper()}_API_KEY"
        
        model_config = ModelConfig(
            model_id=request.model_id,
            name=request.name,
            provider=provider,
            endpoint_url=request.endpoint_url,
            api_key_env=api_key_env,
            context_window=request.context_window,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            provider_config=request.provider_config,
            config_note=request.config_note
        )
        
        config.add_model(model_config)
        return {"success": True, "message": f"Model added: {request.model_id}", "api_key_env": api_key_env}
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# PUT /api/ai-engine/update-model
@router.put("/update-model")
async def update_model(
    request: UpdateModelRequest,
    config: AIEngineConfigService = Depends(get_ai_engine_config)
):
    """
    Update an existing AI model configuration.
    
    Allows you to change the environment variable name, endpoint, and other settings.
    """
    try:
        updates = {
            "name": request.name,
            "endpoint_url": request.endpoint_url,
            "api_key_env": request.api_key_env,
            "context_window": request.context_window,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "provider_config": request.provider_config,
            "config_note": request.config_note
        }
        
        updated_model = config.update_model(request.model_id, updates)
        
        return {
            "success": True, 
            "message": f"Model updated: {request.model_id}",
            "api_key_env": updated_model.api_key_env,
            "config_note": updated_model.config_note
        }
    
    except AIEngineConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# DELETE /api/ai-engine/remove-model/{model_id}
@router.delete("/remove-model/{model_id}")
async def remove_model(
    model_id: str,
    config: AIEngineConfigService = Depends(get_ai_engine_config)
):
    """
    Remove a model configuration.
    
    Note: Cannot remove the default model. Change default first.
    """
    try:
        if model_id == config.config.default_model_id:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove default model. Set a different default first."
            )
        
        config.remove_model(model_id)
        return {"success": True, "message": f"Model removed: {model_id}"}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# POST /api/ai-engine/update-settings
@router.post("/update-settings")
async def update_engine_settings(
    request: UpdateConfigRequest,
    config: AIEngineConfigService = Depends(get_ai_engine_config)
):
    """
    Update AI engine global settings.
    
    Configure timeout, retries, fallback behavior, and caching.
    """
    if request.timeout_seconds is not None:
        config.config.timeout_seconds = request.timeout_seconds
    if request.max_retries is not None:
        config.config.max_retries = request.max_retries
    if request.enable_fallback is not None:
        config.config.enable_fallback = request.enable_fallback
    if request.enable_caching is not None:
        config.config.enable_caching = request.enable_caching
    
    config.save_config()
    
    return {"success": True, "message": "Settings updated"}

# GET /api/ai-engine/providers
@router.get("/providers")
async def list_providers():
    """
    List all supported AI providers.
    
    Returns provider names and their supported features.
    """
    providers = [
        {
            "id": "ollama",
            "name": "Ollama",
            "description": "Local LLM server",
            "requires_api_key": False,
            "features": ["text", "completion", "local"]
        },
        {
            "id": "nvidia_nim",
            "name": "NVIDIA NIM",
            "description": "NVIDIA Inference Microservices",
            "requires_api_key": True,
            "features": ["text", "completion", "chat"]
        },
        {
            "id": "google_gemma",
            "name": "Google Gemma",
            "description": "Google Gemma models via Generative Language API",
            "requires_api_key": True,
            "features": ["text", "completion", "chat"]
        },
        {
            "id": "ibm_bob",
            "name": "IBM Bob",
            "description": "IBM Bob AI platform",
            "requires_api_key": True,
            "features": ["text", "completion"]
        },
        {
            "id": "openai",
            "name": "OpenAI",
            "description": "OpenAI GPT models",
            "requires_api_key": True,
            "features": ["text", "completion", "chat", "vision"]
        },
        {
            "id": "anthropic",
            "name": "Anthropic",
            "description": "Anthropic Claude models",
            "requires_api_key": True,
            "features": ["text", "completion", "chat"]
        }
    ]
    
    return {"providers": providers}