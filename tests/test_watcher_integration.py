"""
Integration tests for the file watcher.
Verifies the actual interaction between the OS filesystem events,
the watchdog observer, and the Orchestrator.
"""

import unittest
import tempfile
import os
import time
import shutil
from unittest.mock import Mock
from agents.watcher import FileWatcher
from agents.orchestrator import Orchestrator

class TestFileWatcherIntegration(unittest.TestCase):

    def setUp(self):
        """Set up a real temporary directory for watching."""
        self.test_dir = tempfile.mkdtemp()
        # We use a Mock for the Orchestrator to verify calls without running the full pipeline
        self.mock_orchestrator = Mock(spec=Orchestrator)
        self.watcher = FileWatcher(self.test_dir, self.mock_orchestrator)
        self.watcher.start()

    def tearDown(self):
        """Stop watcher and clean up directory."""
        self.watcher.stop()
        shutil.rmtree(self.test_dir)

    def test_integration_new_idea_trigger(self):
        """Verify that creating ideas.md actually triggers the orchestrator."""
        idea_file = os.path.realpath(os.path.join(self.test_dir, "ideas.md"))

        with open(idea_file, "w") as f:
            f.write("New Idea: Automate my emails")

        # Watchdog events are asynchronous, so we poll for a short time
        success = False
        for _ in range(20):
            if self.mock_orchestrator.handle_new_idea.called:
                success = True
                break
            time.sleep(0.1)

        self.assertTrue(success, "Orchestrator.handle_new_idea was not called after creating ideas.md")

        # Use realpath for the expected call to avoid /var/ vs /private/var/ mismatches on macOS
        actual_call_args = self.mock_orchestrator.handle_new_idea.call_args[0][0]
        self.assertEqual(os.path.realpath(actual_call_args), idea_file)

    def test_integration_review_update_trigger(self):
        """Verify that modifying review.md actually triggers the orchestrator."""
        review_file = os.path.realpath(os.path.join(self.test_dir, "review.md"))

        # Initial creation
        with open(review_file, "w") as f:
            f.write("Initial review")

        # Wait for initial trigger to pass and debounce to reset
        time.sleep(2.5)
        self.mock_orchestrator.handle_review_update.reset_mock()

        # Now modify the file
        with open(review_file, "a") as f:
            f.write("\nUpdated review")

        success = False
        for _ in range(20):
            if self.mock_orchestrator.handle_review_update.called:
                success = True
                break
            time.sleep(0.1)

        self.assertTrue(success, "Orchestrator.handle_review_update was not called after modifying review.md")

        # Use realpath for the expected call
        actual_call_args = self.mock_orchestrator.handle_review_update.call_args[0][0]
        self.assertEqual(os.path.realpath(actual_call_args), review_file)

    def test_integration_debounce_behavior(self):
        """Verify that rapid writes to the same file are debounced in a real scenario."""
        idea_file = os.path.join(self.test_dir, "ideas.md")

        # Rapid writes
        for i in range(5):
            with open(idea_file, "w") as f:
                f.write(f"Idea version {i}")
            time.sleep(0.05)

        # Wait for processing
        time.sleep(0.5)

        # Should have been triggered only once due to the 2s debounce interval
        self.assertEqual(self.mock_orchestrator.handle_new_idea.call_count, 1,
                         f"Expected 1 trigger, but got {self.mock_orchestrator.handle_new_idea.call_count}")

    def test_integration_ignore_unrelated_files(self):
        """Verify that files other than ideas.md or review.md do not trigger the orchestrator."""
        random_file = os.path.join(self.test_dir, "random.txt")

        with open(random_file, "w") as f:
            f.write("Some unrelated content")

        time.sleep(0.5)

        self.assertFalse(self.mock_orchestrator.handle_new_idea.called)
        self.assertFalse(self.mock_orchestrator.handle_review_update.called)

if __name__ == '__main__':
    unittest.main()
