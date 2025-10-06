"""Game sidebar widget for navigation."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from qtframework.widgets import VBox
from pserver_manager.utils.paths import get_app_paths


if TYPE_CHECKING:
    from pserver_manager.models import Game


class GameSidebar(VBox):
    """Sidebar widget for game navigation.

    Displays games in a tree structure with expandable versions.
    """

    game_selected = Signal(str)  # game_id
    version_selected = Signal(str, str)  # game_id, version_id
    all_servers_selected = Signal()  # Show all servers

    def __init__(self, parent=None) -> None:
        """Initialize the game sidebar."""
        super().__init__(spacing=0, margins=0, parent=parent)

        self._setup_ui()
        self._games: dict[str, Game] = {}

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Create tree widget
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(20)
        self._tree.setProperty("widget-type", "sidebar")
        self._tree.setAnimated(True)

        # Set uniform row heights for consistency
        self._tree.setUniformRowHeights(True)

        # Set icon size - most expansion icons have roughly 1.5:1 width:height ratio
        icon_height = 48
        self._tree.setIconSize(QSize(int(icon_height * 1.5), icon_height))

        # Set selection behavior
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self._tree.itemClicked.connect(self._on_item_clicked)

        self.add_widget(self._tree)

    def set_games(self, games: list[Game], servers: list | None = None) -> None:
        """Set the list of games to display.

        Args:
            games: List of games to display
            servers: Optional list of servers to filter versions (only show versions with servers)
        """
        self._games = {game.id: game for game in games}
        self._tree.clear()

        # Build set of version IDs that have servers
        used_version_ids = set()
        if servers:
            for server in servers:
                used_version_ids.add((server.game_id, server.version_id))

        # Add "All Servers" item at the top
        all_item = QTreeWidgetItem(["All Servers"])
        all_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "all"})
        self._tree.addTopLevelItem(all_item)

        for game in games:
            game_item = QTreeWidgetItem([game.name])
            game_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "game", "id": game.id})

            # Set game icon if available
            if game.icon:
                # Try user icons directory first, fall back to bundled
                user_icon_path = get_app_paths().get_icons_dir() / game.icon
                bundled_icon_path = Path(__file__).parent.parent / "assets" / game.icon

                icon_path = user_icon_path if user_icon_path.exists() else bundled_icon_path
                if icon_path.exists():
                    game_item.setIcon(0, QIcon(str(icon_path)))

            # Add versions as children if they exist
            if game.versions:
                for version in game.versions:
                    # If servers list provided, only show versions that have servers
                    if servers and (game.id, version.id) not in used_version_ids:
                        continue

                    version_item = QTreeWidgetItem([version.name])
                    version_item.setData(
                        0,
                        Qt.ItemDataRole.UserRole,
                        {"type": "version", "game_id": game.id, "version_id": version.id},
                    )

                    # Set version icon if available
                    if version.icon:
                        # Try user icons directory first, fall back to bundled
                        user_version_icon_path = get_app_paths().get_icons_dir() / version.icon
                        bundled_version_icon_path = Path(__file__).parent.parent / "assets" / version.icon

                        version_icon_path = user_version_icon_path if user_version_icon_path.exists() else bundled_version_icon_path
                        if version_icon_path.exists():
                            version_item.setIcon(0, QIcon(str(version_icon_path)))

                    game_item.addChild(version_item)

            self._tree.addTopLevelItem(game_item)

        # Expand all items by default
        self._tree.expandAll()

        # Select "All Servers" by default
        self._tree.setCurrentItem(all_item)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle item click.

        Args:
            item: Clicked tree item
            column: Clicked column
        """
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        if data["type"] == "all":
            self.all_servers_selected.emit()
        elif data["type"] == "game":
            self.game_selected.emit(data["id"])
        elif data["type"] == "version":
            self.version_selected.emit(data["game_id"], data["version_id"])

    def get_selected_game_id(self) -> str | None:
        """Get the currently selected game ID.

        Returns:
            Game ID or None if no selection
        """
        items = self._tree.selectedItems()
        if not items:
            return None

        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return None

        if data["type"] == "game":
            return data["id"]
        elif data["type"] == "version":
            return data["game_id"]

        return None
