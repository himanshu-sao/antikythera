"""
Tests for the Heartbeat Scheduler (agents/scheduler.py).
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open


class TestRunHeartbeat:
    @patch("agents.scheduler.orchestrator.run_pipeline")
    def test_run_heartbeat_calls_orchestrator(self, mock_run_pipeline):
        """run_heartbeat should call orchestrator.run_pipeline()."""
        mock_run_pipeline.return_value = 3

        from agents.scheduler import run_heartbeat
        run_heartbeat()

        mock_run_pipeline.assert_called_once()

    @patch("agents.scheduler.orchestrator.run_pipeline")
    def test_run_heartbeat_handles_exception(self, mock_run_pipeline):
        """run_heartbeat should handle exceptions gracefully."""
        mock_run_pipeline.side_effect = Exception("Pipeline error")

        from agents.scheduler import run_heartbeat
        # Should not raise
        run_heartbeat()


class TestStartStopScheduler:
    @patch("agents.scheduler.run_heartbeat")
    @patch("agents.scheduler._load_config")
    def test_start_scheduler_disabled(self, mock_load_config, mock_heartbeat):
        """start_scheduler should not run when disabled in config."""
        mock_load_config.return_value = {
            "heartbeat": {"time": "22:00", "enabled": False},
        }

        from agents.scheduler import start_scheduler
        start_scheduler()

        mock_heartbeat.assert_not_called()

    @patch("agents.scheduler.run_heartbeat")
    @patch("agents.scheduler._load_config")
    def test_start_scheduler_runs_initial_heartbeat(self, mock_load_config, mock_heartbeat):
        """start_scheduler should run an initial heartbeat when enabled."""
        mock_load_config.return_value = {
            "heartbeat": {"time": "22:00", "enabled": True},
        }

        from agents.scheduler import start_scheduler, stop_scheduler

        # Start in a way that won't block
        import threading
        t = threading.Thread(target=start_scheduler, daemon=True)
        t.start()

        import time
        time.sleep(0.1)
        stop_scheduler()
        t.join(timeout=1)

        mock_heartbeat.assert_called_once()

    def test_stop_scheduler_sets_flag(self):
        """stop_scheduler should set the running flag to False."""
        from agents.scheduler import stop_scheduler, _scheduler_running

        # Reset
        import agents.scheduler
        agents.scheduler._scheduler_running = True

        stop_scheduler()

        assert agents.scheduler._scheduler_running is False


class TestLoadConfig:
    def test_load_config_defaults(self):
        """_load_config should return defaults when config file doesn't exist."""
        with patch("os.path.exists", return_value=False):
            from agents.scheduler import _load_config
            config = _load_config()
            assert config["heartbeat"]["time"] == "22:00"
            assert config["heartbeat"]["enabled"] is True

    def test_load_config_merges_with_defaults(self):
        """_load_config should merge partial config with defaults."""
        from agents.scheduler import _load_config
        yaml_data = "heartbeat:\n  time: \"08:00\"\n"
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=yaml_data)):
                config = _load_config()
                assert config["heartbeat"]["time"] == "08:00"
                assert config["heartbeat"]["enabled"] is True  # Default
                assert config["paths"]["pipeline_state"] == "automation-ideas/pipeline-state.json"