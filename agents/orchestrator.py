import copy
import datetime
import logging
import asyncio
import os
from filelock import FileLock, Timeout
from agents import state as state_module
from agents.constants import REVIEW_STAGES, STAGE_AGENTS, STAGE_HANDLERS
from agents.notifications import notify_stage_transition
from agents.handlers import StageHandler
# Expose sub‑modules for test patches
import agents.refiner as refiner
import agents.architect as architect
import agents.tester as tester
# Ensure an event loop exists for async‑compatible tests
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

logger = logging.getLogger(__name__)

# 2.4 / T18: the API stores lowercase priorities (api/constants.py
# VALID_PRIORITIES). Ranks are matched case-insensitively; lower rank runs first.
PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_UNKNOWN_PRIORITY_RANK = 4

_MISSING = object()

# P2-12: consecutive handler failures after which an item is blocked and skipped.
MAX_CONSECUTIVE_FAILURES = 3


def _changed_keys(before, after):
    """Top-level keys that were added, changed or removed between two item dicts."""
    return {
        key
        for key in set(before) | set(after)
        if before.get(key, _MISSING) != after.get(key, _MISSING)
    }


def _priority_rank(priority):
    """Sort rank for a stored priority. Missing/None -> medium; unknown -> last."""
    if not isinstance(priority, str) or not priority.strip():
        return PRIORITY_RANK["medium"]
    return PRIORITY_RANK.get(priority.strip().lower(), _UNKNOWN_PRIORITY_RANK)

