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
        # Load any persisted provider API keys from ~/.antikythera/.ai_env
        self._load_persistent_env()
    
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
        # Persist the updated key to the ~/.antikythera/.ai_env file
        self._write_persistent_env()

    def set_provider_api_key(self, provider_id: str, api_key: str) -> None:
        """Set a single API key for *all* models belonging to ``provider_id``.

        The function updates the environment variable referenced by each model's
        ``api_key_env`` (or falls back to the conventional ``<PROVIDER>_API_KEY``
        name if none is defined). This enables the UI to present a single input
        field under the Providers tab while still allowing per‑model overrides
        via the existing ``/set-api-key`` endpoint.
        """
        # Normalize provider identifier to match AIProvider enum values (allow aliases)
        normalized = provider_id.lower().replace("-", "_")
        alias_map = {
            "nvidia": "nvidia_nim",
            "nvidia_nim": "nvidia_nim",
            "google": "google_gemma",
            "google_gemma": "google_gemma",
            "ibm": "ibm_bob",
            "ibm_bob": "ibm_bob",
            "ollama": "ollama",
            "openai": "openai",
            "openrouter": "openrouter",
        }
        normalized_key = alias_map.get(normalized)
        if not normalized_key:
            raise AIEngineConfigError(f"Invalid provider '{provider_id}'")
        try:
            provider_enum = AIProvider(normalized_key)
        except ValueError as exc:
            raise AIEngineConfigError(f"Invalid provider '{provider_id}'") from exc

        for model_cfg in self.config.models.values():
            if model_cfg.provider != provider_enum:
                continue
            # Determine which env var to use
            env_var = model_cfg.api_key_env or f"{provider_enum.value.split('_')[0].upper()}_API_KEY"
            # Update model config to store the env var name if it was missing
            if not model_cfg.api_key_env:
                # Mutate the stored config to remember the env var name for UI
                model_cfg.api_key_env = env_var
            os.environ[env_var] = api_key
            logger.info(f"Set provider API key for {provider_id} (model {model_cfg.model_id}) via {env_var}")
        # Persist all provider keys to the env file so they survive restarts
        self._write_persistent_env()
    
    def get_api_key(self, model_id: str) -> Optional[str]:
        """Get API key for a model from environment"""
        model_config = self.get_model_config(model_id)
        if not model_config:
            return None
        if not model_config.api_key_env:
            return None
        
        return os.environ.get(model_config.api_key_env)
    
    def update_model(self, model_id: str, updates: Dict[str, Any]) -> ModelConfig:
        """Update model configuration with provided fields"""
        if model_id not in self.config.models:
            raise AIEngineConfigError(f"Model '{model_id}' not found")
        
        existing = self.config.models[model_id]
        
        # Update only provided fields
        update_data = {k: v for k, v in updates.items() if v is not None}
        updated = existing.model_copy(update=update_data)
        
        self.config.models[model_id] = updated
        self.config.updated_at = datetime.utcnow()
        self.save_config()
        
        logger.info(f"Updated model: {model_id}")
        return updated
    
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
            # Check if API key is set (only if api_key_env is defined)
            api_key = self.get_api_key(model_id)
            # ibm_bob is CLI-based — bob manages its own auth, so no API key is required.
            needs_api_key = model_config.provider in [AIProvider.GOOGLE_GEMMA, AIProvider.NVIDIA_NIM]
            if needs_api_key and model_config.api_key_env and not api_key:
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
            # Use base URL without /api/generate suffix
            base_url = model_config.endpoint_url or "http://localhost:11434"
            # Remove trailing /api/generate if present
            if "/api/generate" in base_url:
                base_url = base_url.replace("/api/generate", "")
            if base_url.endswith("/"):
                base_url = base_url.rstrip("/")
            
            url = f"{base_url}/api/tags"
            
            with httpx.Client(timeout=5) as client:
                response = client.get(url)
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "Ollama connection successful",
                    "details": {"endpoint": base_url}
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
                "message": f"NVIDIA API key not set. Set environment variable: {model_config.api_key_env or 'NVIDIA_API_KEY'}"
            }
        
        try:
            base_url = model_config.provider_config.get('base_url', 'https://integrate.api.nvidia.com/v1')
            # Remove trailing /v1 if present to avoid duplication
            if base_url.endswith("/v1"):
                base_url = base_url[:-3]
            if base_url.endswith("/"):
                base_url = base_url.rstrip("/")
            
            url = f"{base_url}/v1/models"
            
            with httpx.Client(timeout=10) as client:
                response = client.get(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"}
                )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "NVIDIA NIM connection successful",
                    "details": {"endpoint": base_url, "api_key_env": model_config.api_key_env}
                }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "message": f"Invalid API key. Check {model_config.api_key_env or 'NVIDIA_API_KEY'}"
                }
            else:
                return {
                    "success": False,
                    "message": f"NVIDIA NIM returned status {response.status_code}: {response.text[:200]}"
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
            base_url = model_config.provider_config.get('base_url', 'https://generativelanguage.googleapis.com')
            # Remove trailing slash if present
            if base_url.endswith("/"):
                base_url = base_url.rstrip("/")
            
            # Google API uses query parameter for API key
            url = f"{base_url}/v1beta/models?key={api_key}"
            
            with httpx.Client(timeout=10) as client:
                response = client.get(url)
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "Google Gemma connection successful",
                    "details": {"endpoint": base_url}
                }
            else:
                return {
                    "success": False,
                    "message": f"Google Gemma returned status {response.status_code}: {response.text[:100]}"
                }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Google Gemma test failed: {str(e)}"
            }
    
    def _test_ibm_bob(self, model_config: ModelConfig) -> Dict[str, Any]:
        """Test IBM Bob connectivity via the local ``bob`` CLI binary.

        ``ibm_bob`` is a *CLI-based* provider (see CLAUDE.md gotcha #10): there is
        no HTTP endpoint to probe. The ``bob`` binary manages its own auth
        (first-run browser SSO, cached credentials valid ~24 hours), so this
        smoke test just shells out a trivial "ping" prompt and checks the exit
        code. No API key is inspected.

        Flags mirror ``LLMClient._chat_bob`` (verified against ``bob --help``
        on v1.0.6): ``--chat-mode ask`` for a plain Q&A, ``--allowed-mcp-server-
        names ""`` to skip MCP-server discovery at startup, ``--hide-intermediary-
        output`` and ``-o text`` for a clean stdout, ``-m`` only when a model id
        is configured (a fabricated id crashes the binary).
        """
        import subprocess

        command = ["bob", "--chat-mode", "ask",
                   "--allowed-mcp-server-names", "",
                   "--hide-intermediary-output", "-o", "text"]
        if model_config.model_id:
            command += ["-m", model_config.model_id]
        command += ["-p", "ping"]

        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                check=False,
            )
        except FileNotFoundError:
            return {
                "success": False,
                "message": "bob CLI not found on PATH — install the bob binary and retry",
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": "bob CLI test timed out (30s) — check first-run browser SSO auth",
            }

        if result.returncode == 0:
            return {
                "success": True,
                "message": "IBM Bob connection successful (bob CLI responsive)",
                "details": {"model_id": model_config.model_id},
            }
        return {
            "success": False,
            "message": f"bob CLI exited {result.returncode}: {result.stderr.strip() or result.stdout.strip()}",
        }

    # ---------------------------------------------------------------------
    # Model discovery helpers (real provider calls)
    # ---------------------------------------------------------------------
    def _list_ollama_models(self, model_cfg: ModelConfig) -> List[str]:
        """Query a running Ollama instance for its available model names.
+
+        Ollama exposes ``/api/tags`` which returns a JSON object containing a
+        ``models`` array with each entry having a ``name`` field.
+        """
        import httpx
        base_url = model_cfg.endpoint_url or "http://localhost:11434"
        # Normalise – remove any trailing ``/api/generate`` and trailing slash
        if "/api/generate" in base_url:
            base_url = base_url.replace("/api/generate", "")
        base_url = base_url.rstrip("/")
        try:
            resp = httpx.get(f"{base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            return [m.get("name") for m in data.get("models", []) if m.get("name")]
        except Exception as exc:
            raise AIEngineConfigError(f"Failed to list Ollama models: {exc}")

    def _list_nvidia_nim_models(self, model_cfg: ModelConfig) -> List[str]:
        """Query NVIDIA NIM for its model catalogue.
+
+        The service uses the ``/v1/models`` endpoint with a Bearer token.
+        The response shape is ``{"data": [{"id": "..."}, ...]}``.
+        """
        import httpx
        api_key = os.getenv(model_cfg.api_key_env or "")
        if not api_key:
            raise AIEngineConfigError(
                f"NVIDIA API key not set. Set env var {model_cfg.api_key_env or 'NVIDIA_API_KEY'}"
            )
        base = model_cfg.provider_config.get("base_url", "https://integrate.api.nvidia.com/v1")
        # Remove trailing ``/v1`` if present to avoid duplication
        if base.endswith("/v1"):
            base = base[:-3]
        base = base.rstrip("/")
        try:
            resp = httpx.get(
                f"{base}/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return [m.get("id") for m in data.get("data", []) if m.get("id")]
        except Exception as exc:
            raise AIEngineConfigError(f"Failed to list NVIDIA NIM models: {exc}")

    def _list_google_gemma_models(self, model_cfg: ModelConfig) -> List[str]:
        """Query Google Gemma (Generative Language API) for available models.
+
+        The public endpoint ``/v1beta/models`` returns a list of model names in the
+        form ``models/gemma-7b``. We strip the prefix and return just the short name.
+        """
        import httpx
        api_key = os.getenv(model_cfg.api_key_env or "")
        if not api_key:
            raise AIEngineConfigError(
                f"Google API key not set. Set env var {model_cfg.api_key_env}"
            )
        base = model_cfg.provider_config.get(
            "base_url", "https://generativelanguage.googleapis.com"
        ).rstrip("/")
        try:
            resp = httpx.get(
                f"{base}/v1beta/models?key={api_key}", timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            return [m.get("name", "").split("/")[-1] for m in data.get("models", [])]
        except Exception as exc:
            raise AIEngineConfigError(f"Failed to list Google Gemma models: {exc}")

    def _list_ibm_bob_models(self, model_cfg: ModelConfig) -> List[str]:
        """Return the statically-configured ``ibm_bob`` model id(s).

        ``ibm_bob`` is a *CLI-based* provider (see CLAUDE.md gotcha #10): the
        ``bob`` binary has no ``--list-models`` command (confirmed via
        ``bob --help``), and no HTTP model-catalogue endpoint. So unlike the
        HTTP providers, the only "available model" we can report is the one
        configured in ``ai_config.json`` itself. We return it as a single-element
        list so the public ``list_provider_models`` contract (``List[str]``) is
        preserved and the UI can show it.
        """
        if model_cfg.model_id:
            return [model_cfg.model_id]
        raise AIEngineConfigError(
            "No ibm_bob model_id configured — set a model_id in ai_config.json"
        )

    def _list_lm_studio_models(self, model_cfg: ModelConfig) -> List[str]:
        """Query a running LM Studio instance for its model list.
        LM Studio provides an OpenAI‑compatible ``/v1/models`` endpoint.
        """
        import httpx
        base_url = model_cfg.endpoint_url or "http://127.0.0.1:1234"
        base_url = base_url.rstrip('/')
        try:
            resp = httpx.get(f"{base_url}/v1/models", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            # OpenAI format: {"data": [{"id": "model-name"}, ...]}
            return [m.get("id") for m in data.get("data", []) if m.get("id")]
        except Exception as exc:
            raise AIEngineConfigError(f"Failed to list LM Studio models: {exc}")

    def list_provider_models(self, provider: AIProvider) -> List[str]:
        """Public helper used by the API router to obtain a *live* model list.
+
+        It picks the first configured model for the requested provider to obtain
+        the endpoint URL and any required API‑key environment variable. If there
+        is no config for that provider, an ``AIEngineConfigError`` is raised.
+        """
        # Find any model configuration that matches the provider
        cfg = next((c for c in self.config.models.values() if c.provider == provider), None)
        if cfg is None:
            raise AIEngineConfigError(f"No configuration found for provider '{provider.value}'")

        if provider == AIProvider.OLLAMA:
            return self._list_ollama_models(cfg)
        if provider == AIProvider.NVIDIA_NIM:
            return self._list_nvidia_nim_models(cfg)
        if provider == AIProvider.GOOGLE_GEMMA:
            return self._list_google_gemma_models(cfg)
        if provider == AIProvider.IBM_BOB:
            return self._list_ibm_bob_models(cfg)
        if provider == AIProvider.LM_STUDIO:
            return self._list_lm_studio_models(cfg)
        # For providers without a list‑models implementation we fall back to the static placeholder
        raise AIEngineConfigError(f"Model listing not implemented for provider '{provider.value}'")

    def list_available_models(self) -> List[Dict[str, Any]]:
        """List all configured models with their status (used by UI config view)."""
        models: List[Dict[str, Any]] = []
        for model_id, cfg in self.config.models.items():
            is_default = model_id == self.config.default_model_id
            # ibm_bob is CLI-based — bob manages its own auth, so no API key is required.
            needs_key = cfg.provider in [AIProvider.GOOGLE_GEMMA, AIProvider.NVIDIA_NIM]
            api_key_set = False
            if cfg.api_key_env:
                api_key_set = bool(self.get_api_key(model_id))
            elif not needs_key:
                api_key_set = True
            model_info = {
                "model_id": model_id,
                "name": cfg.name,
                "provider": cfg.provider.value,
                "is_default": is_default,
                "api_key_set": api_key_set,
                "endpoint": cfg.endpoint_url,
                "context_window": cfg.context_window,
                "api_key_env": cfg.api_key_env,
                "config_note": cfg.config_note,
            }
            models.append(model_info)
        return models

    def get_config_for_ui(self) -> Dict[str, Any]:
        """Get configuration in a format suitable for UI display."""
        return {
            "default_provider": self.config.default_provider.value,
            "default_model_id": self.config.default_model_id,
            "models": self.list_available_models(),
            "connection_settings": {
                "timeout_seconds": self.config.timeout_seconds,
                "max_retries": self.config.max_retries,
                "enable_fallback": self.config.enable_fallback,
                "enable_caching": self.config.enable_caching,
            },
        }


    # ---------------------------------------------------------------------
    # Persistent env handling (~/\.antikythera/.ai_env)
    # ---------------------------------------------------------------------
    def _persistent_env_path(self) -> str:
        """Return the path to the persisted env file used by Antikythera.

        The file is deliberately placed under the **real** user's home directory so it
        survives a container or VM restart but remains outside the project
        source tree. We resolve the true home directory via the password database
        rather than the potentially overridden ``HOME`` environment variable (which
        may point to an Antikythera profile directory).
        """
        try:
            import pwd
            real_home = pwd.getpwuid(os.getuid()).pw_dir
        except Exception:
            # Fallback to Path.home() if pwd lookup fails (e.g., on non‑POSIX).
            real_home = str(Path.home())
        antikythera_dir = Path(real_home) / ".antikythera"
        antikythera_dir.mkdir(exist_ok=True)
        return str(antikythera_dir / ".ai_env")

    def _load_persistent_env(self) -> None:
        """Load key‑value pairs from ``~/.antikythera/.ai_env`` into ``os.environ``.

        The file follows a simple ``KEY=VALUE`` syntax, optionally quoting the
        value with single or double quotes. Lines starting with ``#`` are ignored.
        Missing file is treated as no persisted keys.
        """
        env_path = self._persistent_env_path()
        if not os.path.exists(env_path):
            return
        try:
            with open(env_path, "r") as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    # Strip surrounding quotes if present
                    if (val.startswith('"') and val.endswith('"')) or (
                        val.startswith("'") and val.endswith("'")
                    ):
                        val = val[1:-1]
                    os.environ[key] = val
        except Exception as e:
            logger.warning(f"Failed to load persistent env from {env_path}: {e}")

    def _write_persistent_env(self) -> None:
        """Write all provider‑related env vars currently in ``os.environ`` to the
        persistent file.

        Only keys that match known provider prefixes (e.g. ``NVIDIA_``, ``GOOGLE_``,
        ``IBM_BOB_``, ``OPENAI_``, ``ANTHROPIC_``, ``OLLAMA_``) are persisted. This
        avoids leaking unrelated environment variables.
        """
        env_path = self._persistent_env_path()
        provider_prefixes = ["NVIDIA_", "GOOGLE_", "IBM_BOB_", "OPENAI_", "ANTHROPIC_", "OLLAMA_", "OPENROUTER_"]
        lines: List[str] = []
        for key, val in os.environ.items():
            if any(key.startswith(p) for p in provider_prefixes):
                escaped = val.replace('"', '\\"')
                lines.append(f"{key}=\"{escaped}\"")
        try:
            with open(env_path, "w") as f:
                f.write("# Auto‑generated by Antikythera AI Engine Config\n")
                for line in lines:
                    f.write(line + "\n")
            os.chmod(env_path, 0o600)
        except Exception as e:
            logger.warning(f"Failed to write persistent env to {env_path}: {e}")

_ai_engine_config_service: Optional[AIEngineConfigService] = None

def get_ai_engine_config() -> AIEngineConfigService:
    """Get or create the global AI engine config service"""
    global _ai_engine_config_service
    if _ai_engine_config_service is None:
        _ai_engine_config_service = AIEngineConfigService()
    return _ai_engine_config_service