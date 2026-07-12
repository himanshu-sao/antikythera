import os
import json
import logging
import subprocess
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

def get_workspace_files() -> List[str]:
    """
    Scans the current working directory for files, excluding common ignore patterns.
    """
    workspace_files = []
    for root, dirs, files in os.walk(os.getcwd()):
        if any(x in root for x in ["venv", "node_modules", ".git"]):
            continue
        for f in files:
            workspace_files.append(os.path.relpath(os.path.join(root, f), os.getcwd()))
    return workspace_files

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

def _is_verification_command(cmd: str) -> bool:
    """
    Heuristic: does this shell command look like an actual verification step
    (run the tests / lint the code) rather than an incidental use of the words
    "test" or "verify"?  We look at the leading program / well-known test
    runners rather than substring-matching anywhere in the command, so e.g.
    ``echo "running test"`` does NOT count as a verification.
    """
    import re

    cmd = (cmd or "").strip()
    if not cmd:
        return False
    body = re.split(r"(?:&&|\|\||;)", cmd)[-1].strip()  # last chain segment
    body = re.sub(r"^[A-Za-z_][A-Za-z0-9_]*=\S+\s+", "", body)  # drop VAR=val prefix
    tokens = body.split()
    program = tokens[0] if tokens else ""
    known_test_runners = {
        "pytest", "unittest", "npm", "yarn", "pnpm",
        "vitest", "jest", "playwright", "tox", "nox", "go", "cargo",
        "mvn", "gradle", "make", "rake", "rspec", "minitest",
    }
    # `python -m pytest` / `python -m unittest` style invocation
    if program in {"python", "python3"}:
        if "-m" in tokens and len(tokens) > 2 and tokens[tokens.index("-m") + 1] in known_test_runners:
            return True
        return False
    return program in known_test_runners


def execute_tool(tool_name: str, args: Dict[str, Any], item_id: str) -> Tuple[bool, str]:
    """
    Executes a specific tool using native Python system calls.

    Returns ``(is_done, result_text)``.  ``is_done=True`` signals the executor
    loop that the current task is complete (a COMPLETED entry is logged and we
    move to the next planned task).  Completion semantics per tool:

    * ``write_file``  -> done when the file is written successfully.
    * ``patch``       -> done when the file is patched successfully.
    * ``terminal``    -> done when the command is a real verification step
      (a recognised test runner) AND it exits 0.
    * ``read_file``   -> never done on its own; it's an information-gathering
      step that feeds the next turn.
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

            # A passing verification command means the task is genuinely done.
            if _is_verification_command(cmd):
                return True, f"Verification successful:\n{output}"

            return False, f"TOOL RESULT (terminal):\n{output}"

        elif tool_name == "write_file":
            path = args.get("path")
            content = args.get("content", "")
            if not path: return False, "ERROR: No path provided"

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
