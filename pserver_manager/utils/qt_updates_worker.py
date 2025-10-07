"""Qt worker for non-blocking updates fetching."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from pserver_manager.utils.updates_scraper import ServerUpdate, UpdatesScraper


class UpdatesWorker(QObject):
    """Worker that runs updates fetching in a background thread."""

    # Signals
    fetch_finished = Signal(list)  # list[dict]
    fetch_error = Signal(str)  # error message

    def __init__(
        self,
        url: str,
        is_rss: bool = False,
        use_js: bool = False,
        item_selector: str = "article",
        title_selector: str = "h2, h3",
        link_selector: str = "a",
        time_selector: str = "time, .date, .time",
        preview_selector: str = "p",
        limit: int = 10,
    ):
        """Initialize worker.

        Args:
            url: URL to fetch updates from
            is_rss: Whether the URL is an RSS feed
            item_selector: CSS selector for update items
            title_selector: CSS selector for title within item
            link_selector: CSS selector for link within item
            time_selector: CSS selector for time/date within item
            preview_selector: CSS selector for preview text within item
            limit: Number of updates to fetch
        """
        super().__init__()
        self.url = url
        self.is_rss = is_rss
        self.use_js = use_js
        self.item_selector = item_selector
        self.title_selector = title_selector
        self.link_selector = link_selector
        self.time_selector = time_selector
        self.preview_selector = preview_selector
        self.limit = limit
        self._cancelled = False

    def run(self):
        """Run fetching in background thread."""
        try:
            scraper = UpdatesScraper()

            if self.is_rss:
                updates = scraper.fetch_rss_updates(self.url, self.limit)
            else:
                updates = scraper.fetch_updates(
                    self.url,
                    item_selector=self.item_selector,
                    title_selector=self.title_selector,
                    link_selector=self.link_selector,
                    time_selector=self.time_selector,
                    preview_selector=self.preview_selector,
                    limit=self.limit,
                    use_js=self.use_js,
                )

            if not self._cancelled:
                # Convert to dictionaries for easier handling
                updates_dict = [update.to_dict() for update in updates]
                self.fetch_finished.emit(updates_dict)

        except Exception as e:
            if not self._cancelled:
                self.fetch_error.emit(str(e))

    def cancel(self):
        """Cancel the fetch operation."""
        self._cancelled = True


class UpdatesFetchHelper(QObject):
    """Helper class for managing updates fetching in Qt applications."""

    # Expose signals at helper level
    finished = Signal(list)  # list[dict]
    error = Signal(str)

    def __init__(self):
        """Initialize helper."""
        super().__init__()
        self.thread: QThread | None = None
        self.worker: UpdatesWorker | None = None

    def start_fetching(
        self,
        url: str,
        is_rss: bool = False,
        use_js: bool = False,
        selectors: dict | None = None,
        limit: int = 10,
    ) -> None:
        """Start fetching updates in background.

        Args:
            url: URL to fetch updates from
            is_rss: Whether the URL is an RSS feed
            use_js: Whether to use Playwright for JavaScript rendering
            selectors: Dictionary of CSS selectors for scraping
            limit: Number of updates to fetch
        """
        # Clean up previous thread
        if self.thread is not None:
            self.stop_fetching()

        # Default selectors
        if selectors is None:
            selectors = {}

        # Create worker and thread
        self.worker = UpdatesWorker(
            url=url,
            is_rss=is_rss,
            use_js=use_js,
            item_selector=selectors.get("item", "article"),
            title_selector=selectors.get("title", "h2, h3"),
            link_selector=selectors.get("link", "a"),
            time_selector=selectors.get("time", "time, .date, .time"),
            preview_selector=selectors.get("preview", "p"),
            limit=limit,
        )
        self.thread = QThread()

        # Move worker to thread
        self.worker.moveToThread(self.thread)

        # Connect worker signals to helper signals
        self.thread.started.connect(self.worker.run)
        self.worker.fetch_finished.connect(self.finished.emit)
        self.worker.fetch_finished.connect(self._on_finished)
        self.worker.fetch_error.connect(self.error.emit)
        self.worker.fetch_error.connect(self._on_error)

        # Start thread
        self.thread.start()

    def stop_fetching(self) -> None:
        """Stop fetching and clean up."""
        if self.worker:
            self.worker.cancel()

        if self.thread:
            self.thread.quit()
            self.thread.wait(5000)  # Wait up to 5 seconds
            self.thread = None

        self.worker = None

    def _on_finished(self, updates: list):
        """Handle fetch completion."""
        self.stop_fetching()

    def _on_error(self, error: str):
        """Handle fetch error."""
        self.stop_fetching()

    @property
    def is_running(self) -> bool:
        """Check if fetching is in progress."""
        return self.thread is not None and self.thread.isRunning()
