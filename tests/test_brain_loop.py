import unittest
import os
import shutil
from unittest.mock import patch, MagicMock
from agents import brain_loop, memory

class TestBrainLoop(unittest.TestCase):
    def setUp(self):
        # Setup temporary brain directory
        self.test_brain_dir = "tests/test_brain"
        os.makedirs(self.test_brain_dir, exist_ok=True)
        self.patterns_file = os.path.join(self.test_brain_dir, "patterns.md")
        self.pending_file = os.path.join(self.test_brain_dir, "pending-updates.md")
        self.history_dir = os.path.join(self.test_brain_dir, "history")

        # Patch paths in the modules
        self.patcher_patterns = patch('agents.brain_loop.PATTERNS_FILE', self.patterns_file)
        self.patcher_pending = patch('agents.brain_loop.PENDING_UPDATES_FILE', self.pending_file)
        self.patcher_history = patch('agents.brain_loop.HISTORY_DIR', self.history_dir)
        self.patcher_mem_patterns = patch('agents.memory.PATTERNS_FILE', self.patterns_file)
        self.patcher_mem_pending = patch('agents.memory.PENDING_UPDATES_FILE', self.pending_file)

        self.patcher_patterns.start()
        self.patcher_pending.start()
        self.patcher_history.start()
        self.patcher_mem_patterns.start()
        self.patcher_mem_pending.start()

        with open(self.patterns_file, "w") as f:
            f.write("# System Patterns\n- Initial pattern")

    def tearDown(self):
        shutil.rmtree("tests/test_brain", ignore_errors=True)
        patch.stopall()

    def test_apply_approved_updates(self):
        # Create a pending update marked as APPROVED
        with open(self.pending_file, "w") as f:
            f.write("### Proposed Change 1\n**What to add:** New pattern A\n**review_status:** APPROVED\n---\n")
            f.write("### Proposed Change 2\n**What to add:** New pattern B\n**review_status:** PENDING\n---\n")

        applied = brain_loop.apply_approved_updates()

        self.assertEqual(applied, 1)
        with open(self.patterns_file, "r") as f:
            content = f.read()
            self.assertIn("New pattern A", content)
            self.assertNotIn("New pattern B", content)

        # Verify history archive exists
        self.assertTrue(os.path.exists(self.history_dir))
        self.assertTrue(len(os.listdir(self.history_dir)) > 0)

    def test_nightly_loop_integration(self):
        # Proposals found: the loop logs the pending-proposal count, no notifier involved.
        with patch('agents.memory.analyze_and_propose', return_value=True), \
             patch('agents.brain_loop.apply_approved_updates', return_value=0):

            with open(self.pending_file, "w") as f:
                f.write("### Proposed Change 1\n### Proposed Change 2\n")

            with self.assertLogs('agents.brain_loop', level='INFO') as logs:
                brain_loop.run_nightly_loop()

        proposal_lines = [m for m in logs.output if "proposed pattern" in m]
        self.assertEqual(len(proposal_lines), 1)
        self.assertIn("2 proposed pattern(s)", proposal_lines[0])
        self.assertFalse(any("Telegram" in m for m in logs.output))

    def test_nightly_loop_has_no_telegram_dependency(self):
        import sys
        self.assertNotIn("agents.telegram", sys.modules)
        self.assertFalse(hasattr(brain_loop, "TelegramHandler"))

    def test_nightly_loop_no_proposals_does_not_read_pending_file(self):
        # No proposals: pending file is not required and nothing about proposals is logged.
        self.assertFalse(os.path.exists(self.pending_file))
        with patch('agents.memory.analyze_and_propose', return_value=False), \
             patch('agents.brain_loop.apply_approved_updates', return_value=0), \
             self.assertLogs('agents.brain_loop', level='INFO') as logs:
            brain_loop.run_nightly_loop()
        self.assertFalse(any("proposed pattern" in m for m in logs.output))

    def test_nightly_loop_logs_applied_count(self):
        with patch('agents.memory.analyze_and_propose', return_value=False), \
             patch('agents.brain_loop.apply_approved_updates', return_value=3), \
             self.assertLogs('agents.brain_loop', level='INFO') as logs:
            brain_loop.run_nightly_loop()
        self.assertTrue(any("applied 3 approved patterns" in m for m in logs.output))

    def test_nightly_loop_proposals_and_applied_together(self):
        with open(self.pending_file, "w") as f:
            f.write("### Proposed Change 1\n")
        with patch('agents.memory.analyze_and_propose', return_value=True), \
             patch('agents.brain_loop.apply_approved_updates', return_value=1), \
             self.assertLogs('agents.brain_loop', level='INFO') as logs:
            brain_loop.run_nightly_loop()
        self.assertTrue(any("1 proposed pattern(s)" in m for m in logs.output))
        self.assertTrue(any("applied 1 approved patterns" in m for m in logs.output))

if __name__ == "__main__":
    unittest.main()
