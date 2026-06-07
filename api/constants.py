import os

# Base directory for data storage
BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "automation-ideas")
LOG_BASE_DIR = os.path.join(BASE_DIR, "logs")

# Valid pipeline stages for validation
VALID_STAGES = [
    "INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE",
    "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"
]

# Valid priority levels
VALID_PRIORITIES = ["low", "medium", "high", "critical"]

# Valid artifacts for items
VALID_ARTIFACTS = [
    "spec.md", "architecture.md", "tests.md", 
    "review.md", "execution_report.md", "deliverables.md"
]
