"""Info panel controller for managing info panel data and state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from pserver_manager.config_loader import GameDefinition, ServerDefinition
    from pserver_manager.services.cache_service import CacheService, ServerDataCache
    from pserver_manager.services.data_fetch_service import DataFetchService
    from pserver_manager.widgets.info_panel import InfoPanel
    from qtframework.widgets.advanced import NotificationManager


class InfoPanelController(QObject):
    """Controller for managing info panel operations."""

    # Signals
    panel_should_show = Signal()
    panel_should_hide = Signal()

    def __init__(
        self,
        info_panel: InfoPanel,
        data_fetch_service: DataFetchService,
        cache_service: CacheService,
        notifications: NotificationManager,
    ) -> None:
        """Initialize info panel controller.

        Args:
            info_panel: Info panel widget
            data_fetch_service: Data fetch service
            cache_service: Cache service
            notifications: Notification manager
        """
        super().__init__()
        self._info_panel = info_panel
        self._data_fetch_service = data_fetch_service
        self._cache_service = cache_service
        self._notifications = notifications

        # Connect data fetch signals
        self._data_fetch_service.reddit_fetched.connect(self._on_reddit_fetched)
        self._data_fetch_service.reddit_error.connect(self._on_reddit_error)
        self._data_fetch_service.updates_fetched.connect(self._on_updates_fetched)
        self._data_fetch_service.updates_error.connect(self._on_updates_error)

    def load_game_data(self, game: GameDefinition) -> None:
        """Load data for a game (Reddit and updates).

        Args:
            game: Game definition
        """
        # Clear server info since we're viewing game-level data
        self._info_panel.set_server_info(None)

        has_reddit = bool(game.reddit)
        has_updates = bool(game.updates_url)

        if has_reddit:
            self._info_panel.set_subreddit(game.reddit)
            self._data_fetch_service.fetch_reddit_posts(game.reddit, limit=15, sort="hot")
        else:
            self._info_panel.set_subreddit("")

        if has_updates:
            self._info_panel.set_updates_url(game.updates_url)
            self._fetch_updates_with_cache(
                url=game.updates_url,
                is_rss=game.updates_is_rss,
                use_js=game.updates_use_js,
                selectors=game.updates_selectors,
                limit=10,
                max_dropdown_options=game.updates_max_dropdown_options,
                forum_mode=game.updates_forum_mode,
                forum_pagination_selector=game.updates_forum_pagination_selector,
                forum_page_limit=game.updates_forum_page_limit,
            )
        else:
            self._info_panel.set_updates_url("")

        # Always keep panel visible - Info tab is persistent and available for server selection
        # Even if the game has no Reddit/Updates, the Info tab will show server data when selected
        self.panel_should_show.emit()

    def load_server_data(self, server: ServerDefinition) -> None:
        """Load data for a server.

        Args:
            server: Server definition
        """
        # Always show Info tab with server information
        self._info_panel.set_server_info(server)

        has_reddit = bool(server.reddit)
        has_updates = bool(server.updates_url)

        # Get cached data if available
        cached_data = self._cache_service.get_server_data(server.id)

        if has_reddit:
            self._info_panel.set_subreddit(server.reddit)
            if cached_data and cached_data.reddit_posts is not None:
                self._info_panel.set_posts(cached_data.reddit_posts)
            elif cached_data and cached_data.reddit_error:
                self._info_panel.set_content(f"Error loading Reddit posts:\n{cached_data.reddit_error}")
            else:
                self._info_panel.set_content("Reddit data not loaded. Use File > Refresh Reddit to fetch.")
        else:
            self._info_panel.set_subreddit("")

        if has_updates:
            self._info_panel.set_updates_url(server.updates_url)
            if cached_data and cached_data.updates is not None:
                updates_dict = [update.to_dict() for update in cached_data.updates]
                self._info_panel.set_updates(updates_dict)
            elif cached_data and cached_data.updates_error:
                self._info_panel.set_content(f"Error loading updates:\n{cached_data.updates_error}")
            else:
                self._info_panel.set_content("Updates not loaded. Use File > Refresh Updates to fetch.")
        else:
            self._info_panel.set_updates_url("")

        # Panel should always be visible (Info tab is always present)
        self.panel_should_show.emit()

    def refresh_reddit(self, server: ServerDefinition) -> None:
        """Refresh Reddit data for a server.

        Args:
            server: Server definition
        """
        if not server.reddit:
            self._notifications.warning("No Reddit", "Selected server has no Reddit configured")
            return

        self._data_fetch_service.fetch_reddit_posts(server.reddit, limit=15, sort="hot")
        self._notifications.info("Refreshing", f"Fetching Reddit posts for {server.name}...")

    def refresh_updates(self, server: ServerDefinition) -> None:
        """Refresh updates data for a server.

        Args:
            server: Server definition
        """
        if not server.updates_url:
            self._notifications.warning("No Updates", "Selected server has no updates configured")
            return

        self._fetch_updates_with_cache(
            url=server.updates_url,
            is_rss=server.updates_is_rss,
            use_js=server.updates_use_js,
            selectors=server.updates_selectors,
            limit=getattr(server, 'updates_limit', 10),
            max_dropdown_options=server.updates_max_dropdown_options,
            forum_mode=server.updates_forum_mode,
            forum_pagination_selector=server.updates_forum_pagination_selector,
            forum_page_limit=server.updates_forum_page_limit,
            force=True,
        )
        self._notifications.info("Refreshing", f"Fetching updates for {server.name}...")

    def force_refresh_updates(self, game: GameDefinition) -> None:
        """Force refresh updates for a game (bypass cache).

        Args:
            game: Game definition
        """
        if not game.updates_url:
            self._notifications.warning("No Updates", "No updates source available for current selection")
            return

        self._fetch_updates_with_cache(
            url=game.updates_url,
            is_rss=game.updates_is_rss,
            use_js=game.updates_use_js,
            selectors=game.updates_selectors,
            limit=10,
            max_dropdown_options=game.updates_max_dropdown_options,
            forum_mode=game.updates_forum_mode,
            forum_pagination_selector=game.updates_forum_pagination_selector,
            forum_page_limit=game.updates_forum_page_limit,
            force=True,
        )
        self._notifications.info("Refreshing", "Fetching latest updates...")

    def _fetch_updates_with_cache(
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
        force: bool = False,
    ) -> None:
        """Fetch updates with cache checking.

        Args:
            url: Updates URL
            is_rss: Whether URL is RSS feed
            use_js: Whether to use JavaScript rendering
            selectors: CSS selectors dict
            limit: Number of updates to fetch
            max_dropdown_options: Max dropdown options
            forum_mode: Whether to scrape forum threads
            forum_pagination_selector: CSS selector for next page link
            forum_page_limit: Maximum number of forum pages
            force: If True, bypass cache
        """
        # Check cache unless force refresh
        if not force and not self._cache_service.should_fetch_updates(url):
            cached_updates = self._cache_service.get_cached_updates(url)
            if cached_updates:
                self._info_panel.set_updates(cached_updates)
                return

        # Fetch updates
        self._data_fetch_service.fetch_updates(
            url=url,
            is_rss=is_rss,
            use_js=use_js,
            selectors=selectors,
            limit=limit,
            max_dropdown_options=max_dropdown_options,
            forum_mode=forum_mode,
            forum_pagination_selector=forum_pagination_selector,
            forum_page_limit=forum_page_limit,
        )

    def _on_reddit_fetched(self, posts: list) -> None:
        """Handle Reddit posts being fetched.

        Args:
            posts: List of RedditPost objects
        """
        self._info_panel.set_posts(posts)

    def _on_reddit_error(self, error: str) -> None:
        """Handle Reddit fetch error.

        Args:
            error: Error message
        """
        self._info_panel.set_content(f"Error loading Reddit posts:\n{error}")

    def _on_updates_fetched(self, updates: list) -> None:
        """Handle updates being fetched.

        Args:
            updates: List of update dictionaries
        """
        # Cache the updates
        if self._info_panel._updates_url:
            self._cache_service.cache_updates(self._info_panel._updates_url, updates)

        self._info_panel.set_updates(updates)

    def _on_updates_error(self, error: str) -> None:
        """Handle updates fetch error.

        Args:
            error: Error message
        """
        from PySide6.QtWidgets import QLabel

        self._info_panel._clear_updates_cards()
        label = QLabel(f"Error loading updates:\n{error}")
        label.setWordWrap(True)
        self._info_panel._updates_cards_layout.insertWidget(0, label)

    def hide_panel(self) -> None:
        """Hide the info panel."""
        self._info_panel.hide()
        self._info_panel._is_collapsed = False

    def show_panel(self) -> None:
        """Show the info panel."""
        self._info_panel.show()
        if self._info_panel.is_collapsed():
            self._info_panel.expand()

    def toggle_panel(self) -> None:
        """Toggle panel collapsed/expanded state."""
        if self._info_panel.is_collapsed():
            self._info_panel.expand()
        else:
            self._info_panel.collapse()