class Orchestrator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.handlers = StageHandler(self)
        # P2-12: in-memory only, keyed by (state file, item id) so a different
        # state file never inherits counters. failures: key -> (stage, count);
        # blocked: key -> stage at which it was blocked (skipped until it changes).
        self._failures = {}
        self._blocked = {}

    @staticmethod
    def _fail_key(item_id):
        return (state_module.STATE_FILE, item_id)

    def get_next_actionable_items(self, state):
        items = state.get("items", {})
        actionable = []
        for item_id, item in items.items():
            stage = item.get("stage", "INTAKE")
            # Review gates wait for the owner. Only a decision (APPROVED or
            # NEEDS_REVISION) makes the item actionable, so the handler can
            # advance it or send it back. PENDING / missing waits.
            if stage in REVIEW_STAGES:
                review_status = item.get("review_status", "PENDING")
                if review_status not in ("APPROVED", "NEEDS_REVISION"):
                    continue
            actionable.append((item_id, item))
        
        actionable.sort(key=lambda x: _priority_rank(x[1].get("priority")))
        return actionable

    def transition_stage(self, item, new_stage, state, item_id=None):
        old_stage = item.get("stage", "INTAKE")
        item["stage"] = new_stage
        agent = STAGE_AGENTS.get(new_stage)
        item["assigned_agent"] = agent
        # 2.14: review_status belongs to the gate it was given at. A decision
        # (APPROVED / NEEDS_REVISION) must not carry into the next stage, or an
        # approval at REVIEW_SPEC would auto-pass REVIEW_ARCH.
        item["review_status"] = "PENDING"

        if item_id:
            # Log history only if the item exists in the state; otherwise skip to avoid KeyError.
            if item_id.upper() in state.get("items", {}):
                state_module.add_history_entry(state, item_id, new_stage, agent=agent)
            else:
                logger.warning("History entry skipped for unknown item ID %s", item_id)
            notify_stage_transition(item_id, item, old_stage, new_stage, agent)

        self.logger.info("Transitioned %s: %s -> %s (agent: %s)", item_id or "?", old_stage, new_stage, agent or "none")

    def process_item(self, item, state, item_id):
        stage = item.get("stage", "INTAKE")
        handler_name = STAGE_HANDLERS.get(stage)
        if handler_name:
            method = getattr(self.handlers, handler_name)
            method(item, state, item_id)
        else:
            self.logger.warning("No handler for stage %s on item %s", stage, item_id)

    def run_pipeline(self):
        """Process every actionable item once, then record a heartbeat.

        Merge rule (2.11 / T1, decision D10). API edits can land on disk while
        a run is in flight, so the pipeline never writes back a whole-state
        snapshot taken at the start of the run:

        1. Each item is processed against the snapshot loaded at the start of
           the run. Before the handler runs, a deep copy ``before`` is taken.
        2. The keys whose values differ between ``before`` and the processed
           item (added, changed, or removed) are that item's *pipeline-owned*
           changes. Everything else is not ours to write.
        3. Under the state lock, the latest state is re-read from disk and only
           those keys are applied onto the freshly read item. Keys the handler
           did not change (e.g. a title edited by the API) keep their current
           values. Values are replaced wholesale, so a list the handler
           changed (``history``) is written as the handler left it.
        4. If the item was deleted meanwhile, nothing is written, so it is not
           resurrected.
        5. The fresh state is saved.

        Failure isolation (2.12): an exception raised by a handler or by the
        commit is logged with the item id, the item is left as it is on disk,
        and the loop moves on. The heartbeat is committed last under the lock.

        Mutual exclusion (P0-7): the whole run holds a non-blocking cross-process
        lock on ``<state file>.pipeline.lock``. If another run holds it, this call
        logs "pipeline already running" and returns 0. That lock is separate from
        the per-item ``state_lock()`` taken by ``_commit_item``.

        Corrupt state (P0-2): if the state cannot be loaded, one error is logged
        (with the backup path when the loader made one) and 0 is returned; the next
        cycle retries.

        Returns the number of items whose handler completed without raising.
        """
        lock_path = state_module.STATE_FILE + ".pipeline.lock"
        try:
            os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
        except OSError:
            pass
        lock = FileLock(lock_path)
        try:
            lock.acquire(timeout=0)
        except Timeout:
            self.logger.info("pipeline already running; skipping this run")
            return 0
        try:
            return self._run_pipeline_locked()
        finally:
            lock.release()

    def _run_pipeline_locked(self):
        self.logger.info("Pipeline run starting")
        try:
            state = state_module.load_state()
        except Exception as exc:
            backup = getattr(exc, "backup_path", None)
            if backup:
                self.logger.error(
                    "Pipeline state could not be loaded; skipping this cycle. "
                    "Backup of the unreadable file: %s (%s)", backup, exc,
                )
            else:
                self.logger.error("Pipeline state could not be loaded; skipping this cycle: %s", exc)
            return 0
        actionable = self.get_next_actionable_items(state)

        processed = 0
        for item_id, item in actionable:
            stage = item.get("stage")
            key = self._fail_key(item_id)
            if self._blocked.get(key) == stage:
                self.logger.info("Skipping %s: blocked after repeated failures at stage %s", item_id, stage)
                continue
            self._blocked.pop(key, None)
            self.logger.info("Processing item %s at stage %s", item_id, stage)
            before = copy.deepcopy(item)
            try:
                self.process_item(item, state, item_id)
            except Exception as exc:
                self.logger.exception("Processing item %s failed; leaving it as on disk", item_id)
                self._record_failure(item_id, stage, before, exc)
                continue
            self._failures.pop(key, None)
            processed += 1
            try:
                self._commit_item(item_id, before, item)
            except Exception:
                self.logger.exception("Committing item %s failed; leaving it as on disk", item_id)

        self._commit_heartbeat()
        self.logger.info("Pipeline run complete. Processed %d items.", processed)
        return processed

    def _record_failure(self, item_id, stage, before, exc):
        """Count a handler failure; after MAX_CONSECUTIVE_FAILURES block the item (P2-12).

        Counters live in memory only. Blocking sets ``blocked_reason`` through
        ``_commit_item`` (a merge of just that key) and skips the item until its
        stage changes. The half-mutated in-flight item is not committed.
        """
        key = self._fail_key(item_id)
        prev_stage, count = self._failures.get(key, (stage, 0))
        count = count + 1 if prev_stage == stage else 1
        self._failures[key] = (stage, count)
        if count < MAX_CONSECUTIVE_FAILURES:
            return
        self._blocked[key] = stage
        self._failures.pop(key, None)
        after = copy.deepcopy(before)
        after["blocked_reason"] = (
            f"Blocked after {count} consecutive failures at {stage}: {type(exc).__name__}: {exc}"
        )
        self.logger.error("Item %s blocked after %d consecutive failures at %s", item_id, count, stage)
        try:
            self._commit_item(item_id, before, after)
        except Exception:
            self.logger.exception("Committing blocked_reason for %s failed", item_id)

    def _commit_item(self, item_id, before, after):
        """Merge one item's pipeline-owned changes into the latest on-disk state.

        Returns True if something was written. See ``run_pipeline`` for the rule.
        """
        changed = _changed_keys(before, after)
        if not changed:
            return False
        with state_module.state_lock():
            fresh = state_module.load_state()
            current = fresh.get("items", {}).get(item_id)
            if current is None:
                self.logger.info("Item %s was deleted during the run; not resurrecting it", item_id)
                return False
            for key in changed:
                if key in after:
                    current[key] = copy.deepcopy(after[key])
                else:
                    current.pop(key, None)
            state_module.save_state(fresh)
        return True

    def _commit_heartbeat(self):
        now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            with state_module.state_lock():
                fresh = state_module.load_state()
                fresh["last_heartbeat"] = now
                state_module.save_state(fresh)
        except Exception:
            self.logger.exception("Failed to record pipeline heartbeat")

    def promote_artifact_to_pattern(self, item_id, artifact_name, content):
        """
        Orchestrates the extraction of patterns from a successful artifact.
        """
        self.logger.info("Promoting %s/%s to patterns for %s", artifact_name, item_id, item_id)
        try:
            from agents import memory
            success = memory.extract_pattern_from_content(item_id, artifact_name, content)
            if success:
                self.logger.info("Successfully promoted %s/%s to patterns", artifact_name, item_id)
                return True
            else:
                self.logger.error("Memory agent failed to extract pattern for %s", item_id)
                return False
        except Exception as e:
            self.logger.error("Pattern promotion failed for %s: %s", item_id, str(e))
            return False

    def handle_new_idea(self, file_path):
        self.logger.info(f"Handling new idea event for file: {file_path}")
        self.run_pipeline()

    def handle_review_update(self, file_path):
        self.logger.info(f"Handling review update event for file: {file_path}")
        self.run_pipeline()

