"""
Audit Agent — passive logger that appends structured entries to audit/YYYY-MM-DD.md.

The Audit Agent records every agent action with: agent name, idea ID,
stage, action taken, inputs used, outputs produced, and timestamp.
It runs alongside all other agents and requires no owner interaction.
"""

import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_DIR = os.path.join(PROJECT_ROOT, "automation-ideas", "audit")


def get_audit_path(date_str=None):
    """
    Get the path to the audit file for a given date.

    Creates the audit directory if it doesn't exist.

    Args:
        date_str (str, optional): Date string in YYYY-MM-DD format.
            Defaults to today's date.

    Returns:
        str: The path to the audit file.
    """
    if date_str is None:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
    os.makedirs(AUDIT_DIR, exist_ok=True)
    return os.path.join(AUDIT_DIR, f"{date_str}.md")


def _ensure_file_exists(file_path):
    """
    Ensure the audit file exists with a header.

    Creates the file with a markdown header if it doesn't exist.

    Args:
        file_path (str): Path to the audit file.
    """
    if not os.path.exists(file_path):
        date_str = os.path.splitext(os.path.basename(file_path))[0]
        with open(file_path, "w") as f:
            f.write(f"# Audit Log — {date_str}\n\n")


def log_action(agent_name, idea_id, stage, action, inputs=None, outputs=None):
    """
    Log an audit entry for an agent action.

    Appends a structured entry to audit/YYYY-MM-DD.md with timestamp,
    agent name, idea ID, stage, action, inputs, and outputs.

    Creates the audit file with a header if it doesn't exist.
    Handles errors gracefully (logs warning, does not raise).

    Args:
        agent_name (str): Name of the agent (e.g. "architect", "tester").
        idea_id (str): The item ID (e.g. "ID-001").
        stage (str): The pipeline stage (e.g. "ARCHITECTURE", "TESTING").
        action (str): Description of the action taken.
        inputs (str, optional): Description of inputs used.
        outputs (str, optional): Description of outputs produced.
    """
    try:
        file_path = get_audit_path()
        _ensure_file_exists(file_path)

        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        inputs_str = inputs or "None"
        outputs_str = outputs or "None"

        entry = f"""## {timestamp}

- **Agent**: {agent_name}
- **Idea**: {idea_id}
- **Stage**: {stage}
- **Action**: {action}
- **Inputs**: {inputs_str}
- **Outputs**: {outputs_str}

---
"""

        with open(file_path, "a") as f:
            f.write(entry)

        logger.debug(
            "Audit entry written: %s/%s/%s",
            agent_name,
            idea_id,
            stage,
        )
    except Exception as e:
        logger.warning("Failed to write audit entry: %s", str(e))


def log_stage_transition(
    agent_name, idea_id, from_stage, to_stage, inputs=None, outputs=None
):
    """
    Log a stage transition audit entry.

    Convenience wrapper around log_action that formats the action as
    "Stage transition: {from_stage} → {to_stage}".

    Args:
        agent_name (str): Name of the agent.
        idea_id (str): The item ID.
        from_stage (str): The source stage.
        to_stage (str): The destination stage.
        inputs (str, optional): Description of inputs used.
        outputs (str, optional): Description of outputs produced.
    """
    action = f"Stage transition: {from_stage} → {to_stage}"
    log_action(agent_name, idea_id, to_stage, action, inputs, outputs)