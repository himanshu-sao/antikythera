import unittest
from unittest.mock import MagicMock, patch
from agents.telegram import TelegramHandler

class TestTelegramHandler(unittest.TestCase):
    def setUp(self):
        self.config = {
            "telegram": {
                "enabled": True,
                "bot_token": "test_token",
                "chat_id": "test_chat_id"
            }
        }
        self.handler = TelegramHandler(self.config)

    def test_send_brain_update_notification(self):
        with patch.object(self.handler, '_send_message') as mock_send:
            self.handler.send_brain_update_notification(5)
            mock_send.assert_called_once()
            args, _ = mock_send.call_args
            self.assertIn("5 new patterns", args[0])
            self.assertIn("pending-updates.md", args[0])

    def test_send_notification_review_stage(self):
        with patch.object(self.handler, '_send_message') as mock_send:
            self.handler.send_notification("ID-001", "REVIEW_SPEC", "Test Title", 85)
            mock_send.assert_called_once()
            args, _ = mock_send.call_args
            self.assertIn("ID-001 ready for review", args[0])
            self.assertIn("REVIEW_SPEC", args[0])
            self.assertIn("85/100", args[0])

    def test_send_notification_done(self):
        with patch.object(self.handler, '_send_message') as mock_send:
            self.handler.send_notification("ID-001", "DONE", "Test Title")
            mock_send.assert_called_once()
            args, _ = mock_send.call_args
            self.assertIn("ID-001", args[0])
            self.assertIn("is now DONE", args[0])

if __name__ == "__main__":
    unittest.main()
