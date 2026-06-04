import uuid
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class SessionStateManager:
    """
    Manages the temporary state for a WYSIWYG recording session.
    Allows steps to store outputs and supports rollback.
    """
    def __init__(self):
        # state: { "step_01.output": { ... }, "user_var": "value" }
        self.state: Dict[str, Any] = {}
        # history: list of (step_id, state_snapshot) for rollback
        self.history: list[tuple[str, Dict[str, Any]]] = []

    def set_value(self, key: str, value: Any):
        """Store a value in the session state."""
        self.state[key] = value
        logger.info(f"SessionState: Set {key} = {value}")

    def get_value(self, key: str) -> Any:
        """Retrieve a value from the session state."""
        return self.state.get(key)

    def snapshot(self, step_id: str):
        """Save a snapshot of the state before executing a step."""
        self.history.append((step_id, self.state.copy()))

    def rollback(self, to_step_id: str):
        """Rollback state to the snapshot taken before the specified step."""
        for i in range(len(self.history) - 1, -1, -1):
            step_id, snapshot = self.history[i]
            if step_id == to_step_id:
                self.state = snapshot.copy()
                # Remove all snapshots after this point
                self.history = self.history[:i]
                logger.info(f"SessionState: Rolled back to {to_step_id}")
                return True
        return False

    def clear(self):
        """Reset the session state."""
        self.state = {}
        self.history = []

    def export_state(self) -> Dict[str, Any]:
        """Export final state as a context bundle."""
        return self.state
