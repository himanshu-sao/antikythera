"""D14 settings store: ``settings.json`` under the config directory.

The file lives at ``$ANTIKYTHERA_HOME/settings.json`` (default
``~/.antikythera/settings.json``) and holds only the values the operator has
overridden, as a flat ``{key: value}`` JSON object. Every key has a schema entry
(type, safe bounds, default). Defaults are today's hardcoded values, so an
absent file changes nothing.

Rules:
* ``save_settings`` validates every key and value and rejects unknown keys and
  out-of-bounds values with :class:`SettingsValidationError` (nothing is
  written on error). A ``None`` value resets that key to its default.
* ``get_setting`` never raises for a known key: a missing, unreadable or
  corrupt file, or a stored value that fails validation, yields the default.
* Writes are atomic (temp file in the same directory, fsync, rename) and the
  file is mode 0600.
* ``get_setting`` reads the file on every call, so a consumer that calls it per
  use picks up a PATCH without a restart.

This module deliberately imports nothing heavy so that ``agents`` and ``api``
modules can both depend on it.
"""
from __future__ import annotations

import json
import logging
import math
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("antikythera.settings")

SETTINGS_FILENAME = "settings.json"

_lock = threading.RLock()


class SettingsValidationError(ValueError):
    """Raised when a save contains unknown keys or out-of-bounds values.

    ``errors`` maps setting key -> human-readable message.
    """

    def __init__(self, errors: Dict[str, str]):
        self.errors = dict(errors)
        super().__init__("; ".join(f"{k}: {m}" for k, m in self.errors.items()))


@dataclass(frozen=True)
class SettingSpec:
    key: str
    kind: str  # "int" | "float" | "int_list"
    default: Any
    minimum: float
    maximum: float
    description: str
    # Whether a changed value needs a process restart to take effect. True when
    # the consumer reads the value once at startup (or has no live consumer yet).
    restart_required: bool
    # Which code reads the value and when. Shown in GET /api/settings.
    consumer: str
    # Whether a consumer in this codebase actually reads the value today.
    wired: bool = True
    # int_list only: allowed number of items.
    min_items: int = 1
    max_items: int = 1

    def bounds(self) -> Dict[str, Any]:
        if self.kind == "int_list":
            return {
                "min_items": self.min_items,
                "max_items": self.max_items,
                "item_min": self.minimum,
                "item_max": self.maximum,
            }
        return {"min": self.minimum, "max": self.maximum}


SCHEMA: Dict[str, SettingSpec] = {
    s.key: s
    for s in (
        SettingSpec(
            "orchestrator_interval_s", "int", 30, 5, 3600,
            "Seconds between orchestrator pipeline cycles.",
            restart_required=True,
            consumer="scripts/run_orchestrator.py loop (fixed INTERVAL_SECONDS today; "
                     "read once at process start once wired)",
            wired=False,
        ),
        SettingSpec(
            "retry_delays_min", "int_list", [5, 10, 15], 1, 1440,
            "Minutes to wait before each retry of a failed workflow run. The number "
            "of entries is also the retry count before the run is BLOCKED.",
            restart_required=False,
            consumer="api/retry_manager.py RetryManager (read on every call)",
            min_items=1, max_items=5,
        ),
        SettingSpec(
            "poison_strikes", "int", 3, 1, 10,
            "Consecutive handler failures at one stage before the orchestrator "
            "blocks an item.",
            restart_required=False,
            consumer="agents/orchestrator.py Orchestrator._record_failure (read on every failure)",
        ),
        SettingSpec(
            "reap_age_s", "int", 3600, 0, 86400,
            "Default age in seconds after which an in-flight run is reaped when "
            "reap_stale_runs is called without an explicit age. Server boot passes "
            "0 explicitly and is not affected.",
            restart_required=False,
            consumer="api/managers/run_manager.py RunManager.reap_stale_runs (read on every call)",
        ),
        SettingSpec(
            "bob_timeout_s", "int", 120, 10, 600,
            "Timeout in seconds for one ibm_bob CLI call.",
            restart_required=False,
            consumer="agents/llm_client.py LLMClient._chat_bob (read on every call)",
        ),
        SettingSpec(
            "max_tasks", "int", 6, 1, 20,
            "Maximum number of tasks kept from the executor planner checklist.",
            restart_required=False,
            consumer="agents/executor_planner.py ExecutorPlanner.create_checklist (read on every call)",
        ),
        SettingSpec(
            "digest_interval_h", "float", 6, 0.25, 24,
            "Hours between notification digests.",
            restart_required=True,
            consumer="none yet (notification digest is not implemented; arc B, D10)",
            wired=False,
        ),
        SettingSpec(
            "studio_undefined_queue_cap", "int", 100, 1, 1000,
            "Default undefined-queue cap for new Studio graphs.",
            restart_required=False,
            consumer="none yet (Studio models and router default to 100; arc B)",
            wired=False,
        ),
        SettingSpec(
            "studio_max_run_logs", "int", 50, 1, 1000,
            "Default number of run logs kept per new Studio graph.",
            restart_required=False,
            consumer="none yet (Studio models and router default to 50; arc B)",
            wired=False,
        ),
    )
}


# --------------------------------------------------------------------------- paths

def config_dir() -> Path:
    """``$ANTIKYTHERA_HOME`` when set, else ``<home>/.antikythera``."""
    override = os.environ.get("ANTIKYTHERA_HOME", "").strip()
    if override:
        return Path(os.path.expanduser(override))
    return Path.home() / ".antikythera"


