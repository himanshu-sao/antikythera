"""
LLM Client for Antikythera Agents.
Provides a unified interface for interacting with multiple LLM providers.

Provider/model resolution order:
  1. AIEngineConfigService — the UI-selected default model
     (POST /api/ai-engine/set-default). This is what makes the AI Engine UI
     actually steer agent execution.
  2. config.yaml (fallback) — the static ``llm`` block, used when the config
     service has no usable default (e.g. still the placeholder, or the import
     is unavailable in the test environment).

Supported providers (all 8 from ``AIProvider``):
  - openai, nvidia_nim, ibm_bob, openrouter, lm_studio, anthropic, ollama
    all route through a single OpenAI-compatible Chat Completions client.
    No provider-specific SDKs are required (Anthropic uses its OpenAI-compat
    endpoint; Ollama uses its /v1 OpenAI-compat server).
  - google / google_gemma — Google Generative AI SDK (genai.Client).
"""

import os
import logging
import subprocess
import yaml
from typing import Optional, Dict, Any
from openai import OpenAI
# Attempt to import the real Google Generative AI SDK; fall back to a lightweight stub if unavailable
try:
    import google.genai as genai
    from google.genai import types
except Exception:  # pragma: no cover – stub used in test environment
    # Minimal stub matching the parts of the SDK used by the code
    class _StubClient:
        def __init__(self, api_key=None):
            self.api_key = api_key
        class models:
            @staticmethod
            def generate_content(*args, **kwargs):
                class _Resp:
                    text = "stub response"
                return _Resp()
    genai = type('genai', (), {'Client': _StubClient})
    class _StubTypes:
        class GenerateContentConfig:
            def __init__(self, *args, **kwargs):
                pass
    types = _StubTypes
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Providers that speak the OpenAI-compatible Chat Completions API. Routed
# through a single ``OpenAI`` client with a per-provider base_url.
# NOTE: ``ibm_bob`` is NOT here — it shells out to the local ``bob`` CLI binary
# which manages its own auth (browser SSO, 24h cache). See ``_chat_bob``.
_OPENAI_COMPAT = {
    "openai", "nvidia_nim", "openrouter",
    "lm_studio", "anthropic", "ollama",
}

# ``ibm_bob`` is reached via the local ``bob`` CLI binary (subprocess), not
# over HTTP. The binary handles its own authentication, so no API key is
# managed by the LLMClient.
_IBM_BOB_CLI = "ibm_bob"
_BOB_BINARY = "bob"
_BOB_TIMEOUT = 60  # seconds — bob can be slow on first-run auth

# Ollama's local OpenAI-compatible server. The key value is ignored by Ollama
# but the OpenAI SDK requires a non-empty string.
_OLLAMA_BASE_URL = "http://localhost:11434/v1"
_OLLAMA_DUMMY_KEY = "ollama"

# Anthropic's OpenAI-compatible endpoint (no ``anthropic`` SDK dep needed).
_ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"


def _resolve_from_config_service() -> Optional[Dict[str, Any]]:
    """Ask ``AIEngineConfigService`` for the UI-selected default model.

    Returns a dict ``{provider, model, base_url, api_key}`` or ``None`` when the
    service has no usable default (e.g. still the placeholder with no key/
    endpoint, or the service/import is unavailable). The caller falls back to
    ``config.yaml`` when this returns ``None``.

    The import is done lazily inside the function to avoid import cycles at
    module load and to keep the test environment (which stubs ``google.genai``)
    working even if the service import fails.
    """
    try:
        from api.services.ai_engine_config import get_ai_engine_config
        svc = get_ai_engine_config()
        default_id = svc.config.default_model_id
        cfg = svc.get_model_config(default_id) if default_id else None
        if cfg is None:
            return None
        api_key = os.getenv(cfg.api_key_env) if cfg.api_key_env else None
        base_url = cfg.provider_config.get("base_url") or cfg.endpoint_url
        return {
            "provider": cfg.provider.value,   # e.g. "nvidia_nim"
            "model": cfg.model_id,             # e.g. "meta/llama-3.1-405b-instruct"
            "base_url": base_url,
            "api_key": api_key,
        }
    except Exception as e:
        logger.debug(f"config-service resolution skipped: {e}")
        return None


