"""Qt worker for non-blocking Reddit post fetching."""

from __future__ import annotations

from PySide6.QtCore import Signal

from pserver_manager.utils.qt_background_worker import BackgroundHelper
from pserver_manager.utils.reddit_scraper import RedditPost, RedditScraper


def _fetch_reddit_posts(subreddit: str, limit: int, sort: str) -> list[RedditPost]:
    """Fetch Reddit posts (runs in background thread).

    Args:
        subreddit: Subreddit name (without r/ prefix)
        limit: Number of posts to fetch
        sort: Sort type ("hot" or "new")

    Returns:
        List of RedditPost objects
    """
    scraper = RedditScraper()

    if sort == "new":
        return scraper.fetch_new_posts(subreddit, limit)
    else:
        return scraper.fetch_hot_posts(subreddit, limit)


class RedditFetchHelper(BackgroundHelper[list[RedditPost]]):
    """Helper class for managing Reddit fetching in Qt applications.

    This class uses the generic BackgroundHelper to eliminate boilerplate code.
    """

    # Re-export signals with more specific types for backwards compatibility
    finished = Signal(list)  # list[RedditPost]
    error = Signal(str)

    def start_fetching(self, subreddit: str, limit: int = 10, sort: str = "hot") -> None:
        """Start fetching Reddit posts in background.

        Args:
            subreddit: Subreddit name (without r/ prefix)
            limit: Number of posts to fetch
            sort: Sort type ("hot" or "new")
        """
        self.run_task(_fetch_reddit_posts, subreddit, limit, sort)

    def stop_fetching(self) -> None:
        """Stop fetching and clean up.

        This is an alias for stop_task() to maintain backwards compatibility.
        """
        self.stop_task()
