"""Tests for the logger-only stage-transition notifier (Telegram feature removed, D6)."""
import builtins
import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest

from agents import notifications


@pytest.fixture
def task_log():
    fake = MagicMock()
    with patch.object(notifications.task_logger, "get_logger", return_value=fake) as getter:
        yield getter, fake


def test_stage_transition_logged_once_at_info(task_log, caplog):
    with caplog.at_level("INFO", logger="agents.notifications"):
        notifications.notify_stage_transition(
            "ID-001", {"title": "T"}, "INTAKE", "REFINING", "refiner")
    records = [r for r in caplog.records if r.name == "agents.notifications"]
    assert len(records) == 1
    assert records[0].levelname == "INFO"
    msg = records[0].getMessage()
    assert "ID-001" in msg and "INTAKE -> REFINING" in msg and "refiner" in msg


def test_task_timeline_entry_written(task_log):
    getter, fake = task_log
    notifications.notify_stage_transition("ID-002", {}, "A", "B", "architect")
    getter.assert_called_once_with("ID-002")
    fake.info.assert_called_once_with("architect", "STAGE_TRANSITION", "Moved from A to B")


def test_missing_agent_defaults_to_orchestrator(task_log, caplog):
    getter, fake = task_log
    with caplog.at_level("INFO", logger="agents.notifications"):
        notifications.notify_stage_transition("ID-003", {}, "A", "B", None)
    fake.info.assert_called_once_with("orchestrator", "STAGE_TRANSITION", "Moved from A to B")
    assert "orchestrator" in caplog.text


@pytest.mark.parametrize("new_stage", ["REVIEW_SPEC", "REVIEW_ARCH", "REVIEW_TEST", "DONE", "EXECUTING"])
def test_every_stage_is_logged_exactly_once(task_log, caplog, new_stage):
    with caplog.at_level("INFO", logger="agents.notifications"):
        notifications.notify_stage_transition("ID-004", {"title": "x"}, "PREV", new_stage, "a")
    assert len([r for r in caplog.records if r.name == "agents.notifications"]) == 1


def test_timeline_failure_is_swallowed_and_logged(caplog):
    with patch.object(notifications.task_logger, "get_logger", side_effect=OSError("disk")):
        with caplog.at_level("INFO", logger="agents.notifications"):
            notifications.notify_stage_transition("ID-005", {}, "A", "B", "a")
    levels = [r.levelname for r in caplog.records if r.name == "agents.notifications"]
    assert levels == ["INFO", "ERROR"]


def test_no_config_file_read_and_no_network(task_log):
    real_open = builtins.open

    def guard(path, *a, **k):
        assert "config.yaml" not in str(path)
        return real_open(path, *a, **k)

    with patch("builtins.open", side_effect=guard), \
         patch("socket.socket", side_effect=AssertionError("network used")), \
         patch("socket.create_connection", side_effect=AssertionError("network used")):
        notifications.notify_stage_transition("ID-006", {}, "A", "DONE", "a")


def test_item_without_title_does_not_matter(task_log):
    notifications.notify_stage_transition("ID-007", {}, "A", "DONE", "a")


def test_module_has_no_telegram_or_yaml_dependency():
    assert not hasattr(notifications, "telegram")
    assert not hasattr(notifications, "yaml")
    assert "agents.telegram" not in sys.modules
    with pytest.raises(ImportError):
        importlib.import_module("agents.telegram")
