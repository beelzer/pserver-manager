"""Data fetch service for managing all data fetching operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from pserver_manager.utils.qt_reddit_worker import RedditFetchHelper
from pserver_manager.utils.qt_updates_worker import UpdatesFetchHelper
from pserver_manager.utils.batch_scanner import BatchScanHelper

if TYPE_CHECKING:
    from pserver_manager.config_loader import ServerDefinition


class DataFetchService(QObject):
    """Service for managing all data fetching operations."""

    # Signals for Reddit
    reddit_fetched = Signal(list)  # posts
    reddit_error = Signal(str)  # error message

    # Signals for Updates
    updates_fetched = Signal(list)  # updates
    updates_error = Signal(str)  # error message

    # Signals for batch scanning
    scan_progress = Signal(int, int, str)  # current, total, server_name
    server_data_complete = Signal(str, object)  # server_id, ServerDataResult
    batch_scan_finished = Signal(dict)  # all_results
    scan_error = Signal(str)  # error message

    def __init__(self) -> None:
        """Initialize data fetch service."""
        super().__init__()

        # Initialize Reddit fetch helper
        self._reddit_helper = RedditFetchHelper()
        self._reddit_helper.finished.connect(self._on_reddit_fetched)
        self._reddit_helper.error.connect(self._on_reddit_error)

        # Initialize Updates fetch helper
        self._updates_helper = UpdatesFetchHelper()
        self._updates_helper.finished.connect(self._on_updates_fetched)
        self._updates_helper.error.connect(self._on_updates_error)

        # Initialize batch scanner
        self._batch_scanner = BatchScanHelper()
        self._batch_scanner.progress.connect(self.scan_progress.emit)
        self._batch_scanner.data_complete.connect(self.server_data_complete.emit)
        self._batch_scanner.finished.connect(self.batch_scan_finished.emit)
        self._batch_scanner.error.connect(self.scan_error.emit)

    def fetch_reddit_posts(self, subreddit: str, limit: int = 15, sort: str = "hot") -> None:
        """Fetch Reddit posts for a subreddit.

        Args:
            subreddit: Subreddit name (without r/ prefix)
            limit: Number of posts to fetch
            sort: Sort order (hot, new, top)
        """
        self._reddit_helper.start_fetching(subreddit, limit=limit, sort=sort)

    def fetch_updates(
        self,
        url: str,
        is_rss: bool,
        use_js: bool,
        selectors: dict,
        limit: int = 10,
        max_dropdown_options: int | None = None,
        forum_mode: bool = False,
        forum_pagination_selector: str = ".ipsPagination_next",
        forum_page_limit: int = 1,
        fetch_thread_content: bool = False,
        thread_content_selector: str = "",
        auto_detect_date: bool = False,
        wiki_mode: bool = False,
        wiki_update_link_selector: str = "a[href*='/wiki/Updates/']",
        wiki_content_selector: str = ".mw-parser-output",
    ) -> None:
        """Fetch server updates from a URL.

        Args:
            url: Updates URL
            is_rss: Whether URL is RSS feed
            use_js: Whether to use JavaScript rendering
            selectors: CSS selectors dict
            limit: Number of updates to fetch
            max_dropdown_options: Max dropdown options for dropdown-based changelogs
            forum_mode: Whether to scrape forum threads (enables pagination)
            forum_pagination_selector: CSS selector for next page link in forum mode
            forum_page_limit: Maximum number of forum pages to scrape
            fetch_thread_content: Whether to fetch full content from thread pages
            thread_content_selector: CSS selector for content within thread page
            auto_detect_date: If True, scan update content for dates if time selector fails
            wiki_mode: Whether to scrape MediaWiki-based updates
            wiki_update_link_selector: CSS selector for update page links in wiki mode
            wiki_content_selector: CSS selector for content within wiki update pages
        """
        self._updates_helper.start_fetching(
            url=url,
            is_rss=is_rss,
            use_js=use_js,
            selectors=selectors,
            limit=limit,
            max_dropdown_options=max_dropdown_options,
            forum_mode=forum_mode,
            forum_pagination_selector=forum_pagination_selector,
            forum_page_limit=forum_page_limit,
            fetch_thread_content=fetch_thread_content,
            thread_content_selector=thread_content_selector,
            auto_detect_date=auto_detect_date,
            wiki_mode=wiki_mode,
            wiki_update_link_selector=wiki_update_link_selector,
            wiki_content_selector=wiki_content_selector,
        )

    def start_batch_scan(self, servers: list[ServerDefinition], max_workers: int = 5) -> None:
        """Start batch data fetching for multiple servers.

        Args:
            servers: List of servers to fetch data for
            max_workers: Maximum number of concurrent operations
        """
        self._batch_scanner.start_batch_fetch(servers, max_workers)

    def stop_batch_scan(self) -> None:
        """Stop current batch scanning operation."""
        self._batch_scanner.stop_fetch()

    def _on_reddit_fetched(self, posts: list) -> None:
        """Handle Reddit posts being fetched.

        Args:
            posts: List of RedditPost objects
        """
        self.reddit_fetched.emit(posts)

    def _on_reddit_error(self, error: str) -> None:
        """Handle Reddit fetch error.

        Args:
            error: Error message
        """
        self.reddit_error.emit(error)

    def _on_updates_fetched(self, updates: list) -> None:
        """Handle updates being fetched.

        Args:
            updates: List of update dictionaries
        """
        self.updates_fetched.emit(updates)

    def _on_updates_error(self, error: str) -> None:
        """Handle updates fetch error.

        Args:
            error: Error message
        """
        self.updates_error.emit(error)
