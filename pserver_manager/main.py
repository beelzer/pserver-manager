"""Main application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QSplitter

from qtframework import Application
from qtframework.core import BaseWindow
from qtframework.plugins import PluginManager
from qtframework.utils import ResourceManager
from qtframework.widgets import VBox

from pserver_manager.models import Game, GameVersion, Server, ServerStatus
from pserver_manager.widgets import GameSidebar, ServerTable


class MainWindow(BaseWindow):
    """Main application window."""

    def __init__(self, application: Application) -> None:
        """Initialize main window.

        Args:
            application: Application instance
        """
        # Initialize data before parent init (which calls _setup_ui)
        self._games: list[Game] = []
        self._servers: list[Server] = []
        self._load_sample_data()

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
        self._sidebar.set_games(self._games)
        self._sidebar.game_selected.connect(self._on_game_selected)
        self._sidebar.version_selected.connect(self._on_version_selected)
        self._sidebar.setMinimumWidth(250)
        self._sidebar.setMaximumWidth(400)

        # Create server table
        self._server_table = ServerTable()
        self._server_table.set_servers(self._servers)
        self._server_table.server_selected.connect(self._on_server_selected)
        self._server_table.server_double_clicked.connect(self._on_server_double_clicked)

        # Add to splitter
        splitter.addWidget(self._sidebar)
        splitter.addWidget(self._server_table)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        # Add splitter with stretch to fill vertical space
        main_layout.add_widget(splitter, stretch=1)

        # Set central widget
        self.setCentralWidget(main_layout)

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

    def _load_sample_data(self) -> None:
        """Load sample data for demonstration."""
        # Create games with versions
        self._games = [
            Game(
                id="minecraft",
                name="Minecraft",
                versions=[
                    GameVersion(id="1.20", name="1.20.x"),
                    GameVersion(id="1.19", name="1.19.x"),
                    GameVersion(id="1.18", name="1.18.x"),
                    GameVersion(id="modded", name="Modded"),
                ],
            ),
            Game(
                id="valheim",
                name="Valheim",
                versions=[
                    GameVersion(id="vanilla", name="Vanilla"),
                    GameVersion(id="mistlands", name="Mistlands"),
                ],
            ),
            Game(
                id="terraria",
                name="Terraria",
                versions=[
                    GameVersion(id="1.4.4", name="1.4.4 (Current)"),
                    GameVersion(id="modded", name="tModLoader"),
                ],
            ),
            Game(
                id="ark",
                name="ARK: Survival Evolved",
                versions=[
                    GameVersion(id="island", name="The Island"),
                    GameVersion(id="ragnarok", name="Ragnarok"),
                    GameVersion(id="genesis", name="Genesis"),
                ],
            ),
        ]

        # Create sample servers
        self._servers = [
            Server(
                id="mc1",
                name="Survival Main",
                game_id="minecraft",
                version_id="1.20",
                status=ServerStatus.ONLINE,
                host="mc.example.com",
                port=25565,
                players=42,
                max_players=100,
                uptime="3d 14h",
            ),
            Server(
                id="mc2",
                name="Creative Build",
                game_id="minecraft",
                version_id="1.20",
                status=ServerStatus.ONLINE,
                host="creative.example.com",
                port=25566,
                players=18,
                max_players=50,
                uptime="1d 8h",
            ),
            Server(
                id="mc3",
                name="Modded Adventure",
                game_id="minecraft",
                version_id="modded",
                status=ServerStatus.MAINTENANCE,
                host="modded.example.com",
                port=25567,
                players=0,
                max_players=60,
                uptime="0h 0m",
            ),
            Server(
                id="vh1",
                name="Viking Adventures",
                game_id="valheim",
                version_id="mistlands",
                status=ServerStatus.ONLINE,
                host="valheim.example.com",
                port=2456,
                players=8,
                max_players=10,
                uptime="7d 2h",
            ),
            Server(
                id="vh2",
                name="New World",
                game_id="valheim",
                version_id="vanilla",
                status=ServerStatus.STARTING,
                host="valheim2.example.com",
                port=2457,
                players=0,
                max_players=10,
                uptime="0h 2m",
            ),
            Server(
                id="tr1",
                name="Hardmode Expert",
                game_id="terraria",
                version_id="1.4.4",
                status=ServerStatus.ONLINE,
                host="terraria.example.com",
                port=7777,
                players=6,
                max_players=8,
                uptime="12h 34m",
            ),
            Server(
                id="ark1",
                name="PvE Ragnarok",
                game_id="ark",
                version_id="ragnarok",
                status=ServerStatus.ONLINE,
                host="ark.example.com",
                port=27015,
                players=24,
                max_players=70,
                uptime="5d 18h",
            ),
        ]

    def _on_game_selected(self, game_id: str) -> None:
        """Handle game selection.

        Args:
            game_id: Selected game ID
        """
        print(f"Game selected: {game_id}")
        self._server_table.filter_by_game(game_id)

    def _on_version_selected(self, game_id: str, version_id: str) -> None:
        """Handle version selection.

        Args:
            game_id: Game ID
            version_id: Version ID
        """
        print(f"Version selected: {game_id} - {version_id}")
        self._server_table.filter_by_game(game_id, version_id)

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

    def _on_add_server(self) -> None:
        """Handle add server button click."""
        print("Add server clicked")

    def _on_refresh(self) -> None:
        """Handle refresh button click."""
        print("Refresh clicked")
        self._server_table.set_servers(self._servers)

    def _on_settings(self) -> None:
        """Handle settings button click."""
        print("Settings clicked")

    def _on_show_all(self) -> None:
        """Handle show all servers action."""
        print("Show all servers")
        self._server_table.filter_by_game(None)

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
