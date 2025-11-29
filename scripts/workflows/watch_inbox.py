#!/usr/bin/env python3
"""
IFMOS Inbox File Watcher
Monitors inbox directory and automatically processes new files
"""

import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class InboxFileHandler(FileSystemEventHandler):
    """Handles new files in inbox directory"""

    def __init__(self, project_root: Path, delay_seconds: int = 5):
        self.project_root = project_root
        self.delay_seconds = delay_seconds
        self.processing = set()

    def on_created(self, event):
        """Called when a file is created"""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Skip hidden files and temp files
        if file_path.name.startswith('.') or file_path.name.startswith('~'):
            return

        # Skip if already processing
        if str(file_path) in self.processing:
            return

        logger.info(f"New file detected: {file_path.name}")

        # Add to processing set
        self.processing.add(str(file_path))

        # Wait for file to be completely written
        time.sleep(self.delay_seconds)

        # Process the file
        self.process_file(file_path)

        # Remove from processing set
        self.processing.discard(str(file_path))

    def process_file(self, file_path: Path):
        """Process a single file through IFMOS pipeline"""
        try:
            logger.info(f"Processing: {file_path.name}")

            # Get Python executable
            python_exe = sys.executable

            # Run auto-organize script
            auto_organize_script = self.project_root / 'scripts' / 'workflows' / 'auto_organize.py'

            result = subprocess.run(
                [python_exe, str(auto_organize_script), '--file', str(file_path)],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                logger.info(f"Successfully processed: {file_path.name}")
            else:
                logger.error(f"Error processing {file_path.name}: {result.stderr}")

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout processing: {file_path.name}")
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}")


def watch_inbox(inbox_path: str, project_root: str):
    """Start watching inbox directory"""

    inbox = Path(inbox_path)
    project = Path(project_root)

    if not inbox.exists():
        logger.error(f"Inbox directory not found: {inbox}")
        return

    logger.info("=" * 80)
    logger.info("IFMOS INBOX WATCHER")
    logger.info("=" * 80)
    logger.info(f"Watching: {inbox}")
    logger.info(f"Project root: {project}")
    logger.info("")
    logger.info("Waiting for new files... (Press Ctrl+C to stop)")
    logger.info("")

    # Create event handler and observer
    event_handler = InboxFileHandler(project, delay_seconds=5)
    observer = Observer()
    observer.schedule(event_handler, str(inbox), recursive=True)

    # Start watching
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("")
        logger.info("Stopping inbox watcher...")
        observer.stop()

    observer.join()
    logger.info("Inbox watcher stopped.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Watch inbox and auto-process files")
    parser.add_argument(
        '--inbox',
        type=str,
        default='C:/Users/kjfle/00_Inbox',
        help='Inbox directory to watch'
    )
    parser.add_argument(
        '--project',
        type=str,
        default='C:/Users/kjfle/Projects/intelligent-file-management-system',
        help='IFMOS project root'
    )

    args = parser.parse_args()

    watch_inbox(args.inbox, args.project)
