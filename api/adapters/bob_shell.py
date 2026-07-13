import os
import subprocess
from typing import Dict, Any, Optional

from api.adapters.base import BaseAdapter

# Allowlist of ``bob`` CLI options a workflow template may pass via ``args``.
# Restricted to value-less boolean flags so a caller cannot smuggle a
# free-form value (``-m <x>``, ``--include-directories <path>`` …) into the
# subprocess argv through this adapter. Source: ``bob --help`` (v1.0.6).
# Anything not in this set is rejected fail-closed in ``_build_command``.
_BOB_ALLOWED_ARGS = frozenset({
    "-y", "--yolo",
    "-s", "--sandbox",
    "--hide-intermediary-output",
    "--accept-license",
    "--pre-check-auto-approved",
    "--trust",
    "--screen-reader",
})


class BobShellAdapter(BaseAdapter):
    """Adapter to interact with IBM Bob Shell via CLI.

    Executes Bob Shell in non-interactive mode using ``bob -p <prompt>``
    (the prompt is the *value* of ``-p``, so a leading-dash prompt is not
    reinterpreted as a flag — unlike a bare positional). The caller provides a
    prompt and an optional, allowlisted set of extra CLI flags (e.g.
    ``["--yolo"]``).

    Authentication is handled entirely by the ``bob`` binary itself: on first
    run it opens a browser for SSO login, then caches credentials for ~24 hours
    (see CLAUDE.md gotcha #10). No API key is managed here — the legacy
    ``api_key_env`` / vault config keys are accepted for backward compatibility
    but ignored, since ``bob`` does not read them.

    Security posture (hardened after P2.6 review):
      * ``args`` is screened against ``_BOB_ALLOWED_ARGS`` — anything else is
        rejected, and only value-less flags are permitted, so a workflow
        template cannot perform argv injection via this adapter.
      * The prompt is passed as the value of ``-p`` (not as a bare positional),
        so a prompt beginning with ``-`` cannot be reinterpreted as a flag.
      * The subprocess runs with a minimal environment (PATH only) so env-driven
        ``bob`` config in the parent shell is not honored.

    Note: this adapter (workflow-tool execution) and ``LLMClient._chat_bob``
    (LLM chat) are the two distinct "BOB" call sites in this project — see
    CLAUDE.md gotcha #10.
    """

    @staticmethod
    def _build_command(prompt: str, args) -> list:
        """Build the validated ``bob`` command line.

        Returns argv as ``["bob", "-p", prompt, *allowlisted_flags]``.
        Raises ``ValueError`` if any element of ``args`` is not on the
        allowlist, or if ``prompt`` is empty. Kept static so tests can assert
        the exact argv shape without shelling out.
        """
        if not prompt:
            raise ValueError("prompt must be a non-empty string")
        for a in args or []:
            if a not in _BOB_ALLOWED_ARGS:
                # Fail-closed: reject any extra arg we don't recognize as a
                # safe value-less bob flag. This blocks argv injection via
                # untrusted ``args`` (e.g. ``-m``, ``--allowed-tools``, an
                # arbitrary path, or a leading-dash prompt smuggled as a flag).
                raise ValueError(
                    f"Disallowed bob argument {a!r}; permitted: "
                    f"{sorted(_BOB_ALLOWED_ARGS)}"
                )
        return ["bob", "-p", prompt, *(args or [])]

    def __init__(self, vault=None):
        super().__init__(vault)

    def execute(self, run_id: str, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Run a Bob Shell command.

        Expected ``config`` keys:
            - ``prompt`` (str): Prompt to send to Bob.
            - ``args`` (list[str], optional): Additional CLI flags — must each
              be on ``_BOB_ALLOWED_ARGS`` (e.g. ``["--yolo"]``).
            - ``api_key_env`` (str, optional): IGNORED — kept for backward
              compatibility. ``bob`` manages its own auth (browser SSO + 24h
              cache), so no key is required to invoke the binary.
        Returns a dict with ``status`` and either ``output`` on success or
        ``message`` on error. Subprocess stderr is never echoed in ``message``;
        failures map to static strings.
        """
        prompt = config.get("prompt")
        if not prompt:
            return {"status": "error", "message": "Missing 'prompt' in config"}

        args = config.get("args", []) or []

        try:
            command = self._build_command(prompt, args)
        except ValueError as e:
            # Allowlist violation — fail-closed without shelling out.
            return {"status": "error", "message": str(e)}

        # Minimal env: only PATH so ``bob`` is found. We deliberately do NOT
        # pass the full parent environment, to avoid honoring any env-driven
        # bob config (BOB_* vars etc.) set in the ambient shell.
        minimal_env = {"PATH": os.environ.get("PATH", "")}

        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=minimal_env,
                timeout=30,
                check=False,
            )
            if result.returncode != 0:
                # Static message — raw stderr may contain auth/MCP trail.
                return {"status": "error", "message": "Bob Shell command failed (non-zero exit)"}
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
