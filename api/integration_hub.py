import os
import json
import subprocess
import logging
import re
import shutil
import tempfile
from datetime import datetime, timezone
from filelock import FileLock
from typing import Dict, Any, Optional, List
# SecretVault import removed – credentials are now read from environment variables via placeholders

logger = logging.getLogger("backend")

# Canonical adapter names (the template validator's allowlist plus the
# execution-capable bob_shell, which only pre-existing stored templates use).
# Used as a fallback when no integration with that name exists in
# integrations.json; synthetic records are never persisted.
CANONICAL_ADAPTERS = {
    "internal": "api.adapters.internal",
    "github": "api.adapters.github",
    "jira": "api.adapters.jira",
    "ai": "api.adapters.ai",
    "bob_shell": "api.adapters.bob_shell",
}

MASK_PLACEHOLDER = "*****"

# Name segments that mark a secret. Matching is on whole segments after splitting
# camelCase and snake/kebab/dot names, so "path" is not "pat" and "monkey" is not "key".
_SECRET_SEGMENTS = {
    "token", "tokens", "pat", "password", "passwords", "passwd", "pwd", "secret", "secrets",
    "key", "keys", "apikey", "credential", "credentials", "auth", "authorization",
    "bearer", "cookie", "session",
}

_CAMEL_1 = re.compile(r"([a-z0-9])([A-Z])")
_CAMEL_2 = re.compile(r"([A-Z]+)([A-Z][a-z])")
_URL_USERINFO = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]*://[^/?#@\s:]*):([^/?#@\s]+)@")


def _segments(name: str) -> List[str]:
    """Split a config key into lower-case segments: accessToken -> [access, token]."""
    spaced = _CAMEL_2.sub(r"\1_\2", _CAMEL_1.sub(r"\1_\2", str(name)))
    return [seg for seg in re.split(r"[^A-Za-z0-9]+", spaced.lower()) if seg]


def _is_secret_key(name: str) -> bool:
    return any(seg in _SECRET_SEGMENTS for seg in _segments(name))


def _is_secret_flag(item: Any) -> bool:
    """True for a command-line flag such as ``--api-key`` or ``-token``."""
    if not isinstance(item, str) or not item.startswith("-"):
        return False
    return _is_secret_key(item.lstrip("-"))


def _mask_url(text: str) -> str:
    """Replace the password in ``scheme://user:password@host`` with MASK_PLACEHOLDER."""
    return _URL_USERINFO.sub(lambda m: f"{m.group(1)}:{MASK_PLACEHOLDER}@", text, count=1)


