import os
import subprocess
from typing import Dict, Any, Optional

from api.adapters.base import BaseAdapter

class BobShellAdapter(BaseAdapter):
    """Adapter to interact with IBM Bob Shell via CLI.

    Executes Bob Shell in non-interactive mode using the ``bob -p`` command.
    The caller provides a prompt and optional extra CLI arguments (e.g.
    ``["--yolo"]``).

    Authentication is handled entirely by the ``bob`` binary itself: on first
    run it opens a browser for SSO login, then caches credentials for ~24 hours
    (see CLAUDE.md gotcha #10). No API key is managed here — the legacy
    ``api_key_env`` / vault config keys are accepted for backward compatibility
    but ignored, since ``bob`` does not read them.
    """

    @staticmethod
    def _build_command(prompt: str, args) -> list:
        """Build the ``bob`` command line.

        Kept as a static method so tests can assert the exact argv shape
        without shelling out. We use the ``-p`` prompt form (still supported
        on bob v1.0.6; ``bob --help`` marks it deprecated but functional) for
        parity with the existing integration-test contract. Extra ``args``
        (options like ``--yolo``) are appended.
        """
        return ["bob", "-p", prompt, *args]

    def __init__(self, vault=None):
        super().__init__(vault)

    def execute(self, run_id: str, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Run a Bob Shell command.

        Expected ``config`` keys:
            - ``prompt`` (str): Prompt to send to Bob.
            - ``args`` (list[str], optional): Additional CLI arguments
              (e.g. ``["--yolo"]``).
            - ``api_key_env`` (str, optional): IGNORED — kept for backward
              compatibility. ``bob`` manages its own auth (browser SSO + 24h
              cache), so no key is required to invoke the binary.
        Returns a dict with ``status`` and either ``output`` on success or
        ``message`` on error.
        """
        prompt = config.get("prompt")
        if not prompt:
            return {"status": "error", "message": "Missing 'prompt' in config"}

        args = config.get("args", []) or []

        # Build the command line. ``bob`` manages its own auth, so no API key
        # is injected into the environment.
        command = self._build_command(prompt, args)

        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=os.environ.copy(),
                timeout=30,
                check=False,
            )
            if result.returncode != 0:
                return {"status": "error", "message": f"Bob Shell failed: {result.stderr.strip()}"}
            return {"status": "success", "output": result.stdout.strip()}
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Bob Shell command timed out"}
        except FileNotFoundError:
            return {"status": "error", "message": "bob CLI not found on PATH"}
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
