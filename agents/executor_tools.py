import os
import json
import logging
from typing import List, Dict, Any, Tuple
from hermes_tools import terminal, write_file, patch, read_file

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
    Executes a specific tool and returns a tuple of (success, result_text).
    """
    try:
        if tool_name == "terminal":
            result = terminal(command=args["command"])
            output = result.get('output', 'No output')
            # If the command was a verification command (e.g. 'pytest'), we might be done
            if result.get("exit_code") == 0 and ("test" in args["command"] or "verify" in args["command"]):
                return True, f"Verification successful: {output}"
            
            if result.get("exit_code") != 0:
                return False, f"ERROR: {output}"
            return False, f"TOOL RESULT (terminal): {output}"
        
        elif tool_name == "write_file":
            write_file(path=args["path"], content=args["content"])
            return False, f"SUCCESS: Wrote to {args['path']}"
        
        elif tool_name == "patch":
            patch(path=args["path"], old_string=args["old_string"], new_string=args["new_string"])
            return False, f"SUCCESS: Patched {args['path']}"
        
        elif tool_name == "read_file":
            content = read_file(path=args["path"])
            return False, f"FILE CONTENT ({args['path']}):\n{content}"
        
        else:
            logger.error(f"[{item_id}] Unknown tool: {tool_name}")
            return False, f"Unknown tool: {tool_name}"

    except Exception as e:
        logger.error(f"[{item_id}] Tool execution error: {str(e)}")
        return False, f"ERROR: {str(e)}"
