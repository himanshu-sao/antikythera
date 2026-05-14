"""
Heartbeat Scheduler — runs the pipeline on a configurable schedule.

Uses the `schedule` library for cron-like scheduling.
Default schedule: daily at 10 PM (22:00).
"""

import logging
import time
import os
import yaml

from agents import orchestrator

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.yaml")

_scheduler_running = False
_scheduler_thread = None


def _load_config():
    """
    Load configuration from config.yaml.

    Returns:
        dict: Configuration dictionary with defaults applied.
    """
    default_config = {
        "heartbeat": {
            "time": "22:00",
            "enabled": True,
        },
        "paths": {
            "project_root": ".",
            "ideas_file": "automation-ideas/ideas.md",
            "pipeline_state": "automation-ideas/pipeline-state.json",
            "requirements_dir": "automation-ideas/requirements",
            "brain_patterns": "automation-ideas/brain/patterns.md",
        },
    }
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f) or {}
            # Merge with defaults
            for key, default_val in default_config.items():
                if key not in config:
                    config[key] = default_val
                elif isinstance(default_val, dict):
                    for subkey, subval in default_val.items():
                        if subkey not in config[key]:
                            config[key][subkey] = subval
            return config
    return default_config


def run_heartbeat():
    """
    Execute a single pipeline heartbeat.

    Calls orchestrator.run_pipeline() and logs execution time and results.
    """
    import datetime

    start = datetime.datetime.utcnow()
    logger.info("Heartbeat started at %s", start.isoformat())

    try:
        processed = orchestrator.run_pipeline()
        elapsed = (datetime.datetime.utcnow() - start).total_seconds()
        logger.info(
            "Heartbeat completed in %.2f seconds. Processed %d items.",
            elapsed,
            processed,
        )
    except Exception as e:
        elapsed = (datetime.datetime.utcnow() - start).total_seconds()
        logger.error("Heartbeat failed after %.2f seconds: %s", elapsed, str(e))


def start_scheduler():
    """
    Start the heartbeat scheduler.

    Reads config for heartbeat time, runs the job immediately once,
    then schedules it for recurring execution.

    This function blocks the current thread. For non-blocking use,
    run in a separate thread.
    """
    global _scheduler_running

    import schedule

    config = _load_config()
    heartbeat_config = config.get("heartbeat", {})
    heartbeat_time = heartbeat_config.get("time", "22:00")
    enabled = heartbeat_config.get("enabled", True)

    if not enabled:
        logger.info("Heartbeat scheduler is disabled in config")
        return

    logger.info("Starting heartbeat scheduler. Schedule: daily at %s", heartbeat_time)

    # Run immediately on start
    logger.info("Running initial heartbeat...")
    run_heartbeat()

    # Schedule recurring execution
    schedule.every().day.at(heartbeat_time).do(run_heartbeat)

    _scheduler_running = True
    logger.info("Scheduler running. Next heartbeat at %s", heartbeat_time)

    try:
        while _scheduler_running:
            schedule.run_pending()
            time.sleep(30)  # Check every 30 seconds
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
        _scheduler_running = False


def stop_scheduler():
    """
    Gracefully stop the heartbeat scheduler.
    """
    global _scheduler_running
    logger.info("Stopping heartbeat scheduler...")
    _scheduler_running = False


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    start_scheduler()