import os
import json
import logging
import subprocess
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

# P3.2.6 Phase 1 — the executor no longer verifies its own work.  Verification
# of *correctness* is a separate concern (Phase 2 will run the spec's own
# tests against what the executor built).  In Phase 1 the executor's only
# honest assertion is "the artifact I was asked to write landed on disk and is
# not a stub/placeholder".  These markers and the size floor gate that
# assertion so a model can't false-complete a task by writing an obvious
# stand-in.  Deterministic and inspectable — not an LLM judgement.
_STUB_MARKERS = ("stub response", "# TODO", "placeholder", "notimplementederror")
_MIN_ARTIFACT_BYTES = 30


def _is_stub_content(content: str) -> bool:
    """True if ``content`` is empty, too small, or carries a stub/placeholder."""
    if not content or not content.strip():
        return True
    if len(content.strip()) < _MIN_ARTIFACT_BYTES:
        return True
    return any(m in content.lower() for m in _STUB_MARKERS)

# Hard cap on how many workspace file entries get baked into an executor prompt.
# A multi-hundred-line file list (the old os.walk behaviour) ballooned every
# ``_perform_task_multi_turn`` prompt and is the most likely cause of the
# 60–120s ``bob`` timeouts/hangs observed during P3.2.  Keep this bounded.
WORKSPACE_FILES_CAP = 60

# Directories that are never useful workspace context for the executor —
# build/cache/dependency trees that only bloat the prompt.
_EXCLUDED_DIRS = {
    "venv", "node_modules", ".git", ".ui",
    "__pycache__", ".pytest_cache", ".mypy_cache",
    "dist", "build", "playwright-report", "test-results",
    ".cache", ".tox", ".nox",
}


def get_workspace_files(root: str = None) -> List[str]:
    """
    Return a bounded, relevant set of workspace file paths for the executor
    prompt — top-level files plus the ``api/`` source tree, sorted and
    capped at :data:`WORKSPACE_FILES_CAP` entries.

    The old implementation ``os.walk``-ed the whole repo (minus
    venv/node_modules/.git), baking a multi-hundred-line file list into every
    ``_perform_task_multi_turn`` turn.  That giant per-turn context is the
    most plausible cause of the 60–120s ``bob`` timeouts/hangs seen during
    P3.2, so this returns a small, predictable set instead.

    ``root`` defaults to ``os.getcwd()`` so the existing call site
    (``agents/executor.py``) is unchanged; passing an explicit ``root`` makes
    the function testable without depending on the process cwd.

    Exclude ``venv/``, ``node_modules/``, ``.git/``, ``.ui/`` and other
    build/cache dirs (see :data:`_EXCLUDED_DIRS`).  The result is sorted and
    truncated to :data:`WORKSPACE_FILES_CAP`.
    """
    root = os.path.abspath(root or os.getcwd())
    selected: List[str] = []

    def _rel(path: str) -> str:
        return os.path.relpath(path, root)

    def _excluded(entry: str) -> bool:
        return entry in _EXCLUDED_DIRS or os.path.basename(entry) in _EXCLUDED_DIRS

    # 1. Non-directory files at the top level (VERSION, README, Makefile, …).
    for entry in sorted(os.listdir(root)):
        full = os.path.join(root, entry)
        if os.path.isfile(full) and not _excluded(entry):
            selected.append(_rel(full))

    # 2. The api/ source tree — the executor's primary surface.  Prune
    #    excluded dirs from the descent so os.walk never enters them.
    api_root = os.path.join(root, "api")
    if os.path.isdir(api_root):
        for dirpath, dirs, files in os.walk(api_root):
            dirs[:] = sorted(d for d in dirs if d not in _EXCLUDED_DIRS)
            for f in sorted(files):
                if not _excluded(f):
                    selected.append(_rel(os.path.join(dirpath, f)))

    # 3. Dedup, sort, and cap.
    unique_sorted = sorted(set(selected))
    return unique_sorted[:WORKSPACE_FILES_CAP]

