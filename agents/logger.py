import json
import os
from datetime import datetime
from typing import Optional

class TaskLogger:
    """
    A logger for capturing structured task events (logs) for a specific pipeline item.
    Events are stored in JSON Lines format in `automation-ideas/logs/{item_id}/timeline.jsonl`.
    """
    def __init__(self, item_id: str, base_dir: str = "automation-ideas/logs"):
        self.item_id = item_id.upper()
        self.log_dir = os.path.join(base_dir, self.item_id)
        self.log_file = os.path.join(self.log_dir, "timeline.jsonl")

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

# Singleton-style access helpers
_loggers: dict[str, TaskLogger] = {}

def get_logger(item_id: str) -> TaskLogger:
    """Returns a logger instance for the given item_id."""
    uid = item_id.upper()
    if uid not in _loggers:
        _loggers[uid] = TaskLogger(uid)
    return _loggers[uid]