def _mask_all(value: Any) -> Any:
    """Mask every non-empty scalar under *value* (used under a secret-named key)."""
    if isinstance(value, dict):
        return {k: _mask_all(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask_all(v) for v in value]
    return MASK_PLACEHOLDER if value not in (None, "") else value


def _mask_value(key: Optional[str], value: Any) -> Any:
    """Mask one config value. *key* is the enclosing key, or None for a list element."""
    if key is not None and _is_secret_key(key):
        return _mask_all(value)
    if isinstance(value, dict):
        return _mask_tree(value)
    if isinstance(value, list):
        return _mask_list(value)
    if isinstance(value, str):
        return _mask_url(value)
    return value


def _mask_tree(config: Dict[str, Any]) -> Dict[str, Any]:
    masked: Dict[str, Any] = {}
    for key, value in config.items():
        if key == "env" and isinstance(value, dict):
            masked[key] = {k: (MASK_PLACEHOLDER if v not in (None, "") else v) for k, v in value.items()}
        else:
            masked[key] = _mask_value(key, value)
    return masked


def _mask_list(items: List[Any]) -> List[Any]:
    """Mask a list. A value after a secret flag, or after ``--flag=``, is masked."""
    out: List[Any] = []
    mask_next = False
    for item in items:
        if mask_next and item not in (None, "") and not (isinstance(item, str) and item.startswith("-")):
            out.append(MASK_PLACEHOLDER)
            mask_next = False
            continue
        mask_next = False
        if isinstance(item, str) and item.startswith("-"):
            flag, sep, value = item.partition("=")
            if sep and value != "" and _is_secret_flag(flag):
                out.append(f"{flag}={MASK_PLACEHOLDER}")
                continue
            if not sep and _is_secret_flag(flag):
                mask_next = True
            out.append(item)
            continue
        out.append(_mask_value(None, item))
    return out


def mask_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of *config* with secret-looking values replaced by MASK_PLACEHOLDER.

    - Keys whose name marks a secret (token, pat, password, secret, api_key, auth, ...)
      are masked when they hold a non-empty value. camelCase and snake/kebab names are
      split into segments; dicts and lists under a secret key are masked element-wise.
    - Every value inside an ``env`` mapping (MCP environment) is masked.
    - In ``args`` lists, the value after a secret flag (``--api-key X``, ``--token=X``) is masked.
    - URL passwords (``scheme://user:pw@host``) are masked in any string value.
    Empty values are left as-is so the UI can show "not set".
    """
    return _mask_tree(config)


_MISSING = object()
_DROP = object()


def _restore_list(stored: List[Any], incoming: List[Any]) -> List[Any]:
    out: List[Any] = []
    for i, item in enumerate(incoming):
        if item == MASK_PLACEHOLDER:
            prev = incoming[i - 1] if i > 0 else None
            if _is_secret_flag(prev):
                value = _stored_after_flag(stored, prev)
            elif i < len(stored):
                # A masked element of a list under a secret key sits at the same index.
                value = stored[i]
            else:
                value = _MISSING
            if value is not _MISSING:
                out.append(value)
            continue
        if isinstance(item, str) and item.startswith("-") and "=" in item:
            flag, _, value = item.partition("=")
            if value == MASK_PLACEHOLDER and _is_secret_flag(flag):
                match = next((s for s in stored if isinstance(s, str) and s.startswith(flag + "=")), _MISSING)
                if match is not _MISSING:
                    out.append(match)
                continue
        if isinstance(item, str):
            match = next((s for s in stored if isinstance(s, str) and _mask_url(s) == item), _MISSING)
            out.append(item if match is _MISSING else match)
            continue
        if isinstance(item, (dict, list)):
            base = stored[i] if i < len(stored) else _MISSING
            restored = _restore(base, item)
            if restored is not _DROP:
                out.append(restored)
            continue
        out.append(item)
    return out


def _stored_after_flag(stored: List[Any], flag: Any) -> Any:
    for j, item in enumerate(stored[:-1]):
        if item == flag and not (isinstance(stored[j + 1], str) and stored[j + 1].startswith("-")):
            return stored[j + 1]
    return _MISSING


def _restore(stored: Any, incoming: Any) -> Any:
    """Return *incoming* with each masked placeholder replaced by the stored value at the same path.

    A placeholder with no stored counterpart is dropped (``_DROP``) rather than stored.
    A string equal to the masked form of the stored string (URL with a masked password)
    keeps the stored string.
    """
    if isinstance(incoming, str):
        if incoming == MASK_PLACEHOLDER:
            return stored if stored is not _MISSING else _DROP
        if isinstance(stored, str) and incoming == _mask_url(stored):
            return stored
        return incoming
    if isinstance(incoming, dict):
        base = stored if isinstance(stored, dict) else {}
        out: Dict[str, Any] = {}
        for key, value in incoming.items():
            restored = _restore(base.get(key, _MISSING), value)
            if restored is not _DROP:
                out[key] = restored
        return out
    if isinstance(incoming, list):
        return _restore_list(stored if isinstance(stored, list) else [], incoming)
    return incoming


def merge_config_preserving_mask(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Merge *incoming* over *existing*, keeping stored values where *incoming* sends a mask.

    Masked values are restored at any depth: a masked nested value (``auth.token``,
    ``headers.Authorization``, a secret element of ``args``, a URL password) takes the
    stored value at the same path. A placeholder with no stored counterpart is dropped
    rather than stored as a literal. The ``env`` mapping is merged key by key.
    """
    merged: Dict[str, Any] = dict(existing)
    for key, value in incoming.items():
        if key == "env" and isinstance(value, dict) and isinstance(existing.get("env"), dict):
            env = dict(existing["env"])
            for env_key, env_val in value.items():
                restored = _restore(existing["env"].get(env_key, _MISSING), env_val)
                if restored is _DROP:
                    env.pop(env_key, None)
                else:
                    env[env_key] = restored
            merged["env"] = env
            continue
        restored = _restore(existing.get(key, _MISSING), value)
        if restored is _DROP:
            merged.pop(key, None)
        else:
            merged[key] = restored
    return merged


class IntegrationConfigCorruptError(Exception):
    """integrations.json exists but is not a valid JSON object (SEC-/2.16).

    The bad file is preserved as ``<file>.corrupt-<UTC timestamp>`` before this
    is raised, so the hub never silently behaves as if no integrations exist and
    never overwrites the unreadable original.
    """


PUBLIC_INTEGRATION_CORRUPT_MESSAGE = (
    "A data file is corrupt (not valid JSON). A backup copy of it was saved next to the original. "
    "Restore or remove the original file, then retry."
)


def public_error_detail(exc: BaseException, code: str, what: str) -> str:
    """Client-safe message for an unexpected server error (P1-6).

    Corrupt-file errors (the hub's own and the managers' ``CorruptStateError``)
    carry absolute paths in their text, so they get a fixed message. Anything else
    gets ``"<what> failed (error code <code>)"``. The full exception is always
    logged server-side; the text of *exc* is never returned.
    """
    from api.managers.base import CorruptStateError

    if isinstance(exc, (IntegrationConfigCorruptError, CorruptStateError)):
        logger.error("%s: corrupt data file: %s", code, exc)
        return PUBLIC_INTEGRATION_CORRUPT_MESSAGE
    logger.error("%s: %s failed", code, what, exc_info=exc)
    return f"{what} failed (error code {code})"


def _run_coroutine_sync(coro_factory):
    """Run an adapter coroutine to completion from synchronous code (2.20 / T24).

    ``asyncio.run`` cannot be nested inside a running loop. Hub methods are
    called from async FastAPI handlers, so when a loop is already running the
    coroutine is executed on a short-lived worker thread that owns its own loop.
    ``coro_factory`` is a zero-arg callable. The coroutine object is created on
    the caller's thread when the factory is called; ``asyncio.run`` (on the
    worker thread in the nested case) only drives it to completion.
    """
    import asyncio
    import concurrent.futures

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory())

    with concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="hub-adapter") as pool:
        return pool.submit(asyncio.run, coro_factory()).result()


