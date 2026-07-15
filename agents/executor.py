import os
import json
import logging
from typing import List, Dict, Any, Tuple
from agents.llm_client import LLMClient
from agents.executor_planner import ExecutorPlanner
from agents.executor_diagnostics import ExecutorDiagnostics
from agents.executor_tools import get_workspace_files, get_tools_description, execute_tool
from api.managers.run_manager import RunManager

logger = logging.getLogger(__name__)

class ExecutorAgent:
    def __init__(self, config_path: str, run_manager: RunManager, run_id: str):
        self.llm = LLMClient(config_path=config_path)
        self.planner = ExecutorPlanner(self.llm)
        self.diagnostics = ExecutorDiagnostics(self.llm)
        self.run_manager = run_manager
        self.run_id = run_id
        self.checklist: List[Dict[str, Any]] = []
        self.implementation_log: List[str] = []
        # P3.2.6 Phase 1: the per-task outer-retry layer is gone.  We had two
        # retry levels — an inner "5 turns/task" loop AND an outer "3 retries of
        # the whole inner loop" wrapper — giving 4 × 5 = 20 LLM turns before one
        # stuck task hard-failed the run.  Now there is a single bounded loop
        # per task (MAX_TASK_ATTEMPTS, see _perform_task_multi_turn) and no
        # outer retry. _execution_loop runs every task to completion-or-
        # exhaustion and never raises; the honest _all_tasks_complete() decides
        # the run's success.  A stuck task costs at most MAX_TASK_ATTEMPTS turns,
        # not 4× that.
        self.MAX_TASK_ATTEMPTS = 5

    def _log_progress(self, message: str):
        self.run_manager.log_event(self.run_id, "AGENT_PROGRESS", {"message": message}, actor="executor")
        logger.info(f"[{self.run_id}] {message}")

    def execute(self, item_id: str, spec_content: str, arch_content: str) -> bool:
        logger.info(f"Executor Agent starting work on {item_id}")
        try:
            self._log_progress("Starting analysis and planning phase...")
            self._analyze_phase(item_id, spec_content, arch_content)
            # Fail loud on an empty plan.  An empty checklist means the planner
            # LLM call produced no usable tasks (empty/unparseable output — the
            # planner now returns [] instead of a stub 3-task placeholder, see
            # agents/executor_planner.py).  Running _execution_loop over [] is a
            # silent no-op that _finalize_phase would write up as a SUCCESS-style
            # "## Implementation Summary" with zero COMPLETED entries — exactly the
            # fake-success empty-report bug P3.2/P3.2.3 is killing.  Raise here so
            # the surrounding except calls _report_failure (a FAILURE report with
            # no COMPLETED entries) and execute() returns False -> executor_idea 0.
            if not self.checklist:
                raise RuntimeError(
                    "Planner produced an empty checklist; refusing to execute "
                    "an empty/stub plan (no real tasks to perform)."
                )
            self._log_progress("Planning complete. Starting execution loop...")
            self._execution_loop(item_id)
            self._log_progress("Execution loop finished. Finalizing...")
            self._finalize_phase(item_id)
            # "Done" means every planned task actually completed.  A single
            # failed task is silently skipped by _execution_loop but must not
            # read as success -- otherwise the pipeline marks an item DONE with
            # an incomplete execution_report.md (the empty-report bug P2.3
            # surfaced).
            return self._all_tasks_complete()
        except Exception as e:
            logger.error(f"Executor Agent failed for {item_id}: {str(e)}")
            self._report_failure(item_id, str(e))
            return False

    def _all_tasks_complete(self) -> bool:
        """True iff the checklist is non-empty and every task is done."""
        if not self.checklist:
            return False
        return all(bool(t.get("done")) for t in self.checklist)

    def _analyze_phase(self, item_id: str, spec_content: str, arch_content: str):
        logger.info(f"[{item_id}] Phase: ANALYZING & PLANNING")
        self._log_progress("Analyzing requirements and generating checklist...")
        self.checklist = self.planner.create_checklist(spec_content, arch_content)
        logger.info(f"[{item_id}] Generated checklist with {len(self.checklist)} tasks.")

    def _execution_loop(self, item_id: str):
        logger.info(f"[{item_id}] Phase: EXECUTING")
        # P3.2.6 Phase 1: run EVERY task to completion-or-exhaustion.  We do NOT
        # raise on a stuck task — the previous behaviour (outer 3× retry then a
        # hard ``raise``) aborted the run mid-way on the first unfinishable task,
        # hiding later COMPLETED entries.  Now a task that can't reach is_done in
        # MAX_TASK_ATTEMPTS simply stays task["done"]=False, a partial-progress
        # entry is logged, and the run continues.  The honest verdict is then
        # _all_tasks_complete() (False if anything is unfinished), which is what
        # the handler already keys the stage transition on (confidence==0 ->
        # REVIEW_TEST / REVIEW_SPEC human gate).
        for task in self.checklist:
            if task.get("done"):
                continue

            logger.info(f"[{item_id}] Executing task: {task['task']}")
            self._log_progress(f"Executing task: {task['task']}")
            success = self._perform_task_multi_turn(task, item_id)

            if success:
                task["done"] = True
                self.implementation_log.append(f"COMPLETED: {task['task']}")
            else:
                self._log_progress(
                    f"Task incomplete after {self.MAX_TASK_ATTEMPTS} attempts; "
                    f"leaving undone: {task['task']}"
                )
                logger.warning(
                    "[%s] Task incomplete after %d attempts: %s",
                    item_id, self.MAX_TASK_ATTEMPTS, task["task"],
                )

    def _perform_task_multi_turn(self, task: Dict[str, Any], item_id: str) -> bool:
        attempts = 0
        task_context = f"Current Task: {task['task']}\n"

        while attempts < self.MAX_TASK_ATTEMPTS:
            attempts += 1
            logger.info(f"[{item_id}] Task attempt {attempts}/{self.MAX_TASK_ATTEMPTS}")
            self._log_progress(f"Task attempt {attempts}/{self.MAX_TASK_ATTEMPTS} for: {task['task']}")

            workspace_files = get_workspace_files()
            context = f"Current Workspace Files:\n{chr(10).join(workspace_files)}\n\n{task_context}"

            system_prompt = (
                "You are the Antikythera Executor Agent. Complete the task by "
                "issuing exactly ONE tool call this turn. "
                + get_tools_description()
                + "\n\n### DECISION RULES (strict):\n"
                "- A task is COMPLETE only once you have written the target "
                "artifact using `write_file(path, content)` (full intended "
                "contents) or applied a `patch(path, old_string, new_string)` "
                "that landed. These are the only tools that complete a task.\n"
                "- If the task is to CREATE new content that is not yet in the "
                "file, or the file does not exist, use `write_file(path, content)` "
                "with the FULL intended file contents.\n"
                "- If you need to MODIFY existing content in a file that already "
                "exists, use `patch(path, old_string, new_string)` — NEVER rewrite "
                "the whole file when a small edit suffices.\n"
                "- Do NOT call `read_file` more than once per task, and never as "
                "the only action. `read_file` only gathers information; it does "
                "NOT complete the task.\n"
                "- `terminal(command)` runs a shell command for information or "
                "side effects (e.g. install a dependency); it does NOT by itself "
                "complete a task. Do not wait for a `terminal` run to mark a "
                "creation task done — write/patch the artifact instead.\n"
                "- `write_file` content must be real, complete file contents — "
                "empty, tiny, or placeholder/stub content is rejected.\n"
                "- Respond with ONLY a JSON object {\"tool\": ..., \"args\": {...}}. "
                "No prose, no markdown fences, no preamble."
            )

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
                self._log_progress(f"Decided to use tool: {tool_name}")
                
                # Use the extracted tool execution logic
                is_done, result_text = execute_tool(tool_name, args, item_id)
                
                if is_done:
                    return True
                
                task_context += f"\n{result_text}\n"

                # Error recovery hint.  This is the loop's only within-bounded-loop
                # recovery mechanism: when a tool turn errors, ask the diagnostic LLM
                # for a one-line corrective action and feed it back as context for
                # the next turn.  P3.2.6 Phase 1 kept the outer 3x retry layer
                # removed, so without this an errored turn would just re-prompt an
                # identical context until exhaustion.
                #
                # But the diagnostic is itself an LLM call, so it must respect the
                # MAX_TASK_ATTEMPTS budget: each diagnostic consumes one of the
                # remaining turns (attempts += 1 below).  This is what makes a
                # stuck task cost AT MOST MAX_TASK_ATTEMPTS total ``chat`` calls —
                # not 2x that (the hidden cost-multiplier the stub-content regression
                # test caught: every erroring turn fired a free diagnostics call,
                # inflating the real turn count to 10 for MAX_TASK_ATTEMPTS=5).
                # The ``and attempts < self.MAX_TASK_ATTEMPTS`` guard also stops us
                # blowing the budget on the very last turn (no point diagnosing an
                # error we cannot then act on).
                if "ERROR" in result_text and attempts < self.MAX_TASK_ATTEMPTS:
                    attempts += 1
                    self._log_progress(
                        f"Task attempt {attempts}/{self.MAX_TASK_ATTEMPTS} (diagnostic) "
                        f"for: {task['task']}"
                    )
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
        self._log_progress("Finalizing implementation and generating report...")
        report_path = os.path.join(os.getcwd(), "automation-ideas", "requirements", item_id, "execution_report.md")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w") as f:
            f.write(f"# Execution Report for {item_id}\n\n## Implementation Summary\n")
            for entry in self.implementation_log:
                f.write(f"- {entry}\n")
        logger.info(f"[{item_id}] Execution report written to {report_path}")

    def _report_failure(self, item_id: str, error_message: str):
        logger.error(f"[{item_id}] Reporting FAILURE: {error_message}")
        self._log_progress(f"FAILURE: {error_message}")
        report_path = os.path.join(os.getcwd(), "automation-ideas", "requirements", item_id, "execution_report.md")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w") as f:
            f.write(f"# Execution Report for {item_id}\n\n## STATUS: FAILURE\n\n### Error Details\n{error_message}\n")

def executor_idea(item_id: str, run_manager: RunManager, run_id: str) -> int:
    import yaml
    config_path = os.path.join(os.getcwd(), "config.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    executor = ExecutorAgent(config_path=config_path, run_manager=run_manager, run_id=run_id)
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
