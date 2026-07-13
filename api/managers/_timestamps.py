"""Shared timestamp normalization for pipeline-state items.

Several historical writers emitted ``created_at: "now"`` (a string literal)
instead of an ISO-8601 timestamp. P3.6 backfills the one surviving bad entry
and adds a load-time sanitizer so any lingering bad value self-heals on read
(and is persisted on the next save) instead of leaking to the UI / API
consumers that expect a real timestamp.

Kept dependency-free (only ``datetime`` + ``logging``) so both ``api/`` and
``agents/`` can import it without introducing package coupling.
"""
import logging
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)

_ISO_FORMATS = ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f")


def _is_iso(value: Any) -> bool:
    """Return True iff ``value`` parses as one of the ISO formats we write."""
    if not isinstance(value, str) or not value:
        return False
    for fmt in _ISO_FORMATS:
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue
    return False


def normalize_created_at(item: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure ``created_at`` (and ``updated_at``) on ``item`` are real ISO strings.

    Replaces a non-ISO ``created_at`` (e.g. the literal ``"now"``) with the
    current UTC time, and backfills a missing ``updated_at`` to match. The
    item is mutated in place and returned. Safe to call on partial/legacy
    items that predate the current schema (e.g. one with only a ``name`` field).
    """
    if not isinstance(item, dict):
        return item
    if not _is_iso(item.get("created_at")):
        logger.warning(
            "Repairing non-ISO created_at=%r; replacing with current UTC time.",
            item.get("created_at"),
        )
        item["created_at"] = datetime.utcnow().isoformat() + "Z"
    if not _is_iso(item.get("updated_at")):
        item["updated_at"] = item["created_at"]
    return item


def sanitize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Run ``normalize_created_at`` over every item in a pipeline-state dict.

    The state's ``items`` is a dict keyed by idea ID (per CLAUDE.md's ID-
    normalization rule, keys are uppercase). Mutates in place and returns it.
    Tolerates a missing/empty ``items`` mapping.
    """
    if not isinstance(state, dict):
        return state
    items = state.get("items")
    if isinstance(items, dict):
        for item_id, item in items.items():
            if isinstance(item, dict):
                normalize_created_at(item)
    return state
