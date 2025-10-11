"""Main application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QSplitter

from qtframework import Application
from qtframework.config import ConfigManager
from qtframework.core import BaseWindow
from qtframework.plugins import PluginManager
from qtframework.utils import ResourceManager
from qtframework.widgets import VBox, HBox
from qtframework.widgets.buttons import Button, ButtonSize, ButtonVariant
from qtframework.widgets.advanced import NotificationManager
from qtframework.widgets.advanced.notifications import NotificationPosition

from pserver_manager.config_loader import ColumnDefinition, ConfigLoader
from pserver_manager.models import Game
from pserver_manager.utils import get_app_paths
from pserver_manager.utils.schema_migrations import migrate_user_servers
from pserver_manager.widgets import GameSidebar, InfoPanel, ServerTable
from pserver_manager.widgets.server_editor import ServerEditor
from pserver_manager.widgets.preferences_dialog import PreferencesDialog
from pserver_manager.widgets.update_dialog import UpdateDialog

# Import services and controllers
from pserver_manager.services import (
    CacheService,
    DataFetchService,
    ServerService,
    UpdateService,
)
from pserver_manager.controllers import (
    InfoPanelController,
    ServerController,
    ThemeController,
)


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
        self._perform_initial_migrations()

        # Initialize config manager
        self._config_manager = ConfigManager()
        self._init_config()

        # Initialize config loader
        self._config_loader = ConfigLoader(
            config_dir=Path(__file__).parent / "config",
            servers_dir=self._app_paths.get_servers_dir(),
        )

        # Initialize services
        self._cache_service = CacheService(cache_hours=24)
        self._server_service = ServerService(self._config_loader, self._app_paths)
        self._data_fetch_service = DataFetchService()
        self._update_service = UpdateService(self._app_paths)

        # Load initial data through service
        self._server_service.load_all()

        super().__init__(application=application)
        self.setWindowTitle("PServer Manager")
        self.setMinimumSize(1280, 800)

        # Setup notification manager
        self._notifications = NotificationManager(self)
        self._notifications.set_position(NotificationPosition.BOTTOM_RIGHT)

        # Initialize controllers (after UI is created)
        self._server_controller = ServerController(
            self._server_service, self._cache_service, self._notifications
        )
        self._info_panel_controller = InfoPanelController(
            self._info_panel, self._data_fetch_service, self._cache_service, self._notifications
        )
        self._theme_controller = ThemeController(
            self.application, self._config_manager, self._app_paths, self._notifications
        )

        # Connect controller signals
        self._connect_controller_signals()

        # Connect batch scanner signals
        self._data_fetch_service.scan_progress.connect(self._on_scan_progress)
        self._data_fetch_service.server_data_complete.connect(self._on_server_data_complete)
        self._data_fetch_service.batch_scan_finished.connect(self._on_batch_scan_finished)
        self._data_fetch_service.scan_error.connect(self._on_scan_error)

        # Check for updates on startup (after window is shown)
        QTimer.singleShot(1000, self._check_for_updates_on_startup)
        QTimer.singleShot(2000, self._start_batch_scan_if_enabled)

    def _perform_initial_migrations(self) -> None:
        """Perform initial configuration and schema migrations."""
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
                migration_marker.write_text("Migration completed")
        elif not migration_marker.exists() and not any(new_servers_dir.rglob("*.yaml")):
            migration_marker.write_text("No migration needed")

        # Migrate user servers to current schema if needed
        user_servers_dir = self._app_paths.get_servers_dir()
        if user_servers_dir.exists() and any(user_servers_dir.rglob("*.yaml")):
            print("Checking server configurations for schema updates...")
            migration_report = migrate_user_servers(user_servers_dir, show_report=False)
            if migration_report["migrated"] > 0:
                print(f"Migrated {migration_report['migrated']} server(s) to current schema")

    def _init_config(self) -> None:
        """Initialize configuration with defaults."""
        config_file = self._app_paths.get_settings_file()

        if config_file.exists():
            try:
                self._config_manager.load_file(config_file)
            except Exception as e:
                print(f"Warning: Could not load config file: {e}")
                self._load_default_config()
        else:
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

    def _connect_controller_signals(self) -> None:
        """Connect controller signals to handlers."""
        # Server controller signals
        self._server_controller.servers_loaded.connect(self._on_servers_loaded)
        self._server_controller.server_deleted.connect(self._on_server_deleted)

        # Info panel controller signals
        self._info_panel_controller.panel_should_show.connect(self._show_info_panel_ui)
        self._info_panel_controller.panel_should_hide.connect(self._hide_info_panel_ui)

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        # Create menu bar
        menubar = self._create_menu_bar()

        # Create main container
        main_layout = VBox(spacing=0, margins=0)

        # Create splitter for sidebar and content
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Create sidebar
        self._sidebar = GameSidebar()
        games = [gd.to_game() for gd in self._server_service.get_games()]
        self._sidebar.set_games(games, self._server_service.get_servers())
        self._sidebar.all_servers_selected.connect(self._on_all_servers_selected)
        self._sidebar.game_selected.connect(self._on_game_selected)
        self._sidebar.version_selected.connect(self._on_version_selected)
        self._sidebar.setMinimumWidth(250)
        self._sidebar.setMaximumWidth(400)

        # Create server table
        self._server_table = ServerTable()
        self._show_all_servers()
        self._server_table.server_selected.connect(self._on_server_selected)
        self._server_table.server_double_clicked.connect(self._on_server_double_clicked)
        self._server_table.edit_server_requested.connect(self._on_edit_server)
        self._server_table.delete_server_requested.connect(self._on_delete_server)
        self._server_table.manage_accounts_requested.connect(self._on_manage_accounts)
        self._server_table.register_requested.connect(self._on_register)
        self._server_table.login_requested.connect(self._on_login)

        # Create Info panel
        self._info_panel = InfoPanel()
        self._info_panel.hide()
        self._info_panel.collapsed_changed.connect(self._on_info_panel_collapsed_changed)

        # Create Info menubar button
        self._info_menubar_button = Button(
            "▶ Info",
            size=ButtonSize.COMPACT,
            variant=ButtonVariant.PRIMARY
        )
        self._info_menubar_button.clicked.connect(self._on_info_menubar_button_clicked)
        self._info_menubar_button.setToolTip("Show info panel")
        self._info_menubar_button.setStyleSheet("""
            QPushButton {
                padding: 2px 8px;
                min-height: 0px;
                max-height: 22px;
                margin-right: 5px;
            }
        """)
        self._info_menubar_button.hide()
        menubar.setCornerWidget(self._info_menubar_button, Qt.Corner.TopRightCorner)

        # Add to splitter
        splitter.addWidget(self._sidebar)
        splitter.addWidget(self._server_table)
        splitter.addWidget(self._info_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)

        main_layout.add_widget(splitter, stretch=1)

        # Create status bar
        self._setup_status_bar(main_layout)

        self.setCentralWidget(main_layout)

    def _setup_status_bar(self, parent_layout) -> None:
        """Setup status bar with progress indication."""
        from PySide6.QtWidgets import QLabel, QProgressBar

        status_bar = HBox(spacing=8, margins=(8, 4, 8, 4))

        self._status_label = QLabel("Ready")
        status_bar.add_widget(self._status_label)
        status_bar.add_stretch()

        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFixedWidth(200)
        self._progress_bar.setVisible(False)
        status_bar.add_widget(self._progress_bar)

        parent_layout.add_widget(status_bar)

    def _create_menu_bar(self):
        """Create the menu bar."""
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

    def _create_theme_menu(self, theme_menu) -> None:
        """Create theme submenu with available themes."""
        theme_manager = self.application.theme_manager
        theme_action_group = QActionGroup(self)
        theme_action_group.setExclusive(True)

        self._theme_menu_actions = {}

        # Access theme manager directly since controller isn't initialized yet
        current_theme = theme_manager.get_current_theme()
        current_theme_name = current_theme.name if current_theme else None

        for theme_name in theme_manager.list_themes():
            theme_info = theme_manager.get_theme_info(theme_name)
            display_name = (
                theme_info.get("display_name", theme_name.replace("_", " ").title())
                if theme_info
                else theme_name.replace("_", " ").title()
            )

            action = QAction(display_name, self)
            action.setCheckable(True)
            action.setData(theme_name)

            if current_theme_name and current_theme_name == theme_name:
                action.setChecked(True)

            # Use lambda that will call controller method when it exists
            action.triggered.connect(lambda checked, tn=theme_name: self._apply_theme(tn))

            theme_action_group.addAction(action)
            theme_menu.addAction(action)
            self._theme_menu_actions[theme_name] = action

        # Connect to theme manager's theme_changed signal
        def update_theme_menu(new_theme_name: str):
            for theme_name, action in self._theme_menu_actions.items():
                action.setChecked(theme_name == new_theme_name)

        theme_manager.theme_changed.connect(update_theme_menu)

        # Refresh server table when theme changes to update ping colors
        def refresh_on_theme_change(new_theme_name: str):
            if hasattr(self, '_server_table'):
                self._server_table._refresh_table()

        theme_manager.theme_changed.connect(refresh_on_theme_change)

    def _apply_theme(self, theme_name: str) -> None:
        """Apply theme (delegates to controller when available)."""
        if hasattr(self, '_theme_controller'):
            self._theme_controller.apply_theme(theme_name)
        else:
            # Fallback for early initialization
            self.application.theme_manager.set_theme(theme_name)

    def _show_all_servers(self) -> None:
        """Show all servers with generic columns."""
        # Update controller state if it exists (not during initial UI setup)
        if hasattr(self, '_server_controller'):
            self._server_controller.set_current_game(None)
            self._server_controller.set_current_server(None)

        generic_columns = [
            ColumnDefinition("name", "Server Name", "stretch"),
            ColumnDefinition("status", "Status", "content"),
            ColumnDefinition("address", "Address", "content"),
            ColumnDefinition("players", "Players", "content"),
            ColumnDefinition("uptime", "Uptime", "content"),
            ColumnDefinition("version", "Version", "content"),
        ]

        self._server_table.set_columns(generic_columns)
        self._server_table.set_servers(self._server_service.get_servers())

    def _on_servers_loaded(self, game_defs, server_defs) -> None:
        """Handle servers being loaded."""
        games = [gd.to_game() for gd in game_defs]
        self._sidebar.set_games(games, server_defs)

    def _on_server_deleted(self, server_id: str) -> None:
        """Handle server being deleted."""
        self._server_controller.reload_servers()
        current_game = self._server_controller.get_current_game()
        if current_game:
            self._on_game_selected(current_game.id)
        else:
            self._show_all_servers()

    def _on_all_servers_selected(self) -> None:
        """Handle all servers selection."""
        self._show_all_servers()
        self._hide_info_panel_ui()
        self._info_panel._is_collapsed = False

    def _on_game_selected(self, game_id: str) -> None:
        """Handle game selection."""
        game_def = self._server_controller.get_game_by_id(game_id)
        if not game_def:
            return

        self._server_controller.set_current_game(game_def)
        self._server_table.set_columns(game_def.columns)
        self._server_table.filter_by_game(self._server_service.get_servers(), game_id)
        self._info_panel_controller.load_game_data(game_def)

    def _on_version_selected(self, game_id: str, version_id: str) -> None:
        """Handle version selection."""
        game_def = self._server_controller.get_game_by_id(game_id)
        if not game_def:
            return

        self._server_controller.set_current_game(game_def)
        self._server_table.set_columns(game_def.columns)
        self._server_table.filter_by_game(self._server_service.get_servers(), game_id, version_id)
        self._info_panel_controller.load_game_data(game_def)

    def _on_server_selected(self, server_id: str) -> None:
        """Handle server selection."""
        server = self._server_controller.get_server_by_id(server_id)
        if not server:
            return

        self._server_controller.set_current_server(server)
        self._info_panel_controller.load_server_data(server)

    def _on_server_double_clicked(self, server_id: str) -> None:
        """Handle server double click."""
        pass

    def _on_edit_server(self, server_id: str) -> None:
        """Handle edit server request."""
        server = self._server_controller.get_server_by_id(server_id)
        if not server:
            self._notifications.error("Server Not Found", f"Could not find server: {server_id}")
            return

        game = self._server_controller.get_game_by_id(server.game_id)
        if not game:
            self._notifications.error("Configuration Error", f"Game configuration not found for {server.game_id}")
            return

        editor = ServerEditor(server, game, self)
        if editor.exec():
            if editor.save_to_file():
                self._notifications.success("Server Saved", f"'{server.name}' saved successfully")
                self._server_controller.reload_servers()
                current_game = self._server_controller.get_current_game()
                if current_game:
                    self._on_game_selected(current_game.id)
                else:
                    self._show_all_servers()
            else:
                self._notifications.error("Save Failed", f"Failed to save server '{server.name}'")

    def _on_delete_server(self, server_id: str) -> None:
        """Handle delete server request."""
        self._server_controller.delete_server(server_id)

    def _on_manage_accounts(self, server_id: str) -> None:
        """Handle manage accounts request."""
        server = self._server_controller.get_server_by_id(server_id)
        if not server:
            self._notifications.error("Server Not Found", f"Could not find server: {server_id}")
            return

        from pserver_manager.widgets.account_dialog import AccountDialog
        dialog = AccountDialog(server, self)
        dialog.exec()

    def _on_register(self, server_id: str) -> None:
        """Handle register account request."""
        server = self._server_controller.get_server_by_id(server_id)
        if not server:
            return

        if self._server_controller.open_server_url(server_id, "register_url"):
            self._notifications.info("Opening Browser", f"Opening registration page for {server.name}")
        else:
            self._notifications.warning("No Registration URL", f"No registration URL configured for {server.name}")

    def _on_login(self, server_id: str) -> None:
        """Handle login request."""
        server = self._server_controller.get_server_by_id(server_id)
        if not server:
            return

        if self._server_controller.open_server_url(server_id, "login_url"):
            self._notifications.info("Opening Browser", f"Opening account login for {server.name}")
        else:
            self._notifications.warning("No Login URL", f"No login URL configured for {server.name}")

    def _on_add_server(self) -> None:
        """Handle add server button click."""
        self._notifications.info("Coming Soon", "Add server functionality coming soon")

    def _on_refresh(self) -> None:
        """Handle refresh button click."""
        self._server_controller.reload_servers()
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

    def _on_refresh_reddit(self) -> None:
        """Refresh Reddit data for currently selected server."""
        current_server = self._server_controller.get_current_server()
        if not current_server:
            self._notifications.warning("No Server", "No server selected")
            return

        self._info_panel_controller.refresh_reddit(current_server)

    def _on_refresh_updates(self) -> None:
        """Refresh updates data for currently selected server."""
        current_server = self._server_controller.get_current_server()
        if not current_server:
            self._notifications.warning("No Server", "No server selected")
            return

        self._info_panel_controller.refresh_updates(current_server)

    def _on_info_panel_collapsed_changed(self, is_collapsed: bool) -> None:
        """Handle Info panel collapsed state change."""
        if is_collapsed:
            self._info_menubar_button.setText("▶ Info")
            self._info_menubar_button.setToolTip("Show info panel")
        else:
            self._info_menubar_button.setText("◀ Info")
            self._info_menubar_button.setToolTip("Hide info panel")

    def _on_info_menubar_button_clicked(self) -> None:
        """Handle Info menubar button click."""
        self._info_panel_controller.toggle_panel()

    def _show_info_panel_ui(self) -> None:
        """Show info panel UI elements."""
        self._info_menubar_button.show()
        # Always show and expand the panel to ensure it's fully visible
        self._info_panel.show()
        # Always expand to ensure panel is not collapsed (expand is idempotent)
        self._info_panel.expand()
        # Reset collapsed state flag
        self._info_panel._is_collapsed = False

    def _hide_info_panel_ui(self) -> None:
        """Hide info panel UI elements."""
        self._info_panel.hide()
        self._info_menubar_button.hide()
        # Reset collapsed state when hiding
        self._info_panel._is_collapsed = False

    def _on_settings(self) -> None:
        """Handle settings button click."""
        dialog = PreferencesDialog(
            config_manager=self._config_manager,
            theme_manager=self.application.theme_manager,
            app_paths=self._app_paths,
            servers=self._server_service.get_servers(),
            game_defs=self._server_service.get_games(),
            parent=self,
        )
        if dialog.exec():
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
            if self._update_service.is_first_run():
                print("Servers directory is empty - auto-importing bundled servers and themes...")
                imported = self._update_service.import_all_new_servers()
                print(f"Auto-imported {imported} bundled servers")

                imported_themes = self._update_service.import_all_new_themes()
                print(f"Auto-imported {imported_themes} bundled themes")

                if imported_themes > 0:
                    self._theme_controller.reload_themes()

                self._server_controller.reload_servers()
                self._show_all_servers()
                return

            update_info = self._update_service.check_for_updates()

            if self._update_service.has_updates(update_info):
                dialog = UpdateDialog(update_info, self._update_service.get_update_checker(), self)
                if dialog.exec():
                    self._server_controller.reload_servers()
                    current_game = self._server_controller.get_current_game()
                    if current_game:
                        self._on_game_selected(current_game.id)
                    else:
                        self._show_all_servers()

                    if update_info.updated_themes or update_info.new_themes:
                        self._theme_controller.reload_themes()

                    self._notifications.success("Updates Applied", "Configurations updated")
        except Exception as e:
            print(f"Error checking for updates: {e}")

    def check_for_updates_manual(self) -> None:
        """Manually check for updates."""
        try:
            update_info = self._update_service.check_for_updates()

            if self._update_service.has_updates(update_info):
                dialog = UpdateDialog(update_info, self._update_service.get_update_checker(), self)
                if dialog.exec():
                    self._server_controller.reload_servers()
                    current_game = self._server_controller.get_current_game()
                    if current_game:
                        self._on_game_selected(current_game.id)
                    else:
                        self._show_all_servers()

                    if update_info.updated_themes or update_info.new_themes:
                        self._theme_controller.reload_themes()

                    self._notifications.success("Updates Applied", "Configurations updated")
            else:
                self._notifications.info("No Updates", "Your configurations are up to date")
        except Exception as e:
            self._notifications.error("Update Check Failed", f"Error: {str(e)}")

    def _start_batch_scan_if_enabled(self) -> None:
        """Start batch scanning if enabled in settings."""
        scan_on_startup = self._config_manager.get("scanning.scan_on_startup", True)

        if not scan_on_startup:
            self._status_label.setText("Ready (auto-scan disabled)")
            return

        servers_to_fetch = self._server_service.get_servers()

        if not servers_to_fetch:
            self._status_label.setText("Ready (no servers)")
            return

        max_workers = self._config_manager.get("scanning.parallel_scan_limit", 5)
        self._status_label.setText(f"Fetching data for {len(servers_to_fetch)} servers...")
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)

        self._data_fetch_service.start_batch_scan(servers_to_fetch, max_workers)

    def _on_scan_progress(self, current: int, total: int, server_name: str) -> None:
        """Handle scan progress update."""
        progress = int((current / total) * 100)
        self._progress_bar.setValue(progress)
        self._progress_bar.setFormat(f"{current}/{total} - {server_name}")
        self._status_label.setText(f"Scanning servers ({current}/{total})...")

    def _on_server_data_complete(self, server_id: str, result: object) -> None:
        """Handle individual server data fetch completion."""
        # Store result in cache
        cache_entry = self._cache_service.get_or_create_server_data(server_id)
        cache_entry.scrape_success = result.scrape_success
        cache_entry.scrape_data = result.scrape_data
        cache_entry.scrape_error = result.scrape_error
        cache_entry.ping_ms = result.ping_ms
        cache_entry.ping_success = result.ping_success
        cache_entry.worlds_data = result.worlds_data
        cache_entry.reddit_posts = result.reddit_posts
        cache_entry.reddit_error = result.reddit_error
        cache_entry.updates = result.updates
        cache_entry.updates_error = result.updates_error

        # Update server table if scraping data is available
        if result.scrape_success and result.scrape_data:
            self._server_table.update_server_data(server_id, result.scrape_data)

        # Update ping if available
        if result.ping_success:
            for server in self._server_service.get_servers():
                if server.id == server_id:
                    server.ping_ms = result.ping_ms
                    if result.worlds_data is not None:
                        if 'worlds' in server.data:
                            server.data['worlds'] = result.worlds_data
                    break
            self._server_table._refresh_table()

    def _on_batch_scan_finished(self, all_results: dict) -> None:
        """Handle batch data fetch completion."""
        total_count = len(all_results)
        scrape_success = sum(1 for r in all_results.values() if r.scrape_success)
        ping_success = sum(1 for r in all_results.values() if r.ping_success)

        self._progress_bar.setVisible(False)
        self._status_label.setText(
            f"Data fetch complete: {scrape_success}/{total_count} scraped, {ping_success}/{total_count} pinged"
        )

        QTimer.singleShot(5000, lambda: self._status_label.setText("Ready"))

    def _on_scan_error(self, error: str) -> None:
        """Handle scan error."""
        self._progress_bar.setVisible(False)
        self._status_label.setText(f"Scan error: {error}")
        print(f"Batch scan error: {error}")


def main() -> int:
    """Run the application."""
    resource_manager = ResourceManager()
    app_paths = get_app_paths()

    resource_manager.add_search_path("themes", app_paths.get_themes_dir())
    resource_manager.add_search_path("themes", Path("pserver_manager/themes"))
    resource_manager.add_search_path("icons", Path("pserver_manager/icons"))
    resource_manager.add_search_path("translations", Path("pserver_manager/translations"))

    app = Application(
        argv=sys.argv,
        app_name="PServerManager",
        org_name="PServerManager",
        org_domain="pservermanager.local",
        resource_manager=resource_manager,
        included_themes=[],
        excluded_themes=["monokai"],
        include_auto_theme=False,
    )

    app.setStyle("Fusion")

    plugin_manager = PluginManager(application=app)
    plugin_manager.add_plugin_path(Path("pserver_manager/plugins"))

    available_plugins = plugin_manager.discover_plugins()
    for plugin_metadata in available_plugins:
        print(f"Found plugin: {plugin_metadata.id} - {plugin_metadata.name}")
        plugin_manager.load_plugin(plugin_metadata.id)
        plugin_manager.activate_plugin(plugin_metadata.id)

    window = MainWindow(application=app)

    saved_theme = window._config_manager.get("ui.theme", "nord")
    app.theme_manager.set_theme(saved_theme)

    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
