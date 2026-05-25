import logging
from typing import Dict, Set, List, Tuple, Any

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
