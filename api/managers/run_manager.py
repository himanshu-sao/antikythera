import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from api.managers.base import BaseJSONManager, CorruptStateError
from api.settings_store import get_setting

logger = logging.getLogger(__name__)

# Statuses that mean "a run is still in flight" and therefore a candidate
# for orphan-reaping on startup. Stored case-insensitively so both the
# workflow-run convention ("RUNNING") and the pipeline-run convention that
# leaks lowercase values ("running", "executing", "active") are covered.
_ACTIVE_STATUSES = {"running", "executing", "active", "pending"}

_ISO_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
)


def _parse_started_at(value: Any) -> Optional[datetime]:
    """Parse a run's ``started_at`` into an aware UTC ``datetime``.

    Returns ``None`` if the value is missing or unparseable; the reaper then
    treats the run as *stale* (safest default — a run with no usable start
    time that is still marked active is almost certainly orphaned).
    """
    if not isinstance(value, str) or not value:
        return None
    for fmt in _ISO_FORMATS:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


class RunManager(BaseJSONManager):
    def __init__(self, base_dir: str):
        super().__init__(base_dir, "workflow_runs.json")
        self.events_dir = os.path.join(base_dir, "events")

    def get_all_runs(self) -> Dict[str, Dict[str, Any]]:
        """Return the full run mapping (run_id -> run_data)."""
        return self._load()

    def reap_stale_runs(
        self,
        max_age_seconds: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> List[str]:
        """Mark in-flight runs as FAILED so nothing shows them as still running.

        Any run in an active status (see ``_ACTIVE_STATUSES``) whose
        ``started_at`` is at least ``max_age_seconds`` old is flipped to
        ``FAILED`` with reap_reason ``"orphaned: server restart"``, and a
        ``RUN_REAPED`` timeline event is logged.

        ``max_age_seconds`` defaults to the ``reap_age_s`` setting (3600 s when
        unset), read per call. ``max_age_seconds <= 0`` reaps every in-flight run
        regardless of age.
        The server calls it that way at boot, because a run's driver (its retry
        timers) lives only in memory, so every in-flight run is an orphan at
        that point.

        Load, mark and save happen under one lock acquisition (``_update``), so
        a concurrent writer cannot be lost between them.

        ``now`` is injectable for deterministic tests; it defaults to the
        current UTC time. Returns the list of run IDs that were reaped.
        """
        if max_age_seconds is None:
            max_age_seconds = get_setting("reap_age_s")
        if now is None:
            now = datetime.now(timezone.utc)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        else:
            now = now.astimezone(timezone.utc)

        reaped_events: List[tuple] = []

        def apply(runs: Dict[str, Any]):
            reaped: List[str] = []
            for run_id, run in runs.items():
                if not isinstance(run, dict):
                    continue
                status = run.get("status")
                if not isinstance(status, str) or status.lower() not in _ACTIVE_STATUSES:
                    continue
                if max_age_seconds > 0:
                    started = _parse_started_at(run.get("started_at"))
                    # Treat an unparseable start time as ancient -> stale (safe default).
                    if started is not None and (now - started).total_seconds() < max_age_seconds:
                        continue

                run["status"] = "FAILED"
                run["reaped_at"] = now.isoformat().replace("+00:00", "Z")
                run["reap_reason"] = "orphaned: server restart"
                reaped.append(run_id)
                reaped_events.append((run_id, status))
            return bool(reaped), reaped

        try:
            reaped = self._update(apply)
        except Exception:
            logger.exception("Failed to reap orphaned runs")
            return []

        # Best-effort audit trail, written after the state save. A missing
        # events dir must not fail the reap.
        for run_id, previous_status in reaped_events:
            try:
                self.log_event(
                    run_id,
                    "RUN_REAPED",
                    {"reason": "orphaned: server restart", "previous_status": previous_status},
                    actor="lifespan",
                )
            except Exception:
                logger.warning("Reaped %s but failed to log timeline event", run_id, exc_info=True)
        if reaped:
            logger.info("Reaped %d in-flight run(s): %s", len(reaped), reaped)
        return reaped

    def create_run(self, run_id: str, run_data: Dict[str, Any]) -> bool:
        """Persist a new run and return True.

        Write failures (including ``CorruptStateError``) propagate to the
        caller instead of being reported as False, so a run id is never handed
        out for a run that was not saved.
        """
        def apply(runs: Dict[str, Any]):
            run_data["started_at"] = datetime.utcnow().isoformat() + "Z"
            runs[run_id] = run_data
            return True, True
        return self._update(apply)

    def update_run(self, run_id: str, updates: Dict[str, Any]) -> bool:
        # Load, merge and save under one lock acquisition so concurrent
        # updates to different keys of the same run cannot lose each other.
        def apply(runs: Dict[str, Any]):
            if run_id not in runs:
                return False, False
            runs[run_id].update(updates)
            return True, True
        try:
            return self._update(apply)
        except CorruptStateError:
            raise
        except Exception:
            return False

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        runs = self._load()
        return runs.get(run_id)

    def log_event(self, run_id: str, event_type: str, payload: Dict[str, Any], actor: str = "system") -> bool:
        try:
            run_events_path = os.path.join(self.events_dir, f"{run_id}.jsonl")
            os.makedirs(self.events_dir, exist_ok=True)
            
            event = {
                "event_id": f"ev_{int(datetime.utcnow().timestamp() * 1000)}",
                "run_id": run_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "event_type": event_type,
                "payload": payload,
                "actor": actor
            }
            
            with open(run_events_path, "a") as f:
                f.write(json.dumps(event) + "\n")
            return True
        except Exception:
            return False

    def get_run_timeline(self, run_id: str) -> List[Dict[str, Any]]:
        run_events_path = os.path.join(self.events_dir, f"{run_id}.jsonl")
        if not os.path.exists(run_events_path):
            return []
        
        events = []
        try:
            with open(run_events_path, "r") as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line))
        except Exception:
            pass
        return events
