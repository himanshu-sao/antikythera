from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from api.brain_schemas import CognitiveDelta, ObserverEvent

class BrainManagerInterface(ABC):
    @abstractmethod
    def get_artifact_content(self, filename: str) -> str:
        """Returns the current content of a brain artifact."""
        pass

    @abstractmethod
    def commit_delta(self, delta_id: str) -> bool:
        """Applies a pending delta to the physical markdown file."""
        pass

    @abstractmethod
    def get_pending_deltas(self) -> List[CognitiveDelta]:
        """Returns all deltas with status 'PENDING'."""
        pass

    @abstractmethod
    def refine_delta(self, delta_id: str, comment: str) -> CognitiveDelta:
        """Updates a delta based on user feedback and returns the new REFINED version."""
        pass

    @abstractmethod
    def reject_delta(self, delta_id: str) -> bool:
        """Discards a delta."""
        pass

class ObserverManagerInterface(ABC):
    @abstractmethod
    def process_event(self, event: ObserverEvent) -> List[CognitiveDelta]:
        """Ingests an event and returns any newly generated CognitiveDeltas."""
        pass

    @abstractmethod
    def analyze_kanban_logs(self, kanban_id: str) -> List[CognitiveDelta]:
        """Specifically analyzes the logs of a completed/running kanban task."""
        pass
