"""
Tests for the file watcher agent.
"""

import unittest
import tempfile
import os
import time
from unittest.mock import Mock, patch
from agents.watcher import FileWatcher, HermesFileHandler
from agents.orchestrator import Orchestrator

class TestFileWatcher(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.mock_orchestrator = Mock(spec=Orchestrator)

    def tearDown(self):
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.test_dir)

    def test_watcher_initialization(self):
        """Test that the watcher can be initialized."""
        watcher = FileWatcher(self.test_dir, self.mock_orchestrator)
        self.assertEqual(watcher.watch_path, self.test_dir)
        self.assertEqual(watcher.orchestrator, self.mock_orchestrator)

    def test_file_handler_creation(self):
        """Test that the file handler can be created."""
        handler = HermesFileHandler(self.mock_orchestrator)
        self.assertIsInstance(handler, HermesFileHandler)

    @patch('agents.watcher.Observer')
    def test_watcher_start_stop(self, mock_observer_class):
        """Test that the watcher can be started and stopped."""
        mock_observer = Mock()
        mock_observer_class.return_value = mock_observer

        watcher = FileWatcher(self.test_dir, self.mock_orchestrator)
        watcher.start()
        mock_observer.schedule.assert_called_once()
        mock_observer.start.assert_called_once()

        watcher.stop()
        mock_observer.stop.assert_called_once()
        mock_observer.join.assert_called_once()

    def test_handler_triggers_orchestrator(self):
        """Test that the handler triggers the correct orchestrator methods."""
        handler = HermesFileHandler(self.mock_orchestrator)

        # Test ideas.md trigger
        mock_event_idea = Mock()
        mock_event_idea.is_directory = False
        mock_event_idea.src_path = os.path.join(self.test_dir, 'ideas.md')
        handler.on_created(mock_event_idea)
        self.mock_orchestrator.handle_new_idea.assert_called_with(mock_event_idea.src_path)

        # Test review.md trigger
        mock_event_review = Mock()
        mock_event_review.is_directory = False
        mock_event_review.src_path = os.path.join(self.test_dir, 'review.md')
        handler.on_modified(mock_event_review)
        self.mock_orchestrator.handle_review_update.assert_called_with(mock_event_review.src_path)

    def test_handler_debouncing(self):
        """Test that rapid file events are debounced."""
        handler = HermesFileHandler(self.mock_orchestrator)

        mock_event = Mock()
        mock_event.is_directory = False
        mock_event.src_path = os.path.join(self.test_dir, 'ideas.md')

        # First event should trigger
        handler.on_created(mock_event)
        self.assertEqual(self.mock_orchestrator.handle_new_idea.call_count, 1)

        # Immediate second event should be debounced
        handler.on_created(mock_event)
        self.assertEqual(self.mock_orchestrator.handle_new_idea.call_count, 1)

        # Wait for debounce interval (default 2s)
        time.sleep(2.1)

        # Third event should trigger again
        handler.on_created(mock_event)
        self.assertEqual(self.mock_orchestrator.handle_new_idea.call_count, 2)

if __name__ == '__main__':
    unittest.main()
