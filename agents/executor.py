"""
Executor Agent — The implementation engine.
Implements the ANALYZE -> PLAN -> EXECUTE -> VERIFY loop.
"""

import os
import logging
import json
from typing import List, Dict, Any
from agents.llm_client import LLMClient
from agents.executor_planner import ExecutorPlanner
from agents.executor_diagnostics import ExecutorDiagnostics

logger = logging.getLogger(__name__)

class ExecutorAgent:
    def __init__(self, config_path: str):
        """
        Initialize the Executor Agent.
        """
        self.llm = LLMClient(config_path=config_path)
        self.planner = ExecutorPlanner(self.llm)
        self.diagnostics = ExecutorDiagnostics(self.llm)
        self.checklist: List[Dict[str, Any]] = []
        self.implementation_log: List[str] = []
        self.retry_counts: Dict[str, int] = {}
        self.MAX_RETRIES = 3

    def execute(self, item_id: str, spec_content: str, arch_content: str) -> bool:
        """
        Main entry point for the Executor Agent.
        Returns True on SUCCESS, False on FAILURE.
        """
        logger.info(f"Executor Agent starting work on {item_id}")
        
        try:
            # 1. ANALYZE & PLAN
            self._analyze_phase(item_id, spec_content, arch_content)
            
            # 2. EXECUTE & VERIFY (Iterative loop)
            self._execution_loop(item_id)
            
            # 3. FINALIZATION
            self._finalize_phase(item_id)
            return True

        except Exception as e:
            logger.error(f"Executor Agent failed for {item_id}: {str(e)}")
            self._report_failure(item_id, str(e))
            return False

    def _analyze_phase(self, item_id: str, spec_content: str, arch_content: str):
        """
        Analyze the requirements and generate the checklist.
        """
        logger.info(f"[{item_id}] Phase: ANALYZING & PLANNING")
        self.checklist = self.planner.create_checklist(spec_content, arch_content)
        logger.info(f"[{item_id}] Generated checklist with {len(self.checklist)} tasks.")

    def _execution_loop(self, item_id: str):
        logger.info(f"[{item_id}] Phase: EXECUTING")
        
        for task in self.checklist:
            if task.get("done"):
                continue
                
            logger.info(f"[{item_id}] Executing task: {task['task']}")
            
            # Real Implementation: A loop for multi-turn reasoning per task
            success = self._perform_task_multi_turn(task, item_id)
            
            if success:
                task["done"] = True
                self.implementation_log.append(f"COMPLETED: {task['task']}")
            else:
                # Handle retries
                task_name = task['task']
                self.retry_counts[task_name] = self.retry_counts.get(task_name, 0) + 1
                
                if self.retry_counts[task_name] > self.MAX_RETRIES:
                    raise RuntimeError(f"Max retries reached for task: {task_name}")
                
                logger.warning(f"[{item_id}] Task failed. Retry {self.retry_counts[task_name]}/{self.MAX_RETRIES}...")
                # We don't set task["done"] = True here, so the loop will retry it
                # In a real implementation, we'd want to pass the error back to the LLM

    def _perform_task_multi_turn(self, task: Dict[str, Any], item_id: str) -> bool:
        """
        A multi-turn reasoning loop for a single task.
        Uses the LLM to iterate through tool calls until the task is finished.
        """
        attempts = 0
        max_attempts_per_task = 5 # Prevent infinite loops
        
        task_context = f"Current Task: {task['task']}\n"

        while attempts < max_attempts_per_task:
            attempts += 1
            logger.info(f"[{item_id}] Task attempt {attempts}/{max_attempts_per_task}")

            # 1. Prepare Workspace Context
            workspace_files = []
            for root, dirs, files in os.walk(os.getcwd()):
                if any(x in root for x in ["venv", "node_modules", ".git"]):
                    continue
                for f in files:
                    workspace_files.append(os.path.relpath(os.path.join(root, f), os.getcwd()))
            
            context = f"""
Current Workspace Files:
{chr(10).join(workspace_files)}

{task_context}
"""

            # 2. Define tools
            tools_description = """
Available Tools:
- `terminal(command)`: Run a shell command. Returns stdout/stderr.
- `write_file(path, content)`: Write content to a file.
- `patch(path, old_string, new_string)`: Find and replace text in a file.
- `read_file(path)`: Read the contents of a file.

You must respond with a JSON object representing the tool call.
Example response:
{"tool": "terminal", "args": {"command": "ls -la"}}
"""
            system_prompt = f"You are the Hermes Executor Agent. Complete the task. {tools_description}"

            try:
                response_text = self.llm.chat(system_prompt=system_prompt, user_prompt=context)
                
                # Clean response
                clean_response = response_text.strip()
                if clean_response.startswith("```json"):
                    clean_response = clean_response.split("```json")[1].split("```")[0].strip()
                elif clean_response.startswith("```"):
                    clean_response = clean_response.split("```")[1].split("```")[0].strip()
                
                action = json.loads(clean_response)
                tool_name = action.get("tool")
                args = action.get("args", {})

                logger.info(f"[{item_id}] Decided: {tool_name}({args})")

                # 3. Execute tool
                if tool_name == "terminal":
                    from hermes_tools import terminal
                    result = terminal(command=args["command"])
                    # Feed result back to context for next turn
                    task_context += f"\nTOOL RESULT (terminal): {result.get('output')}\n"
                    if result.get("exit_code") == 0:
                        # If the command was a verification command (e.g. 'pytest'), we might be done
                        if "test" in args["command"] or "verify" in args["command"]:
                            return True
                        # Otherwise, continue to next turn
                    else:
                        task_context += f"\nERROR: {result.get('output')}\n"
                        
                        # 4. DIAGNOSTICS: Suggest a fix
                        suggestion = self.diagnostics.diagnose_error(
                            error_message=result.get('output', 'Unknown error'),
                            context=task_context
                        )
                        if suggestion:
                            logger.info(f"[{item_id}] Diagnostic suggestion: {suggestion}")
                            task_context += f"\nDIAGNOSTIC SUGGESTION: {suggestion}\n"
                        else:
                            task_context += "\nDIAGNOSTIC: No specific suggestion found. Try a different approach.\n"
                
                elif tool_name == "write_file":
                    from hermes_tools import write_file
                    write_file(path=args["path"], content=args["content"])
                    task_context += f"\nSUCCESS: Wrote to {args['path']}\n"
                
                elif tool_name == "patch":
                    from hermes_tools import patch
                    patch(path=args["path"], old_string=args["old_string"], new_string=args["new_string"])
                    task_context += f"\nSUCCESS: Patched {args['path']}\n"
                
                elif tool_name == "read_file":
                    from hermes_tools import read_file
                    content = read_file(path=args["path"])
                    task_context += f"\nFILE CONTENT ({args['path']}):\n{content}\n"
                
                else:
                    logger.error(f"[{item_id}] Unknown tool: {tool_name}")
                    return False

            except Exception as e:
                logger.error(f"[{item_id}] Turn error: {str(e)}")
                task_context += f"\nERROR: {str(e)}\n"

        return False # Max attempts reached

    def _perform_task(self, task: Dict[str, Any], item_id: str) -> bool:
        # DEPRECATED in favor of _perform_task_multi_turn
        return self._perform_task_multi_turn(task, item_id)

    def _finalize_phase(self, item_id: str):
        logger.info(f"[{item_id}] Phase: FINALIZING")
        # Generate execution_report.md
        report_path = os.path.join(os.getcwd(), "automation-ideas", "requirements", item_id, "execution_report.md")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        
        with open(report_path, "w") as f:
            f.write(f"# Execution Report for {item_id}\n\n")
            f.write("## Implementation Summary\n")
            for entry in self.implementation_log:
                f.write(f"- {entry}\n")
        
        logger.info(f"[{item_id}] Execution report written to {report_path}")

    def _report_failure(self, item_id: str, error_message: str):
        logger.error(f"[{item_id}] Reporting FAILURE: {error_message}")
        report_path = os.path.join(os.getcwd(), "automation-ideas", "requirements", item_id, "execution_report.md")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        
        with open(report_path, "w") as f:
            f.write(f"# Execution Report for {item_id}\n\n")
            f.write(f"## STATUS: FAILURE\n\n")
            f.write(f"### Error Details\n{error_message}\n")

def executor_idea(item_id: str) -> int:
    """
    Entry point for the Orchestrator.
    Returns 100 on SUCCESS, 0 on FAILURE.
    """
    import yaml
    import os
    config_path = os.path.join(os.getcwd(), "config.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    executor = ExecutorAgent(config_path=config_path)
    
    # Real implementation: Load spec and architecture from the requirement directory
    req_dir = os.path.join(os.getcwd(), "automation-ideas", "requirements", item_id)
    spec_path = os.path.join(req_dir, "spec.md")
    arch_path = os.path.join(req_dir, "architecture.md")
    
    if not os.path.exists(spec_path) or not os.path.exists(arch_path):
        print(f"ERROR: Missing spec.md or architecture.md for {item_id}")
        return 0

    with open(spec_path, "r") as f:
        spec_content = f.read()
    with open(arch_path, "r") as f:
        arch_content = f.read()
    
    success = executor.execute(item_id, spec_content, arch_content)
    return 100 if success else 0
