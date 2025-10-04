"""Server table widget."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)

from qtframework.widgets import VBox


if TYPE_CHECKING:
    from pserver_manager.models import Server, ServerStatus


class ServerTable(VBox):
    """Table widget for displaying game servers."""

    server_selected = Signal(str)  # server_id
    server_double_clicked = Signal(str)  # server_id

    def __init__(self, parent=None) -> None:
        """Initialize the server table."""
        super().__init__(spacing=0, margins=0, parent=parent)

        self._setup_ui()
        self._servers: dict[str, Server] = {}

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Create table
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["Server Name", "Status", "Address", "Players", "Uptime", "Version"]
        )

        # Configure table behavior
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)

        # Configure header
        header = self._table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        # Connect signals
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.itemDoubleClicked.connect(self._on_item_double_clicked)

        self.add_widget(self._table)

    def set_servers(self, servers: list[Server]) -> None:
        """Set the list of servers to display.

        Args:
            servers: List of servers to display
        """
        self._servers = {server.id: server for server in servers}
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Refresh the table with current servers."""
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)

        for row, server in enumerate(self._servers.values()):
            self._table.insertRow(row)

            # Server name
            name_item = QTableWidgetItem(server.name)
            name_item.setData(Qt.ItemDataRole.UserRole, server.id)
            self._table.setItem(row, 0, name_item)

            # Status
            status_item = QTableWidgetItem(self._format_status(server.status))
            status_item.setData(Qt.ItemDataRole.UserRole, server.status.value)
            self._set_status_color(status_item, server.status)
            self._table.setItem(row, 1, status_item)

            # Address
            address_item = QTableWidgetItem(server.address)
            self._table.setItem(row, 2, address_item)

            # Players
            players_item = QTableWidgetItem(server.player_count)
            players_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 3, players_item)

            # Uptime
            uptime_item = QTableWidgetItem(server.uptime)
            uptime_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 4, uptime_item)

            # Version
            version_item = QTableWidgetItem(server.version_id)
            self._table.setItem(row, 5, version_item)

        self._table.setSortingEnabled(True)

    def _format_status(self, status: ServerStatus) -> str:
        """Format status for display.

        Args:
            status: Server status

        Returns:
            Formatted status string
        """
        from pserver_manager.models import ServerStatus

        status_map = {
            ServerStatus.ONLINE: "● Online",
            ServerStatus.OFFLINE: "● Offline",
            ServerStatus.MAINTENANCE: "● Maintenance",
            ServerStatus.STARTING: "● Starting",
        }
        return status_map.get(status, str(status.value))

    def _set_status_color(self, item: QTableWidgetItem, status: ServerStatus) -> None:
        """Set item color based on status.

        Args:
            item: Table item
            status: Server status
        """
        from PySide6.QtGui import QColor
        from pserver_manager.models import ServerStatus

        color_map = {
            ServerStatus.ONLINE: QColor(46, 204, 113),  # Green
            ServerStatus.OFFLINE: QColor(231, 76, 60),  # Red
            ServerStatus.MAINTENANCE: QColor(241, 196, 15),  # Yellow
            ServerStatus.STARTING: QColor(52, 152, 219),  # Blue
        }

        color = color_map.get(status)
        if color:
            item.setForeground(color)

    def _on_selection_changed(self) -> None:
        """Handle selection change."""
        items = self._table.selectedItems()
        if items:
            server_id = items[0].data(Qt.ItemDataRole.UserRole)
            if server_id:
                self.server_selected.emit(server_id)

    def _on_item_double_clicked(self, item: QTableWidgetItem) -> None:
        """Handle item double click.

        Args:
            item: Double-clicked item
        """
        server_id = item.data(Qt.ItemDataRole.UserRole)
        if server_id:
            self.server_double_clicked.emit(server_id)

    def filter_by_game(self, game_id: str | None = None, version_id: str | None = None) -> None:
        """Filter servers by game and version.

        Args:
            game_id: Game ID to filter by
            version_id: Version ID to filter by
        """
        if game_id is None:
            # Show all servers
            self._refresh_table()
            return

        # Filter servers
        filtered_servers = {}
        for server in self._servers.values():
            if server.game_id == game_id:
                if version_id is None or server.version_id == version_id:
                    filtered_servers[server.id] = server

        # Temporarily replace servers and refresh
        original_servers = self._servers
        self._servers = filtered_servers
        self._refresh_table()
        self._servers = original_servers
