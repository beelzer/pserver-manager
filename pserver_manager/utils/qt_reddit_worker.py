"""Qt worker for non-blocking Reddit post fetching."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from pserver_manager.utils.reddit_scraper import RedditPost, RedditScraper


class RedditWorker(QObject):
    """Worker that runs Reddit fetching in a background thread."""

    # Signals
    fetch_finished = Signal(list)  # list[RedditPost]
    fetch_error = Signal(str)  # error message

    def __init__(self, subreddit: str, limit: int = 10, sort: str = "hot"):
        """Initialize worker.

        Args:
            subreddit: Subreddit name (without r/ prefix)
            limit: Number of posts to fetch
            sort: Sort type ("hot" or "new")
        """
        super().__init__()
        self.subreddit = subreddit
        self.limit = limit
        self.sort = sort
        self._cancelled = False

    def run(self):
        """Run fetching in background thread."""
        try:
            scraper = RedditScraper()

            if self.sort == "new":
                posts = scraper.fetch_new_posts(self.subreddit, self.limit)
            else:
                posts = scraper.fetch_hot_posts(self.subreddit, self.limit)

            if not self._cancelled:
                self.fetch_finished.emit(posts)

        except Exception as e:
            if not self._cancelled:
                self.fetch_error.emit(str(e))

    def cancel(self):
        """Cancel the fetch operation."""
        self._cancelled = True


class RedditFetchHelper(QObject):
    """Helper class for managing Reddit fetching in Qt applications."""

    # Expose signals at helper level
    finished = Signal(list)  # list[RedditPost]
    error = Signal(str)

    def __init__(self):
        """Initialize helper."""
        super().__init__()
        self.thread: QThread | None = None
        self.worker: RedditWorker | None = None

    def start_fetching(self, subreddit: str, limit: int = 10, sort: str = "hot") -> None:
        """Start fetching Reddit posts in background.

        Args:
            subreddit: Subreddit name (without r/ prefix)
            limit: Number of posts to fetch
            sort: Sort type ("hot" or "new")
        """
        # Clean up previous thread
        if self.thread is not None:
            self.stop_fetching()

        # Create worker and thread
        self.worker = RedditWorker(subreddit, limit, sort)
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

    def _on_finished(self, posts: list):
        """Handle fetch completion."""
        self.stop_fetching()

    def _on_error(self, error: str):
        """Handle fetch error."""
        self.stop_fetching()

    @property
    def is_running(self) -> bool:
        """Check if fetching is in progress."""
        return self.thread is not None and self.thread.isRunning()
