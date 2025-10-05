"""Server table widget."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
    QStyledItemDelegate,
)

from qtframework.widgets import VBox
from qtframework.widgets.badge import Badge, BadgeVariant
from qtframework.widgets.advanced import ConfirmDialog
from pserver_manager.models import ServerStatus
from pserver_manager.utils import ping_multiple_servers_sync
from pserver_manager.utils.paths import get_app_paths


if TYPE_CHECKING:
    from pserver_manager.config_loader import ColumnDefinition, ServerDefinition
    from pserver_manager.models import ServerStatus


class ColoredTextDelegate(QStyledItemDelegate):
    """Delegate that respects foreground color even with stylesheets."""

    def paint(self, painter, option, index):
        """Paint the item with custom foreground color."""
        # Get the foreground color from item data
        color_data = index.data(Qt.ItemDataRole.ForegroundRole)

        if color_data:
            # Save painter state
            painter.save()

            # Create a modified option with no text to draw background only
            opt = option
            self.initStyleOption(opt, index)

            # Temporarily remove text so background draws without text
            text = opt.text
            opt.text = ""

            # Draw background only (selection, hover, alternating colors, etc.)
            opt.widget.style().drawControl(
                opt.widget.style().ControlElement.CE_ItemViewItem,
                opt,
                painter,
                opt.widget
            )

            # Now draw text with custom color
            if hasattr(color_data, 'color'):
                # It's a QBrush
                painter.setPen(color_data.color())
            else:
                # Try to convert to QColor
                try:
                    painter.setPen(QColor(color_data))
                except:
                    pass

            # Draw the text
            if text:
                text_rect = option.rect
                text_rect.adjust(4, 0, -4, 0)  # Add padding
                alignment = index.data(Qt.ItemDataRole.TextAlignmentRole)
                if alignment is None:
                    alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                painter.drawText(text_rect, alignment, text)

            painter.restore()
        else:
            # No custom color, use default painting
            super().paint(painter, option, index)


class ServerTable(VBox):
    """Table widget for displaying game servers."""

    server_selected = Signal(str)  # server_id
    server_double_clicked = Signal(str)  # server_id
    edit_server_requested = Signal(str)  # server_id
    delete_server_requested = Signal(str)  # server_id

    def __init__(self, parent=None) -> None:
        """Initialize the server table."""
        super().__init__(spacing=0, margins=0, parent=parent)

        self._setup_ui()
        self._servers: list[ServerDefinition] = []
        self._columns: list[ColumnDefinition] = []

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Create table
        self._table = QTableWidget()

        # Configure table behavior
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)

        # Install custom delegate to handle colored text
        self._table.setItemDelegate(ColoredTextDelegate(self._table))

        # Connect signals
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)

        self.add_widget(self._table)

    def set_columns(self, columns: list[ColumnDefinition]) -> None:
        """Set the table columns.

        Args:
            columns: List of column definitions
        """
        self._columns = columns
        self._table.setColumnCount(len(columns))
        self._table.setHorizontalHeaderLabels([col.label for col in columns])

        # Configure column widths
        header = self._table.horizontalHeader()
        for i, col in enumerate(columns):
            if col.width == "stretch":
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

    def set_servers(self, servers: list[ServerDefinition]) -> None:
        """Set the list of servers to display.

        Args:
            servers: List of server definitions to display
        """
        self._servers = servers
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Refresh the table with current servers."""
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)

        for row, server in enumerate(self._servers):
            self._table.insertRow(row)

            # Populate columns based on column definitions
            for col_idx, col in enumerate(self._columns):
                value = self._get_column_value(server, col.id)
                item = QTableWidgetItem(str(value))

                # Store server ID in first column
                if col_idx == 0:
                    item.setData(Qt.ItemDataRole.UserRole, server.id)

                    # Add server icon if available
                    if server.icon:
                        # Try user icons directory first, fall back to bundled
                        user_icon_path = get_app_paths().get_icons_dir() / server.icon
                        bundled_icon_path = Path(__file__).parent.parent / "assets" / server.icon

                        icon_path = user_icon_path if user_icon_path.exists() else bundled_icon_path
                        if icon_path.exists():
                            item.setIcon(QIcon(str(icon_path)))

                # Special formatting for certain columns
                if col.id in ["players", "uptime"]:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                # Set status color with inline stylesheet
                if col.id == "status":
                    self._set_status_color_inline(item, server.status, server.ping_ms)

                self._table.setItem(row, col_idx, item)

        self._table.setSortingEnabled(True)

    def _get_column_value(self, server: ServerDefinition, column_id: str) -> Any:
        """Get the value for a specific column.

        Args:
            server: Server definition
            column_id: Column identifier

        Returns:
            Column value
        """
        if column_id == "name":
            return server.name
        elif column_id == "status":
            return self._format_status(server.status, server.ping_ms)
        elif column_id == "address":
            # Use host directly (may already include port)
            return server.host
        elif column_id == "players":
            return f"{server.players}/{server.max_players}"
        elif column_id == "uptime":
            return server.uptime
        elif column_id == "version":
            return server.version_id
        else:
            # Get custom field from server data
            value = server.get_field(column_id, "")
            # Format boolean values
            if isinstance(value, bool):
                return "Yes" if value else "No"
            return value

    def _format_status(self, status: ServerStatus, ping_ms: int) -> str:
        """Format status for display with ping.

        Args:
            status: Server status
            ping_ms: Ping in milliseconds (-1 if not pinged)

        Returns:
            Formatted status string with ping
        """
        if status == ServerStatus.ONLINE and ping_ms >= 0:
            return f"🟢 {ping_ms}ms"
        elif status == ServerStatus.OFFLINE:
            return "🔴 Offline"
        elif status == ServerStatus.MAINTENANCE:
            return "🟡 Maintenance"
        elif status == ServerStatus.STARTING:
            return "🟡 Starting"
        else:
            return f"● {status.value}"

    def _set_status_color_inline(self, item: QTableWidgetItem, status: ServerStatus, ping_ms: int) -> None:
        """Set status color using inline stylesheet.

        Args:
            item: Table item
            status: Server status
            ping_ms: Ping in milliseconds (-1 if not pinged)
        """
        try:
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app and hasattr(app, "theme_manager"):
                theme = app.theme_manager.get_current_theme()
                if theme and theme.tokens:
                    tokens = theme.tokens.semantic

                    # Determine color based on status and ping
                    if status == ServerStatus.OFFLINE:
                        color = tokens.feedback_error
                    elif status == ServerStatus.MAINTENANCE:
                        color = tokens.feedback_warning
                    elif status == ServerStatus.STARTING:
                        color = tokens.feedback_info
                    elif status == ServerStatus.ONLINE:
                        # Color based on ping latency
                        if ping_ms < 150:
                            color = tokens.feedback_success
                        elif ping_ms < 250:
                            color = tokens.feedback_warning
                        else:
                            color = tokens.feedback_error
                    else:
                        color = tokens.fg_primary

                    # Use data role to store color for inline styling
                    # This won't work directly, so we need a different approach
                    from PySide6.QtGui import QColor, QBrush
                    from PySide6.QtCore import Qt

                    # Set font color
                    item.setForeground(QBrush(QColor(color)))

                    # ALSO set background to transparent explicitly to avoid issues
                    item.setBackground(QBrush(Qt.GlobalColor.transparent))
        except (AttributeError, ImportError):
            pass

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

    def _show_context_menu(self, pos) -> None:
        """Show context menu for server.

        Args:
            pos: Menu position
        """
        item = self._table.itemAt(pos)
        if not item:
            return

        server_id = item.data(Qt.ItemDataRole.UserRole)
        if not server_id:
            return

        menu = QMenu(self._table)
        edit_action = menu.addAction("Edit")
        delete_action = menu.addAction("Delete")

        action = menu.exec(self._table.viewport().mapToGlobal(pos))
        if action == edit_action:
            self.edit_server_requested.emit(server_id)
        elif action == delete_action:
            # Show confirmation dialog before deleting
            if ConfirmDialog.confirm(
                "Delete Server",
                f"Are you sure you want to delete this server?\n\nThis action cannot be undone.",
                self,
            ):
                self.delete_server_requested.emit(server_id)

    def filter_by_game(
        self,
        all_servers: list[ServerDefinition],
        game_id: str | None = None,
        version_id: str | None = None,
    ) -> None:
        """Filter servers by game and version.

        Args:
            all_servers: Complete list of all servers
            game_id: Game ID to filter by
            version_id: Version ID to filter by
        """
        if game_id is None:
            # Show all servers
            self._servers = all_servers
        else:
            # Filter servers
            filtered = []
            for server in all_servers:
                if server.game_id == game_id:
                    if version_id is None or server.version_id == version_id:
                        filtered.append(server)
            self._servers = filtered

        self._refresh_table()

    def ping_servers(self) -> None:
        """Ping all servers to update their status."""
        if not self._servers:
            return

        # Ping servers and get status + latency results
        ping_results = ping_multiple_servers_sync(self._servers, timeout=3.0)

        # Update server statuses and ping times
        for server in self._servers:
            if server.id in ping_results:
                status, ping_ms = ping_results[server.id]
                server.status = status
                server.ping_ms = ping_ms

        # Refresh table to show updated statuses
        self._refresh_table()
