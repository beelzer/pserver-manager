"""Main application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from qtframework import Application
from qtframework.core import BaseWindow
from qtframework.plugins import PluginManager
from qtframework.utils import ResourceManager
from qtframework.widgets import Button, Card, VBox, HBox


class MainWindow(BaseWindow):
    """Main application window."""

    def __init__(self, application: Application) -> None:
        """Initialize main window.

        Args:
            application: Application instance
        """
        super().__init__(application=application)
        self.setWindowTitle("PServer Manager")
        self.setMinimumSize(1024, 768)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        # Create main layout
        layout = VBox(spacing=16, margins=20)

        # Welcome card
        welcome_card = Card(title="Welcome to PServer Manager")
        welcome_layout = VBox(spacing=12)

        welcome_button = Button("Get Started", variant="primary")
        welcome_button.clicked.connect(self._on_welcome_clicked)

        welcome_layout.add_widget(welcome_button)
        welcome_card.set_content(welcome_layout)
        layout.add_widget(welcome_card)

        # Quick actions card
        actions_card = Card(title="Quick Actions")
        actions_layout = HBox(spacing=8)

        servers_btn = Button("View Servers", variant="secondary")
        servers_btn.clicked.connect(self._on_servers_clicked)

        settings_btn = Button("Settings", variant="secondary")
        settings_btn.clicked.connect(self._on_settings_clicked)

        actions_layout.add_widget(servers_btn)
        actions_layout.add_widget(settings_btn)

        actions_card.set_content(actions_layout)
        layout.add_widget(actions_card)

        # Add stretch to push content to top
        layout.add_stretch()

        # Set central widget
        self.setCentralWidget(layout)

    def _on_welcome_clicked(self) -> None:
        """Handle welcome button click."""
        print("Welcome to PServer Manager!")

    def _on_servers_clicked(self) -> None:
        """Handle servers button click."""
        print("Viewing servers...")

    def _on_settings_clicked(self) -> None:
        """Handle settings button click."""
        print("Opening settings...")


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
