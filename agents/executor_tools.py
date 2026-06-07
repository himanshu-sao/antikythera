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

def execute_tool(tool_name: str, args: Dict[str, Any], item_id: str) -> Tuple[bool, str]:
    """
    Executes a specific tool using native Python system calls.
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
            
            # If the command was a verification command, we mark as successful
            if "test" in cmd or "verify" in cmd:
                return True, f"Verification successful:\n{output}"
            
            return False, f"TOOL RESULT (terminal):\n{output}"
        
        elif tool_name == "write_file":
            path = args.get("path")
            content = args.get("content", "")
            if not path: return False, "ERROR: No path provided"
            
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return False, f"SUCCESS: Wrote to {path}"
        
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
            return False, f"SUCCESS: Patched {path}"
        
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
