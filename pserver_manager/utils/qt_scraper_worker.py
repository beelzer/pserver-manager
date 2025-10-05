"""Qt worker for non-blocking server scraping.

This module provides Qt integration for server scraping without freezing the UI.
"""

import asyncio
from typing import TYPE_CHECKING

from qtpy.QtCore import QObject, QThread, Signal

from pserver_manager.utils.server_scraper import (
    ScraperProgress,
    ServerScrapeResult,
    scrape_servers,
)

if TYPE_CHECKING:
    from pserver_manager.config_loader import ServerDefinition


class ScraperWorker(QObject):
    """Worker that runs server scraping in a background thread."""

    # Signals
    progress_updated = Signal(str, int, int)  # message, step, total_steps
    scraping_finished = Signal(dict)  # {server_id: ServerScrapeResult}
    scraping_error = Signal(str)  # error message

    def __init__(self, servers: list["ServerDefinition"], timeout: float = 10.0):
        """Initialize worker.

        Args:
            servers: List of servers to scrape
            timeout: Timeout in seconds for each scrape
        """
        super().__init__()
        self.servers = servers
        self.timeout = timeout
        self._cancelled = False

    def run(self):
        """Run scraping in background thread."""
        try:
            # Create progress callback
            def progress_callback(message: str, step: int, total_steps: int):
                if not self._cancelled:
                    self.progress_updated.emit(message, step, total_steps)

            progress = ScraperProgress(callback=progress_callback)

            # Run scraping
            results = asyncio.run(
                scrape_servers(self.servers, timeout=self.timeout, progress=progress)
            )

            if not self._cancelled:
                self.scraping_finished.emit(results)

        except Exception as e:
            if not self._cancelled:
                self.scraping_error.emit(str(e))

    def cancel(self):
        """Cancel the scraping operation."""
        self._cancelled = True


class AsyncScraperHelper(QObject):
    """Helper class for managing scraping in Qt applications.

    Example usage:
        >>> helper = AsyncScraperHelper()
        >>> helper.progress_updated.connect(self.on_progress)
        >>> helper.finished.connect(self.on_results)
        >>> helper.start_scraping(servers)
    """

    # Expose signals at helper level
    progress_updated = Signal(str, int, int)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self):
        """Initialize helper."""
        super().__init__()
        self.thread: QThread | None = None
        self.worker: ScraperWorker | None = None

    def start_scraping(
        self, servers: list["ServerDefinition"], timeout: float = 10.0
    ) -> None:
        """Start scraping in background.

        Args:
            servers: List of servers to scrape
            timeout: Timeout in seconds
        """
        # Clean up previous thread
        if self.thread is not None:
            self.stop_scraping()

        # Create worker and thread
        self.worker = ScraperWorker(servers, timeout)
        self.thread = QThread()

        # Move worker to thread
        self.worker.moveToThread(self.thread)

        # Connect worker signals to helper signals
        self.thread.started.connect(self.worker.run)
        self.worker.progress_updated.connect(self.progress_updated.emit)
        self.worker.scraping_finished.connect(self.finished.emit)
        self.worker.scraping_finished.connect(self._on_finished)
        self.worker.scraping_error.connect(self.error.emit)
        self.worker.scraping_error.connect(self._on_error)

        # Start thread
        self.thread.start()

    def stop_scraping(self) -> None:
        """Stop scraping and clean up."""
        if self.worker:
            self.worker.cancel()

        if self.thread:
            self.thread.quit()
            self.thread.wait(5000)  # Wait up to 5 seconds
            self.thread = None

        self.worker = None

    def _on_finished(self, results: dict):
        """Handle scraping completion."""
        self.stop_scraping()

    def _on_error(self, error: str):
        """Handle scraping error."""
        self.stop_scraping()

    @property
    def is_running(self) -> bool:
        """Check if scraping is in progress."""
        return self.thread is not None and self.thread.isRunning()
