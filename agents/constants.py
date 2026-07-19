import logging
from typing import Dict, Set, List, Tuple, Any, Optional

# All pipeline stages in order
PIPELINE_STAGES = [
    "INTAKE",
    "REFINEMENT",
    "REVIEW_SPEC",
    "ARCHITECTURE",
    "REVIEW_ARCH",
    "TESTING",
    "REVIEW_TEST",
    "APPROVED",
    "EXECUTING",
    "DONE",
]

# Stages that block on owner review
REVIEW_STAGES = {"REVIEW_SPEC", "REVIEW_ARCH", "REVIEW_TEST"}

# Agent responsible for each non-review stage
STAGE_AGENTS = {
    "INTAKE": None,
    "REFINEMENT": "refiner",
    "REVIEW_SPEC": None,
    "ARCHITECTURE": "architect",
    "REVIEW_ARCH": None,
    "TESTING": "tester",
    "REVIEW_TEST": None,
    "APPROVED": None,
    "EXECUTING": "executor",
    "DONE": None,
}

# Mapping of stages to Orchestrator handler methods
STAGE_HANDLERS = {
    "INTAKE": "handle_intake",
    "REFINEMENT": "handle_refinement",
    "REVIEW_SPEC": "handle_review_spec",
    "ARCHITECTURE": "handle_architecture",
    "REVIEW_ARCH": "handle_review_arch",
    "TESTING": "handle_testing",
    "REVIEW_TEST": "handle_review_test",
    "APPROVED": "handle_approved",
    "EXECUTING": "handle_executing",
    "DONE": "handle_done",
}

# ---------------------------------------------------------------------------
# P4.1 — Complexity-tier stage-skip pipeline (GateGuard)
# Per-item complexity controls which stages the orchestrator advances through.
# Default "complex" = full 10-stage pipeline (backward-compatible).
# ---------------------------------------------------------------------------

TIER_STAGES = {
    "trivial": ["INTAKE", "REFINEMENT", "REVIEW_SPEC", "EXECUTING", "DONE"],
    "simple":  ["INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE",
                "REVIEW_ARCH", "EXECUTING", "DONE"],
    "complex":  PIPELINE_STAGES,  # the current 10 — no skip
}

DEFAULT_COMPLEXITY = "complex"


def next_stage(current: str, complexity: str) -> Optional[str]:
    """Return the next stage for *current* in *complexity* tier, or None.

    ``None`` / ``""`` / ``"auto"`` / unknown complexity → ``DEFAULT_COMPLEXITY``.
    ``current`` not found in the tier path or is terminal → ``None``.
    """
    path = TIER_STAGES.get(
        (complexity or DEFAULT_COMPLEXITY).strip().lower(),
        TIER_STAGES[DEFAULT_COMPLEXITY],
    )
    try:
        return path[path.index(current) + 1]
    except (ValueError, IndexError):
        return None
