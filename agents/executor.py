import os
import json
import logging
from typing import List, Dict, Any, Tuple
from agents.llm_client import LLMClient
from agents.executor_planner import ExecutorPlanner
from agents.executor_diagnostics import ExecutorDiagnostics
from agents.executor_tools import get_workspace_files, get_tools_description, execute_tool

logger = logging.getLogger(__name__)

class ExecutorAgent:
    def __init__(self, config_path: str):
        self.llm = LLMClient(config_path=config_path)
        self.planner = ExecutorPlanner(self.llm)
        self.diagnostics = ExecutorDiagnostics(self.llm)
        self.checklist: List[Dict[str, Any]] = []
        self.implementation_log: List[str] = []
        self.retry_counts: Dict[str, int] = {}
        self.MAX_RETRIES = 3

    def execute(self, item_id: str, spec_content: str, arch_content: str) -> bool:
        logger.info(f"Executor Agent starting work on {item_id}")
        try:
            self._analyze_phase(item_id, spec_content, arch_content)
            self._execution_loop(item_id)
            self._finalize_phase(item_id)
            return True
        except Exception as e:
            logger.error(f"Executor Agent failed for {item_id}: {str(e)}")
            self._report_failure(item_id, str(e))
            return False

    def _analyze_phase(self, item_id: str, spec_content: str, arch_content: str):
        logger.info(f"[{item_id}] Phase: ANALYZING & PLANNING")
        self.checklist = self.planner.create_checklist(spec_content, arch_content)
        logger.info(f"[{item_id}] Generated checklist with {len(self.checklist)} tasks.")

    def _execution_loop(self, item_id: str):
        logger.info(f"[{item_id}] Phase: EXECUTING")
        for task in self.checklist:
            if task.get("done"):
                continue
            
            logger.info(f"[{item_id}] Executing task: {task['task']}")
            success = self._perform_task_multi_turn(task, item_id)
            
            if success:
                task["done"] = True
                self.implementation_log.append(f"COMPLETED: {task['task']}")
            else:
                task_name = task['task']
                self.retry_counts[task_name] = self.retry_counts.get(task_name, 0) + 1
                if self.retry_counts[task_name] > self.MAX_RETRIES:
                    raise RuntimeError(f"Max retries reached for task: {task_name}")
                logger.warning(f"[{item_id}] Task failed. Retry {self.retry_counts[task_name]}/{self.MAX_RETRIES}...")

    def _perform_task_multi_turn(self, task: Dict[str, Any], item_id: str) -> bool:
        attempts = 0
        max_attempts_per_task = 5
        task_context = f"Current Task: {task['task']}\n"

        while attempts < max_attempts_per_task:
            attempts += 1
            logger.info(f"[{item_id}] Task attempt {attempts}/{max_attempts_per_task}")

            workspace_files = get_workspace_files()
            context = f"Current Workspace Files:\n{chr(10).join(workspace_files)}\n\n{task_context}"
            
            system_prompt = f"You are the Antikythera Executor Agent. Complete the task. {get_tools_description()}"

            try:
                response_text = self.llm.chat(system_prompt=system_prompt, user_prompt=context)
                clean_response = response_text.strip()
                if clean_response.startswith("```json"):
                    clean_response = clean_response.split("```json")[1].split("```")[0].strip()
                elif clean_response.startswith("```"):
                    clean_response = clean_response.split("```")[1].split("```")[0].strip()
                
                action = json.loads(clean_response)
                tool_name = action.get("tool")
                args = action.get("args", {})

                logger.info(f"[{item_id}] Decided: {tool_name}({args})")
                
                # Use the extracted tool execution logic
                is_done, result_text = execute_tool(tool_name, args, item_id)
                
                if is_done:
                    return True
                
                task_context += f"\n{result_text}\n"
                
                if "ERROR" in result_text:
                    suggestion = self.diagnostics.diagnose_error(
                        error_message=result_text,
                        context=task_context
                    )
                    if suggestion:
                        logger.info(f"[{item_id}] Diagnostic suggestion: {suggestion}")
                        task_context += f"\nDIAGNOSTIC SUGGESTION: {suggestion}\n"
                    else:
                        task_context += "\nDIAGNOSTIC: No specific suggestion found. Try a different approach.\n"

            except Exception as e:
                logger.error(f"[{item_id}] Turn error: {str(e)}")
                task_context += f"\nERROR: {str(e)}\n"

        return False

    def _finalize_phase(self, item_id: str):
        logger.info(f"[{item_id}] Phase: FINALIZING")
        report_path = os.path.join(os.getcwd(), "automation-ideas", "requirements", item_id, "execution_report.md")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w") as f:
            f.write(f"# Execution Report for {item_id}\n\n## Implementation Summary\n")
            for entry in self.implementation_log:
                f.write(f"- {entry}\n")
        logger.info(f"[{item_id}] Execution report written to {report_path}")

    def _report_failure(self, item_id: str, error_message: str):
        logger.error(f"[{item_id}] Reporting FAILURE: {error_message}")
        report_path = os.path.join(os.getcwd(), "automation-ideas", "requirements", item_id, "execution_report.md")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w") as f:
            f.write(f"# Execution Report for {item_id}\n\n## STATUS: FAILURE\n\n### Error Details\n{error_message}\n")

def executor_idea(item_id: str) -> int:
    import yaml
    config_path = os.path.join(os.getcwd(), "config.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    executor = ExecutorAgent(config_path=config_path)
    req_dir = os.path.join(os.getcwd(), "automation-ideas", "requirements", item_id)
    spec_path = os.path.join(req_dir, "spec.md")
    arch_path = os.path.join(req_dir, "architecture.md")
    
    if not os.path.exists(spec_path) or not os.path.exists(arch_path):
        return 0

    with open(spec_path, "r") as f:
        spec_content = f.read()
    with open(arch_path, "r") as f:
        arch_content = f.read()
    
    success = executor.execute(item_id, spec_content, arch_content)
    return 100 if success else 0