class LLMClient:
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize the LLM Client.

        Provider/model are resolved from the AIEngineConfigService default
        first (so the AI Engine UI steers execution), falling back to the
        ``llm`` block of ``config_path`` when the service default is unusable.

        Args:
            config_path (str): Path to the configuration file (fallback only).
        """
        # Load .env file if it exists in the current directory
        load_dotenv()

        # 1. Try the UI config service.
        resolved = _resolve_from_config_service()
        if resolved is not None:
            self.provider = resolved["provider"]
            self.model = resolved["model"]
            self.base_url = resolved["base_url"]
            self._resolved_api_key = resolved["api_key"]
        else:
            # 2. Fall back to config.yaml.
            self.config = self._load_config(config_path)
            self.provider = self.config.get("provider", "google")
            self.model = self.config.get("model")
            self.base_url = self.config.get("base_url")
            self._resolved_api_key = None

        self._initialize_client()

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        if not os.path.exists(config_path):
            logger.error(f"Configuration file not found: {config_path}")
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        return config.get("llm", {})

    def _get_env_var(self, env_name: str) -> Optional[str]:
        return os.getenv(env_name)

    def _initialize_client(self):
        prov = self.provider

        # Google GenAI SDK — accepts both the config.yaml spelling ("google")
        # and the AIProvider enum spelling ("google_gemma").
        if prov in ("google", "google_gemma"):
            api_key = self._resolved_api_key
            if api_key is None:
                env_name = "GOOGLE_API_KEY"
                if hasattr(self, "config"):
                    env_name = self.config.get("api_key_env", "GOOGLE_API_KEY_KANBAN")
                api_key = self._get_env_var(env_name)

            if not api_key:
                logger.warning("No API key provided for Google. Requests will likely fail.")

            if not self.model:
                self.model = "gemini-1.5-pro"

            # Attempt to create a real client; fallback to None if unavailable (tests use stub chat)
            try:
                self.client = genai.Client(api_key=api_key)
            except Exception:
                logger.warning("Google client unavailable, using None stub.")
                self.client = None
            return

        # ibm_bob is CLI-based, not HTTP — no OpenAI client to construct.
        # The ``bob`` binary manages its own auth (browser SSO, 24h cache).
        # We just record the resolved model id; the actual subprocess call
        # happens in ``_chat_bob``. If the binary isn't on PATH, ``chat()``
        # degrades gracefully to the stub string (the FileNotFoundError is
        # caught by the chat() try/except).
        if prov == _IBM_BOB_CLI:
            # Do NOT fabricate a default model id — an id the ``bob`` binary
            # doesn't recognize crashes it with "An unexpected critical error
            # occurred: [object Object]" (rc 1). If none is configured we
            # leave ``self.model`` empty and ``_chat_bob`` omits ``-m`` so
            # ``bob`` uses its own default model.
            self.client = None
            return

        # OpenAI-compatible Chat Completions — covers 6 providers.
        if prov in _OPENAI_COMPAT:
            api_key = self._resolved_api_key
            base_url = self.base_url

            if prov == "openai":
                if api_key is None and hasattr(self, "config"):
                    api_key = self._get_env_var(self.config.get("openai_api_key_env", "OPENAI_API_KEY"))
                    base_url = base_url or self._get_env_var(self.config.get("openai_base_url_env", "OPENAI_BASE_URL"))
                if not api_key:
                    logger.warning("No API key provided for OpenAI. Requests will likely fail.")
                if not self.model:
                    self.model = "gpt-4o"

            elif prov == "ollama":
                # Ollama's OpenAI-compat server ignores the key; the SDK needs a non-empty string.
                if not api_key:
                    api_key = _OLLAMA_DUMMY_KEY
                if not base_url:
                    base_url = _OLLAMA_BASE_URL
                elif "/v1" not in base_url:
                    # Preconfigured base_url is the native /api endpoint; use /v1 for OpenAI-compat.
                    base_url = base_url.rstrip("/").replace("/api/generate", "") + "/v1"

            elif prov == "anthropic":
                if not base_url:
                    base_url = _ANTHROPIC_BASE_URL
                if not api_key:
                    logger.warning("No API key provided for Anthropic. Requests will likely fail.")

            else:
                # nvidia_nim, openrouter, lm_studio — model id is the
                # preconfigured model_id string; base_url from the service.
                if not api_key and prov != "lm_studio":
                    logger.warning(f"No API key for provider {prov}. Requests will likely fail.")

            if prov == "openai" and not base_url:
                # SDK uses its own cloud endpoint when base_url is None.
                base_url = None

            # The OpenAI SDK raises at construction time if api_key is None.
            # We'd rather defer the failure to chat() (which degrades to the
            # stub string) so the pipeline never breaks at init. Use a dummy
            # placeholder when no key is available — the real call will fail
            # and fall back to the deterministic stub.
            if not api_key:
                api_key = "antikythera-missing-key"

            self.client = OpenAI(api_key=api_key, base_url=base_url)
            return

        raise ValueError(f"Unsupported provider: {prov}")

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
        """
        Sends a single chat request to the configured LLM provider.

        When no API key is available or the provider client is uninitialized
        the call degrades gracefully to a stub response so the pipeline
        doesn't break.  The same stub path is used when the real Google
        genai SDK is not installed (e.g. test environment).
        """
        try:
            if self.provider in ("google", "google_gemma"):
                return self._chat_google(system_prompt, user_prompt, temperature)

            if self.provider == _IBM_BOB_CLI:
                return self._chat_bob(system_prompt, user_prompt, temperature)

            if self.provider in _OPENAI_COMPAT:
                return self._chat_openai(system_prompt, user_prompt, temperature)

            raise ValueError(f"Unsupported provider: {self.provider}")

        except Exception as e:
            logger.error(f"{self.provider} chat failed: {str(e)}")
            # Degrade gracefully — fall back to the deterministic stub so
            # downstream agents / routers / the pipeline don't break.
            return ("[stub response — "
                    f"{self.provider} LLM call failed: {str(e)}]")

    # ------------------------------------------------------------------
    # Provider-specific helpers
    # ------------------------------------------------------------------

    def _chat_openai(self, system_prompt: str, user_prompt: str,
                     temperature: float) -> str:
        """Route a chat through the OpenAI-compatible client (7 providers)."""
        if self.client is None:
            raise RuntimeError(f"{self.provider} client not initialized (no API key?)")

        msgs = [{"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt}]

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=msgs,
            temperature=temperature,
        )
        return completion.choices[0].message.content

    def _chat_google(self, system_prompt: str, user_prompt: str,
                     temperature: float) -> str:
        """Route a chat through the Google Generative AI SDK."""
        # If the Google SDK module was stubbed (test env), detect it and fall
        # back to the classic stub phrase so existing tests stay green.
        import google.genai as _genai
        if not hasattr(_genai.Client, "models") or self.client is None:
            raise RuntimeError(
                "Google genai client is a stub (SDK not installed or "
                "no API key configured)"
            )

        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system_prompt,
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=config,
        )
        return response.text

    def _chat_bob(self, system_prompt: str, user_prompt: str,
                  temperature: float) -> str:
        """Route a chat through the local ``bob`` CLI binary (ibm_bob provider).

        ``ibm_bob`` is the only non-HTTP provider: it shells out to the
        ``bob`` binary, which manages its own authentication (first-run
        browser SSO, then cached credentials valid ~24 hours). No API key
        is managed here.

        The ``bob`` CLI takes a single prompt string (no separate
        system/user split), so the system prompt is prepended to the user
        prompt and passed as the positional ``query`` argument. Flags
        chosen against ``bob --help`` and verified empirically on v1.0.6:

          * positional prompt — ``-p``/``--prompt`` is deprecated and will
            be removed in a future ``bob`` version;
          * ``-m`` only when a model is configured — passing an id the binary
            doesn't recognize crashes it ("An unexpected critical error
            occurred: [object Object]"). With no ``-m``, ``bob`` uses its
            own default model;
          * ``--chat-mode ask`` — plain Q&A; without it ``bob`` returns the
            full ``<thinking>`` agentic trace instead of just the answer;
          * ``--allowed-mcp-server-names ""`` — empty allow-list skips
            MCP-server discovery at startup (otherwise ``bob`` emits
            connection errors for unreachable servers on stderr);
          * ``--hide-intermediary-output`` — only the final completion
            reaches stdout;
          * ``-o text`` — raw completion text (choices: text|json|stream-json).

        On a non-zero exit we raise ``RuntimeError`` carrying stderr, which
        ``chat()``'s try/except degrades to the stub string.
        """
        prompt = f"{system_prompt}\n\n{user_prompt}"
        command = [
            _BOB_BINARY,
            "--chat-mode", "ask",
            "--allowed-mcp-server-names", "",   # [] -> skip MCP discovery
            "--hide-intermediary-output",
            "-o", "text",
        ]
        if self.model:
            command += ["-m", self.model]
        command.append(prompt)                  # positional query (not -p)

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=_BOB_TIMEOUT,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"bob CLI exited {result.returncode}: {result.stderr.strip()}"
            )
        return result.stdout.strip()

    def generate_structured_content(self, system_prompt: str, user_prompt: str) -> str:
        """
        A wrapper for chat specifically for generating markdown content.
        """
        return self.chat(system_prompt, user_prompt, temperature=0.2)
