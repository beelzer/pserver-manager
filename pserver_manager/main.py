"""Main application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QSplitter

from qtframework import Application
from qtframework.config import ConfigManager
from qtframework.core import BaseWindow
from qtframework.plugins import PluginManager
from qtframework.utils import ResourceManager
from qtframework.widgets import VBox
from qtframework.widgets.buttons import Button, ButtonSize, ButtonVariant
from qtframework.widgets.advanced import NotificationManager
from qtframework.widgets.advanced.notifications import NotificationPosition

from pserver_manager.config_loader import ColumnDefinition, ConfigLoader, GameDefinition, ServerDefinition
from pserver_manager.models import Game
from pserver_manager.utils import ServerUpdateChecker, get_app_paths
from pserver_manager.utils.qt_reddit_worker import RedditFetchHelper
from pserver_manager.utils.qt_updates_worker import UpdatesFetchHelper
from pserver_manager.utils.schema_migrations import migrate_user_servers
from pserver_manager.widgets import GameSidebar, InfoPanel, ServerTable
from pserver_manager.widgets.server_editor import ServerEditor
from pserver_manager.widgets.preferences_dialog import PreferencesDialog
from pserver_manager.widgets.update_dialog import UpdateDialog


class MainWindow(BaseWindow):
    """Main application window."""

    def __init__(self, application: Application) -> None:
        """Initialize main window.

        Args:
            application: Application instance
        """
        # Initialize path management
        self._app_paths = get_app_paths()
        self._app_paths.ensure_directories()

        # Migrate old config if it exists and has servers (only run once)
        migration_marker = self._app_paths.get_user_data_dir() / ".migration_complete"
        old_config_dir = Path(__file__).parent / "config"
        old_servers_dir = old_config_dir / "servers"
        new_servers_dir = self._app_paths.get_servers_dir()

        # Check if old servers exist, new directory is empty, and migration hasn't run before
        needs_migration = (
            not migration_marker.exists()
            and old_servers_dir.exists()
            and any(old_servers_dir.rglob("*.yaml"))
            and not any(new_servers_dir.rglob("*.yaml"))
        )

        if needs_migration:
            print("Migrating old configuration to new location...")
            if self._app_paths.migrate_old_config(old_config_dir):
                print(f"Configuration migrated to: {self._app_paths.get_user_data_dir()}")
                # Mark migration as complete
                migration_marker.write_text("Migration completed")
        elif not migration_marker.exists() and not any(new_servers_dir.rglob("*.yaml")):
            # First run with empty directory - mark as complete to skip future migrations
            migration_marker.write_text("No migration needed")

        # Migrate user servers to current schema if needed
        user_servers_dir = self._app_paths.get_servers_dir()
        if user_servers_dir.exists() and any(user_servers_dir.rglob("*.yaml")):
            print("Checking server configurations for schema updates...")
            migration_report = migrate_user_servers(user_servers_dir, show_report=False)
            if migration_report["migrated"] > 0:
                print(f"Migrated {migration_report['migrated']} server(s) to current schema")

        # Initialize config manager
        self._config_manager = ConfigManager()
        self._init_config()

        # Initialize data before parent init (which calls _setup_ui)
        # Game definitions still from bundled config, servers from user directory
        self._config_loader = ConfigLoader(
            config_dir=Path(__file__).parent / "config",
            servers_dir=self._app_paths.get_servers_dir(),
        )
        self._game_defs: list[GameDefinition] = []
        self._all_servers = []
        self._current_game: GameDefinition | None = None
        self._current_server: ServerDefinition | None = None
        self._load_config()

        super().__init__(application=application)
        self.setWindowTitle("PServer Manager")
        self.setMinimumSize(1280, 800)

        # Setup notification manager
        self._notifications = NotificationManager(self)
        self._notifications.set_position(NotificationPosition.BOTTOM_RIGHT)

        # Initialize update checker
        bundled_servers_dir = Path(__file__).parent / "config" / "servers"
        user_servers_dir = self._app_paths.get_servers_dir()
        bundled_themes_dir = Path(__file__).parent / "themes"
        user_themes_dir = self._app_paths.get_themes_dir()
        self._update_checker = ServerUpdateChecker(
            bundled_servers_dir, user_servers_dir, bundled_themes_dir, user_themes_dir
        )

        # Initialize Reddit fetch helper
        self._reddit_helper = RedditFetchHelper()
        self._reddit_helper.finished.connect(self._on_reddit_posts_fetched)
        self._reddit_helper.error.connect(self._on_reddit_error)

        # Initialize Updates fetch helper
        self._updates_helper = UpdatesFetchHelper()
        self._updates_helper.finished.connect(self._on_updates_fetched)
        self._updates_helper.error.connect(self._on_updates_error)

        # Track last fetch time for updates (URL -> timestamp)
        self._updates_last_fetch: dict[str, float] = {}
        self._updates_cache: dict[str, list[dict]] = {}  # URL -> cached updates
        self._updates_cache_hours = 24  # Cache updates for 24 hours

        # Batch scanner for parallel server scanning
        from pserver_manager.utils.batch_scanner import BatchScanHelper

        self._batch_scanner = BatchScanHelper()
        self._batch_scanner.progress.connect(self._on_scan_progress)
        self._batch_scanner.data_complete.connect(self._on_server_data_complete)
        self._batch_scanner.finished.connect(self._on_batch_scan_finished)
        self._batch_scanner.error.connect(self._on_scan_error)
        self._server_data_cache: dict[str, object] = {}  # Cache all server data  # server_id -> ScanResult

        # Check for updates on startup (after window is shown)
        from PySide6.QtCore import QTimer

        QTimer.singleShot(1000, self._check_for_updates_on_startup)
        QTimer.singleShot(2000, self._start_batch_scan_if_enabled)

    def _init_config(self) -> None:
        """Initialize configuration with defaults."""
        config_file = self._app_paths.get_settings_file()

        # Try to load existing config
        if config_file.exists():
            try:
                self._config_manager.load_file(config_file)
            except Exception as e:
                print(f"Warning: Could not load config file: {e}")
                self._load_default_config()
        else:
            # Load defaults and save to file
            self._load_default_config()
            config_file.parent.mkdir(parents=True, exist_ok=True)
            self._config_manager.save(config_file)

    def _load_default_config(self) -> None:
        """Load default configuration."""
        self._config_manager.load_defaults({
            "ui": {
                "theme": "dark",
                "auto_refresh_interval": 300,
                "show_offline_servers": True,
            },
            "scanning": {
                "scan_on_startup": True,
                "parallel_scan_limit": 5,
            },
            "network": {
                "ping_timeout": 3,
                "max_retries": 3,
                "concurrent_pings": 10,
            },
            "display": {
                "compact_view": False,
                "show_icons": True,
            },
        })

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        # Create menu bar (store reference for later use)
        menubar = self._create_menu_bar()

        # Create main container
        main_layout = VBox(spacing=0, margins=0)

        # Create splitter for sidebar and content
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Create sidebar
        self._sidebar = GameSidebar()
        games = [gd.to_game() for gd in self._game_defs]
        self._sidebar.set_games(games, self._all_servers)
        self._sidebar.all_servers_selected.connect(self._on_all_servers_selected)
        self._sidebar.game_selected.connect(self._on_game_selected)
        self._sidebar.version_selected.connect(self._on_version_selected)
        self._sidebar.setMinimumWidth(250)
        self._sidebar.setMaximumWidth(400)

        # Create server table
        self._server_table = ServerTable()
        self._show_all_servers()  # Show all servers by default
        self._server_table.server_selected.connect(self._on_server_selected)
        self._server_table.server_double_clicked.connect(self._on_server_double_clicked)
        self._server_table.edit_server_requested.connect(self._on_edit_server)
        self._server_table.delete_server_requested.connect(self._on_delete_server)
        self._server_table.manage_accounts_requested.connect(self._on_manage_accounts)
        self._server_table.register_requested.connect(self._on_register)
        self._server_table.login_requested.connect(self._on_login)

        # Create Info panel (Reddit + Updates tabs)
        self._info_panel = InfoPanel()
        self._info_panel.hide()  # Hidden by default
        self._info_panel.collapsed_changed.connect(self._on_info_panel_collapsed_changed)

        # Create Info menubar button (toggles panel visibility)
        # Must be created before adding to splitter and set as menubar corner widget
        self._info_menubar_button = Button(
            "▶ Info",
            size=ButtonSize.COMPACT,
            variant=ButtonVariant.PRIMARY
        )
        self._info_menubar_button.clicked.connect(self._on_info_menubar_button_clicked)
        self._info_menubar_button.setToolTip("Show info panel")
        # Override ONLY size properties to fit menubar, preserve theme colors
        self._info_menubar_button.setStyleSheet("""
            QPushButton {
                padding: 2px 8px;
                min-height: 0px;
                max-height: 22px;
                margin-right: 5px;
            }
        """)
        self._info_menubar_button.hide()  # Hidden by default
        menubar.setCornerWidget(self._info_menubar_button, Qt.Corner.TopRightCorner)

        # Add to splitter
        splitter.addWidget(self._sidebar)
        splitter.addWidget(self._server_table)
        splitter.addWidget(self._info_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)

        # Add splitter with stretch to fill vertical space
        main_layout.add_widget(splitter, stretch=1)

        # Create status bar at the bottom
        self._setup_status_bar(main_layout)

        # Set central widget
        self.setCentralWidget(main_layout)

    def _setup_status_bar(self, parent_layout) -> None:
        """Setup status bar with progress indication.

        Args:
            parent_layout: Parent layout to add status bar to
        """
        from PySide6.QtWidgets import QLabel, QProgressBar

        from qtframework.widgets import HBox

        # Create status bar container
        status_bar = HBox(spacing=8, margins=(8, 4, 8, 4))

        # Status label (left side)
        self._status_label = QLabel("Ready")
        status_bar.add_widget(self._status_label)

        status_bar.add_stretch()

        # Progress bar (right side, initially hidden)
        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFixedWidth(200)
        self._progress_bar.setVisible(False)
        status_bar.add_widget(self._progress_bar)

        parent_layout.add_widget(status_bar)

    def _create_theme_menu(self, theme_menu) -> None:
        """Create theme submenu with available themes.

        Args:
            theme_menu: Theme menu to populate
        """
        theme_manager = self.application.theme_manager
        theme_names = theme_manager.list_themes()

        # Create action group for exclusive theme selection
        theme_action_group = QActionGroup(self)
        theme_action_group.setExclusive(True)

        # Store theme actions for updating later
        self._theme_menu_actions = {}

        current_theme = theme_manager.get_current_theme()

        for theme_name in theme_names:
            theme_info = theme_manager.get_theme_info(theme_name)
            display_name = (
                theme_info.get("display_name", theme_name.replace("_", " ").title())
                if theme_info
                else theme_name.replace("_", " ").title()
            )

            action = QAction(display_name, self)
            action.setCheckable(True)
            action.setData(theme_name)

            # Check if this is the current theme
            if current_theme and current_theme.name == theme_name:
                action.setChecked(True)

            # Connect to apply theme
            action.triggered.connect(lambda checked, tn=theme_name: self._apply_theme(tn))

            theme_action_group.addAction(action)
            theme_menu.addAction(action)

            # Store action for later updates
            self._theme_menu_actions[theme_name] = action

        # Connect to theme manager's theme_changed signal to update menu
        def update_theme_menu(new_theme_name: str):
            """Update checked state of theme menu items."""
            for theme_name, action in self._theme_menu_actions.items():
                action.setChecked(theme_name == new_theme_name)

        theme_manager.theme_changed.connect(update_theme_menu)

    def _apply_theme(self, theme_name: str) -> None:
        """Apply selected theme.

        Args:
            theme_name: Theme name to apply
        """
        self.application.theme_manager.set_theme(theme_name)
        # Update config to persist theme selection
        self._config_manager.set("ui.theme", theme_name)
        config_file = self._app_paths.get_settings_file()
        self._config_manager.save(config_file)

    def _create_menu_bar(self):
        """Create the menu bar.

        Returns:
            The menubar instance
        """
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        add_server_action = QAction("&Add Server", self)
        add_server_action.setShortcut("Ctrl+N")
        add_server_action.triggered.connect(self._on_add_server)
        file_menu.addAction(add_server_action)

        refresh_action = QAction("&Refresh", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._on_refresh)
        file_menu.addAction(refresh_action)

        ping_action = QAction("&Ping Servers", self)
        ping_action.setShortcut("Ctrl+P")
        ping_action.triggered.connect(self._on_ping_servers)
        file_menu.addAction(ping_action)

        fetch_info_action = QAction("Fetch Server &Info", self)
        fetch_info_action.setShortcut("Ctrl+L")
        fetch_info_action.triggered.connect(self._on_fetch_player_counts)
        file_menu.addAction(fetch_info_action)

        refresh_reddit_action = QAction("Refresh &Reddit", self)
        refresh_reddit_action.setShortcut("Ctrl+R")
        refresh_reddit_action.triggered.connect(self._on_refresh_reddit)
        file_menu.addAction(refresh_reddit_action)

        refresh_updates_action = QAction("Refresh &Updates", self)
        refresh_updates_action.setShortcut("Ctrl+U")
        refresh_updates_action.triggered.connect(self._on_refresh_updates)
        file_menu.addAction(refresh_updates_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        show_all_action = QAction("Show &All Servers", self)
        show_all_action.setShortcut("Ctrl+A")
        show_all_action.triggered.connect(self._on_show_all)
        view_menu.addAction(show_all_action)

        view_menu.addSeparator()

        # Theme submenu
        theme_menu = view_menu.addMenu("&Theme")
        self._create_theme_menu(theme_menu)

        # Settings menu
        settings_menu = menubar.addMenu("&Settings")

        preferences_action = QAction("&Preferences", self)
        preferences_action.setShortcut("Ctrl+,")
        preferences_action.triggered.connect(self._on_settings)
        settings_menu.addAction(preferences_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

        return menubar

    def _load_config(self) -> None:
        """Load configuration from YAML files."""
        self._game_defs = self._config_loader.load_games()
        self._all_servers = self._config_loader.load_servers()
        # Refresh sidebar to update version filters
        if hasattr(self, '_sidebar'):
            games = [gd.to_game() for gd in self._game_defs]
            self._sidebar.set_games(games, self._all_servers)

    def _show_all_servers(self) -> None:
        """Show all servers with generic columns."""
        self._current_game = None
        self._current_server = None

        # Use generic columns for all servers view
        generic_columns = [
            ColumnDefinition("name", "Server Name", "stretch"),
            ColumnDefinition("status", "Status", "content"),
            ColumnDefinition("address", "Address", "content"),
            ColumnDefinition("players", "Players", "content"),
            ColumnDefinition("uptime", "Uptime", "content"),
            ColumnDefinition("version", "Version", "content"),
        ]

        self._server_table.set_columns(generic_columns)
        self._server_table.set_servers(self._all_servers)

    def _on_all_servers_selected(self) -> None:
        """Handle all servers selection."""
        self._show_all_servers()
        # Hide Info panel and menubar button when showing all servers
        self._info_panel.hide()
        self._info_menubar_button.hide()
        self._info_panel._is_collapsed = False

    def _on_game_selected(self, game_id: str) -> None:
        """Handle game selection.

        Args:
            game_id: Selected game ID
        """
        # Find game definition
        game_def = self._config_loader.get_game_by_id(game_id, self._game_defs)
        if not game_def:
            return

        self._current_game = game_def

        # Set columns specific to this game
        self._server_table.set_columns(game_def.columns)

        # Filter servers for this game
        self._server_table.filter_by_game(self._all_servers, game_id)

        # Show/hide Info panel based on whether game has Reddit or updates defined
        has_reddit = bool(game_def.reddit)
        has_updates = bool(game_def.updates_url)

        if has_reddit or has_updates:
            if has_reddit:
                self._info_panel.set_subreddit(game_def.reddit)
                # Fetch Reddit posts
                self._reddit_helper.start_fetching(game_def.reddit, limit=15, sort="hot")
            else:
                self._info_panel.set_subreddit("")

            if has_updates:
                self._info_panel.set_updates_url(game_def.updates_url)
                # Fetch updates (with 24-hour cache)
                self._fetch_updates(
                    url=game_def.updates_url,
                    is_rss=game_def.updates_is_rss,
                    use_js=game_def.updates_use_js,
                    selectors=game_def.updates_selectors,
                    limit=10,
                    max_dropdown_options=game_def.updates_max_dropdown_options,
                    forum_mode=game_def.updates_forum_mode,
                    forum_pagination_selector=game_def.updates_forum_pagination_selector,
                    forum_page_limit=game_def.updates_forum_page_limit,
                )
            else:
                self._info_panel.set_updates_url("")

            # Show menubar button and expand panel
            self._info_menubar_button.show()
            if self._info_panel.is_collapsed():
                self._info_panel.expand()
        else:
            # Hide panel and menubar button when no Reddit or updates available
            self._info_panel.hide()
            self._info_menubar_button.hide()
            self._info_panel._is_collapsed = False

    def _on_version_selected(self, game_id: str, version_id: str) -> None:
        """Handle version selection.

        Args:
            game_id: Game ID
            version_id: Version ID
        """
        # Find game definition
        game_def = self._config_loader.get_game_by_id(game_id, self._game_defs)
        if not game_def:
            return

        self._current_game = game_def

        # Set columns specific to this game
        self._server_table.set_columns(game_def.columns)

        # Filter servers for this game and version
        self._server_table.filter_by_game(self._all_servers, game_id, version_id)

        # Show/hide Info panel based on whether game has Reddit or updates defined
        has_reddit = bool(game_def.reddit)
        has_updates = bool(game_def.updates_url)

        if has_reddit or has_updates:
            if has_reddit:
                self._info_panel.set_subreddit(game_def.reddit)
                # Fetch Reddit posts
                self._reddit_helper.start_fetching(game_def.reddit, limit=15, sort="hot")
            else:
                self._info_panel.set_subreddit("")

            if has_updates:
                self._info_panel.set_updates_url(game_def.updates_url)
                # Fetch updates (with 24-hour cache)
                self._fetch_updates(
                    url=game_def.updates_url,
                    is_rss=game_def.updates_is_rss,
                    use_js=game_def.updates_use_js,
                    selectors=game_def.updates_selectors,
                    limit=10,
                    max_dropdown_options=game_def.updates_max_dropdown_options,
                    forum_mode=game_def.updates_forum_mode,
                    forum_pagination_selector=game_def.updates_forum_pagination_selector,
                    forum_page_limit=game_def.updates_forum_page_limit,
                )
            else:
                self._info_panel.set_updates_url("")

            # Show menubar button and expand panel
            self._info_menubar_button.show()
            if self._info_panel.is_collapsed():
                self._info_panel.expand()
        else:
            # Hide panel and menubar button when no Reddit or updates available
            self._info_panel.hide()
            self._info_menubar_button.hide()
            self._info_panel._is_collapsed = False

    def _on_reddit_posts_fetched(self, posts: list) -> None:
        """Handle Reddit posts being fetched.

        Args:
            posts: List of RedditPost objects
        """
        self._info_panel.set_posts(posts)

        # Update cache if we have a current server
        if self._current_server and self._current_server.id in self._server_data_cache:
            self._server_data_cache[self._current_server.id].reddit_posts = posts
            self._server_data_cache[self._current_server.id].reddit_error = None

    def _on_reddit_error(self, error: str) -> None:
        """Handle Reddit fetch error.

        Args:
            error: Error message
        """
        self._info_panel.set_content(f"Error loading Reddit posts:\n{error}")

        # Update cache if we have a current server
        if self._current_server and self._current_server.id in self._server_data_cache:
            self._server_data_cache[self._current_server.id].reddit_error = error

    def _on_updates_fetched(self, updates: list) -> None:
        """Handle server updates being fetched.

        Args:
            updates: List of update dictionaries
        """
        # Cache the updates by URL
        if self._info_panel._updates_url:
            self._updates_cache[self._info_panel._updates_url] = updates

        self._info_panel.set_updates(updates)

    def _on_updates_error(self, error: str) -> None:
        """Handle updates fetch error.

        Args:
            error: Error message
        """
        # Display error in updates tab
        self._info_panel._clear_updates_cards()
        from PySide6.QtWidgets import QLabel
        label = QLabel(f"Error loading updates:\n{error}")
        label.setWordWrap(True)
        self._info_panel._updates_cards_layout.insertWidget(0, label)
        self._info_panel.hide_loading()

    def _should_fetch_updates(self, url: str) -> bool:
        """Check if we should fetch updates based on cache time.

        Args:
            url: Updates URL

        Returns:
            True if we should fetch (cache expired or no cache), False otherwise
        """
        import time

        if url not in self._updates_last_fetch:
            return True

        last_fetch = self._updates_last_fetch[url]
        elapsed_hours = (time.time() - last_fetch) / 3600

        return elapsed_hours >= self._updates_cache_hours

    def _fetch_updates(
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
            max_dropdown_options: Max dropdown options for dropdown-based changelogs
            forum_mode: Whether to scrape forum threads (enables pagination)
            forum_pagination_selector: CSS selector for next page link in forum mode
            forum_page_limit: Maximum number of forum pages to scrape
            force: If True, bypass cache and force fetch
        """
        import time

        # Check cache unless force refresh
        if not force and not self._should_fetch_updates(url):
            # Updates are cached, display cached data
            if url in self._updates_cache:
                self._info_panel.set_updates(self._updates_cache[url])
            return

        # Fetch updates
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
        )

        # Update last fetch time
        self._updates_last_fetch[url] = time.time()

    def _force_refresh_updates(self) -> None:
        """Force refresh current updates (bypass cache)."""
        # Check what's currently selected
        if self._current_game:
            if self._current_game.updates_url:
                self._info_panel.show_loading()
                self._fetch_updates(
                    url=self._current_game.updates_url,
                    is_rss=self._current_game.updates_is_rss,
                    use_js=self._current_game.updates_use_js,
                    selectors=self._current_game.updates_selectors,
                    limit=10,
                    max_dropdown_options=self._current_game.updates_max_dropdown_options,
                    forum_mode=self._current_game.updates_forum_mode,
                    forum_pagination_selector=self._current_game.updates_forum_pagination_selector,
                    forum_page_limit=self._current_game.updates_forum_page_limit,
                    force=True,
                )
                self._notifications.info("Refreshing", "Fetching latest updates...")
        else:
            self._notifications.warning("No Updates", "No updates source available for current selection")

    def _on_refresh_reddit(self) -> None:
        """Refresh Reddit data for currently selected server."""
        if not self._current_server:
            self._notifications.warning("No Server", "No server selected")
            return

        if not self._current_server.reddit:
            self._notifications.warning("No Reddit", "Selected server has no Reddit configured")
            return

        # Fetch Reddit posts
        self._info_panel.show_loading()
        self._reddit_helper.start_fetching(self._current_server.reddit, limit=15, sort="hot")
        self._notifications.info("Refreshing", f"Fetching Reddit posts for {self._current_server.name}...")

    def _on_refresh_updates(self) -> None:
        """Refresh updates data for currently selected server."""
        if not self._current_server:
            self._notifications.warning("No Server", "No server selected")
            return

        if not self._current_server.updates_url:
            self._notifications.warning("No Updates", "Selected server has no updates configured")
            return

        # Fetch updates
        self._info_panel.show_loading()
        from pserver_manager.utils.updates_scraper import UpdatesScraper
        from PySide6.QtCore import QThread

        # Create a worker thread to fetch updates
        def fetch_updates():
            try:
                scraper = UpdatesScraper()
                updates_limit = getattr(self._current_server, 'updates_limit', 10)

                if self._current_server.updates_is_rss:
                    # RSS feed
                    updates = scraper.fetch_rss_updates(self._current_server.updates_url, limit=updates_limit)
                elif self._current_server.updates_forum_mode:
                    # Forum scraping
                    updates = scraper.fetch_forum_threads(
                        url=self._current_server.updates_url,
                        thread_selector=self._current_server.updates_selectors.get("item", "li"),
                        title_selector=self._current_server.updates_selectors.get("title", "a"),
                        link_selector=self._current_server.updates_selectors.get("link", "a"),
                        time_selector=self._current_server.updates_selectors.get("time", "time"),
                        preview_selector=self._current_server.updates_selectors.get("preview", ""),
                        pagination_selector=self._current_server.updates_forum_pagination_selector,
                        page_limit=self._current_server.updates_forum_page_limit,
                        thread_limit=updates_limit,
                        use_js=self._current_server.updates_use_js,
                    )
                else:
                    # Regular webpage scraping
                    updates = scraper.fetch_updates(
                        url=self._current_server.updates_url,
                        use_js=self._current_server.updates_use_js,
                        item_selector=self._current_server.updates_selectors.get("item", "article"),
                        title_selector=self._current_server.updates_selectors.get("title", "h2, h3"),
                        link_selector=self._current_server.updates_selectors.get("link", "a"),
                        time_selector=self._current_server.updates_selectors.get("time", "time"),
                        preview_selector=self._current_server.updates_selectors.get("preview", "p"),
                        limit=updates_limit,
                        dropdown_selector=self._current_server.updates_selectors.get("dropdown"),
                        max_dropdown_options=self._current_server.updates_max_dropdown_options,
                    )

                # Update cache with ServerUpdate objects
                if self._current_server.id in self._server_data_cache:
                    self._server_data_cache[self._current_server.id].updates = updates
                    self._server_data_cache[self._current_server.id].updates_error = None

                # Convert to dictionaries and display
                updates_dict = [update.to_dict() for update in updates]
                self._info_panel.set_updates(updates_dict)
            except Exception as e:
                # Update cache with error
                if self._current_server.id in self._server_data_cache:
                    self._server_data_cache[self._current_server.id].updates_error = str(e)

                self._info_panel.set_content(f"Error loading updates:\n{str(e)}")

        # Run in thread to avoid blocking UI
        import threading
        threading.Thread(target=fetch_updates, daemon=True).start()

        self._notifications.info("Refreshing", f"Fetching updates for {self._current_server.name}...")

    def _on_info_panel_collapsed_changed(self, is_collapsed: bool) -> None:
        """Handle Info panel collapsed state change.

        Args:
            is_collapsed: True if panel is now collapsed, False if expanded
        """
        if is_collapsed:
            # Panel collapsed - change button to expand arrow
            self._info_menubar_button.setText("▶ Info")
            self._info_menubar_button.setToolTip("Show info panel")
        else:
            # Panel expanded - change button to collapse arrow
            self._info_menubar_button.setText("◀ Info")
            self._info_menubar_button.setToolTip("Hide info panel")

    def _on_info_menubar_button_clicked(self) -> None:
        """Handle Info menubar button click (toggle panel)."""
        if self._info_panel.is_collapsed():
            self._info_panel.expand()
        else:
            self._info_panel.collapse()

    def _on_server_selected(self, server_id: str) -> None:
        """Handle server selection.

        Args:
            server_id: Selected server ID
        """
        # Find the server
        server = None
        for s in self._all_servers:
            if s.id == server_id:
                server = s
                break

        if not server:
            return

        # Track currently selected server
        self._current_server = server

        # Show/hide Info panel based on whether server has Reddit or updates defined
        has_reddit = bool(server.reddit)
        has_updates = bool(server.updates_url)

        if has_reddit or has_updates:
            # Check if we have cached data for this server
            cached_data = self._server_data_cache.get(server_id)

            if has_reddit:
                self._info_panel.set_subreddit(server.reddit)
                # Display cached Reddit data if available, otherwise show loading
                if cached_data and cached_data.reddit_posts is not None:
                    self._info_panel.set_posts(cached_data.reddit_posts)
                elif cached_data and cached_data.reddit_error:
                    self._info_panel.set_content(f"Error loading Reddit posts:\n{cached_data.reddit_error}")
                else:
                    # No cached data, but don't auto-fetch
                    self._info_panel.set_content("Reddit data not loaded. Use File > Refresh Reddit to fetch.")
            else:
                self._info_panel.set_subreddit("")

            if has_updates:
                self._info_panel.set_updates_url(server.updates_url)
                # Display cached updates if available, otherwise show loading
                if cached_data and cached_data.updates is not None:
                    # Convert ServerUpdate objects to dictionaries for display
                    updates_dict = [update.to_dict() for update in cached_data.updates]
                    self._info_panel.set_updates(updates_dict)
                elif cached_data and cached_data.updates_error:
                    self._info_panel.set_content(f"Error loading updates:\n{cached_data.updates_error}")
                else:
                    # No cached data, but don't auto-fetch
                    self._info_panel.set_content("Updates not loaded. Use File > Refresh Updates to fetch.")
            else:
                self._info_panel.set_updates_url("")

            # Show menubar button and expand panel
            self._info_menubar_button.show()
            if self._info_panel.is_collapsed():
                self._info_panel.expand()
        else:
            # No Reddit or updates for this server - hide panel
            self._info_menubar_button.hide()
            self._info_panel.collapse()

    def _on_server_double_clicked(self, server_id: str) -> None:
        """Handle server double click.

        Args:
            server_id: Double-clicked server ID
        """
        # Server double-clicked - could open details view in future

    def _on_edit_server(self, server_id: str) -> None:
        """Handle edit server request.

        Args:
            server_id: Server ID to edit
        """
        # Find the server and game
        server = None
        for s in self._all_servers:
            if s.id == server_id:
                server = s
                break

        if not server:
            self._notifications.error("Server Not Found", f"Could not find server: {server_id}")
            return

        # Find the game definition
        game = self._config_loader.get_game_by_id(server.game_id, self._game_defs)
        if not game:
            self._notifications.error("Configuration Error", f"Game configuration not found for {server.game_id}")
            return

        # Open editor dialog
        editor = ServerEditor(server, game, self)
        if editor.exec():
            # Save changes
            if editor.save_to_file():
                self._notifications.success("Server Saved", f"'{server.name}' saved successfully")
                # Reload config and refresh display
                self._load_config()
                if self._current_game:
                    self._on_game_selected(self._current_game.id)
                else:
                    self._show_all_servers()
            else:
                self._notifications.error("Save Failed", f"Failed to save server '{server.name}'")

    def _on_delete_server(self, server_id: str) -> None:
        """Handle delete server request.

        Args:
            server_id: Server ID to delete
        """
        # Find the server
        server = None
        for s in self._all_servers:
            if s.id == server_id:
                server = s
                break

        if not server:
            self._notifications.error("Server Not Found", f"Could not find server: {server_id}")
            return

        # Delete the server's YAML file
        try:
            # Server files are in servers/{game_id}/{server_id}.yaml
            # server.id is like "wow.retro-wow", extract just "retro-wow"
            server_filename = server.id.split(".", 1)[1] if "." in server.id else server.id
            servers_dir = self._app_paths.get_servers_dir()
            server_file = servers_dir / server.game_id / f"{server_filename}.yaml"

            if server_file.exists():
                server_file.unlink()
                self._notifications.success("Server Deleted", f"'{server.name}' deleted successfully")
                # Reload config and refresh display
                self._load_config()
                if self._current_game:
                    self._on_game_selected(self._current_game.id)
                else:
                    self._show_all_servers()
            else:
                self._notifications.error("Delete Failed", "Server configuration file not found")
        except Exception as e:
            self._notifications.error("Delete Failed", f"Failed to delete server: {str(e)}")

    def _on_manage_accounts(self, server_id: str) -> None:
        """Handle manage accounts request.

        Args:
            server_id: Server ID
        """
        # Find the server
        server = None
        for s in self._all_servers:
            if s.id == server_id:
                server = s
                break

        if not server:
            self._notifications.error("Server Not Found", f"Could not find server: {server_id}")
            return

        from pserver_manager.widgets.account_dialog import AccountDialog
        dialog = AccountDialog(server, self)
        dialog.exec()

    def _on_register(self, server_id: str) -> None:
        """Handle register account request.

        Args:
            server_id: Server ID
        """
        # Find the server
        server = None
        for s in self._all_servers:
            if s.id == server_id:
                server = s
                break

        if not server:
            return

        register_url = server.get_field("register_url", "")
        if register_url:
            import webbrowser
            webbrowser.open(register_url)
            self._notifications.info("Opening Browser", f"Opening registration page for {server.name}")
        else:
            self._notifications.warning("No Registration URL", f"No registration URL configured for {server.name}")

    def _on_login(self, server_id: str) -> None:
        """Handle login request.

        Args:
            server_id: Server ID
        """
        # Find the server
        server = None
        for s in self._all_servers:
            if s.id == server_id:
                server = s
                break

        if not server:
            return

        login_url = server.get_field("login_url", "")
        if login_url:
            import webbrowser
            webbrowser.open(login_url)
            self._notifications.info("Opening Browser", f"Opening account login for {server.name}")
        else:
            self._notifications.warning("No Login URL", f"No login URL configured for {server.name}")

    def _on_add_server(self) -> None:
        """Handle add server button click."""
        self._notifications.info("Coming Soon", "Add server functionality coming soon")

    def _on_refresh(self) -> None:
        """Handle refresh button click."""
        self._load_config()
        self._show_all_servers()
        self._notifications.success("Refreshed", "Server list refreshed")

    def _on_ping_servers(self) -> None:
        """Handle ping servers action."""
        self._notifications.info("Pinging Servers", "Checking server status...")
        self._server_table.ping_servers()
        self._notifications.success("Ping Complete", "Server status updated")

    def _on_fetch_player_counts(self) -> None:
        """Handle fetch server info action."""
        self._notifications.info("Fetching Server Info", "Retrieving player counts, uptime, and more...")
        self._server_table.fetch_player_counts()
        self._notifications.success("Fetch Complete", "Server information updated")

    def _on_settings(self) -> None:
        """Handle settings button click."""
        # Open preferences dialog
        dialog = PreferencesDialog(
            config_manager=self._config_manager,
            theme_manager=self.application.theme_manager,
            app_paths=self._app_paths,
            servers=self._all_servers,
            game_defs=self._game_defs,
            parent=self,
        )
        if dialog.exec():
            # Save config to file after accepting changes
            config_file = self._app_paths.get_settings_file()
            self._config_manager.save(config_file)
            self._notifications.success("Settings Saved", "Your preferences have been saved")

    def _on_show_all(self) -> None:
        """Handle show all servers action."""
        self._show_all_servers()

    def _on_about(self) -> None:
        """Handle about action."""
        self._notifications.info("About", "PServer Manager v1.0")

    def _check_for_updates_on_startup(self) -> None:
        """Check for updates on startup and show dialog if available."""
        try:
            # Check if user servers directory is completely empty (no .yaml files at all)
            user_servers_dir = self._app_paths.get_servers_dir()
            existing_files = list(user_servers_dir.rglob("*.yaml"))
            has_any_servers = len(existing_files) > 0

            print(f"[Update Check] Servers directory: {user_servers_dir}")
            print(f"[Update Check] Existing .yaml files: {len(existing_files)}")
            if existing_files:
                print(f"[Update Check] Files found: {[str(f.relative_to(user_servers_dir)) for f in existing_files[:5]]}")

            # If directory is completely empty, auto-import all bundled files without prompting
            if not has_any_servers:
                print("Servers directory is empty - auto-importing bundled servers and themes...")

                # Import all bundled servers
                imported = self._update_checker.import_all_new_servers()
                print(f"Auto-imported {imported} bundled servers")

                # Import all bundled themes
                imported_themes = self._update_checker.import_all_new_themes()
                print(f"Auto-imported {imported_themes} bundled themes")

                if imported_themes > 0:
                    self._reload_themes()

                # Reload config to show imported servers
                self._load_config()
                self._show_all_servers()
                return

            # Directory has files - check for updates normally
            update_info = self._update_checker.check_for_updates()

            # Only show dialog if there are updates
            has_updates = (
                len(update_info.new_servers) > 0
                or len(update_info.updated_servers) > 0
                or len(update_info.removed_servers) > 0
                or len(update_info.conflicts) > 0
                or len(update_info.new_themes) > 0
                or len(update_info.updated_themes) > 0
                or len(update_info.theme_conflicts) > 0
            )

            if has_updates:
                dialog = UpdateDialog(update_info, self._update_checker, self)
                if dialog.exec():
                    # Updates were applied - reload config and themes
                    self._load_config()
                    if self._current_game:
                        self._on_game_selected(self._current_game.id)
                    else:
                        self._show_all_servers()

                    # Reload themes if any theme updates were applied
                    if update_info.updated_themes or update_info.new_themes:
                        self._reload_themes()

                    self._notifications.success("Updates Applied", "Configurations updated")
        except Exception as e:
            print(f"Error checking for updates: {e}")

    def check_for_updates_manual(self) -> None:
        """Manually check for updates (called from preferences/menu)."""
        try:
            update_info = self._update_checker.check_for_updates()

            # Show dialog even if no updates (to inform user)
            has_updates = (
                len(update_info.new_servers) > 0
                or len(update_info.updated_servers) > 0
                or len(update_info.removed_servers) > 0
                or len(update_info.conflicts) > 0
                or len(update_info.new_themes) > 0
                or len(update_info.updated_themes) > 0
                or len(update_info.theme_conflicts) > 0
            )

            if has_updates:
                dialog = UpdateDialog(update_info, self._update_checker, self)
                if dialog.exec():
                    # Updates were applied - reload config and themes
                    self._load_config()
                    if self._current_game:
                        self._on_game_selected(self._current_game.id)
                    else:
                        self._show_all_servers()

                    # Reload themes if any theme updates were applied
                    if update_info.updated_themes or update_info.new_themes:
                        self._reload_themes()

                    self._notifications.success("Updates Applied", "Configurations updated")
            else:
                self._notifications.info("No Updates", "Your configurations are up to date")
        except Exception as e:
            self._notifications.error("Update Check Failed", f"Error: {str(e)}")

    def _start_batch_scan_if_enabled(self) -> None:
        """Start batch scanning if enabled in settings."""
        scan_on_startup = self._config_manager.get("scanning.scan_on_startup", True)

        print(f"[MainWindow] Batch scan check: scan_on_startup={scan_on_startup}")

        if not scan_on_startup:
            self._status_label.setText("Ready (auto-scan disabled)")
            return

        # Fetch data for ALL servers (not just those with scraping)
        # We want to get ping, reddit, updates, etc. for all servers
        servers_to_fetch = self._all_servers

        print(f"[MainWindow] Starting batch fetch for {len(servers_to_fetch)} servers")

        if not servers_to_fetch:
            self._status_label.setText("Ready (no servers)")
            return

        # Start batch scan
        max_workers = self._config_manager.get("scanning.parallel_scan_limit", 5)
        self._status_label.setText(f"Fetching data for {len(servers_to_fetch)} servers...")
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)

        self._batch_scanner.start_batch_fetch(servers_to_fetch, max_workers)

    def _on_scan_progress(self, current: int, total: int, server_name: str) -> None:
        """Handle scan progress update.

        Args:
            current: Current scan number
            total: Total scans
            server_name: Name of server being scanned
        """
        progress = int((current / total) * 100)
        self._progress_bar.setValue(progress)
        self._progress_bar.setFormat(f"{current}/{total} - {server_name}")
        self._status_label.setText(f"Scanning servers ({current}/{total})...")

    def _on_server_data_complete(self, server_id: str, result: object) -> None:
        """Handle individual server data fetch completion.

        Args:
            server_id: Server ID that had data fetched
            result: ServerDataResult object
        """
        print(f"[MainWindow] Data complete for {server_id}")
        print(f"  - scrape_success: {result.scrape_success}, data: {result.scrape_data}")
        print(f"  - ping_success: {result.ping_success}, ping_ms: {result.ping_ms}")
        print(f"  - reddit_posts: {len(result.reddit_posts) if result.reddit_posts else 'None'}")
        print(f"  - updates: {len(result.updates) if result.updates else 'None'}")

        # Store result for later use (acts as cache)
        self._server_data_cache[server_id] = result

        # Update the server table immediately if scraping data is available
        if result.scrape_success and result.scrape_data:
            print(f"[MainWindow] Updating table for {server_id}")
            self._server_table.update_server_data(server_id, result.scrape_data)

        # Update ping if available
        if result.ping_success:
            print(f"[MainWindow] Updating ping for {server_id}: {result.ping_ms}ms")
            # Find server and update ping_ms
            for server in self._all_servers:
                if server.id == server_id:
                    server.ping_ms = result.ping_ms

                    # If worlds data was updated, apply it to the server
                    if result.worlds_data is not None:
                        print(f"[MainWindow] Updating {len(result.worlds_data)} worlds data for {server_id}")
                        # The server's data dict should have a 'worlds' key
                        if 'worlds' in server.data:
                            server.data['worlds'] = result.worlds_data
                    break
            self._server_table._refresh_table()

    def _on_batch_scan_finished(self, all_results: dict) -> None:
        """Handle batch data fetch completion.

        Args:
            all_results: Dictionary of all server data results
        """
        print(f"[MainWindow] Batch scan finished with {len(all_results)} results")

        total_count = len(all_results)
        scrape_success = sum(1 for r in all_results.values() if r.scrape_success)
        ping_success = sum(1 for r in all_results.values() if r.ping_success)
        reddit_success = sum(1 for r in all_results.values() if r.reddit_posts is not None)
        updates_success = sum(1 for r in all_results.values() if r.updates is not None)

        print(f"[MainWindow] Results summary:")
        print(f"  - Scrape: {scrape_success}/{total_count}")
        print(f"  - Ping: {ping_success}/{total_count}")
        print(f"  - Reddit: {reddit_success}/{total_count}")
        print(f"  - Updates: {updates_success}/{total_count}")

        self._progress_bar.setVisible(False)
        self._status_label.setText(
            f"Data fetch complete: {scrape_success}/{total_count} scraped, {ping_success}/{total_count} pinged"
        )

        # Hide status after a few seconds
        from PySide6.QtCore import QTimer

        QTimer.singleShot(5000, lambda: self._status_label.setText("Ready"))

    def _on_scan_error(self, error: str) -> None:
        """Handle scan error.

        Args:
            error: Error message
        """
        self._progress_bar.setVisible(False)
        self._status_label.setText(f"Scan error: {error}")
        print(f"Batch scan error: {error}")

    def _reload_themes(self) -> None:
        """Reload themes after updates."""
        try:
            from PySide6.QtWidgets import QApplication

            # Get current theme name
            current_theme = self._config_manager.get("ui.theme", "auto")

            # Get application instance
            app = QApplication.instance()
            if not app:
                return

            # Reload themes in theme manager
            theme_manager = app.theme_manager
            theme_manager.reload_themes()

            # Reapply current theme
            theme_manager.set_theme(current_theme)

            # Regenerate and apply stylesheet
            stylesheet = theme_manager.get_stylesheet()
            app.setStyleSheet(stylesheet)
        except Exception as e:
            self._notifications.error("Theme Reload Failed", f"Error: {str(e)}")


