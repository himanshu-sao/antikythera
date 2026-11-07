import os
import json
import pytest

from agents.logger import TaskLogger, get_logger

def test_logger_write_and_read(tmp_path):
    logger = TaskLogger(item_id="id-001", base_dir=str(tmp_path))
    logger.info(agent="tester", action="start", message="begin")
    logger.warn(agent="tester", action="check", message="caution")
    logger.error(agent="tester", action="fail", message="boom")
    logs = logger.get_logs()
    assert len(logs) == 3
    # Verify ordering by timestamp (should be increasing)
    timestamps = [log["timestamp"] for log in logs]
    assert timestamps == sorted(timestamps)
    # Verify levels
    assert logs[0]["level"] == "INFO"
    assert logs[1]["level"] == "WARN"
    assert logs[2]["level"] == "ERROR"
    # The singleton helper is keyed by directory: a logger for an explicit
    # base_dir is not the default-directory logger, and the default one is cached.
    default = get_logger("ID-001")
    assert default is not logger
    assert get_logger("ID-001") is default
    assert default.log_dir != logger.log_dir
