import json
import os
from datetime import datetime
from typing import Optional

# Default log root, used when no ``base_dir`` is given.  It is read at call time
# (never baked into a default argument) so the test fixture can repoint it.
DEFAULT_LOG_DIR = "automation-ideas/logs"


def _cache_key(item_id: str, base_dir: str) -> tuple:
    """Logger identity: the item id AND the (absolute) directory it writes to."""
    return (item_id.upper(), os.path.abspath(base_dir))


class TaskLogger:
    """
    A logger for capturing structured task events (logs) for a specific pipeline item.
    Events are stored in JSON Lines format in `automation-ideas/logs/{item_id}/timeline.jsonl`.
    """
    def __init__(self, item_id: str, base_dir: Optional[str] = None):
        if base_dir is None:
            base_dir = DEFAULT_LOG_DIR
        self.item_id = item_id.upper()
        self.log_dir = os.path.join(base_dir, self.item_id)
        self.log_file = os.path.join(self.log_dir, "timeline.jsonl")
        # Register this logger in the per-(item, directory) map
        _loggers[_cache_key(self.item_id, base_dir)] = self

    def _log(self, level: str, agent: str, action: str, message: str, metadata: Optional[dict] = None):
        """Writes a single log entry to the JSONL file."""
        os.makedirs(self.log_dir, exist_ok=True)
        
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level.upper(),
            "agent": agent,
            "action": action,
            "message": message,
            "metadata": metadata or {}
        }
        
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def info(self, agent: str, action: str, message: str, metadata: Optional[dict] = None):
        self._log("INFO", agent, action, message, metadata)

    def warn(self, agent: str, action: str, message: str, metadata: Optional[dict] = None):
        self._log("WARN", agent, action, message, metadata)

    def error(self, agent: str, action: str, message: str, metadata: Optional[dict] = None):
        self._log("ERROR", agent, action, message, metadata)

    def get_logs(self) -> list[dict]:
        """Returns all log entries for this task, sorted by timestamp."""
        if not os.path.exists(self.log_file):
            return []
        
        logs = []
        with open(self.log_file, "r") as f:
            for line in f:
                if line.strip():
                    logs.append(json.loads(line))
        
        # Sort by timestamp just in case
        return sorted(logs, key=lambda x: x["timestamp"])

# Singleton-style access helpers.  The cache is keyed by (item id, base
# directory) so a logger created while the default directory pointed elsewhere
# is never handed out once the default changes.
_loggers: dict[tuple, TaskLogger] = {}

def get_logger(item_id: str) -> TaskLogger:
    """Returns a logger instance for the given item_id (under DEFAULT_LOG_DIR)."""
    key = _cache_key(item_id, DEFAULT_LOG_DIR)
    if key not in _loggers:
        _loggers[key] = TaskLogger(item_id, DEFAULT_LOG_DIR)
    return _loggers[key]
