import os
import json
import subprocess
import logging
import re
from typing import Dict, Any, Optional, List, Union
from api.secret_vault import SecretVault

logger = logging.getLogger("backend")

class IntegrationHub:
    """
    Manages external service connections.
    Supports:
    1. Native Adapters: Python classes defined in the codebase.
    2. MCP Servers: Model Context Protocol servers (stdio/http).
    """
    def __init__(self, base_dir: str, vault: SecretVault):
        self.base_dir = base_dir
        self.vault = vault
        self.config_path = os.path.join(base_dir, "integrations.json")
        self._lock_path = self.config_path + ".lock"

    def _load_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            return {}
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_config(self, config: Dict[str, Any]):
        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=2)

    def add_integration(self, name: str, type: str, config: Dict[str, Any]) -> bool:
        """
        type: 'native' or 'mcp'
        config: { "adapter_class": "..." } or { "command": "...", "args": [...] }
        """
        if type == "mcp":
            if "command" not in config or not config["command"]:
                raise ValueError("MCP integration requires a 'command' field. For security, we recommend using environment variables via '${env:VAR}' syntax for any sensitive credentials.")
            if "args" not in config:
                config["args"] = []
        elif type == "native":
            if "adapter_module" not in config:
                raise ValueError("Native integration requires an 'adapter_module' field in config.")

        try:
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
        return [{"name": name, **data} for name, data in self._load_config().items()]

    def delete_integration(self, name: str) -> bool:
        current = self._load_config()
        if name in current:
            del current[name]
            self._save_config(current)
            return True
        return False

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
        secrets = self.vault.get_secret(integration_name)
        
        if integration["type"] == "native":
            return self._execute_native(integration, action_name, params, secrets)
        elif integration["type"] == "mcp":
            return self._execute_mcp(integration, action_name, params, secrets)
        else:
            raise Exception(f"Unsupported integration type: {integration['type']}")

    def _execute_native(self, integration: Dict[str, Any], action: str, params: Dict[str, Any], secrets: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        adapter_module = integration["config"].get("adapter_module")
        if not adapter_module:
            raise Exception("Native adapter missing module configuration")
        # For native, logs are empty
        return {"result": f"Native {adapter_module} executed {action}", "logs": ""}

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
