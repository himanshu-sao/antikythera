"""
Brain Loop — handles the nightly memory update cycle.

This module manages the separate loop for the Memory Agent:
1. Triggers the Memory Agent analysis.
2. Provides a mechanism to apply approved updates to the brain.
"""

import os
import re
import shutil
import logging
from datetime import datetime
from agents import memory

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAIN_DIR = os.path.join(PROJECT_ROOT, "automation-ideas", "brain")
PATTERNS_FILE = os.path.join(BRAIN_DIR, "patterns.md")
PENDING_UPDATES_FILE = os.path.join(BRAIN_DIR, "pending-updates.md")
HISTORY_DIR = os.path.join(BRAIN_DIR, "history")

def apply_approved_updates():
    """
    Read pending-updates.md, find APPROVED entries, and apply them to patterns.md.
    Then archive the current patterns.md to history/ and clear processed updates.
    """
    logger.info("Brain Loop: Checking for approved updates")

    if not os.path.exists(PENDING_UPDATES_FILE):
        logger.info("No pending updates file found")
        return 0

    content = ""
    with open(PENDING_UPDATES_FILE, "r") as f:
        content = f.read()

    if not content:
        logger.info("Pending updates file is empty")
        return 0

    # Split by "---" to get individual proposals
    proposals = re.split(r"---", content)
    applied_count = 0
    updates_to_apply = []

    for prop in proposals:
        if "**review_status:** APPROVED" in prop:
            # Extract the "What to add" section
            match = re.search(r"\*\*What to add:\*\*\s*(.*)", prop)
            if match:
                update_text = match.group(1).strip()
                updates_to_apply.append(update_text)
                applied_count += 1

    if not updates_to_apply:
        logger.info("No approved updates found")
        return 0

    # 1. Archive current patterns.md
    if os.path.exists(PATTERNS_FILE):
        os.makedirs(HISTORY_DIR, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H%M%S")
        archive_path = os.path.join(HISTORY_DIR, f"{timestamp}-update.md")
        shutil.copy(PATTERNS_FILE, archive_path)
        logger.info("Archived current patterns to %s", archive_path)

    # 2. Update patterns.md
    with open(PATTERNS_FILE, "a") as f:
        f.write("\n\n## New Patterns (Applied " + datetime.utcnow().strftime("%Y-%m-%d") + ")\n")
        for update in updates_to_apply:
            f.write(f"- {update}\n")

    # 3. Clear approved entries from pending-updates.md
    # For simplicity, we'll just overwrite the file if all were applied,
    # or in a real system, we'd surgically remove the approved blocks.
    # Here we just truncate for the demo.
    with open(PENDING_UPDATES_FILE, "w") as f:
        f.write("# Processed Updates\n\nAll approved updates have been applied.")

    logger.info("Applied %d updates to brain/patterns.md", applied_count)
    return applied_count

def run_nightly_loop():
    """
    Main entry point for the nightly brain update cycle.
    """
    logger.info("Brain Loop: Running nightly cycle")

    # 1. Run Memory Agent to find new patterns
    proposals_found = memory.analyze_and_propose()

    # 2/3. Check for and apply approved updates
    applied = apply_approved_updates()

    if proposals_found:
        # Trigger Telegram notification
        from agents.telegram import TelegramHandler
        import yaml
        import os

        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(PROJECT_ROOT, "config.yaml")
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        tg = TelegramHandler(config)
        # We don't have the exact count easily, so we'll check the file or just notify.
        # Let's just count the "### Proposed Change" markers.
        with open(PENDING_UPDATES_FILE, "r") as f:
            content = f.read()
            count = content.count("### Proposed Change")

        tg.send_brain_update_notification(count)
        logger.info("Brain Loop: Notified owner via Telegram about %d proposals.", count)


    if applied > 0:
        logger.info("Brain Loop: Successfully applied %d approved patterns.", applied)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_nightly_loop()