def get_tools_description() -> str:
    """
    Returns a string description of available tools for the LLM.
    """
    return """
Available Tools:
- `terminal(command)`: Run a shell command. Returns stdout/stderr.
- `write_file(path, content)`: Write content to a file.
- `patch(path, old_string, new_string)`: Find and replace text in a file.
- `read_file(path)`: Read the contents of a file.

You must respond with a JSON object representing the tool call.
Example response:
{"tool": "terminal", "args": {"command": "ls -la"}}
"""

def execute_tool(tool_name: str, args: Dict[str, Any], item_id: str) -> Tuple[bool, str]:
    """
    Executes a specific tool using native Python system calls.

    Returns ``(is_done, result_text)``.  ``is_done=True`` signals the executor
    loop that the current task is complete (a COMPLETED entry is logged and we
    move to the next planned task).

    P3.2.6 Phase 1 — the executor does **not** verify its own work.  These
    done-semantics assert only "the artifact I was asked to write landed on
    disk and is not a stub/placeholder", never "the work is correct".
    Verification of correctness is Phase 2 (a real verifier runs the spec's
    own tests, out of scope here).  Completion semantics per tool:

    * ``write_file``  -> done when the write succeeds AND the content is
      non-empty, ≥ ``_MIN_ARTIFACT_BYTES``, and free of ``_STUB_MARKERS``.
      (A model can't false-complete by writing a stand-in.)
    * ``patch``       -> done when the patch lands (old_string found and
      replaced).
    * ``terminal``    -> **never** ``is_done``.  A shell command, even a
      successful one, is recon / a side-effect that feeds the next turn —
      it is NOT proof the task is complete.  (Old behaviour ran ``pytest``-
      shape commands as a self-verifier and looped on ``ls``; removed.)
    * ``read_file``   -> never done on its own; information-gathering for the
      next turn.

    ⚠ Security note (parked, not Phase 1 scope): the ``terminal`` branch runs
    ``subprocess.run(cmd, shell=True, timeout=300)`` on LLM-controlled
    ``args["command"]`` — shell injection if the executor is ever pointed at
    untrusted input.  Now less load-bearing than before (``terminal`` can no
    longer *manufacture a false completion*), but still a hardening follow-up.
    """
    try:
        if tool_name == "terminal":
            cmd = args.get("command", "ls")
            # Use shell=True to allow pipes and redirects, matching the behavior of terminal tools
            process = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
            output = process.stdout if process.stdout else ""
            error = process.stderr if process.stderr else ""

            if process.returncode != 0:
                return False, f"ERROR: {error or output}"

            # Never assert done from a shell command (see docstring).  Feed the
            # output back as recon for the next turn.
            return False, f"TOOL RESULT (terminal):\n{output}"

        elif tool_name == "write_file":
            path = args.get("path")
            content = args.get("content", "")
            if not path: return False, "ERROR: No path provided"

            if _is_stub_content(content):
                return False, (
                    "ERROR: write_file content is empty, too small, or a "
                    "stub/placeholder. Write the full intended file contents "
                    f"(got {len((content or '').strip())} bytes)."
                )

            # os.path.dirname("") == "" and makedirs("") raises; guard it.
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, f"SUCCESS: Wrote to {path}"

        elif tool_name == "patch":
            path = args.get("path")
            old_string = args.get("old_string")
            new_string = args.get("new_string")
            if not path or old_string is None: return False, "ERROR: Path or old_string missing"

            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()

            if old_string not in text:
                return False, f"ERROR: old_string not found in {path}"

            updated_text = text.replace(old_string, new_string)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(updated_text)
            return True, f"SUCCESS: Patched {path}"

        elif tool_name == "read_file":
            path = args.get("path")
            if not path: return False, "ERROR: No path provided"

            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return False, f"FILE CONTENT ({path}):\n{content}"

        else:
            logger.error(f"[{item_id}] Unknown tool: {tool_name}")
            return False, f"Unknown tool: {tool_name}"

    except Exception as e:
        logger.error(f"[{item_id}] Tool execution error: {str(e)}")
        return False, f"ERROR: {str(e)}"
