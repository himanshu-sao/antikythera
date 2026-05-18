"""
Telegram Integration Handler for the Hermes Pipeline.

This module handles sending notifications to the owner and processing
incoming slash commands to interact with the pipeline state.
"""

import logging
import re
from agents import state as state_module
from agents import orchestrator

logger = logging.getLogger(__name__)


class TelegramHandler:
    def __init__(self, config=None):
        self.config = config or {}
        self.enabled = self.config.get("telegram", {}).get("enabled", False)
        self.bot_token = self.config.get("telegram", {}).get("bot_token")
        self.chat_id = self.config.get("telegram", {}).get("chat_id")

    def _send_message(self, text):
        """
        Internal method to send a message via the Telegram API.
        In a real implementation, this would call the Telegram Bot API
        or interface with the Hermes Telegram MCP server.
        """
        if not self.enabled:
            logger.info("[Telegram Mock] Notification disabled. Message: %s", text)
            return True

        # Mock implementation for now
        logger.info("[Telegram] Sending message to %s: %s", self.chat_id, text)
        return True

    def send_brain_update_notification(self, proposal_count):
        """
        Notifies the owner that the Memory Agent has proposed new patterns for the brain.
        """
        if not self.enabled:
            return

        msg = (
            f"🧠 [Hermes Brain] Memory Agent has identified {proposal_count} new patterns!\n\n"
            f"Proposed updates are waiting for your review in:\n"
            f"automation-ideas/brain/pending-updates.md\n\n"
            f"Please mark them as APPROVED or REJECTED to evolve the system brain."
        )
        self._send_message(msg)

    def send_notification(self, item_id, stage, title, confidence=None):
        """
        Sends a formatted notification to the owner based on the pipeline stage.
        """
        if not self.enabled:
            return

        if stage in {"REVIEW_SPEC", "REVIEW_ARCH", "REVIEW_TEST"}:
            msg = (
                f"🔔 [Hermes Pipeline] {item_id} ready for review\n\n"
                f"Stage: {stage}\n"
                f"Title: {title}\n"
                f"Confidence: {confidence if confidence else 'N/A'}/100\n\n"
                f"Please review: automation-ideas/requirements/{item_id}/review.md"
            )
        elif stage == "DONE":
            msg = f"✅ [Hermes Pipeline] {item_id} ({title}) is now DONE!"
        else:
            return # Only notify on review gates or completion

        self._send_message(msg)

    def handle_command(self, command_text):
        """
        Parses a slash command and executes the corresponding action.
        Returns a response string to be sent back to the user.
        """
        command_text = command_text.strip()
        if not command_text.startswith("/"):
            return "Invalid command format. Please use /command."

        # Use regex to strictly validate ID format (e.g., ID-001)
        # We match against the original text to preserve case for the ID
        match = re.match(r"^/(\w+)(?:\s+([a-zA-Z0-9-]+))?$", command_text)
        if not match:
            return "Invalid command format. Use /command [ID-XXX]"

        cmd, item_id = match.groups()
        cmd = cmd.lower()



        if cmd == "status":
            return self._cmd_status()
        elif cmd == "run":
            if not item_id:
                return "Usage: /run ID-XXX"
            return self._cmd_run(item_id)
        elif cmd == "approve":
            if not item_id:
                return "Usage: /approve ID-XXX"
            return self._cmd_approve(item_id)
        elif cmd == "redo":
            if not item_id:
                return "Usage: /redo ID-XXX"
            return self._cmd_redo(item_id)
        else:
            return f"Unknown command: /{cmd}. Available: /status, /run, /approve, /redo"


    def _cmd_status(self):
        """Summarize the current state of the pipeline."""
        state = state_module.load_state()
        items = state.get("items", {})
        if not items:
            return "Pipeline is currently empty."

        summary = ["🚀 *Hermes Pipeline Status*"]
        for item_id, item in items.items():
            stage = item.get("stage", "INTAKE")
            status = item.get("review_status", "PENDING")
            summary.append(f"• {item_id}: {stage} ({status})")

        return "\n".join(summary)

    def _cmd_run(self, item_id):
        """Manually trigger pipeline run for a specific item."""
        try:
            item_id = item_id.upper()
            state = state_module.load_state()
            if item_id not in state.get("items", {}):
                return f"Item {item_id} not found."

            # We trigger a full pipeline run, but the Orchestrator
            # will prioritize actionable items.
            processed = orchestrator.run_pipeline()
            return f"Pipeline triggered. Processed {processed} items."
        except Exception as e:
            return f"Error triggering pipeline: {str(e)}"

    def _cmd_approve(self, item_id):
        """Mark current review stage as APPROVED."""
        try:
            item_id = item_id.upper()
            state = state_module.load_state()
            item = state_module.get_item(state, item_id)
            state_module.update_item(state, item_id, {"review_status": "APPROVED"})
            state_module.save_state(state)
            return f"Item {item_id} approved. It will move to the next stage on the next heartbeat or /run."
        except KeyError:
            return f"Item {item_id} not found."
        except Exception as e:
            return f"Error approving item: {str(e)}"

    def _cmd_redo(self, item_id):
        """Mark current review stage as NEEDS_REVISION."""
        try:
            item_id = item_id.upper()
            state = state_module.load_state()
            item = state_module.get_item(state, item_id)
            state_module.update_item(state, item_id, {"review_status": "NEEDS_REVISION"})
            state_module.save_state(state)
            return f"Item {item_id} marked for revision."
        except KeyError:
            return f"Item {item_id} not found."
        except Exception as e:
            return f"Error marking item for revision: {str(e)}"
