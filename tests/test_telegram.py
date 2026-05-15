import pytest
from unittest.mock import MagicMock, patch
from agents.telegram import TelegramHandler
from agents import state as state_module

@pytest.fixture
def mock_config():
    return {
        "telegram": {
            "enabled": True,
            "bot_token": "test_token",
            "chat_id": "test_chat_id"
        }
    }

@pytest.fixture
def tg_handler(mock_config):
    return TelegramHandler(mock_config)

def test_send_notification_review_spec(tg_handler):
    with patch.object(tg_handler, '_send_message') as mock_send:
        tg_handler.send_notification("ID-001", "REVIEW_SPEC", "Test Idea", 85)
        mock_send.assert_called_once()
        args, _ = mock_send.call_args
        assert "ID-001 ready for review" in args[0]
        assert "REVIEW_SPEC" in args[0]
        assert "Test Idea" in args[0]
        assert "85/100" in args[0]

def test_send_notification_done(tg_handler):
    with patch.object(tg_handler, '_send_message') as mock_send:
        tg_handler.send_notification("ID-001", "DONE", "Test Idea")
        mock_send.assert_called_once()
        assert "is now DONE!" in mock_send.call_args[0][0]

def test_send_notification_ignored_stage(tg_handler):
    with patch.object(tg_handler, '_send_message') as mock_send:
        tg_handler.send_notification("ID-001", "REFINEMENT", "Test Idea")
        mock_send.assert_not_called()

def test_handle_command_status(tg_handler):
    with patch('agents.state.load_state') as mock_load:
        mock_load.return_value = {
            "items": {
                "ID-001": {"title": "Idea 1", "stage": "REVIEW_SPEC", "review_status": "PENDING"},
                "ID-002": {"title": "Idea 2", "stage": "DONE", "review_status": "APPROVED"}
            }
        }
        response = tg_handler.handle_command("/status")
        assert "ID-001: REVIEW_SPEC (PENDING)" in response
        assert "ID-002: DONE (APPROVED)" in response

def test_handle_command_approve(tg_handler):
    with patch('agents.state.load_state') as mock_load, \
         patch('agents.state.save_state') as mock_save, \
         patch('agents.state.get_item') as mock_get, \
         patch('agents.state.update_item') as mock_update:

        mock_load.return_value = {"items": {"ID-001": {}}}
        mock_get.return_value = {}

        response = tg_handler.handle_command("/approve ID-001")
        assert "approved" in response
        mock_update.assert_called_with(mock_load.return_value, "ID-001", {"review_status": "APPROVED"})
        mock_save.assert_called_once()

def test_handle_command_invalid(tg_handler):
    response = tg_handler.handle_command("Hello")
    assert "Invalid command format" in response

    response = tg_handler.handle_command("/unknown")
    assert "Unknown command" in response
