"""Qt worker for non-blocking updates fetching."""

from __future__ import annotations

from PySide6.QtCore import Signal

from pserver_manager.utils.qt_background_worker import BackgroundHelper
from pserver_manager.utils.updates_scraper import UpdatesScraper


def _fetch_updates(
    url: str,
    is_rss: bool,
    use_js: bool,
    item_selector: str,
    title_selector: str,
    link_selector: str,
    time_selector: str,
    preview_selector: str,
    limit: int,
    dropdown_selector: str | None,
    max_dropdown_options: int | None,
    forum_mode: bool,
    forum_pagination_selector: str,
    forum_page_limit: int,
    fetch_thread_content: bool,
    thread_content_selector: str,
    auto_detect_date: bool,
) -> list[dict]:
    """Fetch updates from a URL (runs in background thread).

    Args:
        url: URL to fetch updates from
        is_rss: Whether the URL is an RSS feed
        use_js: Whether to use Playwright for JavaScript rendering
        item_selector: CSS selector for update items
        title_selector: CSS selector for title within item
        link_selector: CSS selector for link within item
        time_selector: CSS selector for time/date within item
        preview_selector: CSS selector for preview text within item
        limit: Number of updates to fetch
        dropdown_selector: CSS selector for dropdown (enables dropdown mode)
        max_dropdown_options: Max number of dropdown options to process
        forum_mode: Whether to scrape forum threads (enables pagination)
        forum_pagination_selector: CSS selector for next page link in forum mode
        forum_page_limit: Maximum number of forum pages to scrape
        auto_detect_date: If True, scan update content for dates if time selector fails

    Returns:
        List of update dictionaries
    """
    scraper = UpdatesScraper()

    if is_rss:
        updates = scraper.fetch_rss_updates(url, limit)
    else:
        updates = scraper.fetch_updates(
            url,
            item_selector=item_selector,
            title_selector=title_selector,
            link_selector=link_selector,
            time_selector=time_selector,
            preview_selector=preview_selector,
            limit=limit,
            use_js=use_js,
            dropdown_selector=dropdown_selector,
            max_dropdown_options=max_dropdown_options,
            forum_mode=forum_mode,
            forum_pagination_selector=forum_pagination_selector,
            forum_page_limit=forum_page_limit,
            fetch_thread_content=fetch_thread_content,
            thread_content_selector=thread_content_selector,
            auto_detect_date=auto_detect_date,
        )

    # Convert to dictionaries for easier handling
    return [update.to_dict() for update in updates]


class UpdatesFetchHelper(BackgroundHelper[list[dict]]):
    """Helper class for managing updates fetching in Qt applications.

    This class uses the generic BackgroundHelper to eliminate boilerplate code.
    """

    # Re-export signals with more specific types for backwards compatibility
    finished = Signal(list)  # list[dict]
    error = Signal(str)

    def start_fetching(
        self,
        url: str,
        is_rss: bool = False,
        use_js: bool = False,
        selectors: dict | None = None,
        limit: int = 10,
        max_dropdown_options: int | None = None,
        forum_mode: bool = False,
        forum_pagination_selector: str = ".ipsPagination_next",
        forum_page_limit: int = 1,
        fetch_thread_content: bool = False,
        thread_content_selector: str = "",
        auto_detect_date: bool = False,
    ) -> None:
        """Start fetching updates in background.

        Args:
            url: URL to fetch updates from
            is_rss: Whether the URL is an RSS feed
            use_js: Whether to use Playwright for JavaScript rendering
            selectors: Dictionary of CSS selectors for scraping
            limit: Number of updates to fetch
            max_dropdown_options: Max number of dropdown options to process
            forum_mode: Whether to scrape forum threads (enables pagination)
            forum_pagination_selector: CSS selector for next page link in forum mode
            forum_page_limit: Maximum number of forum pages to scrape
            fetch_thread_content: Whether to fetch full content from thread pages
            thread_content_selector: CSS selector for content within thread page
            auto_detect_date: If True, scan update content for dates if time selector fails
        """
        # Default selectors
        if selectors is None:
            selectors = {}

        self.run_task(
            _fetch_updates,
            url=url,
            is_rss=is_rss,
            use_js=use_js,
            item_selector=selectors.get("item", "article"),
            title_selector=selectors.get("title", "h2, h3"),
            link_selector=selectors.get("link", "a"),
            time_selector=selectors.get("time", "time, .date, .time"),
            preview_selector=selectors.get("preview", "p"),
            limit=limit,
            dropdown_selector=selectors.get("dropdown"),
            max_dropdown_options=max_dropdown_options,
            forum_mode=forum_mode,
            forum_pagination_selector=forum_pagination_selector,
            forum_page_limit=forum_page_limit,
            fetch_thread_content=fetch_thread_content,
            thread_content_selector=thread_content_selector,
            auto_detect_date=auto_detect_date,
        )

    def stop_fetching(self) -> None:
        """Stop fetching and clean up.

        This is an alias for stop_task() to maintain backwards compatibility.
        """
        self.stop_task()
