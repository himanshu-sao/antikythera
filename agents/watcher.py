"""
File watcher agent for Hermes system.
Monitors the automation-ideas/ directory for changes and triggers appropriate events.
"""

import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HermesFileHandler(FileSystemEventHandler):
    """Handler for file system events in the automation-ideas directory."""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self._last_trigger_times = {} # Map of file_path -> last_trigger_time
        self._debounce_interval = 2.0 # seconds
        super().__init__()
    
    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory:
            logger.info(f"File modified: {event.src_path}")
            # Trigger appropriate pipeline actions
            self._handle_file_event(event.src_path, 'modified')
    
    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory:
            logger.info(f"File created: {event.src_path}")
            self._handle_file_event(event.src_path, 'created')
    
    def on_moved(self, event):
        """Handle file move events."""
        logger.info(f"File moved: {event.src_path} -> {event.dest_path}")
        if not event.is_directory:
            self._handle_file_event(event.dest_path, 'moved')
    
    def _handle_file_event(self, file_path, event_type):
        """Handle file events by triggering appropriate actions with debouncing."""
        current_time = time.time()
        last_trigger = self._last_trigger_times.get(file_path, 0)

        if current_time - last_trigger < self._debounce_interval:
            logger.info(f"Debouncing event {event_type} for {file_path}")
            return

        self._last_trigger_times[file_path] = current_time

        # Check if it's an ideas.md file
        if 'ideas.md' in file_path:
            if hasattr(self.orchestrator, 'handle_new_idea'):
                self.orchestrator.handle_new_idea(file_path)
        # Check if it's a review.md file
        elif 'review.md' in file_path:
            if hasattr(self.orchestrator, 'handle_review_update'):
                self.orchestrator.handle_review_update(file_path)

class FileWatcher:
    """Main file watcher class for monitoring automation-ideas directory."""
    
    def __init__(self, watch_path="./automation-ideas", orchestrator=None):
        self.watch_path = watch_path
        self.orchestrator = orchestrator
        self.observer = Observer()
        self.handler = HermesFileHandler(orchestrator)
        
    def start(self):
        """Start the file watcher."""
        self.observer.schedule(self.handler, self.watch_path, recursive=True)
        self.observer.start()
        logger.info(f"Started watching {self.watch_path}")
        
    def stop(self):
        """Stop the file watcher."""
        self.observer.stop()
        self.observer.join()
        logger.info("Stopped watching")
        
    def __enter__(self):
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

# Example usage
if __name__ == "__main__":
    # Example of how to use the watcher
    watcher = FileWatcher()
    try:
        watcher.start()
        # Keep the watcher running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watcher.stop()