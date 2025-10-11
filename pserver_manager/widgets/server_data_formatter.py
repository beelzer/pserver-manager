"""Formatter for server data display."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QTreeWidgetItem, QApplication

from pserver_manager.models import ServerStatus

if TYPE_CHECKING:
    from pserver_manager.config_loader import ServerDefinition


class ServerDataFormatter:
    """Formatter for server data display in table."""

    @staticmethod
    def get_column_value(server: ServerDefinition, column_id: str) -> Any:
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
            return ServerDataFormatter.format_status(server.status, server.ping_ms)
        elif column_id == "address":
            # Use host directly (may already include port)
            return server.host
        elif column_id == "players":
            if server.players == -1:
                return "-"
            if server.max_players > 0:
                return f"{server.players}/{server.max_players}"
            return str(server.players)
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

    @staticmethod
    def format_status(status: ServerStatus, ping_ms: int) -> str:
        """Format status for display with ping.

        Args:
            status: Server status
            ping_ms: Ping in milliseconds (-1 if not pinged)

        Returns:
            Formatted status string with ping
        """
        # Show "-" if not pinged yet
        if ping_ms == -1:
            return "-"

        if status == ServerStatus.ONLINE and ping_ms >= 0:
            return f"{ping_ms}ms"
        elif status == ServerStatus.OFFLINE:
            return "Offline"
        elif status == ServerStatus.MAINTENANCE:
            return "Maintenance"
        elif status == ServerStatus.STARTING:
            return "Starting"
        else:
            return status.value

    @staticmethod
    def set_status_color(
        item: QTreeWidgetItem,
        column: int,
        status: ServerStatus,
        ping_ms: int
    ) -> None:
        """Set status color for tree widget item.

        Args:
            item: Tree item
            column: Column index
            status: Server status
            ping_ms: Ping in milliseconds (-1 if not pinged)
        """
        try:
            app = QApplication.instance()
            if app and hasattr(app, "theme_manager"):
                theme = app.theme_manager.get_current_theme()
                if theme and theme.tokens:
                    # Determine color based on status and ping using custom tokens
                    if status == ServerStatus.OFFLINE:
                        # Use custom ping.offline token, fallback to semantic
                        color = theme.tokens.get_custom("ping.offline", theme.tokens.semantic.feedback_error)
                    elif status == ServerStatus.MAINTENANCE:
                        # Use custom server_status.maintenance or warning
                        color = theme.tokens.get_custom("server_status.maintenance", theme.tokens.semantic.feedback_warning)
                    elif status == ServerStatus.STARTING:
                        # Use custom server_status.starting or info
                        color = theme.tokens.get_custom("server_status.starting", theme.tokens.semantic.feedback_info)
                    elif status == ServerStatus.ONLINE:
                        # Color based on ping latency using custom ping tokens
                        if ping_ms < 50:
                            color = theme.tokens.get_custom("ping.excellent", theme.tokens.semantic.feedback_success)
                        elif ping_ms < 100:
                            color = theme.tokens.get_custom("ping.good", theme.tokens.semantic.feedback_success)
                        elif ping_ms < 200:
                            color = theme.tokens.get_custom("ping.fair", theme.tokens.semantic.feedback_warning)
                        elif ping_ms < 300:
                            color = theme.tokens.get_custom("ping.poor", theme.tokens.semantic.feedback_warning)
                        else:
                            color = theme.tokens.get_custom("ping.bad", theme.tokens.semantic.feedback_error)
                    else:
                        color = theme.tokens.semantic.fg_primary

                    # Set font color for this column
                    item.setForeground(column, QBrush(QColor(color)))

                    # Set background to transparent
                    item.setBackground(column, QBrush(Qt.GlobalColor.transparent))
        except (AttributeError, ImportError):
            pass
