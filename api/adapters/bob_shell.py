import os
import subprocess
from typing import Dict, Any, Optional

from api.adapters.base import BaseAdapter

class BobShellAdapter(BaseAdapter):
    """Adapter to interact with IBM Bob Shell via CLI.

    Executes Bob Shell in non‑interactive mode using the ``bob -p`` command.
    The caller provides a prompt and optional arguments. Authentication is
    performed via an API key supplied in an environment variable (default
    ``BOB_API_KEY``) or retrieved from a secret vault if one is configured.
    """

    def __init__(self, vault=None):
        super().__init__(vault)

    def execute(self, run_id: str, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Run a Bob Shell command.

        Expected ``config`` keys:
            - ``prompt`` (str): Prompt to send to Bob.
            - ``args`` (list[str], optional): Additional CLI arguments (e.g. ``[\"--yolo\"]``).
            - ``api_key_env`` (str, optional): Name of the env var holding the Bob API key.
        Returns a dict with ``status`` and either ``output`` on success or ``message`` on error.
        """
        prompt = config.get("prompt")
        if not prompt:
            return {"status": "error", "message": "Missing 'prompt' in config"}

        args = config.get("args", [])
        api_key_env = config.get("api_key_env", "BOB_API_KEY")

        # Resolve API key from environment or vault
        api_key = os.getenv(api_key_env)
        if not api_key and self.vault:
            secret = self.vault.get_secret("bob")
            if secret:
                api_key = secret.get("api_key")
        if not api_key:
            return {"status": "error", "message": f"Bob API key not found in env var {api_key_env}"}

        # Build the command line
        command = ["bob", "-p", prompt] + args

        # Prepare environment with the API key
        env = os.environ.copy()
        env[api_key_env] = api_key

        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                timeout=30,
                check=False,
            )
            if result.returncode != 0:
                return {"status": "error", "message": f"Bob Shell failed: {result.stderr.strip()}"}
            return {"status": "success", "output": result.stdout.strip()}
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Bob Shell command timed out"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def fetch(self, resource_id: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """BobShellAdapter does not support fetch operations."""
        raise NotImplementedError("BobShellAdapter does not support fetch")

    async def update(self, resource_id: str, payload: Dict[str, Any]) -> Any:
        """BobShellAdapter does not support update operations."""
        raise NotImplementedError("BobShellAdapter does not support update")

    async def create(self, payload: Dict[str, Any]) -> Any:
        """BobShellAdapter does not support create operations."""
        raise NotImplementedError("BobShellAdapter does not support create")

    async def delete(self, resource_id: str) -> Any:
        """BobShellAdapter does not support delete operations."""
        raise NotImplementedError("BobShellAdapter does not support delete")