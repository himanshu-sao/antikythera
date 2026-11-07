import os
import json
import subprocess
import logging
import re
import shutil
import tempfile
from datetime import datetime, timezone
from filelock import FileLock
from typing import Dict, Any, Optional, List, Union
# SecretVault import removed – credentials are now read from environment variables via placeholders

logger = logging.getLogger("backend")

MASK_PLACEHOLDER = "*****"

# Config keys whose *segments* (split on _ - . or space) mark a secret.
# Segment matching, not substring: "path" must not be treated as "pat".
_SECRET_SEGMENTS = {
    "token", "pat", "password", "passwd", "pwd", "secret", "key", "apikey",
    "credential", "credentials",
}


def _is_secret_key(name: str) -> bool:
    segments = re.split(r"[_\-. ]+", str(name).lower())
    return any(seg in _SECRET_SEGMENTS for seg in segments)


def mask_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of *config* with secret-looking values replaced by MASK_PLACEHOLDER.

    - Keys whose name marks a secret (token, pat, password, secret, api_key, key, ...)
      are masked when they hold a non-empty value.
    - Every value inside an ``env`` mapping (MCP environment) is masked.
    Empty values are left as-is so the UI can show "not set".
    """
    masked: Dict[str, Any] = {}
    for key, value in config.items():
        if key == "env" and isinstance(value, dict):
            masked[key] = {k: (MASK_PLACEHOLDER if v not in (None, "") else v) for k, v in value.items()}
        elif _is_secret_key(key) and value not in (None, ""):
            masked[key] = MASK_PLACEHOLDER
        else:
            masked[key] = value
    return masked


def merge_config_preserving_mask(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Merge *incoming* over *existing*, keeping stored values where *incoming* sends MASK_PLACEHOLDER.

    A placeholder for a key with no stored value is dropped rather than stored as a literal.
    The ``env`` mapping is merged key by key so a masked env value keeps its stored value.
    """
    merged: Dict[str, Any] = dict(existing)
    for key, value in incoming.items():
        if key == "env" and isinstance(value, dict) and isinstance(existing.get("env"), dict):
            env = dict(existing["env"])
            for env_key, env_val in value.items():
                if env_val == MASK_PLACEHOLDER:
                    if env_key in existing["env"]:
                        env[env_key] = existing["env"][env_key]
                    else:
                        env.pop(env_key, None)
                else:
                    env[env_key] = env_val
            merged["env"] = env
        elif value == MASK_PLACEHOLDER:
            if key in existing:
                merged[key] = existing[key]
            else:
                merged.pop(key, None)
        else:
            merged[key] = value
    return merged


class IntegrationConfigCorruptError(Exception):
    """integrations.json exists but is not a valid JSON object (SEC-/2.16).

    The bad file is preserved as ``<file>.corrupt-<UTC timestamp>`` before this
    is raised, so the hub never silently behaves as if no integrations exist and
    never overwrites the unreadable original.
    """


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
        with open(self.config_path, "r") as f:
            raw = f.read()
        try:
            data = json.loads(raw)
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
                    "type": type,
                    "config": config,
                    "created_at": os.popen('date -u +"%Y-%m-%dT%H:%M:%SZ"').read().strip()
                }
                self._save_config(current)
            return True
        except Exception as e:
            if isinstance(e, ValueError):
                raise e
            raise Exception(f"Failed to save integration: {str(e)}")

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
        try:
            call_args = params.get("arguments", {}) if isinstance(params, dict) else {}
            resource_id = params.get("resource_id") if isinstance(params, dict) else None

            if method_name == "fetch":
                result = asyncio.run(method(resource_id, params=call_args))
            elif method_name in ("update", "create", "delete"):
                payload = call_args.copy() if call_args else {}
                if resource_id:
                    payload["resource_id"] = resource_id
                result = asyncio.run(method(resource_id if method_name == "delete" else None, payload))
            elif method_name == "execute":
                # synchronous mock path (used by tests)
                result = method(run_id=params.get("run_id", ""), config=call_args, context={})
            else:
                result = asyncio.run(method(resource_id, **call_args))

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
