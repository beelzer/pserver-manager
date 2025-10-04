"""Main application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QSplitter

from qtframework import Application
from qtframework.core import BaseWindow
from qtframework.plugins import PluginManager
from qtframework.utils import ResourceManager
from qtframework.widgets import VBox

from pserver_manager.config_loader import ColumnDefinition, ConfigLoader, GameDefinition
from pserver_manager.models import Game
from pserver_manager.widgets import GameSidebar, ServerTable
from pserver_manager.widgets.server_editor import ServerEditor


class MainWindow(BaseWindow):
    """Main application window."""

    def __init__(self, application: Application) -> None:
        """Initialize main window.

        Args:
            application: Application instance
        """
        # Initialize data before parent init (which calls _setup_ui)
        self._config_loader = ConfigLoader(Path(__file__).parent / "config")
        self._game_defs: list[GameDefinition] = []
        self._all_servers = []
        self._current_game: GameDefinition | None = None
        self._load_config()

        super().__init__(application=application)
        self.setWindowTitle("PServer Manager")
        self.setMinimumSize(1280, 800)

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        # Create menu bar
        self._create_menu_bar()

        # Create main container
        main_layout = VBox(spacing=0, margins=0)

        # Create splitter for sidebar and content
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Create sidebar
        self._sidebar = GameSidebar()
        games = [gd.to_game() for gd in self._game_defs]
        self._sidebar.set_games(games)
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

        # Add to splitter
        splitter.addWidget(self._sidebar)
        splitter.addWidget(self._server_table)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        # Add splitter with stretch to fill vertical space
        main_layout.add_widget(splitter, stretch=1)

        # Set central widget
        self.setCentralWidget(main_layout)

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

    def _apply_theme(self, theme_name: str) -> None:
        """Apply selected theme.

        Args:
            theme_name: Theme name to apply
        """
        self.application.theme_manager.set_theme(theme_name)

    def _create_menu_bar(self) -> None:
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

    def _load_config(self) -> None:
        """Load configuration from YAML files."""
        self._game_defs = self._config_loader.load_games()
        self._all_servers = self._config_loader.load_servers()

    def _show_all_servers(self) -> None:
        """Show all servers with generic columns."""
        self._current_game = None

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
        print("All servers selected")
        self._show_all_servers()

    def _on_game_selected(self, game_id: str) -> None:
        """Handle game selection.

        Args:
            game_id: Selected game ID
        """
        print(f"Game selected: {game_id}")

        # Find game definition
        game_def = self._config_loader.get_game_by_id(game_id, self._game_defs)
        if not game_def:
            return

        self._current_game = game_def

        # Set columns specific to this game
        self._server_table.set_columns(game_def.columns)

        # Filter servers for this game
        self._server_table.filter_by_game(self._all_servers, game_id)

    def _on_version_selected(self, game_id: str, version_id: str) -> None:
        """Handle version selection.

        Args:
            game_id: Game ID
            version_id: Version ID
        """
        print(f"Version selected: {game_id} - {version_id}")

        # Find game definition
        game_def = self._config_loader.get_game_by_id(game_id, self._game_defs)
        if not game_def:
            return

        self._current_game = game_def

        # Set columns specific to this game
        self._server_table.set_columns(game_def.columns)

        # Filter servers for this game and version
        self._server_table.filter_by_game(self._all_servers, game_id, version_id)

    def _on_server_selected(self, server_id: str) -> None:
        """Handle server selection.

        Args:
            server_id: Selected server ID
        """
        print(f"Server selected: {server_id}")

    def _on_server_double_clicked(self, server_id: str) -> None:
        """Handle server double click.

        Args:
            server_id: Double-clicked server ID
        """
        print(f"Server double-clicked: {server_id}")

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
            print(f"Server not found: {server_id}")
            return

        # Find the game definition
        game = self._config_loader.get_game_by_id(server.game_id, self._game_defs)
        if not game:
            print(f"Game not found: {server.game_id}")
            return

        # Open editor dialog
        editor = ServerEditor(server, game, self)
        if editor.exec():
            # Save changes
            if editor.save_to_file():
                print(f"Server {server_id} saved successfully")
                # Reload config and refresh display
                self._load_config()
                if self._current_game:
                    self._on_game_selected(self._current_game.id)
                else:
                    self._show_all_servers()
            else:
                print(f"Failed to save server {server_id}")

    def _on_add_server(self) -> None:
        """Handle add server button click."""
        print("Add server clicked")

    def _on_refresh(self) -> None:
        """Handle refresh button click."""
        print("Refresh clicked")
        self._load_config()
        self._show_all_servers()

    def _on_ping_servers(self) -> None:
        """Handle ping servers action."""
        print("Pinging servers...")
        self._server_table.ping_servers()
        print("Ping complete")

    def _on_settings(self) -> None:
        """Handle settings button click."""
        print("Settings clicked")

    def _on_show_all(self) -> None:
        """Handle show all servers action."""
        print("Show all servers")
        self._show_all_servers()

    def _on_about(self) -> None:
        """Handle about action."""
        print("About clicked")


def main() -> int:
    """Run the application.

    Returns:
        Application exit code
    """
    # Setup custom resource manager
    resource_manager = ResourceManager()

    # Add custom resource paths (searched before framework paths)
    resource_manager.add_search_path("themes", Path("pserver_manager/themes"))
    resource_manager.add_search_path("icons", Path("pserver_manager/icons"))
    resource_manager.add_search_path("translations", Path("pserver_manager/translations"))

    # Create application with custom resources
    app = Application(
        argv=sys.argv,
        app_name="PServerManager",
        org_name="PServerManager",
        org_domain="pservermanager.local",
        resource_manager=resource_manager,
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

    # Set theme (uses custom theme if exists, otherwise built-in)
    app.theme_manager.set_theme("dark")

    # Create and show main window
    window = MainWindow(application=app)
    window.show()

    # Run application
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
