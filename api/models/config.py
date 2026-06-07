from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
from enum import Enum
from datetime import datetime

class AIProvider(str, Enum):
    OLLAMA = "ollama"
    IBM_BOB = "ibm_bob"
    GOOGLE_GEMMA = "google_gemma"
    NVIDIA_NIM = "nvidia_nim"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"

class ModelConfig(BaseModel):
    """Configuration for a specific AI model"""
    model_id: str
    provider: AIProvider
    name: str
    endpoint_url: Optional[str] = None  # Custom endpoint if needed
    api_key_env: Optional[str] = None  # Environment variable name for API key (optional, user-customizable)
    context_window: int = 4096
    temperature: float = 0.7
    max_tokens: int = 2048
    supported_features: list = Field(default_factory=lambda: ["text", "completion"])
    
    # Provider-specific settings
    provider_config: Dict[str, Any] = Field(default_factory=dict)
    
    # Documentation
    config_note: Optional[str] = None  # User notes about this model's configuration

class AIEngineConfig(BaseModel):
    """Global AI engine configuration"""
    default_provider: AIProvider = AIProvider.OLLAMA
    default_model_id: str = "llama3.1"
    
    # Model configurations
    models: Dict[str, ModelConfig] = Field(default_factory=dict)
    
    # Connection settings
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: int = 2
    
    # Fallback behavior
    enable_fallback: bool = True
    fallback_order: list = Field(default_factory=lambda: [
        AIProvider.OLLAMA,
        AIProvider.NVIDIA_NIM,
        AIProvider.GOOGLE_GEMMA,
        AIProvider.IBM_BOB
    ])
    
    # Caching
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600
    
    # Logging
    log_level: str = "INFO"
    log_requests: bool = False
    log_responses: bool = False

    version: str = "1.0.0"
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# Pre-configured models for common providers
PRECONFIGURED_MODELS = {
    # Ollama models
    "llama3.1": ModelConfig(
        model_id="llama3.1",
        provider=AIProvider.OLLAMA,
        name="Llama 3.1 (Ollama)",
        endpoint_url="http://localhost:11434",
        api_key_env=None,  # Ollama doesn't require API key by default
        context_window=8192,
        provider_config={"base_url": "http://localhost:11434/api/generate"},
        config_note="Ollama runs locally. No API key needed by default. Set OLLAMA_API_KEY if your instance requires auth."
    ),
    "codellama": ModelConfig(
        model_id="codellama",
        provider=AIProvider.OLLAMA,
        name="CodeLlama (Ollama)",
        endpoint_url="http://localhost:11434",
        api_key_env=None,
        context_window=4096,
        provider_config={"base_url": "http://localhost:11434/api/generate"},
        config_note="Ollama local model. No API key required."
    ),
    "mistral": ModelConfig(
        model_id="mistral",
        provider=AIProvider.OLLAMA,
        name="Mistral (Ollama)",
        endpoint_url="http://localhost:11434",
        api_key_env=None,
        context_window=8192,
        provider_config={"base_url": "http://localhost:11434/api/generate"},
        config_note="Ollama local model. No API key required."
    ),
    
    # NVIDIA NIM models
    "nvidia-nemotron": ModelConfig(
        model_id="meta/llama-3.1-405b-instruct",
        provider=AIProvider.NVIDIA_NIM,
        name="NVIDIA Nemotron-3",
        endpoint_url="https://integrate.api.nvidia.com/v1",
        api_key_env="NVIDIA_API_KEY",
        context_window=128000,
        provider_config={"base_url": "https://integrate.api.nvidia.com/v1"},
        config_note="Set NVIDIA_API_KEY in your shell or .env file. Default: ~/.antikythera/vault"
    ),
    "nvidia-llama3": ModelConfig(
        model_id="meta/llama3-70b-instruct",
        provider=AIProvider.NVIDIA_NIM,
        name="NVIDIA Llama 3",
        endpoint_url="https://integrate.api.nvidia.com/v1",
        api_key_env="NVIDIA_API_KEY",
        context_window=8192,
        provider_config={"base_url": "https://integrate.api.nvidia.com/v1"},
        config_note="Set NVIDIA_API_KEY in your shell or .env file. Default: ~/.antikythera/vault"
    ),
    
    # IBM Bob models
    "ibm-granite": ModelConfig(
        model_id="ibm/granite-13b-instruct",
        provider=AIProvider.IBM_BOB,
        name="IBM Granite",
        endpoint_url="https://bob-api.cloud.ibm.com",
        api_key_env="IBM_BOB_API_KEY",
        context_window=8192,
        provider_config={"base_url": "https://bob-api.cloud.ibm.com/v1"},
        config_note="Set IBM_BOB_API_KEY. You can customize this env var name in model settings."
    ),
    
    # Google Gemma models
    "google-gemma-7b": ModelConfig(
        model_id="google/gemma-7b-it",
        provider=AIProvider.GOOGLE_GEMMA,
        name="Google Gemma 7B",
        endpoint_url="https://generativelanguage.googleapis.com",
        api_key_env="GOOGLE_API_KEY",
        context_window=8192,
        provider_config={"base_url": "https://generativelanguage.googleapis.com/v1beta"},
        config_note="Set GOOGLE_API_KEY. You can customize this env var name in model settings."
    ),
    "google-gemma-2b": ModelConfig(
        model_id="google/gemma-2b-it",
        provider=AIProvider.GOOGLE_GEMMA,
        name="Google Gemma 2B",
        endpoint_url="https://generativelanguage.googleapis.com",
        api_key_env="GOOGLE_API_KEY",
        context_window=2048,
        provider_config={"base_url": "https://generativelanguage.googleapis.com/v1beta"},
        config_note="Set GOOGLE_API_KEY. You can customize this env var name in model settings."
    )
}

# Create default config with pre-configured models
DEFAULT_AI_ENGINE_CONFIG = AIEngineConfig(
    default_provider=AIProvider.OLLAMA,
    default_model_id="llama3.1",
    models=PRECONFIGURED_MODELS,
    enable_fallback=True,
    enable_caching=True
)