_orchestrator_instance = None

def get_orchestrator() -> "Orchestrator":
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = Orchestrator()
    return _orchestrator_instance

# Facade functions for backward compatibility
def get_next_actionable_items(state):
    return get_orchestrator().get_next_actionable_items(state)

def run_pipeline():
    return get_orchestrator().run_pipeline()

def transition_stage(item, new_stage, state, item_id=None):
    return get_orchestrator().transition_stage(item, new_stage, state, item_id)

def process_item(item, state, item_id):
    return get_orchestrator().process_item(item, state, item_id)

def handle_intake(item, state, item_id):
    return get_orchestrator().handlers.handle_intake(item, state, item_id)

def handle_refinement(item, state, item_id):
    return get_orchestrator().handlers.handle_refinement(item, state, item_id)

def handle_review_spec(item, state, item_id):
    return get_orchestrator().handlers.handle_review_spec(item, state, item_id)

def handle_architecture(item, state, item_id):
    return get_orchestrator().handlers.handle_architecture(item, state, item_id)

def handle_review_arch(item, state, item_id):
    return get_orchestrator().handlers.handle_review_arch(item, state, item_id)

def handle_testing(item, state, item_id):
    return get_orchestrator().handlers.handle_testing(item, state, item_id)

def handle_review_test(item, state, item_id):
    return get_orchestrator().handlers.handle_review_test(item, state, item_id)

def handle_approved(item, state, item_id):
    return get_orchestrator().handlers.handle_approved(item, state, item_id)

def handle_executing(item, state, item_id):
    return get_orchestrator().handlers.handle_executing(item, state, item_id)

def handle_done(item, state, item_id):
    return get_orchestrator().handlers.handle_done(item, state, item_id)
