"""Qt worker for non-blocking server scraping.

This module provides Qt integration for server scraping without freezing the UI.
"""

import asyncio
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from pserver_manager.utils.qt_background_worker import BackgroundHelper
from pserver_manager.utils.server_scraper import (
    ScraperProgress,
    ServerScrapeResult,
    scrape_servers,
)

if TYPE_CHECKING:
    from pserver_manager.config_loader import ServerDefinition


def _scrape_servers_sync(
    servers: list["ServerDefinition"], timeout: float, progress_callback
) -> dict[str, ServerScrapeResult]:
    """Scrape servers synchronously (runs in background thread).

    This function wraps the async scrape_servers with asyncio.run() so it can
    be called from a sync context (Qt thread).

    Args:
        servers: List of servers to scrape
        timeout: Timeout in seconds for each scrape
        progress_callback: Callback for progress updates

    Returns:
        Dictionary mapping server_id to ServerScrapeResult
    """
    progress = ScraperProgress(callback=progress_callback)
    return asyncio.run(scrape_servers(servers, timeout=timeout, progress=progress))


class AsyncScraperHelper(BackgroundHelper[dict]):
    """Helper class for managing scraping in Qt applications.

    This class uses the generic BackgroundHelper with special support for
    progress updates during scraping.

    Example usage:
        >>> helper = AsyncScraperHelper()
        >>> helper.progress_updated.connect(self.on_progress)
        >>> helper.finished.connect(self.on_results)
        >>> helper.start_scraping(servers)
    """

    # Additional signal for progress updates
    progress_updated = Signal(str, int, int)  # message, step, total_steps

    # Re-export signals for backwards compatibility
    finished = Signal(dict)  # {server_id: ServerScrapeResult}
    error = Signal(str)

    def start_scraping(
        self, servers: list["ServerDefinition"], timeout: float = 10.0
    ) -> None:
        """Start scraping in background.

        Args:
            servers: List of servers to scrape
            timeout: Timeout in seconds
        """

        def progress_callback(message: str, step: int, total_steps: int):
            """Emit progress updates to connected slots."""
            self.progress_updated.emit(message, step, total_steps)

        self.run_task(_scrape_servers_sync, servers, timeout, progress_callback)

    def stop_scraping(self) -> None:
        """Stop scraping and clean up.

        This is an alias for stop_task() to maintain backwards compatibility.
        """
        self.stop_task()
