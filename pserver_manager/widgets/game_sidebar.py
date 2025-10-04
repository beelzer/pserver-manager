"""Game sidebar widget for navigation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from qtframework.widgets import VBox


if TYPE_CHECKING:
    from pserver_manager.models import Game


class GameSidebar(VBox):
    """Sidebar widget for game navigation.

    Displays games in a tree structure with expandable versions.
    """

    game_selected = Signal(str)  # game_id
    version_selected = Signal(str, str)  # game_id, version_id

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

        # Set selection behavior
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self._tree.itemClicked.connect(self._on_item_clicked)

        self.add_widget(self._tree)

    def set_games(self, games: list[Game]) -> None:
        """Set the list of games to display.

        Args:
            games: List of games to display
        """
        self._games = {game.id: game for game in games}
        self._tree.clear()

        for game in games:
            game_item = QTreeWidgetItem([game.name])
            game_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "game", "id": game.id})

            # Add versions as children if they exist
            if game.versions:
                for version in game.versions:
                    version_item = QTreeWidgetItem([version.name])
                    version_item.setData(
                        0,
                        Qt.ItemDataRole.UserRole,
                        {"type": "version", "game_id": game.id, "version_id": version.id},
                    )
                    game_item.addChild(version_item)

            self._tree.addTopLevelItem(game_item)

        # Expand all items by default
        self._tree.expandAll()

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle item click.

        Args:
            item: Clicked tree item
            column: Clicked column
        """
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        if data["type"] == "game":
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
