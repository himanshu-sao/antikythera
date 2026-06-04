"""
AI Engine Configuration Service

Manages AI model configurations, API keys, and connection settings for multiple providers:
- Ollama (local)
- IBM Bob
- Google Gemma
- NVIDIA NIM
- OpenAI
- Anthropic
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime

from ..models.config import (
    AIEngineConfig, 
    ModelConfig, 
    AIProvider,
    DEFAULT_AI_ENGINE_CONFIG
)

logger = logging.getLogger(__name__)

class AIEngineConfigError(Exception):
    """Custom exception for AI engine configuration errors"""
    pass

class AIEngineConfigService:
    """
    Service for managing AI engine configurations.
    
    Features:
    - Load/save config from file
    - Manage API keys via environment variables
    - Validate model connectivity
    - Switch between providers
    - Test model availability
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.config: AIEngineConfig = self.load_config()
    
    def _get_default_config_path(self) -> str:
        """Get default config file path"""
        home = Path.home()
        antikythera_dir = home / ".antikythera"
        antikythera_dir.mkdir(exist_ok=True)
        return str(antikythera_dir / "ai_config.json")
    
    def load_config(self) -> AIEngineConfig:
        """Load configuration from file"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                
                # Convert to Pydantic model
                config = AIEngineConfig(**data)
                logger.info(f"Loaded AI config from {self.config_path}")
                return config
            except Exception as e:
                logger.warning(f"Failed to load config: {e}, using defaults")
                return DEFAULT_AI_ENGINE_CONFIG
        else:
            logger.info("No config found, using defaults")
            return DEFAULT_AI_ENGINE_CONFIG
    
    def save_config(self) -> None:
        """Save current configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                # Convert Pydantic model to dict, excluding datetime for JSON compatibility
                data = self.config.model_dump()
                data['updated_at'] = datetime.utcnow().isoformat()
                json.dump(data, f, indent=2, default=str)
            
            logger.info(f"Saved AI config to {self.config_path}")
        except Exception as e:
            raise AIEngineConfigError(f"Failed to save config: {e}")
    
    def get_model_config(self, model_id: str) -> Optional[ModelConfig]:
        """Get configuration for a specific model"""
        return self.config.models.get(model_id)
    
    def set_default_model(self, model_id: str) -> None:
        """Set default model for AI engine"""
        if model_id not in self.config.models:
            raise AIEngineConfigError(f"Model '{model_id}' not found in configurations")
        
        model_config = self.config.models[model_id]
        self.config.default_provider = model_config.provider
        self.config.default_model_id = model_id
        self.config.updated_at = datetime.utcnow()
        self.save_config()
        logger.info(f"Set default model to {model_id}")
    
    def add_model(self, model_config: ModelConfig) -> None:
        """Add a new model configuration"""
        self.config.models[model_config.model_id] = model_config
        self.config.updated_at = datetime.utcnow()
        self.save_config()
        logger.info(f"Added model: {model_config.model_id}")
    
    def remove_model(self, model_id: str) -> None:
        """Remove a model configuration"""
        if model_id in self.config.models:
            del self.config.models[model_id]
            self.config.updated_at = datetime.utcnow()
            self.save_config()
            logger.info(f"Removed model: {model_id}")
    
    def set_api_key(self, model_id: str, api_key: str) -> None:
        """
        Set API key for a model by updating environment variable.
        
        Note: In production, use a secure secrets manager instead of env vars.
        """
        model_config = self.get_model_config(model_id)
        if not model_config:
            raise AIEngineConfigError(f"Model '{model_id}' not found")
        
        env_var = model_config.api_key_env
        os.environ[env_var] = api_key
        logger.info(f"Set API key for {model_id} in environment")
    
    def get_api_key(self, model_id: str) -> Optional[str]:
        """Get API key for a model from environment"""
        model_config = self.get_model_config(model_id)
        if not model_config:
            return None
        
        return os.environ.get(model_config.api_key_env)
    
    def test_connection(self, model_id: str) -> Dict[str, Any]:
        """
        Test connection to a model.
        
        Returns:
            Dict with 'success', 'message', and optional 'details'
        """
        model_config = self.get_model_config(model_id)
        if not model_config:
            return {
                "success": False,
                "message": f"Model '{model_id}' not configured"
            }
        
        try:
            # Check if API key is set
            api_key = self.get_api_key(model_id)
            if model_config.provider in [AIProvider.IBM_BOB, AIProvider.GOOGLE_GEMMA, AIProvider.NVIDIA_NIM] and not api_key:
                return {
                    "success": False,
                    "message": f"API key not set. Set environment variable: {model_config.api_key_env}"
                }
            
            # Test based on provider
            if model_config.provider == AIProvider.OLLAMA:
                return self._test_ollama(model_config)
            elif model_config.provider == AIProvider.NVIDIA_NIM:
                return self._test_nvidia_nim(model_config)
            elif model_config.provider == AIProvider.GOOGLE_GEMMA:
                return self._test_google_gemma(model_config)
            elif model_config.provider == AIProvider.IBM_BOB:
                return self._test_ibm_bob(model_config)
            else:
                return {
                    "success": True,
                    "message": f"Connection test not implemented for {model_config.provider.value}"
                }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Connection test failed: {str(e)}"
            }
    
    def _test_ollama(self, model_config: ModelConfig) -> Dict[str, Any]:
        """Test Ollama connection"""
        import httpx
        
        try:
            url = f"{model_config.provider_config.get('base_url', 'http://localhost:11434')}/api/tags"
            
            with httpx.Client(timeout=5) as client:
                response = client.get(url)
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "Ollama connection successful",
                    "details": {"endpoint": model_config.endpoint_url}
                }
            else:
                return {
                    "success": False,
                    "message": f"Ollama returned status {response.status_code}"
                }
        
        except httpx.ConnectError:
            return {
                "success": False,
                "message": "Cannot connect to Ollama. Ensure it's running on localhost:11434"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Ollama test failed: {str(e)}"
            }
    
    def _test_nvidia_nim(self, model_config: ModelConfig) -> Dict[str, Any]:
        """Test NVIDIA NIM connection"""
        import httpx
        import os
        
        api_key = os.environ.get(model_config.api_key_env)
        if not api_key:
            return {
                "success": False,
                "message": f"NVIDIA API key not set. Set {model_config.api_key_env}"
            }
        
        try:
            url = f"{model_config.provider_config.get('base_url', 'https://integrate.api.nvidia.com/v1')}/v1/models"
            
            with httpx.Client(timeout=10) as client:
                response = client.get(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"}
                )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "NVIDIA NIM connection successful",
                    "details": {"endpoint": model_config.endpoint_url}
                }
            else:
                return {
                    "success": False,
                    "message": f"NVIDIA NIM returned status {response.status_code}: {response.text[:100]}"
                }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"NVIDIA NIM test failed: {str(e)}"
            }
    
    def _test_google_gemma(self, model_config: ModelConfig) -> Dict[str, Any]:
        """Test Google Gemma connection"""
        import httpx
        import os
        
        api_key = os.environ.get(model_config.api_key_env)
        if not api_key:
            return {
                "success": False,
                "message": f"Google API key not set. Set {model_config.api_key_env}"
            }
        
        try:
            url = f"{model_config.provider_config.get('base_url', 'https://generativelanguage.googleapis.com')}/v1beta/models"
            
            auth_header = f"?key={api_key}"
            
            with httpx.Client(timeout=10) as client:
                response = client.get(url + auth_header)
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "Google Gemma connection successful",
                    "details": {"endpoint": model_config.endpoint_url}
                }
            else:
                return {
                    "success": False,
                    "message": f"Google Gemma returned status {response.status_code}"
                }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Google Gemma test failed: {str(e)}"
            }
    
    def _test_ibm_bob(self, model_config: ModelConfig) -> Dict[str, Any]:
        """Test IBM Bob connection"""
        import httpx
        import os
        
        api_key = os.environ.get(model_config.api_key_env)
        if not api_key:
            return {
                "success": False,
                "message": f"IBM Bob API key not set. Set {model_config.api_key_env}"
            }
        
        try:
            # IBM Bob typically uses a models endpoint
            url = f"{model_config.provider_config.get('base_url', 'https://bob-api.cloud.ibm.com')}/v1/models"
            
            with httpx.Client(timeout=10) as client:
                response = client.get(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"}
                )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "IBM Bob connection successful",
                    "details": {"endpoint": model_config.endpoint_url}
                }
            else:
                return {
                    "success": False,
                    "message": f"IBM Bob returned status {response.status_code}"
                }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"IBM Bob test failed: {str(e)}"
            }
    
    def list_available_models(self) -> List[Dict[str, Any]]:
        """List all configured models with their status"""
        models = []
        
        for model_id, config in self.config.models.items():
            is_default = model_id == self.config.default_model_id
            api_key_set = bool(self.get_api_key(model_id)) if config.provider != AIProvider.OLLAMA else True
            
            models.append({
                "model_id": model_id,
                "name": config.name,
                "provider": config.provider.value,
                "is_default": is_default,
                "api_key_set": api_key_set,
                "endpoint": config.endpoint_url,
                "context_window": config.context_window
            })
        
        return models
    
    def get_config_for_ui(self) -> Dict[str, Any]:
        """Get configuration in a format suitable for UI display"""
        return {
            "default_provider": self.config.default_provider.value,
            "default_model_id": self.config.default_model_id,
            "models": self.list_available_models(),
            "connection_settings": {
                "timeout_seconds": self.config.timeout_seconds,
                "max_retries": self.config.max_retries,
                "enable_fallback": self.config.enable_fallback,
                "enable_caching": self.config.enable_caching
            }
        }


# Global instance
_ai_engine_config_service: Optional[AIEngineConfigService] = None

def get_ai_engine_config() -> AIEngineConfigService:
    """Get or create the global AI engine config service"""
    global _ai_engine_config_service
    if _ai_engine_config_service is None:
        _ai_engine_config_service = AIEngineConfigService()
    return _ai_engine_config_service