def main() -> int:
    """Run the application.

    Returns:
        Application exit code
    """
    # Setup custom resource manager
    resource_manager = ResourceManager()

    # Get app paths for user data directories
    app_paths = get_app_paths()

    # Add user themes directory (searched first for user customizations)
    resource_manager.add_search_path("themes", app_paths.get_themes_dir())

    # Add bundled resource paths (searched after user paths)
    resource_manager.add_search_path("themes", Path("pserver_manager/themes"))
    resource_manager.add_search_path("icons", Path("pserver_manager/icons"))
    resource_manager.add_search_path("translations", Path("pserver_manager/translations"))

    # Create application with custom resources
    # Don't load framework built-in themes, but load custom themes
    app = Application(
        argv=sys.argv,
        app_name="PServerManager",
        org_name="PServerManager",
        org_domain="pservermanager.local",
        resource_manager=resource_manager,
        included_themes=[],  # No framework built-in themes (light/dark/high_contrast)
        excluded_themes=["monokai"],  # Exclude monokai custom theme
        include_auto_theme=False,
    )

    # Set Fusion style for consistent widget rendering
    app.setStyle("Fusion")

    # Setup plugin manager
    plugin_manager = PluginManager(application=app)
    plugin_manager.add_plugin_path(Path("pserver_manager/plugins"))

    # Discover and load plugins
    available_plugins = plugin_manager.discover_plugins()
    for plugin_metadata in available_plugins:
        print(f"Found plugin: {plugin_metadata.id} - {plugin_metadata.name}")
        plugin_manager.load_plugin(plugin_metadata.id)
        plugin_manager.activate_plugin(plugin_metadata.id)

    # Create and show main window (config is loaded in __init__)
    window = MainWindow(application=app)

    # Apply theme from config after window is initialized
    saved_theme = window._config_manager.get("ui.theme", "nord")
    app.theme_manager.set_theme(saved_theme)

    window.show()

    # Run application
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
