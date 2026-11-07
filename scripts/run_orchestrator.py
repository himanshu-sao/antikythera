import os
import sys
import logging
import signal
import threading

# Ensure the project root is in the path so imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.orchestrator import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("OrchestratorLoop")

INTERVAL_SECONDS = 30


def run_loop(pipeline, sleep, stop, interval=INTERVAL_SECONDS):
    """Run ``pipeline()`` repeatedly until ``stop`` is set. Returns cycles run.

    2.13: an exception in a cycle is logged and the loop continues after the
    normal sleep. Only ``Exception`` is caught, so ``KeyboardInterrupt`` and
    ``SystemExit`` still propagate. ``stop`` is checked before each cycle and
    after each cycle, so a signal ends the loop after the current cycle without
    starting another. ``sleep(seconds)`` is injected so tests need not sleep.
    """
    cycles = 0
    while not stop.is_set():
        logger.info("--- Starting Pipeline Run ---")
        try:
            processed = pipeline()
            logger.info("--- Pipeline Run Complete. Processed %s items. ---", processed)
        except Exception:
            logger.exception("Pipeline run failed; continuing with the next cycle")
        cycles += 1
        if stop.is_set():
            break
        logger.info("Sleeping for %d seconds...", interval)
        sleep(interval)
    return cycles


def install_signal_handlers(stop):
    """Set ``stop`` on SIGTERM / SIGINT so the loop exits after the current cycle."""
    def _request_stop(signum, frame):
        logger.info("Received signal %s; stopping after the current cycle.", signum)
        stop.set()

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)


def main():
    logger.info("Starting Antikythera Orchestrator Loop...")
    logger.info("Press Ctrl+C to stop.")
    stop = threading.Event()
    install_signal_handlers(stop)
    # Event.wait returns early when a stop is requested, so SIGTERM does not
    # have to wait out the full interval.
    run_loop(run_pipeline, stop.wait, stop, INTERVAL_SECONDS)
    logger.info("Orchestrator Loop stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
