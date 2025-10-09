"""Server table widget."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QIcon, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QStyledItemDelegate,
    QWidget,
)


class NumericTreeWidgetItem(QTreeWidgetItem):
    """Tree widget item that sorts numerically when numeric data is available."""

    def __lt__(self, other):
        """Compare items for sorting.

        Uses numeric data (UserRole + 1) if available, otherwise falls back to text comparison.
        """
        # Safety check: ensure we have a tree widget
        tree = self.treeWidget()
        if not tree:
            return super().__lt__(other)

        column = tree.sortColumn()
        if column < 0:
            column = 0

        # Try to get numeric sort data
        try:
            self_data = self.data(column, Qt.ItemDataRole.UserRole + 1)
            other_data = other.data(column, Qt.ItemDataRole.UserRole + 1)

            # If both have numeric data, compare numerically
            if self_data is not None and other_data is not None:
                return float(self_data) < float(other_data)
        except (ValueError, TypeError, RuntimeError):
            # Catch any Qt-related runtime errors
            pass

        # Fall back to text comparison
        try:
            self_text = self.text(column)
            other_text = other.text(column)
            return self_text < other_text
        except (RuntimeError, AttributeError):
            return False

from qtframework.widgets import VBox
from qtframework.widgets.badge import Badge, BadgeVariant
from qtframework.widgets.advanced import ConfirmDialog
from pserver_manager.models import ServerStatus
from pserver_manager.utils import ping_multiple_servers_sync, ping_multiple_hosts_sync, scrape_servers_sync
from pserver_manager.utils.paths import get_app_paths
from pserver_manager.widgets.server_links_widget import ServerLinksWidget
from pserver_manager.widgets.server_data_formatter import ServerDataFormatter


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
            if opt.widget:
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
    manage_accounts_requested = Signal(str)  # server_id
    register_requested = Signal(str)  # server_id
    login_requested = Signal(str)  # server_id

    def __init__(self, parent=None) -> None:
        """Initialize the server table."""
        super().__init__(spacing=0, margins=0, parent=parent)

        self._setup_ui()
        self._servers: list[ServerDefinition] = []
        self._columns: list[ColumnDefinition] = []

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Create tree widget (supports hierarchical data)
        self._table = QTreeWidget()

        # Configure tree behavior
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(False)  # Disabled during population, enabled after
        self._table.setRootIsDecorated(True)  # Show expand/collapse indicators
        self._table.setIndentation(20)  # Indent child items
        self._table.setUniformRowHeights(False)  # Allow different row heights for widgets
        self._table.setAnimated(True)  # Smooth expand/collapse animation

        # Install custom delegate to handle colored text
        self._table.setItemDelegate(ColoredTextDelegate(self._table))

        # Connect signals
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)

        self.add_widget(self._table)

    def set_columns(self, columns: list[ColumnDefinition]) -> None:
        """Set the tree columns.

        Args:
            columns: List of column definitions
        """
        self._columns = columns
        self._table.setColumnCount(len(columns))
        self._table.setHeaderLabels([col.label for col in columns])

        # Configure column widths - use Interactive for all columns initially
        # We'll set proper sizing after content is loaded
        header = self._table.header()
        header.setStretchLastSection(False)
        for i in range(len(columns)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)

    def set_servers(self, servers: list[ServerDefinition]) -> None:
        """Set the list of servers to display.

        Args:
            servers: List of server definitions to display
        """
        self._servers = servers
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Refresh the tree with current servers."""
        if not self._columns:
            return  # No columns set yet

        self._table.setSortingEnabled(False)
        self._table.clear()
        self._table.setHeaderLabels([col.label for col in self._columns])

        for server in self._servers:
            # Check if server has multiple worlds
            worlds = server.get_field('worlds', [])
            has_worlds = isinstance(worlds, list) and len(worlds) > 0

            # Create parent item for the server
            if has_worlds:
                # Server with multiple worlds - use NumericTreeWidgetItem for sorting
                parent_item = NumericTreeWidgetItem(self._table)
            else:
                # Single world server
                parent_item = NumericTreeWidgetItem(self._table)

            self._populate_server_item(parent_item, server, is_parent=has_worlds)

            # Add child items for each world if applicable
            if has_worlds:
                for world in worlds:
                    child_item = NumericTreeWidgetItem(parent_item)
                    self._populate_world_item(child_item, world, server)

                # Expand parent by default
                parent_item.setExpanded(True)

        # Re-enable sorting after all items are added
        self._table.setSortingEnabled(True)

        # Resize all columns to fit their content
        header = self._table.header()
        stretch_column_idx = -1

        for i, col in enumerate(self._columns):
            self._table.resizeColumnToContents(i)
            if col.width == "stretch":
                stretch_column_idx = i

        # If there's a stretch column, give it any remaining space
        if stretch_column_idx >= 0:
            # Calculate total width used by all columns
            total_width = sum(header.sectionSize(i) for i in range(len(self._columns)))
            available_width = self._table.viewport().width()

            # If there's extra space, give it to the stretch column
            if available_width > total_width:
                extra_width = available_width - total_width
                current_width = header.sectionSize(stretch_column_idx)
                header.resizeSection(stretch_column_idx, current_width + extra_width)

    def _populate_server_item(self, item: QTreeWidgetItem, server: ServerDefinition, is_parent: bool = False) -> None:
        """Populate a tree item with server data.

        Args:
            item: Tree item to populate
            server: Server definition
            is_parent: Whether this is a parent item with child worlds
        """
        for col_idx, col in enumerate(self._columns):
            # Handle links column specially with custom widget
            if col.id == "links":
                links_widget = self._create_links_widget(server)
                self._table.setItemWidget(item, col_idx, links_widget)
                continue

            value = self._get_column_value(server, col.id)
            item.setText(col_idx, str(value))

            # Store server ID in first column
            if col_idx == 0:
                item.setData(0, Qt.ItemDataRole.UserRole, server.id)

                # Add server icon if available
                if server.icon:
                    user_icon_path = get_app_paths().get_icons_dir() / server.icon
                    bundled_icon_path = Path(__file__).parent.parent / "assets" / server.icon
                    icon_path = user_icon_path if user_icon_path.exists() else bundled_icon_path
                    if icon_path.exists():
                        item.setIcon(0, QIcon(str(icon_path)))

            # Set numeric sort data for players column
            if col.id == "players":
                player_count = server.players if server.players != -1 else -1
                item.setData(col_idx, Qt.ItemDataRole.UserRole + 1, player_count)

                # Add tooltip for player count showing faction breakdown
                if server.alliance_count is not None or server.horde_count is not None:
                    tooltip_parts = []
                    if server.alliance_count is not None:
                        tooltip_parts.append(f"Alliance: {server.alliance_count}")
                    if server.horde_count is not None:
                        tooltip_parts.append(f"Horde: {server.horde_count}")
                    if tooltip_parts:
                        item.setToolTip(col_idx, " | ".join(tooltip_parts))

            # Set numeric sort data for status column (by ping)
            if col.id == "status":
                # Check if this server has multiple worlds
                worlds = server.get_field('worlds', [])
                if isinstance(worlds, list) and len(worlds) > 0:
                    # Count online vs total worlds
                    total_worlds = len(worlds)
                    online_worlds = sum(1 for w in worlds if w.get('_ping_status') == ServerStatus.ONLINE)
                    item.setText(col_idx, f"{online_worlds}/{total_worlds}")
                    # Use average ping for sorting (or 0 if none online)
                    if online_worlds > 0:
                        avg_ping = sum(w.get('_ping_ms', 0) for w in worlds if w.get('_ping_status') == ServerStatus.ONLINE) // online_worlds
                        item.setData(col_idx, Qt.ItemDataRole.UserRole + 1, avg_ping)
                    else:
                        item.setData(col_idx, Qt.ItemDataRole.UserRole + 1, 999999)
                else:
                    item.setData(col_idx, Qt.ItemDataRole.UserRole + 1, server.ping_ms if server.ping_ms != -1 else 999999)

            # Special formatting for certain columns
            if col.id in ["players", "uptime", "status"]:
                item.setTextAlignment(col_idx, Qt.AlignmentFlag.AlignCenter)

            # Set status color (only if pinged)
            if col.id == "status" and server.ping_ms != -1:
                # Don't set color for multi-world servers (they show X/Y format)
                worlds = server.get_field('worlds', [])
                if not (isinstance(worlds, list) and len(worlds) > 0):
                    self._set_status_color_inline_tree(item, col_idx, server.status, server.ping_ms)

    def _populate_world_item(self, item: QTreeWidgetItem, world: dict, server: ServerDefinition) -> None:
        """Populate a tree item with world data.

        Args:
            item: Tree item to populate
            world: World dictionary with 'name', 'location', 'host'
            server: Parent server definition
        """
        for col_idx, col in enumerate(self._columns):
            if col.id == "name":
                # Show world name and location
                world_name = world.get('name', 'Unknown')
                location = world.get('location', '')
                display_text = f"  {world_name}"
                if location:
                    display_text += f" - {location}"
                item.setText(col_idx, display_text)
                # Store server ID so context menu works
                item.setData(0, Qt.ItemDataRole.UserRole, server.id)
            elif col.id == "status":
                # Show world ping status
                ping_ms = world.get('_ping_ms', -1)
                status = world.get('_ping_status', ServerStatus.OFFLINE)

                if ping_ms == -1:
                    # Not pinged yet
                    item.setText(col_idx, "-")
                elif status == ServerStatus.ONLINE and ping_ms >= 0:
                    item.setText(col_idx, f"🟢 {ping_ms}ms")
                    # Set numeric sort data
                    item.setData(col_idx, Qt.ItemDataRole.UserRole + 1, ping_ms)
                    # Set status color
                    self._set_status_color_inline_tree(item, col_idx, status, ping_ms)
                elif status == ServerStatus.OFFLINE:
                    item.setText(col_idx, "🔴 Offline")
                    item.setData(col_idx, Qt.ItemDataRole.UserRole + 1, 9999)
                    self._set_status_color_inline_tree(item, col_idx, status, ping_ms)

                item.setTextAlignment(col_idx, Qt.AlignmentFlag.AlignCenter)
            elif col.id == "address":
                # Show world host
                host = world.get('host', '')
                item.setText(col_idx, host)
            else:
                # Leave other columns empty for world items
                item.setText(col_idx, "")

    def _create_links_widget(self, server: ServerDefinition) -> QWidget:
        """Create a widget with clickable link icons for a server.

        Args:
            server: Server definition

        Returns:
            Widget containing link icons
        """
        return ServerLinksWidget(server)

    def _get_column_value(self, server: ServerDefinition, column_id: str) -> Any:
        """Get the value for a specific column.

        Args:
            server: Server definition
            column_id: Column identifier

        Returns:
            Column value
        """
        return ServerDataFormatter.get_column_value(server, column_id)

    def _format_status(self, status: ServerStatus, ping_ms: int) -> str:
        """Format status for display with ping.

        Args:
            status: Server status
            ping_ms: Ping in milliseconds (-1 if not pinged)

        Returns:
            Formatted status string with ping
        """
        return ServerDataFormatter.format_status(status, ping_ms)

    def _set_status_color_inline_tree(self, item: QTreeWidgetItem, column: int, status: ServerStatus, ping_ms: int) -> None:
        """Set status color for tree widget item.

        Args:
            item: Tree item
            column: Column index
            status: Server status
            ping_ms: Ping in milliseconds (-1 if not pinged)
        """
        ServerDataFormatter.set_status_color(item, column, status, ping_ms)

    def _on_selection_changed(self) -> None:
        """Handle selection change."""
        items = self._table.selectedItems()
        if items:
            # Get the first column item (contains server ID)
            item = items[0]
            # For tree items, get data from column 0
            server_id = item.data(0, Qt.ItemDataRole.UserRole)
            if server_id:
                self.server_selected.emit(server_id)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle item double click.

        Args:
            item: Double-clicked item
            column: Column that was clicked
        """
        server_id = item.data(0, Qt.ItemDataRole.UserRole)
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

        server_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not server_id:
            return

        # Find the server to check for URLs
        server = None
        for s in self._servers:
            if s.id == server_id:
                server = s
                break

        if not server:
            return

        menu = QMenu(self._table)

        # Account management
        accounts_action = menu.addAction("⚙️ Manage Accounts")
        menu.addSeparator()

        # Register/Login actions (if URLs are configured)
        register_action = None
        login_action = None

        register_url = server.get_field("register_url", "")
        login_url = server.get_field("login_url", "")

        if register_url:
            register_action = menu.addAction("📝 Register Account")
        if login_url:
            login_action = menu.addAction("🔐 Account Login")

        if register_url or login_url:
            menu.addSeparator()

        # Edit/Delete
        edit_action = menu.addAction("✏️ Edit Server")
        delete_action = menu.addAction("🗑️ Delete Server")

        action = menu.exec(self._table.viewport().mapToGlobal(pos))

        if action == accounts_action:
            self.manage_accounts_requested.emit(server_id)
        elif action == register_action:
            self.register_requested.emit(server_id)
        elif action == login_action:
            self.login_requested.emit(server_id)
        elif action == edit_action:
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

            # Also ping individual worlds if they exist
            worlds = server.get_field('worlds', [])
            if isinstance(worlds, list) and len(worlds) > 0:
                # Collect world hosts to ping
                world_hosts = [world.get('host', '') for world in worlds if world.get('host')]

                if world_hosts:
                    # Ping all world hosts
                    world_ping_results = ping_multiple_hosts_sync(world_hosts, timeout=3.0)

                    # Store ping results in the world dicts
                    for world in worlds:
                        world_host = world.get('host', '')
                        if world_host and world_host in world_ping_results:
                            status, ping_ms = world_ping_results[world_host]
                            world['_ping_status'] = status
                            world['_ping_ms'] = ping_ms

        # Refresh table to show updated statuses
        self._refresh_table()

    def fetch_player_counts(self) -> None:
        """Fetch player counts for all servers."""
        if not self._servers:
            return

        # Filter servers that have scraping config (support both new and old key names)
        servers_with_config = [
            s for s in self._servers if s.data.get("scraping") or s.data.get("player_count")
        ]

        if not servers_with_config:
            return

        # Scrape server information
        scrape_results = scrape_servers_sync(servers_with_config, timeout=10.0)

        # Update server player counts
        for server in servers_with_config:
            if server.id in scrape_results:
                result = scrape_results[server.id]
                if result.success:
                    if result.total is not None:
                        server.players = result.total
                    if result.max_players is not None:
                        server.max_players = result.max_players
                    if result.uptime is not None:
                        server.uptime = result.uptime
                    # Store faction counts for tooltip
                    server.alliance_count = result.alliance
                    server.horde_count = result.horde

        # Refresh table to show updated counts
        self._refresh_table()

    def update_server_data(self, server_id: str, data: dict) -> None:
        """Update a single server's data from scan results.

        Args:
            server_id: Server ID to update
            data: Dictionary with scan data (total, alliance_count, horde_count, uptime)
        """
        # Find the server
        server = next((s for s in self._servers if s.id == server_id), None)
        if not server:
            return

        # Update server data
        if 'total' in data:
            server.players = data['total']
        if 'alliance_count' in data:
            server.alliance_count = data['alliance_count']
        if 'horde_count' in data:
            server.horde_count = data['horde_count']
        if 'uptime' in data:
            server.uptime = data['uptime']

        # Refresh table to show updated data
        self._refresh_table()