def settings_path() -> Path:
    return config_dir() / SETTINGS_FILENAME


# ------------------------------------------------------------------------ validation

def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _fmt(n: float) -> str:
    return str(int(n)) if float(n).is_integer() else str(n)


def _validate_value(spec: SettingSpec, value: Any) -> Any:
    """Return the normalized value or raise ``ValueError`` with a clear message."""
    if spec.kind == "int":
        if not _is_int(value):
            raise ValueError(f"must be an integer between {_fmt(spec.minimum)} and {_fmt(spec.maximum)}")
        if not spec.minimum <= value <= spec.maximum:
            raise ValueError(
                f"{value} is out of bounds; must be between {_fmt(spec.minimum)} and {_fmt(spec.maximum)}"
            )
        return value
    if spec.kind == "float":
        if not _is_number(value):
            raise ValueError(f"must be a number between {_fmt(spec.minimum)} and {_fmt(spec.maximum)}")
        if not spec.minimum <= value <= spec.maximum:
            raise ValueError(
                f"{value} is out of bounds; must be between {_fmt(spec.minimum)} and {_fmt(spec.maximum)}"
            )
        return value
    if spec.kind == "int_list":
        if not isinstance(value, list):
            raise ValueError(
                f"must be a list of {spec.min_items} to {spec.max_items} integers"
            )
        if not spec.min_items <= len(value) <= spec.max_items:
            raise ValueError(
                f"has {len(value)} items; must have {spec.min_items} to {spec.max_items}"
            )
        for i, item in enumerate(value):
            if not _is_int(item):
                raise ValueError(f"item {i} must be an integer")
            if not spec.minimum <= item <= spec.maximum:
                raise ValueError(
                    f"item {i} ({item}) is out of bounds; each item must be between "
                    f"{_fmt(spec.minimum)} and {_fmt(spec.maximum)}"
                )
        return list(value)
    raise ValueError(f"unsupported setting kind {spec.kind!r}")  # pragma: no cover


def validate_settings(updates: Any) -> Dict[str, Any]:
    """Validate a partial ``{key: value}`` mapping against the schema.

    Returns the normalized mapping (``None`` values kept: they mean reset).
    Raises :class:`SettingsValidationError` listing every problem.
    """
    if not isinstance(updates, dict):
        raise SettingsValidationError({"_body": "settings must be a JSON object"})
    errors: Dict[str, str] = {}
    out: Dict[str, Any] = {}
    for key, value in updates.items():
        spec = SCHEMA.get(key)
        if spec is None:
            errors[str(key)] = "unknown setting"
            continue
        if value is None:
            out[key] = None
            continue
        try:
            out[key] = _validate_value(spec, value)
        except ValueError as exc:
            errors[key] = str(exc)
    if errors:
        raise SettingsValidationError(errors)
    return out


# ---------------------------------------------------------------------------- reading

def _read_stored() -> Dict[str, Any]:
    """Stored overrides, each validated; invalid or unknown entries are dropped.

    Read from disk on every call (the file is tiny and the consumers call this
    per use), so an external or PATCH edit is seen immediately.
    """
    path = settings_path()
    if not path.exists():
        return {}
    data: Dict[str, Any] = {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("top level is not an object")
    except (OSError, ValueError) as exc:
        logger.warning("Ignoring unreadable settings file %s: %s", path, exc)
        return {}
    for key, value in raw.items():
        spec = SCHEMA.get(key)
        if spec is None:
            logger.warning("Ignoring unknown stored setting %r", key)
            continue
        try:
            data[key] = _validate_value(spec, value)
        except ValueError as exc:
            logger.warning("Ignoring invalid stored setting %r: %s", key, exc)
    return data


def get_setting(key: str) -> Any:
    """The stored value for ``key`` or its default. ``KeyError`` for unknown keys."""
    spec = SCHEMA[key]
    stored = _read_stored()
    if key in stored:
        value = stored[key]
        return list(value) if isinstance(value, list) else value
    default = spec.default
    return list(default) if isinstance(default, list) else default


def effective_settings() -> Dict[str, Dict[str, Any]]:
    """Every setting with value, default, bounds, source and restart_required."""
    stored = _read_stored()
    out: Dict[str, Dict[str, Any]] = {}
    for key, spec in SCHEMA.items():
        default = list(spec.default) if isinstance(spec.default, list) else spec.default
        in_file = key in stored
        value = stored[key] if in_file else default
        out[key] = {
            "value": list(value) if isinstance(value, list) else value,
            "default": default,
            "type": spec.kind,
            "bounds": spec.bounds(),
            "source": SETTINGS_FILENAME if in_file else "default",
            "restart_required": spec.restart_required,
            "description": spec.description,
            "consumer": spec.consumer,
            "wired": spec.wired,
        }
    return out


# ---------------------------------------------------------------------------- writing

def _write_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".settings.")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def save_settings(updates: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Validate and merge ``updates`` into ``settings.json``; return effective values.

    All-or-nothing: on any validation error nothing is written. A ``None`` value
    removes the override for that key.
    """
    normalized = validate_settings(updates)
    path = settings_path()
    with _lock:
        current = dict(_read_stored())
        for key, value in normalized.items():
            if value is None:
                current.pop(key, None)
            else:
                current[key] = value
        _write_atomic(path, current)
    return effective_settings()
