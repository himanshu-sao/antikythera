import os
import json
import subprocess
from typing import Dict, Any, Optional, List, Union
from api.secret_vault import SecretVault

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
        try:
            current = self._load_config()
            current[name] = {
                "type": type,
                "config": config,
                "created_at": os.popen('date -u +"%Y-%m-%dT%H:%M:%SZ"').read().strip()
            }
            self._save_config(current)
            return True
        except Exception:
            return False

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

    def execute_action(self, integration_name: str, action_name: str, params: Dict[str, Any]) -> Any:
        """
        Unified execution interface.
        Dispatches to either the Native adapter or the MCP server.
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

    def _execute_native(self, integration: Dict[str, Any], action: str, params: Dict[str, Any], secrets: Optional[Dict[str, Any]]) -> Any:
        # In a real system, we would dynamically load the adapter class.
        # For now, we simulate dispatch to existing adapter files.
        adapter_module = integration["config"].get("adapter_module")
        if not adapter_module:
            raise Exception("Native adapter missing module configuration")
        
        # This is a simplified mock of the dynamic loading process
        # In the actual engine, this will be integrated with WorkflowEngine.
        return {"status": "success", "data": f"Native {adapter_module} executed {action}"}

    def _execute_mcp(self, integration: Dict[str, Any], action: str, params: Dict[str, Any], secrets: Optional[Dict[str, Any]]) -> Any:
        # MCP execution involves starting a subprocess, sending a JSON-RPC request, and reading the response.
        command = integration["config"].get("command")
        args = integration["config"].get("args", [])
        
        if not command:
            raise Exception("MCP integration missing command")
            
        # Construct JSON-RPC call to MCP server
        # Note: This is a simplified simulation of the MCP protocol.
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": action,
                "arguments": params
            }
        }
        
        try:
            # Start MCP server in stdio mode
            process = subprocess.Popen(
                [command] + args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Send the call and get the response
            stdout, stderr = process.communicate(input=json.dumps(payload))
            
            if process.returncode != 0:
                raise Exception(f"MCP Server Error: {stderr}")
                
            return json.loads(stdout)
        except Exception as e:
            raise Exception(f"MCP Execution failed: {str(e)}")
