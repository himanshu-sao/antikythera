import os
import sys
import logging

# Ensure the project root is in the path so imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.orchestrator import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("OrchestratorLoop")

def main():
    logger.info("Starting Antikythera Orchestrator Loop...")
    logger.info("Press Ctrl+C to stop.")
    
    try:
        while True:
            logger.info("--- Starting Pipeline Run ---")
            processed = run_pipeline()
            logger.info(f"--- Pipeline Run Complete. Processed {processed} items. ---")
            logger.info("Sleeping for 30 seconds...")
            import time
            time.sleep(30)
    except KeyboardInterrupt:
        logger.info("Orchestrator Loop stopped by user.")
    except Exception as e:
        logger.error(f"Critical error in Orchestrator loop: {e}")

if __name__ == "__main__":
    main()
