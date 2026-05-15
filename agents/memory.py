"""
Memory Agent — analyzes audit logs and review comments to evolve brain/patterns.md.

The Memory Agent identifies recurring patterns, owner preferences, and constraints
from the pipeline's history and proposes updates to the system's "brain".
"""

import os
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAIN_DIR = os.path.join(PROJECT_ROOT, "automation-ideas", "brain")
REQUIREMENTS_DIR = os.path.join(PROJECT_ROOT, "automation-ideas", "requirements")
AUDIT_DIR = os.path.join(PROJECT_ROOT, "automation-ideas", "audit")
PATTERNS_FILE = os.path.join(BRAIN_DIR, "patterns.md")
PENDING_UPDATES_FILE = os.path.join(BRAIN_DIR, "pending-updates.md")

def _read_file(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return ""

def _extract_review_comments(requirements_dir):
    """
    Find all review.md files and extract comments and review status.
    """
    all_comments = []
    for root, dirs, files in os.walk(requirements_dir):
        if "review.md" in files:
            path = os.path.join(root, "review.md")
            content = _read_file(path)
            # Basic extraction of comments and status
            # Looking for patterns like **review_status:** APPROVED/NEEDS_REVISION
            status_match = re.search(r"\*\*review_status:\*\*\s*(\w+)", content)
            status = status_match.group(1) if status_match else "UNKNOWN"

            # Extract bullet points under "Comments:"
            comments_section = re.split(r"\*\*Comments:\*\*", content)
            if len(comments_section) > 1:
                comment_text = comments_section[1].split("---")[0].strip()
                all_comments.append({
                    "item_id": os.path.basename(os.path.dirname(path)),
                    "status": status,
                    "comments": comment_text
                })
    return all_comments

def _extract_audit_patterns(audit_dir):
    """
    Parse audit logs to find recurring agent actions or failures.
    """
    patterns = []
    for file in os.listdir(audit_dir):
        if file.endswith(".md"):
            path = os.path.join(audit_dir, file)
            content = _read_file(path)
            # Extract entries between "## [timestamp]" and "---"
            entries = re.split(r"## \d{4}-\d{2}-\d{2}T", content)
            for entry in entries[1:]:
                # Simple pattern: look for "Action: ..." and "Inputs: ..."
                action_match = re.search(r"- \*\*Action\*\*: (.+)", entry)
                if action_match:
                    action = action_match.group(1).strip()
                    patterns.append(action)
    return patterns

def _synthesize_proposed_updates(review_comments, audit_patterns):
    """
    Analyze collected data and propose updates to patterns.md.
    In a real implementation, this would use an LLM.
    For this scaffold, it uses heuristic-based synthesis.
    """
    proposals = []

    # Example heuristic: if "secret" appears in multiple review comments, propose a secret management pattern
    secret_mentions = [c for c in review_comments if "secret" in c["comments"].lower() or "credential" in c["comments"].lower()]
    if len(secret_mentions) >= 1:
        evidence = ", ".join([f"{c['item_id']}" for c in secret_mentions])
        proposals.append({
            "area": "Secret Management",
            "update": "Ensure all secrets are read from environment variables via `os.getenv()` and never hardcoded in specs or code.",
            "evidence": f"Mentioned in review comments for: {evidence}",
            "confidence": "High"
        })

    # Example heuristic: if certain tools are mentioned frequently in audit logs
    # (Simulated logic)
    if any("Docker" in p for p in audit_patterns):
        proposals.append({
            "area": "Infrastructure",
            "update": "Use Docker Compose for all sandbox testing to ensure environment parity.",
            "evidence": "Recurring use of Docker in audit logs",
            "confidence": "Medium"
        })

    return proposals

def _write_pending_updates(proposals):
    """
    Write proposals to brain/pending-updates.md in the specified format.
    """
    if not proposals:
        return

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    header = f"## Pending Brain Update — {date_str}\n\n"

    body = ""
    for i, prop in enumerate(proposals, 1):
        body += f"### Proposed Change {i}\n"
        body += f"**Pattern area:** {prop['area']}\n"
        body += f"**What to add:** {prop['update']}\n"
        body += f"**Evidence:** {prop['evidence']}\n"
        body += f"**Confidence:** {prop['confidence']}\n\n"
        body += f"**review_status:** PENDING\n\n---\n\n"

    with open(PENDING_UPDATES_FILE, "w") as f:
        f.write(header + body)

def analyze_and_propose(patterns_path=None):
    """
    Main entry point for Memory Agent.
    Analyzes audit logs and review comments to propose updates to brain/patterns.md.

    Returns:
        bool: True if proposals were written, False otherwise.
    """
    logger.info("Memory Agent: Starting brain analysis")

    review_comments = _extract_review_comments(REQUIREMENTS_DIR)
    audit_patterns = _extract_audit_patterns(AUDIT_DIR)

    proposals = _synthesize_proposed_updates(review_comments, audit_patterns)

    if proposals:
        _write_pending_updates(proposals)
        logger.info("Memory Agent: Wrote %d proposals to pending-updates.md", len(proposals))
        return True

    logger.info("Memory Agent: No new patterns identified")
    return False
