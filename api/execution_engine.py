import logging
import re
import threading
import uuid
import json
from typing import Dict, Any, Optional
from api.workflow_state_manager import WorkflowStateManager
from api.integration_hub import IntegrationHub
from api.escalation_manager import EscalationManager
from api.retry_manager import RetryManager
from api.models.automation import HITL_STEP_TYPE, migrate_step

logger = logging.getLogger(__name__)

class ExecutionEngine:
    """
    The core orchestration engine that executes WorkflowTemplates as WorkflowRuns.
    Implements the Step Execution Cycle defined in engine-spec.md.
    """
    def __init__(self, state_manager: WorkflowStateManager, hub: IntegrationHub,
                 escalator: EscalationManager, retry_manager: Optional['RetryManager'] = None):
        self.state_manager = state_manager
        self.hub = hub
        self.escalator = escalator
        self.retry_manager = retry_manager
        self.run_manager = state_manager.runs
        # Pending retry timers, keyed by run_id. Timers live in memory only and
        # are not persisted across restarts. A run whose timer was lost in a
        # restart is RUNNING with no driver; the startup reaper in api/main.py
        # marks such runs FAILED.
        self._timers: Dict[str, threading.Timer] = {}
        self._timers_lock = threading.Lock()
        # One non-blocking claim per run, so a timer firing and a resume cannot
        # advance the same run concurrently.
        self._claims: Dict[str, threading.Lock] = {}
        self._claims_lock = threading.Lock()

    def start_run(self, template_id: str, inputs: Dict[str, Any]) -> str:
        """
        Initializes and starts a new workflow run.
        """
        template = self.state_manager.templates.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        run_id = f"run_{uuid.uuid4().hex[:8]}"
        run_data = {
            "template_id": template_id,
            "status": "RUNNING",
            "current_step_index": 0,
            "inputs": inputs,
            "context": {},
            "results": {}
        }

        # A run id must never be handed back for a run that was not saved, or
        # every later lookup 404s. Write errors (e.g. CorruptStateError) are
        # re-raised as RuntimeError so the route returns a 500.
        try:
            created = self.run_manager.create_run(run_id, run_data)
        except Exception as exc:
            logger.exception("Run %s for template %s could not be persisted", run_id, template_id)
            raise RuntimeError(f"Run {run_id} could not be saved; the workflow was not started") from exc
        if not created:
            logger.error("Run %s for template %s was not saved", run_id, template_id)
            raise RuntimeError(f"Run {run_id} could not be saved; the workflow was not started")
        self.run_manager.log_event(run_id, "RUN_STARTED", {"template_id": template_id, "inputs": inputs})
        
        # Trigger the first step asynchronously (simulated here by a direct call)
        self.process_next_step(run_id)
        
        return run_id

    def resume_run_by_item_id(self, item_id: str):
        """
        Resumes a workflow run linked to a specific Kanban item (e.g., a recovery task).
        """
        item = self.state_manager.get_item_details(item_id)
        if not item:
            logger.error(f"Resume failed: Item {item_id} not found on board")
            raise ValueError(f"Item {item_id} not found on board")
 
        # Try to find the linked run ID in the item data
        run_id = item.get("linked_run_id")
        
        # Fallback: Check the binding manager if it's not in the item data
        if not run_id:
            run_id = self.state_manager.get_run_id_for_item(item_id)
            
        if not run_id:
            logger.error(f"Resume failed: No linked_run_id found for item {item_id}. Item data: {item}")
            raise ValueError(f"No active run found for item {item_id}")
 
        logger.info(f"Resuming linked run {run_id} for item {item_id}")

        # A run paused at a HITL step (ORCHESTRATOR_TASK) has had that step
        # answered by the human, so move past it. Without this the resumed run
        # would re-execute the same step and pause again forever. Runs resumed
        # from any other state (e.g. BLOCKED after a failure) retry the step.
        updates: Dict[str, Any] = {"status": "RUNNING"}
        run = self.run_manager.get_run(run_id)
        if run and run.get("status") == "WAITING_FOR_HUMAN":
            template = self.state_manager.templates.get_template(run["template_id"]) or {}
            steps = template.get("steps", [])
            idx = run.get("current_step_index", 0)
            if idx < len(steps) and steps[idx].get("type") == "ORCHESTRATOR_TASK":
                updates["current_step_index"] = idx + 1
                self.run_manager.log_event(
                    run_id, "STEP_END",
                    {"step": steps[idx].get("name", f"Step {idx}"), "result": "HITL_RESOLVED"},
                )

        # A manual resume supersedes any pending automatic retry.
        self._cancel_timer(run_id)

        # Mark run as RUNNING again and trigger next step
        self.run_manager.update_run(run_id, updates)
        self.process_next_step(run_id)
        return run_id
 
    def process_next_step(self, run_id: str):
        """
        The main loop that executes the next step in a run's lifecycle.
        """
        claim = self._claim_for(run_id)
        if not claim.acquire(blocking=False):
            logger.info(f"Run {run_id} is already being advanced; skipping this trigger")
            return
        try:
            self._advance(run_id)
        finally:
            claim.release()

    def _claim_for(self, run_id: str) -> threading.Lock:
        with self._claims_lock:
            claim = self._claims.get(run_id)
            if claim is None:
                claim = threading.Lock()
                self._claims[run_id] = claim
            return claim

    def _cancel_timer(self, run_id: str) -> None:
        with self._timers_lock:
            timer = self._timers.pop(run_id, None)
        if timer is not None:
            timer.cancel()

    def _schedule_retry(self, run_id: str, delay_minutes: int) -> None:
        """Replace any pending retry for this run with a new one."""
        def fire():
            with self._timers_lock:
                # Only the timer that still owns the slot may act. A cancelled or
                # replaced timer must not advance the run.
                if self._timers.get(run_id) is not timer:
                    return
                self._timers.pop(run_id, None)
            # The timer thread has no caller to report to, so any failure here
            # (missing template, corrupt state file, ...) must be contained:
            # log it and block the run so it does not sit RUNNING forever.
            # process_next_step releases the run claim in its own finally.
            try:
                self.process_next_step(run_id)
            except Exception as exc:
                logger.exception("Retry timer for run %s failed", run_id)
                self._block_after_crash(run_id, exc)

        with self._timers_lock:
            previous = self._timers.pop(run_id, None)
            if previous is not None:
                previous.cancel()
            timer = threading.Timer(delay_minutes * 60, fire)
            timer.daemon = True
            self._timers[run_id] = timer
        timer.start()

    def _advance(self, run_id: str):
        """
        Executes the step at the current index. Callers must hold the run claim.
        """
        run = self.run_manager.get_run(run_id)
        if not run or run["status"] != "RUNNING":
            return

        template = self.state_manager.templates.get_template(run["template_id"])
        if template is None:
            # A deleted template cannot be retried into success, so block the
            # run now and escalate instead of raising from a timer thread.
            self._block(run_id, "Template lookup", f"Template {run['template_id']} not found")
            return
        steps = template.get("steps", [])
        idx = run["current_step_index"]

        if idx >= len(steps):
            self._cancel_timer(run_id)
            self.run_manager.update_run(run_id, {"status": "COMPLETED"})
            self.run_manager.log_event(run_id, "RUN_COMPLETED", {})
            return

        # Legacy templates name the integration in ``type``; migrate them in code
        # so already-saved templates keep running (the stored file is not rewritten).
        step = migrate_step(steps[idx])
        step_name = step.get("name", f"Step {idx}")

        # 1. Resolve Context
        resolved_config = self._resolve_context(step.get("config", {}), run)

        # 2. Dispatch to Adapter
        try:
            # Check if this is an Orchestrator Task (HITL). This is the only step
            # kind that ``type`` marks; it never touches the hub.
            if step.get("type") == HITL_STEP_TYPE:
                self.run_manager.log_event(run_id, "STEP_START", {"step": step_name, "type": HITL_STEP_TYPE})
                self._handle_hitl_step(run_id, step)
                return

            adapter = step.get("adapter")
            action = step.get("action")
            if not (isinstance(adapter, str) and adapter.strip()):
                raise ValueError(f"Step '{step_name}' has no adapter; a step must name the adapter it runs on")
            if not (isinstance(action, str) and action.strip()):
                raise ValueError(f"Step '{step_name}' has no action; a step must name the action to run")
            self.run_manager.log_event(run_id, "STEP_START", {"step": step_name, "adapter": adapter, "action": action})

            # Dispatch on the step's adapter and action
            result = self.hub.execute_action(adapter, action, resolved_config)

            # P0-3: the hub reports adapter failures (unsupported action, an
            # adapter exception, an unloadable module) as
            # ``{"status": "error", ...}`` instead of raising. Route that
            # through the same failure path as an exception, with the hub's
            # error text as the reason, or a run whose every step failed
            # marches on to COMPLETED. Anything else (a success status or a
            # legacy plain result dict) advances as before.
            if isinstance(result, dict) and result.get("status") == "error":
                detail = result.get("result") or result.get("logs") or "unknown error"
                raise RuntimeError(f"adapter reported an error: {detail}")

            # 3. Record Outcome
            self.run_manager.log_event(run_id, "STEP_END", {"step": step_name, "result": result})
            
            # Update run context with result for future steps
            run_context = run.get("context", {})
            run_context[step_name] = result
            
            # Move to next step. The retry budget is per step, so a step that
            # succeeds resets it; otherwise failures across steps would add up.
            self.run_manager.update_run(run_id, {
                "current_step_index": idx + 1,
                "context": run_context,
                "retry_count": 0,
            })
            
            # Continue with the next step. The claim is still held, so this must
            # call _advance directly, not process_next_step (which would deadlock).
            self._advance(run_id)

        except Exception as e:
            self._handle_failure(run_id, step_name, e)

    # A placeholder name cannot contain braces, so "{{a}}-{{b}}" is two placeholders.
    _PLACEHOLDER = re.compile(r"\{\{([^{}]*)\}\}")

    def _resolve_context(self, config: Any, run: Dict[str, Any]) -> Any:
        """
        Replaces {{variable}} placeholders in string values of ``config``.

        The config is walked recursively. Substitution happens only inside string
        values, never on the JSON text, so quotes or backslashes in an input cannot
        break out of a string or inject keys. A string that is exactly one
        placeholder is replaced by the raw value, keeping its type. Otherwise the
        value is inserted as text (JSON for dicts, lists, booleans and None).
        Unknown placeholders are left unchanged.
        """
        def lookup(raw_name: str):
            # Priority: Context (previous steps) -> Inputs (start of run)
            name = raw_name.strip()
            context = run.get("context", {}) or {}
            if name in context:
                return True, context[name]
            inputs = run.get("inputs", {}) or {}
            if name in inputs:
                return True, inputs[name]
            return False, None

        def as_text(value: Any) -> str:
            if isinstance(value, str):
                return value
            if isinstance(value, (dict, list, bool)) or value is None:
                return json.dumps(value)
            return str(value)

        def resolve(node: Any) -> Any:
            if isinstance(node, dict):
                return {key: resolve(val) for key, val in node.items()}
            if isinstance(node, list):
                return [resolve(item) for item in node]
            if not isinstance(node, str):
                return node

            whole = self._PLACEHOLDER.fullmatch(node)
            if whole:
                found, value = lookup(whole.group(1))
                return value if found else node

            def replace_match(match):
                found, value = lookup(match.group(1))
                return as_text(value) if found else match.group(0)

            return self._PLACEHOLDER.sub(replace_match, node)

        return resolve(config)

    def _handle_hitl_step(self, run_id: str, step: Dict[str, Any]):
        """
        Pauses the run and escalates to the Orchestrator.
        """
        step_name = step.get("name", "HITL Step")
        target_phase = step.get("target_phase", "DISCOVERY")
        
        # Update run status to WAITING
        self.run_manager.update_run(run_id, {"status": "WAITING_FOR_HUMAN"})
        
        # Spawn the orchestrator task
        self.escalator.escalate_to_orchestrator(
            run_id=run_id,
            step_name=step_name,
            error_message=f"Manual intervention required for phase: {target_phase}"
        )
        
        self.run_manager.log_event(run_id, "RUN_PAUSED", {"reason": "HITL_STEP", "step": step_name})

    def _handle_failure(self, run_id: str, step_name: str, error: Exception):
        """
        Implements the failure classification from engine-spec.md.
        When a RetryManager is wired in, failures are retried at 5/10/15‑minute
        intervals before escalating to BLOCKED.
        """
        error_msg = str(error)
        logger.error(f"Run {run_id} failed at step {step_name}: {error_msg}")

        # If a RetryManager is available, attempt the standard retry policy
        if self.retry_manager is not None:
            delay = self.retry_manager.should_retry(run_id)
            if delay is not None:
                self.retry_manager.record_failure(run_id, error_msg)
                # Schedule a retry after the prescribed interval
                self._schedule_retry(run_id, delay)
                logger.info(
                    f"Retry scheduled for run {run_id} in {delay} minutes"
                )
                return

        # No retry manager or retries exhausted — escalate to BLOCKED
        self._block(run_id, step_name, error_msg)

    def _block(self, run_id: str, step_name: str, error_msg: str) -> None:
        """Move the run to BLOCKED, escalate it to the orchestrator and log why."""
        self._cancel_timer(run_id)
        self.run_manager.update_run(run_id, {"status": "BLOCKED"})

        self.escalator.escalate_to_orchestrator(
            run_id=run_id,
            step_name=step_name,
            error_message=error_msg
        )

        self.run_manager.log_event(run_id, "RUN_BLOCKED", {"error": error_msg})

    def _block_after_crash(self, run_id: str, exc: Exception) -> None:
        """Best-effort BLOCKED transition after an unexpected error on a timer thread.

        Each step is attempted even when an earlier one fails (the run file may
        be the very thing that is corrupt, while the board file is fine), and
        nothing is raised: the timer thread has nobody to report to, and the
        original error is already logged by the caller.
        """
        error_msg = f"Unexpected error while retrying: {exc}"
        self._cancel_timer(run_id)
        steps = (
            ("block the run", lambda: self.run_manager.update_run(run_id, {"status": "BLOCKED"})),
            ("escalate the run", lambda: self.escalator.escalate_to_orchestrator(
                run_id=run_id, step_name="Retry timer", error_message=error_msg)),
            ("log RUN_BLOCKED", lambda: self.run_manager.log_event(run_id, "RUN_BLOCKED", {"error": error_msg})),
        )
        for label, action in steps:
            try:
                action()
            except Exception:
                logger.exception("Could not %s for run %s after a timer failure", label, run_id)