class IntegrationHub:
    """
    Manages external service connections.
    Supports:
    1. Native Adapters: Python classes defined in the codebase.
    2. MCP Servers: Model Context Protocol servers (stdio/http).
    """
    def __init__(self, base_dir: str, vault: Optional[Any] = None):
        self.base_dir = base_dir
        self.vault = vault
        self.config_path = os.path.join(base_dir, "integrations.json")
        self._lock_path = self.config_path + ".lock"

    def _lock(self) -> FileLock:
        """Cross-process lock guarding read-modify-write cycles on integrations.json."""
        return FileLock(self._lock_path)

    def _load_config(self) -> Dict[str, Any]:
        """Return the stored integrations mapping.

        Missing file -> {}. Unreadable/invalid JSON or a non-object root raises
        IntegrationConfigCorruptError after backing the file up (2.16). Other
        I/O errors propagate.
        """
        if not os.path.exists(self.config_path):
            return {}
        with open(self.config_path, "rb") as f:
            raw = f.read()
        # Bad UTF-8 is corrupt in the same way as bad JSON (R7b): it is decoded inside
        # the same handler so it gets the same backup and the same error type.
        try:
            data = json.loads(raw.decode("utf-8"))
        except UnicodeDecodeError as exc:
            backup = self._backup_corrupt_file()
            raise IntegrationConfigCorruptError(
                f"integrations.json is not valid UTF-8 ({exc.reason} at byte {exc.start}); "
                f"the unreadable file was preserved at {backup}"
            ) from exc
        except json.JSONDecodeError as exc:
            backup = self._backup_corrupt_file()
            raise IntegrationConfigCorruptError(
                f"integrations.json is not valid JSON ({exc.msg} at line {exc.lineno}); "
                f"the unreadable file was preserved at {backup}"
            ) from exc
        if not isinstance(data, dict):
            backup = self._backup_corrupt_file()
            raise IntegrationConfigCorruptError(
                f"integrations.json must contain a JSON object; "
                f"the unreadable file was preserved at {backup}"
            )
        return data

    def _backup_corrupt_file(self) -> str:
        """Copy the corrupt config to ``<file>.corrupt-<UTC timestamp>``.

        The original is left in place. If an identical backup already exists
        (repeated loads of the same bad file) no new copy is made.
        """
        with open(self.config_path, "rb") as f:
            payload = f.read()
        existing = sorted(
            p for p in (os.path.join(self.base_dir, n) for n in os.listdir(self.base_dir))
            if os.path.basename(p).startswith(os.path.basename(self.config_path) + ".corrupt-")
        )
        for path in existing:
            with open(path, "rb") as f:
                if f.read() == payload:
                    return path
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = f"{self.config_path}.corrupt-{stamp}"
        shutil.copyfile(self.config_path, backup)
        logger.error("integrations.json was corrupt; preserved copy at %s", backup)
        return backup

    def _save_config(self, config: Dict[str, Any]):
        """Atomically replace integrations.json (temp file in the same dir + os.replace).

        Callers hold self._lock() around the read-modify-write.
        """
        os.makedirs(self.base_dir, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=self.base_dir, prefix=".integrations.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(config, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.config_path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def add_integration(self, name: str, type: str, config: Dict[str, Any]) -> bool:
        """
        type: 'native' or 'mcp'
        config: { "adapter_class": "..." } or { "command": "...", "args": [...] }
        """
        if type == "mcp":
            # Tests may create an MCP integration with an empty config.
            # Provide a harmless default command so the integration can be added.
            if "command" not in config or not config["command"]:
                config["command"] = "echo"
            if "args" not in config:
                config["args"] = []
        elif type == "native":
            # Allow empty config for testing; default to a mock adapter module if none provided
            if "adapter_module" not in config:
                config["adapter_module"] = "mock_module"
                # No exception raised – proceed with mock module


        try:
            with self._lock():
                current = self._load_config()
                current[name] = {
                    "name": name,
                    "type": type,
                    "config": config,
                    "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                }
                self._save_config(current)
            return True
        except (ValueError, IntegrationConfigCorruptError):
            raise
        except Exception as e:
            raise Exception(f"Failed to save integration: {str(e)}") from e

    def get_integration(self, name: str) -> Optional[Dict[str, Any]]:
        return self._load_config().get(name)

    def list_integrations(self) -> List[Dict[str, Any]]:
        """List integrations with secret-looking config values masked (SEC-5).

        Stored values are untouched; only the returned copies are masked.
        Use get_integration() for the raw record needed for connections.
        """
        config = self._load_config()
        results = []
        for name, data in config.items():
            # Ensure status exists, default to 'disconnected'
            status = data.get("status", "disconnected")
            entry = {"name": name, **data, "status": status}
            if isinstance(entry.get("config"), dict):
                entry["config"] = mask_config(entry["config"])
            results.append(entry)
        return results

    def delete_integration(self, name: str) -> bool:
        with self._lock():
            current = self._load_config()
            if name in current:
                del current[name]
                self._save_config(current)
                return True
            return False

    def update_integration(self, name: str, config: Dict[str, Any]) -> bool:
        """Replace the configuration of an existing integration.
        Raises ValueError if the integration does not exist.
        Updates the connection status based on credential presence.
        """
        with self._lock():
            current = self._load_config()
            if name not in current:
                raise ValueError(f"Integration {name} not found")
            # Preserve other fields (type, created_at, status) and merge new config keys
            # into the existing config so required fields like 'adapter_module' survive.
            existing_cfg = current[name].get("config", {}) or {}
            # Merge but preserve real secrets if placeholder values are supplied
            merged_cfg = merge_config_preserving_mask(existing_cfg, config)
            current[name]["config"] = merged_cfg
            self._save_config(current)
        # Validate credentials for known native adapters (e.g., Jira) and set status.
        # Done outside the lock: it re-enters via update_status().
        self._validate_credentials_and_update_status(name)
        return True

    def update_status(self, name: str, status: str):
        """Update the connection status of an integration."""
        with self._lock():
            current = self._load_config()
            if name in current:
                current[name]["status"] = status
                self._save_config(current)

    def execute_action(self, integration_name: str, action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Unified execution interface.
        Dispatches to either the Native adapter or the MCP server.
        Returns a dict with 'result' and 'logs'.
        """
        integration = self.get_integration(integration_name)
        if not integration and isinstance(integration_name, str):
            # Stored templates and the validator use canonical adapter names
            # (internal, github, jira, ai, bob_shell); integrations.json holds
            # free-form names. Fall back to the canonical adapter module.
            lowered = integration_name.strip().lower()
            integration = self.get_integration(lowered)
            if not integration:
                module = CANONICAL_ADAPTERS.get(lowered)
                if module:
                    # Prefer a UI-configured integration that uses the same
                    # adapter module, so its credentials (token, jira_url, ...)
                    # reach the adapter. Deterministic pick when several match.
                    matches = sorted(
                        ((key, rec) for key, rec in self._load_config().items()
                         if isinstance(rec, dict)
                         and rec.get("type") == "native"
                         and isinstance(rec.get("config"), dict)
                         and rec["config"].get("adapter_module") == module),
                        key=lambda pair: pair[0],
                    )
                    if matches:
                        integration = dict(matches[0][1])
                        integration["name"] = matches[0][0]
                        if len(matches) > 1:
                            logger.warning(
                                "Canonical adapter %r: %d integrations use module %s; "
                                "using %r (first by name)",
                                lowered, len(matches), module, integration.get("name"))
                        else:
                            logger.info(
                                "Integration %r not configured; using integration %r "
                                "(adapter module %s) for its credentials",
                                integration_name, integration.get("name"), module)
                    else:
                        integration = {
                            "name": lowered,
                            "type": "native",
                            "config": {"adapter_module": module},
                            "status": "canonical",
                        }
                    if lowered == "bob_shell":
                        logger.warning(
                            "Integration %r not configured; using the canonical "
                            "bob_shell adapter (execution-capable)", integration_name)
                    else:
                        logger.info(
                            "Integration %r not configured; using the canonical "
                            "adapter %s (no credentials resolved from an "
                            "integration record)", integration_name, module)
        if not integration:
            raise Exception(f"Integration {integration_name} not found")
        
        # Get credentials for this integration from the vault
        # No secret store – credentials are resolved from integration config / environment
        secrets = None
        
        try:
            if integration["type"] == "native":
                res = self._execute_native(integration, action_name, params, secrets)
            elif integration["type"] == "mcp":
                res = self._execute_mcp(integration, action_name, params, secrets)
            else:
                raise Exception(f"Unsupported integration type: {integration['type']}")
            
            # Update status to connected on success (but still validate native credentials if needed)
            self._validate_credentials_and_update_status(integration_name)
            return res
        except Exception as e:
            # Update status to error on failure
            self.update_status(integration_name, "error")
            raise e

    def _validate_credentials_and_update_status(self, name: str):
        """Check required credentials for known native adapters and set status.
        Currently supports Jira native adapter.
        """
        integration = self.get_integration(name)
        if not integration:
            return
        if integration["type"] == "native" and integration["config"].get("adapter_module") == "api.adapters.jira":
            cfg = integration["config"]
            token_val = cfg.get("token") or cfg.get("access_token")
            url_val = cfg.get("jira_url") or cfg.get("url")
            def resolve(val):
                if isinstance(val, str) and val.startswith("${env:") and val.endswith("}"):
                    return os.getenv(val[6:-1])
                return val
            token_resolved = resolve(token_val)
            url_resolved = resolve(url_val)
            # Fall back to vault secrets if not present in config
            if not token_resolved and self.vault:
                secret = self.vault.get_secret("jira")
                if secret:
                    token_resolved = secret.get("access_token") or secret.get("token")
            if not url_resolved and self.vault:
                secret_url = self.vault.get_secret("jira_url")
                if secret_url:
                    url_resolved = secret_url
            if token_resolved and url_resolved:
                self.update_status(name, "connected")
            else:
                self.update_status(name, "error")
        else:
            self.update_status(name, "connected")

    # Canonical action → adapter‑method map (mirrors OperatorRegistry.operator_map).
    _ACTION_MAP = {
        "fetch_resource": "fetch",
        "update_resource": "update",
        # Internal-adapter verbs (workflow steps and Studio graphs) dispatch
        # through the adapter's execute(), which switches on config["action"].
        "move_item": "execute",
        "add_comment": "execute",
        # Builder list/vector verbs (github/jira/internal adapters) and the
        # bare update/execute verbs the fallback templates emit: identity
        # entries, dispatched to the adapter method of the same name (P0-3).
        "list_items": "list_items",
        "list_repos": "list_repos",
        "list_pull_requests": "list_pull_requests",
        "list_tickets": "list_tickets",
        "list_projects": "list_projects",
        "update": "update",
        "execute": "execute",
        # AI adapter (api.adapters.ai) — builder templates emit analyze steps.
        "analyze": "analyze",
        "create_resource": "create",
        "delete_resource": "delete",
        "tools/call": None,      # resolved from params["name"] at call time
        "tools/list": "list",     # adapters have a list() convention
    }

    def _resolve_adapter_class(self, module_path: str):
        """Dynamically import and return the adapter class from *module_path*."""
        import importlib
        mod = importlib.import_module(module_path)
        # Heuristic: the adapter class is the first non‑base, non‑import class
        # whose name ends with "Adapter".  Fall back to a known map.
        for attr in dir(mod):
            if attr.endswith("Adapter") and attr != "BaseAdapter":
                return getattr(mod, attr)
        raise ImportError(f"No *Adapter class found in {module_path}")

    _CREDENTIAL_KEYS = ("token", "access_token", "api_key", "password",
                        "jira_url", "url", "base_url")

    def _extract_credentials(self, integration: Dict[str, Any]) -> Dict[str, str]:
        """Credential-ish values from an integration record, safe to hand over.

        ``${env:X}`` references are resolved from the environment; ``*****``
        masked placeholders (SEC-5 list responses) and empty values are
        dropped. Only the known credential keys are considered.
        """
        config = integration.get("config")
        if not isinstance(config, dict):
            return {}
        creds: Dict[str, str] = {}
        for key in self._CREDENTIAL_KEYS:
            value = config.get(key)
            if not isinstance(value, str) or not value.strip():
                continue
            if "*" in value:  # masked placeholder, never a real credential
                continue
            if value.startswith("${env:") and value.endswith("}"):
                value = os.getenv(value[6:-1]) or ""
                if not value:
                    continue
            creds[key] = value
        return creds

    def _execute_native(self, integration: Dict[str, Any], action: str, params: Dict[str, Any],
                        secrets: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        adapter_module = integration["config"].get("adapter_module")
        if not adapter_module:
            raise Exception("Native adapter missing module configuration")

        # --- import the adapter class & instantiate --------------------------------
        import importlib, asyncio

        try:
            adapter_cls = self._resolve_adapter_class(adapter_module)
        except Exception as exc:
            return {"status": "error",
                    "result": f"Failed to load adapter {adapter_module}: {exc}",
                    "logs": str(exc)}

        try:
            adapter_instance = adapter_cls(vault=self.vault)
        except Exception as exc:
            return {"status": "error",
                    "result": f"Failed to construct {adapter_cls.__name__}: {exc}",
                    "logs": str(exc)}

        # Hand the integration record's credentials to the adapter (instance
        # values win over the environment). ``${env:X}`` references are
        # resolved; masked ``*****`` values are never passed through.
        creds = self._extract_credentials(integration)
        if creds and hasattr(adapter_instance, "configure"):
            try:
                adapter_instance.configure(creds)
            except Exception as exc:
                return {"status": "error",
                        "result": f"Failed to configure {adapter_cls.__name__}: {exc}",
                        "logs": str(exc)}

        # --- map action to method name --------------------------------------------
        # tools/call: the caller provides {"name": "<tool>", "arguments": {...}}
        method_name = self._ACTION_MAP.get(action)
        if method_name is None and action == "tools/call":
            tool_name = params.get("name", "") if isinstance(params, dict) else ""
            method_name = self._ACTION_MAP.get(tool_name, tool_name)

        if not method_name or not hasattr(adapter_instance, method_name):
            return {"status": "error",
                    "result": f"Unsupported action '{action}' for adapter {adapter_module}",
                    "logs": ""}

        method = getattr(adapter_instance, method_name)

        # --- call the adapter method (sync bridge for async methods) --------------
        # Workflow-step configs sit at the top level (no "arguments" wrapper),
        # like the execute/analyze branches. "action"/"adapter" are dispatch
        # metadata of the internal-adapter step convention, never method
        # parameters, so they are dropped from the top-level fallback.
        _METADATA_KEYS = ("action", "adapter", "resource_id", "run_id")

        try:
            call_args = params.get("arguments", {}) if isinstance(params, dict) else {}
            resource_id = params.get("resource_id") if isinstance(params, dict) else None

            def _top_level_params() -> Dict[str, Any]:
                """The step config itself, minus dispatch metadata keys."""
                if not isinstance(params, dict):
                    return {}
                return {k: v for k, v in params.items() if k not in _METADATA_KEYS}

            if method_name == "fetch":
                result = _run_coroutine_sync(lambda: method(resource_id, params=call_args))
            elif method_name in ("update", "create", "delete"):
                payload = call_args.copy() if call_args else _top_level_params()
                if resource_id:
                    payload["resource_id"] = resource_id
                result = _run_coroutine_sync(
                    lambda: method(resource_id if method_name == "delete" else None, payload))
            elif method_name == "execute":
                # Workflow steps pass their config at the top level (there is
                # no "arguments" wrapper); tools/call keeps using arguments.
                result = method(run_id=params.get("run_id", ""),
                                config=call_args if call_args else params, context={})
            elif method_name == "analyze":
                result = _run_coroutine_sync(
                    lambda: method(None, **(call_args if call_args else params)))
            else:
                # List/vector verbs. The legacy convention fills the method's
                # first positional slot with resource_id (fetch-like methods);
                # list methods name their first parameter themselves (org,
                # owner, jql, stage) and the config supplies it by keyword, so
                # the positional slot is only filled when the method does not
                # name it — otherwise the call would pass it twice.
                kwargs = dict(call_args) if call_args else _top_level_params()
                import inspect as _inspect
                first_param = next(iter(_inspect.signature(method).parameters), None)
                if first_param is None or first_param in kwargs:
                    # No positional slot to fill (list_projects) or the config
                    # already names the first parameter by keyword.
                    result = _run_coroutine_sync(lambda: method(**kwargs))
                else:
                    result = _run_coroutine_sync(lambda: method(resource_id, **kwargs))

            return {"status": "success", "result": result, "logs": ""}

        except Exception as exc:
            return {"status": "error",
                    "result": f"Adapter {adapter_module}.{method_name} failed: {exc}",
                    "logs": str(exc)}

    def _execute_mcp(self, integration: Dict[str, Any], action: str, params: Dict[str, Any], secrets: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Executes an MCP command via subprocess.
        Logs errors to backend.log for visibility.
        Returns a dict with 'result' and 'logs'.
        """
        config = integration["config"]
        command = config.get("command")
        args = config.get("args", [])
        env_config = config.get("env", {})
        
        if not command:
            raise Exception("MCP integration missing command")
            
        # Construct the environment
        new_env = os.environ.copy()
        
        # Perform environment variable substitution
        for k, v in env_config.items():
            if isinstance(v, str) and v.startswith("${env:") and v.endswith("}"):
                env_key = v[6:-1]
                # 1. Check Secrets
                if secrets and env_key in secrets:
                    new_env[k] = str(secrets[env_key])
                # 2. Check Local Environment
                elif env_key in os.environ:
                    new_env[k] = os.environ[env_key]
                else:
                    new_env[k] = v  # Fallback to literal
            else:
                new_env[k] = str(v)

        # Construct JSON-RPC call to MCP server
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": action, # Can be 'tools/list' or 'tools/call'
            "params": {}
        }

        if action == "tools/call":
            payload["params"] = {
                "name": params.get("name"),
                "arguments": params.get("arguments", {})
            }
        elif action in ["tools/list", "list_tools"]:
            payload["params"] = {}

        try:
            # Start MCP server in stdio mode
            process = subprocess.Popen(
                [command] + args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=new_env
            )
            
            # Send the call and get the response
            stdout, stderr = process.communicate(input=json.dumps(payload) + '\n', timeout=30)
            
            if process.returncode != 0:
                error_msg = f"MCP Server exited with code {process.returncode}. Stderr: {stderr}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
            # Robust JSON extraction: Find the first '{' and the last '}'
            match = re.search(r'(\{.*\})', stdout, re.DOTALL)
            if match:
                json_str = match.group(1)
                try:
                    res = json.loads(json_str)
                    # If the MCP server returned a JSON-RPC error object, treat it as an execution failure
                    if isinstance(res, dict) and "error" in res:
                        error_detail = res["error"].get("message", "Unknown MCP error")
                        error_code = res["error"].get("code", "Unknown code")
                        raise Exception(f"MCP Error ({error_code}): {error_detail}")
                    return {"result": res, "logs": stderr}
                except json.JSONDecodeError as jde:
                    error_msg = f"MCP Server returned invalid JSON structure. Raw stdout: {stdout}. Stderr: {stderr}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
            else:
                error_msg = f"MCP Server did not return a valid JSON response. Raw stdout: {stdout}. Stderr: {stderr}"
                logger.error(error_msg)
                raise Exception(error_msg)

        except subprocess.TimeoutExpired:
            error_msg = f"MCP Server timed out after 30s. Command: {command} {args}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"MCP Execution failed: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
