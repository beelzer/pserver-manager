"""Preferences dialog for PServer Manager."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QVBoxLayout,
    QWidget,
)

from qtframework.utils.search import SearchHighlighter, collect_searchable_text
from qtframework.widgets import Button, ConfigEditorWidget, ConfigFieldDescriptor, HBox
from qtframework.widgets.buttons import ButtonSize, ButtonVariant


if TYPE_CHECKING:
    from qtframework.config import ConfigManager

    from pserver_manager.utils.paths import AppPaths


class PreferencesDialog(QDialog):
    """Preferences dialog with sidebar navigation."""

    def __init__(
        self,
        config_manager: ConfigManager,
        theme_manager,
        app_paths: AppPaths,
        servers: list = None,
        game_defs: list = None,
        parent=None,
    ) -> None:
        """Initialize preferences dialog.

        Args:
            config_manager: Application config manager
            theme_manager: Application theme manager
            app_paths: Application paths manager
            servers: List of server definitions (for accounts page)
            game_defs: List of game definitions
            parent: Parent widget
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self.theme_manager = theme_manager
        self.app_paths = app_paths
        self.servers = servers or []
        self.game_defs = game_defs or []

        # Initialize search highlighter
        self.search_highlighter = SearchHighlighter()
        self.current_search = ""

        # Track page indices dynamically
        self._next_page_index = 0

        # Track server field changes for saving
        self._server_field_changes: dict[str, dict[str, any]] = {}

        self.setWindowTitle("Preferences")
        self.setMinimumSize(900, 650)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the user interface with sidebar navigation."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create horizontal layout for sidebar and content
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Sidebar navigation
        self.sidebar = self._create_sidebar()
        content_layout.addWidget(self.sidebar)

        # Vertical separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        content_layout.addWidget(separator)

        # Content area with stacked pages - wrapped in a container for consistent sizing
        pages_container = QWidget()
        pages_container_layout = QVBoxLayout(pages_container)
        pages_container_layout.setContentsMargins(0, 0, 0, 0)
        pages_container_layout.setSpacing(0)

        self.pages = QStackedWidget()
        self.pages.setObjectName("preferencesContent")
        pages_container_layout.addWidget(self.pages)

        content_layout.addWidget(pages_container, stretch=1)

        # Create category pages
        self._create_pages()

        main_layout.addLayout(content_layout, stretch=1)

        # Bottom button bar
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(16, 12, 16, 12)
        button_layout.setSpacing(8)  # Add spacing between buttons
        button_layout.addStretch()

        cancel_btn = Button("Cancel", variant=ButtonVariant.SECONDARY)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumWidth(80)
        button_layout.addWidget(cancel_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        ok_btn = Button("OK", variant=ButtonVariant.PRIMARY)
        ok_btn.clicked.connect(self._on_ok_clicked)
        ok_btn.setMinimumWidth(80)
        button_layout.addWidget(ok_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        main_layout.addLayout(button_layout)

        # Connect to theme manager's signal
        if self.theme_manager:
            self.theme_manager.theme_changed.connect(self._on_external_theme_change)

    def _create_sidebar(self) -> QWidget:
        """Create sidebar navigation."""
        sidebar = QWidget()
        sidebar.setObjectName("preferencesSidebar")
        sidebar.setMinimumWidth(200)
        sidebar.setMaximumWidth(250)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Title
        title = QLabel("Categories")
        title.setProperty("heading", "h3")
        layout.addWidget(title)

        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search preferences...")
        self.search_box.textChanged.connect(self._filter_categories)

        # Add clear action inside the search box
        self.clear_action = QAction(self.search_box)
        self.clear_action.setText("×")  # Use × character as fallback
        self.clear_action.setToolTip("Clear search")
        self.clear_action.triggered.connect(self._clear_search)
        self.search_box.addAction(self.clear_action, QLineEdit.ActionPosition.TrailingPosition)
        self.clear_action.setVisible(False)

        layout.addWidget(self.search_box)

        # Navigation tree
        self.nav_tree = QTreeWidget()
        self.nav_tree.setObjectName("preferencesNav")
        self.nav_tree.setHeaderHidden(True)
        self.nav_tree.setFrameShape(QTreeWidget.Shape.NoFrame)
        self.nav_tree.itemClicked.connect(self._on_tree_item_clicked)

        # Populate tree with hierarchical structure
        self._populate_tree()

        layout.addWidget(self.nav_tree)
        layout.addStretch()

        return sidebar

    def _populate_tree(self) -> None:
        """Populate the navigation tree with categories."""
        # General category with subcategories
        general_item = QTreeWidgetItem(self.nav_tree, ["General"])
        general_item.setExpanded(True)

        # Store indices for each fixed page
        self._page_indices = {}

        application_item = QTreeWidgetItem(general_item, ["Application"])
        application_item.setToolTip(0, "Application settings, paths, and updates")
        self._page_indices['application'] = self._next_page_index
        application_item.setData(0, Qt.ItemDataRole.UserRole, self._next_page_index)
        self._next_page_index += 1

        appearance_item = QTreeWidgetItem(general_item, ["Appearance"])
        appearance_item.setToolTip(0, "Theme and visual display options")
        self._page_indices['appearance'] = self._next_page_index
        appearance_item.setData(0, Qt.ItemDataRole.UserRole, self._next_page_index)
        self._next_page_index += 1

        network_item = QTreeWidgetItem(general_item, ["Network"])
        network_item.setToolTip(0, "Connection and ping settings")
        self._page_indices['network'] = self._next_page_index
        network_item.setData(0, Qt.ItemDataRole.UserRole, self._next_page_index)
        self._next_page_index += 1

        accounts_item = QTreeWidgetItem(general_item, ["Accounts"])
        accounts_item.setToolTip(0, "Manage server accounts and passwords")
        self._page_indices['accounts'] = self._next_page_index
        accounts_item.setData(0, Qt.ItemDataRole.UserRole, self._next_page_index)
        self._next_page_index += 1

        # Games category (for future expansion)
        games_item = QTreeWidgetItem(self.nav_tree, ["Games"])
        games_item.setExpanded(True)

        # WoW category with auto-generated server sub-pages
        self._add_wow_servers(games_item)

        # RuneScape category with auto-generated server sub-pages
        self._add_runescape_servers(games_item)

        # Select first item by default (Application)
        self.nav_tree.setCurrentItem(application_item)

    def _create_pages(self) -> None:
        """Create all category pages."""
        # Application page (index 0)
        application_page = self._create_application_page()
        self.pages.addWidget(application_page)

        # Appearance page (index 1)
        appearance_page = self._create_appearance_page()
        self.pages.addWidget(appearance_page)

        # Network page (index 2)
        network_page = self._create_network_page()
        self.pages.addWidget(network_page)

        # Accounts page (index 3)
        accounts_page = self._create_accounts_page()
        self.pages.addWidget(accounts_page)

        # WoW server pages (auto-generated from config)
        self._create_wow_server_pages()

        # RuneScape server pages (auto-generated from config)
        self._create_runescape_server_pages()

    def _create_page_container(self, title: str, description: str = None) -> tuple[QWidget, QVBoxLayout]:
        """Create a standard page container with scroll support.

        Args:
            title: Page title
            description: Optional page description

        Returns:
            Tuple of (page widget, content layout)
        """
        from PySide6.QtWidgets import QScrollArea

        # Create scroll area as the main page widget
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Create the actual content widget inside scroll area
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Page title
        title_label = QLabel(title)
        title_label.setProperty("heading", "h2")
        layout.addWidget(title_label)

        # Optional description
        if description:
            desc_label = QLabel(description)
            desc_label.setWordWrap(True)
            desc_label.setObjectName("pageDescription")
            layout.addWidget(desc_label)

        # Set the content widget as the scroll area's widget
        scroll_area.setWidget(content_widget)

        return scroll_area, layout

    def _create_application_page(self) -> QWidget:
        """Create the Application settings page."""
        page, layout = self._create_page_container(
            "Application",
            "Application settings, data locations, and server updates"
        )

        # Application settings
        fields = [
            ConfigFieldDescriptor(
                key="ui.auto_refresh_interval",
                label="Auto-Refresh Interval (seconds)",
                field_type="int",
                default=300,
                min_value=0,
                max_value=3600,
            ),
            ConfigFieldDescriptor(
                key="ui.show_offline_servers",
                label="Show Offline Servers",
                field_type="bool",
                default=True,
            ),
            ConfigFieldDescriptor(
                key="scanning.scan_on_startup",
                label="Scan Servers on Startup",
                field_type="bool",
                default=True,
            ),
            ConfigFieldDescriptor(
                key="scanning.parallel_scan_limit",
                label="Parallel Scan Limit",
                field_type="int",
                default=5,
                min_value=1,
                max_value=20,
            ),
        ]

        self.application_editor = ConfigEditorWidget(
            config_manager=self.config_manager,
            fields=fields,
            show_json_view=False,
            show_file_buttons=False,
        )
        self.application_editor.config_changed.connect(self._on_config_changed)

        layout.addWidget(self.application_editor)

        # Path Information Section
        path_group = self._create_path_section()
        layout.addWidget(path_group)
        layout.addSpacing(16)  # Add spacing after the group box to prevent clipping

        layout.addStretch()
        return page

    def _create_appearance_page(self) -> QWidget:
        """Create the Appearance settings page."""
        page, layout = self._create_page_container(
            "Appearance",
            "Customize the look and feel of the application"
        )

        # Appearance settings
        fields = [
            ConfigFieldDescriptor(
                key="ui.theme",
                label="Theme",
                field_type="choice",
                default="dark",
                choices_callback=self._get_available_themes,
                choices_display_callback=self._get_theme_display_names,
                on_change=self._on_theme_changed,
            ),
            ConfigFieldDescriptor(
                key="display.compact_view",
                label="Compact View",
                field_type="bool",
                default=False,
            ),
            ConfigFieldDescriptor(
                key="display.show_icons",
                label="Show Server Icons",
                field_type="bool",
                default=True,
            ),
        ]

        self.appearance_editor = ConfigEditorWidget(
            config_manager=self.config_manager,
            fields=fields,
            show_json_view=False,
            show_file_buttons=False,
        )
        self.appearance_editor.config_changed.connect(self._on_config_changed)

        layout.addWidget(self.appearance_editor)
        layout.addStretch()
        return page

    def _create_network_page(self) -> QWidget:
        """Create the Network settings page."""
        page, layout = self._create_page_container(
            "Network",
            "Configure connection and ping behavior"
        )

        fields = [
            ConfigFieldDescriptor(
                key="network.ping_timeout",
                label="Ping Timeout (seconds)",
                field_type="int",
                default=3,
                min_value=1,
                max_value=30,
            ),
            ConfigFieldDescriptor(
                key="network.max_retries",
                label="Max Connection Retries",
                field_type="int",
                default=3,
                min_value=0,
                max_value=10,
            ),
            ConfigFieldDescriptor(
                key="network.concurrent_pings",
                label="Concurrent Pings",
                field_type="int",
                default=10,
                min_value=1,
                max_value=50,
            ),
        ]

        self.network_editor = ConfigEditorWidget(
            config_manager=self.config_manager,
            fields=fields,
            show_json_view=False,
            show_file_buttons=False,
        )
        self.network_editor.config_changed.connect(self._on_config_changed)

        layout.addWidget(self.network_editor)
        layout.addStretch()
        return page

    def _create_accounts_page(self) -> QWidget:
        """Create the Accounts management page."""
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
        from pserver_manager.utils.account_manager import get_account_manager

        page, layout = self._create_page_container(
            "Accounts",
            "Manage saved accounts for all servers"
        )

        # Create table
        self.accounts_table = QTableWidget()
        self.accounts_table.setColumnCount(5)
        self.accounts_table.setHorizontalHeaderLabels(["Server", "Username", "Email", "Notes", "Primary"])
        self.accounts_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.accounts_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.accounts_table.setAlternatingRowColors(True)
        self.accounts_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Configure columns
        header = self.accounts_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Server
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Username
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Email
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # Notes
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Primary

        # Context menu
        self.accounts_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.accounts_table.customContextMenuRequested.connect(self._show_account_context_menu)

        # Double-click to edit
        self.accounts_table.itemDoubleClicked.connect(lambda: self._edit_selected_account())

        layout.addWidget(self.accounts_table)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        from qtframework.widgets import Button
        from qtframework.widgets.buttons import ButtonVariant

        add_btn = Button("Add Account", variant=ButtonVariant.PRIMARY)
        add_btn.clicked.connect(self._add_account_from_prefs)
        button_layout.addWidget(add_btn)

        edit_btn = Button("Edit", variant=ButtonVariant.SECONDARY)
        edit_btn.clicked.connect(self._edit_selected_account)
        button_layout.addWidget(edit_btn)
        self.edit_account_btn = edit_btn

        delete_btn = Button("Delete", variant=ButtonVariant.SECONDARY)
        delete_btn.clicked.connect(self._delete_selected_account)
        button_layout.addWidget(delete_btn)
        self.delete_account_btn = delete_btn

        layout.addLayout(button_layout)

        # Load accounts
        self._refresh_accounts_table()

        return page

    def _refresh_accounts_table(self) -> None:
        """Refresh the accounts table with all accounts."""
        from PySide6.QtWidgets import QTableWidgetItem
        from pserver_manager.utils.account_manager import get_account_manager

        self.accounts_table.setRowCount(0)
        account_manager = get_account_manager()

        # Get all servers and their accounts
        row = 0
        for server in self.servers:
            accounts = account_manager.get_accounts(server.id)
            for account in accounts:
                self.accounts_table.insertRow(row)

                # Server name
                server_item = QTableWidgetItem(server.name)
                server_item.setData(Qt.ItemDataRole.UserRole, (server.id, account.username))
                self.accounts_table.setItem(row, 0, server_item)

                # Username
                self.accounts_table.setItem(row, 1, QTableWidgetItem(account.username))

                # Email
                self.accounts_table.setItem(row, 2, QTableWidgetItem(account.email))

                # Notes
                self.accounts_table.setItem(row, 3, QTableWidgetItem(account.notes))

                # Primary
                primary_text = "⭐ Yes" if account.is_primary else ""
                self.accounts_table.setItem(row, 4, QTableWidgetItem(primary_text))

                row += 1

        # Enable/disable buttons based on selection
        has_selection = self.accounts_table.currentRow() >= 0
        self.edit_account_btn.setEnabled(has_selection)
        self.delete_account_btn.setEnabled(has_selection)

    def _show_account_context_menu(self, pos) -> None:
        """Show context menu for account.

        Args:
            pos: Menu position
        """
        from PySide6.QtWidgets import QMenu

        item = self.accounts_table.itemAt(pos)
        if not item:
            return

        menu = QMenu(self.accounts_table)
        edit_action = menu.addAction("✏️ Edit Account")
        delete_action = menu.addAction("🗑️ Delete Account")

        action = menu.exec(self.accounts_table.viewport().mapToGlobal(pos))
        if action == edit_action:
            self._edit_selected_account()
        elif action == delete_action:
            self._delete_selected_account()

    def _add_account_from_prefs(self) -> None:
        """Add a new account from preferences."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox
        from qtframework.widgets import Button
        from qtframework.widgets.buttons import ButtonVariant

        # Create dialog to select server
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Server")
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)

        label = QLabel("Select a server to add an account for:")
        layout.addWidget(label)

        server_combo = QComboBox()
        for server in self.servers:
            server_combo.addItem(server.name, server)
        layout.addWidget(server_combo)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = Button("Cancel", variant=ButtonVariant.SECONDARY)
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = Button("OK", variant=ButtonVariant.PRIMARY)
        ok_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            server = server_combo.currentData()
            if server:
                from pserver_manager.widgets.account_dialog import AccountDialog
                account_dialog = AccountDialog(server, self)
                account_dialog.exec()
                self._refresh_accounts_table()

    def _edit_selected_account(self) -> None:
        """Edit the selected account."""
        row = self.accounts_table.currentRow()
        if row < 0:
            return

        # Get server_id and username from first column
        item = self.accounts_table.item(row, 0)
        server_id, username = item.data(Qt.ItemDataRole.UserRole)

        # Find the server
        server = None
        for s in self.servers:
            if s.id == server_id:
                server = s
                break

        if server:
            from pserver_manager.widgets.account_dialog import AccountDialog
            dialog = AccountDialog(server, self)
            # TODO: Pre-select the account
            dialog.exec()
            self._refresh_accounts_table()

    def _delete_selected_account(self) -> None:
        """Delete the selected account."""
        from qtframework.widgets.advanced import ConfirmDialog
        from pserver_manager.utils.account_manager import get_account_manager

        row = self.accounts_table.currentRow()
        if row < 0:
            return

        # Get server_id and username
        item = self.accounts_table.item(row, 0)
        server_id, username = item.data(Qt.ItemDataRole.UserRole)
        server_name = item.text()

        if ConfirmDialog.confirm(
            "Delete Account",
            f"Are you sure you want to delete the account '{username}' for {server_name}?",
            self
        ):
            account_manager = get_account_manager()
            account_manager.remove_account(server_id, username)
            self._refresh_accounts_table()

    def _create_wow_page(self) -> QWidget:
        """Create the World of Warcraft settings page."""
        page, layout = self._create_page_container(
            "World of Warcraft",
            "Configure WoW client version locations"
        )

        # Version installations group
        versions_group = QGroupBox("Installed Versions")
        versions_layout = QVBoxLayout(versions_group)
        versions_layout.setSpacing(12)
        versions_layout.setContentsMargins(12, 12, 12, 12)

        # Store version widgets for easy access
        self.wow_version_widgets = {}

        # Common WoW versions to configure
        wow_versions = [
            ("vanilla", "Vanilla (1.12.1)", "games.wow.versions.vanilla.path"),
            ("tbc", "TBC (2.4.3)", "games.wow.versions.tbc.path"),
            ("wotlk", "WotLK (3.3.5a)", "games.wow.versions.wotlk.path"),
            ("cata", "Cataclysm (4.3.4)", "games.wow.versions.cata.path"),
        ]

        for version_id, version_label, config_key in wow_versions:
            version_widget = self._create_wow_version_row(
                version_id, version_label, config_key
            )
            self.wow_version_widgets[version_id] = version_widget
            versions_layout.addWidget(version_widget)

        # Scan button
        scan_layout = HBox(spacing=8)
        scan_layout.add_stretch()

        scan_btn = Button("Scan Parent Folder", variant=ButtonVariant.SECONDARY)
        scan_btn.setToolTip("Select a parent folder to scan for multiple WoW versions")
        scan_btn.clicked.connect(self._scan_wow_parent_folder)
        scan_layout.add_widget(scan_btn)

        versions_layout.addWidget(scan_layout)

        layout.addWidget(versions_group)
        layout.addStretch()
        return page

    def _create_wow_version_row(self, version_id: str, version_label: str, config_key: str) -> QWidget:
        """Create a row for configuring a WoW version installation.

        Args:
            version_id: Version identifier (e.g., 'vanilla')
            version_label: Display label (e.g., 'Vanilla (1.12.1)')
            config_key: Config key to store the path

        Returns:
            Widget containing the version configuration row
        """
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Label
        label = QLabel(f"<b>{version_label}</b>")
        layout.addWidget(label)

        # Path selection row
        path_row = HBox(spacing=8)

        # Path display
        path_field = QLineEdit()
        path_field.setPlaceholderText("Not configured")
        path_field.setReadOnly(True)
        current_path = self.config_manager.get(config_key, "")
        if current_path:
            path_field.setText(current_path)
            # Verify on load
            self._verify_wow_path(path_field, current_path, version_id)

        path_field.setObjectName(f"wow_path_{version_id}")
        path_row.add_widget(path_field, stretch=1)

        # Browse button
        browse_btn = Button(
            "Browse...",
            variant=ButtonVariant.SECONDARY,
            size=ButtonSize.COMPACT
        )
        browse_btn.setMinimumWidth(80)
        browse_btn.clicked.connect(
            lambda: self._browse_wow_folder(version_id, version_label, config_key, path_field)
        )
        path_row.add_widget(browse_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Clear button
        clear_btn = Button(
            "Clear",
            variant=ButtonVariant.SECONDARY,
            size=ButtonSize.COMPACT
        )
        clear_btn.setMinimumWidth(80)
        clear_btn.clicked.connect(
            lambda: self._clear_wow_path(config_key, path_field)
        )
        path_row.add_widget(clear_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(path_row)

        # Status label
        status_label = QLabel("")
        status_label.setObjectName(f"wow_status_{version_id}")
        status_label.setWordWrap(True)
        layout.addWidget(status_label)

        return container

    def _browse_wow_folder(self, version_id: str, version_label: str, config_key: str, path_field: QLineEdit) -> None:
        """Browse for WoW installation folder.

        Args:
            version_id: Version identifier
            version_label: Display label for the version
            config_key: Config key to store the path
            path_field: Line edit to update with the selected path
        """
        current_path = path_field.text()
        start_dir = current_path if current_path and os.path.exists(current_path) else str(Path.home())

        folder = QFileDialog.getExistingDirectory(
            self,
            f"Select {version_label} Installation Folder",
            start_dir,
            QFileDialog.Option.ShowDirsOnly
        )

        if folder:
            path_field.setText(folder)
            self.config_manager.set(config_key, folder)
            self._verify_wow_path(path_field, folder, version_id)

    def _clear_wow_path(self, config_key: str, path_field: QLineEdit) -> None:
        """Clear a WoW version path.

        Args:
            config_key: Config key to clear
            path_field: Line edit to clear
        """
        path_field.setText("")
        self.config_manager.set(config_key, "")

        # Clear status label
        version_id = config_key.split('.')[-2]  # Extract version_id from key
        status_label = self.findChild(QLabel, f"wow_status_{version_id}")
        if status_label:
            status_label.setText("")

    def _verify_wow_path(self, path_field: QLineEdit, folder_path: str, version_id: str) -> bool:
        """Verify a WoW installation folder.

        Args:
            path_field: Line edit showing the path
            folder_path: Path to verify
            version_id: Expected version identifier

        Returns:
            True if valid, False otherwise
        """
        status_label = self.findChild(QLabel, f"wow_status_{version_id}")
        if not status_label:
            return False

        path = Path(folder_path)

        if not path.exists():
            status_label.setText("❌ Path does not exist")
            status_label.setStyleSheet("color: #CC3333;")
            return False

        # Check for WoW.exe or Wow.exe
        wow_exe = path / "WoW.exe"
        wow_exe_lower = path / "Wow.exe"

        if not (wow_exe.exists() or wow_exe_lower.exists()):
            status_label.setText("❌ WoW.exe not found in this folder")
            status_label.setStyleSheet("color: #CC3333;")
            return False

        # Try to detect version
        detected_version = self._detect_wow_version(path)
        if detected_version:
            status_label.setText(f"✓ Detected: {detected_version}")
            status_label.setStyleSheet("color: #5FBF3F;")
            return True
        else:
            status_label.setText("✓ Valid WoW installation (version detection failed)")
            status_label.setStyleSheet("color: #8FBF3F;")
            return True

    def _detect_wow_version(self, wow_path: Path) -> str:
        """Detect WoW version from installation folder.

        Args:
            wow_path: Path to WoW installation

        Returns:
            Version string or empty string if detection failed
        """
        # Check for readme files that often contain version info
        readme_files = ["Readme.txt", "README.txt", "readme.txt"]

        for readme_name in readme_files:
            readme_path = wow_path / readme_name
            if readme_path.exists():
                try:
                    with open(readme_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(1024)  # Read first 1KB
                        # Look for version patterns
                        import re
                        version_match = re.search(r'(?:Version|v\.?)\s*(\d+\.\d+\.\d+)', content, re.IGNORECASE)
                        if version_match:
                            return version_match.group(1)
                except Exception:
                    pass

        # Check Data folder for patch files
        data_path = wow_path / "Data"
        if data_path.exists():
            # Common patch files by version
            version_indicators = {
                "patch-3.MPQ": "3.3.5a",
                "patch-2.MPQ": "2.4.3",
                "patch.MPQ": "1.12.1",
            }

            for patch_file, version in version_indicators.items():
                if (data_path / patch_file).exists():
                    return version

        return ""

    def _scan_wow_parent_folder(self) -> None:
        """Scan a parent folder for multiple WoW installations."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Parent Folder to Scan",
            str(Path.home()),
            QFileDialog.Option.ShowDirsOnly
        )

        if not folder:
            return

        parent_path = Path(folder)
        found_versions = {}

        # Scan subdirectories
        for subdir in parent_path.iterdir():
            if subdir.is_dir():
                # Check if it's a WoW installation
                if (subdir / "WoW.exe").exists() or (subdir / "Wow.exe").exists():
                    detected_version = self._detect_wow_version(subdir)
                    if detected_version:
                        found_versions[detected_version] = str(subdir)

        # Map detected versions to our version IDs
        version_mapping = {
            "1.12": "vanilla",
            "1.12.1": "vanilla",
            "2.4": "tbc",
            "2.4.3": "tbc",
            "3.3": "wotlk",
            "3.3.5": "wotlk",
            "3.3.5a": "wotlk",
            "4.3": "cata",
            "4.3.4": "cata",
        }

        # Auto-assign found versions
        for detected_ver, path in found_versions.items():
            for ver_prefix, version_id in version_mapping.items():
                if detected_ver.startswith(ver_prefix):
                    config_key = f"games.wow.versions.{version_id}.path"
                    path_field = self.findChild(QLineEdit, f"wow_path_{version_id}")
                    if path_field:
                        path_field.setText(path)
                        self.config_manager.set(config_key, path)
                        self._verify_wow_path(path_field, path, version_id)
                    break

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle tree item click.

        Args:
            item: Clicked tree item
            column: Column index
        """
        # Only handle child items (leaf nodes with page data)
        page_index = item.data(0, Qt.ItemDataRole.UserRole)
        if page_index is not None and page_index >= 0:
            self.pages.setCurrentIndex(page_index)
            # Apply search highlighting to the newly displayed page
            self._highlight_current_page()

    def _clear_search(self) -> None:
        """Clear the search box."""
        self.search_box.clear()

    def _filter_categories(self, text: str) -> None:
        """Filter categories based on search text.

        Args:
            text: Search text
        """
        search_text = text.lower()

        # Store current search for highlighting
        self.current_search = search_text

        # Show/hide clear action
        self.clear_action.setVisible(bool(text))

        # If empty, show all items and clear highlights
        if not search_text:
            iterator = QTreeWidgetItemIterator(self.nav_tree)
            while iterator.value():
                item = iterator.value()
                item.setHidden(False)
                iterator += 1
            self._highlight_current_page()
            return

        # Filter tree items and track visibility
        first_visible_item = None
        current_item = self.nav_tree.currentItem()
        current_is_visible = False

        # Track which parent categories should be visible
        visible_parents = set()

        # First pass: check all child items
        iterator = QTreeWidgetItemIterator(self.nav_tree)
        while iterator.value():
            item = iterator.value()
            item_text = item.text(0)
            parent = item.parent()

            # Check if this is a child item (has a parent)
            if parent:
                page_index = item.data(0, Qt.ItemDataRole.UserRole)

                # Check if item name matches
                item_matches = search_text in item_text.lower()

                # Check if page content matches
                content_matches = False
                if page_index is not None and page_index >= 0:
                    content_matches = self._search_page_content(page_index, search_text)

                matches = item_matches or content_matches
                item.setHidden(not matches)

                if matches:
                    visible_parents.add(parent)
                    if first_visible_item is None:
                        first_visible_item = item
                    if item == current_item:
                        current_is_visible = True
            else:
                # This is a parent category, will handle visibility in second pass
                pass

            iterator += 1

        # Second pass: show/hide parent categories based on whether they have visible children
        iterator = QTreeWidgetItemIterator(self.nav_tree)
        while iterator.value():
            item = iterator.value()
            if item.parent() is None:  # Parent category
                # Show parent if it has any visible children or matches search
                has_visible_children = item in visible_parents
                parent_matches = search_text in item.text(0).lower()
                item.setHidden(not (has_visible_children or parent_matches))
                # Expand parent if it has matches
                if has_visible_children:
                    item.setExpanded(True)
            iterator += 1

        # If current selection is hidden, select the first visible item
        if not current_is_visible and first_visible_item:
            self.nav_tree.setCurrentItem(first_visible_item)
        # If current selection is still visible, just update highlights
        elif current_is_visible:
            self._highlight_current_page()
        # If no matches, clear the selection and highlights
        elif first_visible_item is None:
            self.nav_tree.setCurrentItem(None)
            # Clear highlights since nothing is selected
            if self.pages.currentWidget():
                self.search_highlighter.clear(self.pages.currentWidget())

    def _search_page_content(self, page_index: int, search_text: str) -> bool:
        """Search for text within a page's content.

        Args:
            page_index: Index of the page to search
            search_text: Text to search for

        Returns:
            True if search text was found in the page
        """
        if page_index >= self.pages.count():
            return False

        page_widget = self.pages.widget(page_index)

        # Use framework utility to collect all searchable text
        searchable_content = collect_searchable_text(page_widget)

        # Also search through ConfigEditorWidget field labels and keys
        for editor in page_widget.findChildren(ConfigEditorWidget):
            for field in editor.fields:
                searchable_content += f" {field.label} {field.key}"
                if hasattr(field, 'description') and field.description:
                    searchable_content += f" {field.description}"

        return search_text in searchable_content.lower()

    def _highlight_current_page(self) -> None:
        """Highlight matching content on the current page."""
        current_widget = self.pages.currentWidget()
        if not current_widget:
            return

        # Always clear previous highlights first
        self.search_highlighter.clear(current_widget)

        # Apply new highlights if there's search text
        if self.current_search:
            self.search_highlighter.highlight(current_widget, self.current_search)

    def _create_path_section(self) -> QGroupBox:
        """Create path information and management section.

        Returns:
            QGroupBox with path controls
        """
        group = QGroupBox("Data Locations")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)  # Add proper margins to prevent clipping

        # Mode indicator
        mode_label = QLabel(
            f"<b>Mode:</b> {'Portable' if self.app_paths.is_portable_mode() else 'Standard'}"
        )
        layout.addWidget(mode_label)

        # User Data (Servers) path
        user_data_widget = HBox(spacing=8)
        user_data_label = QLabel(f"<b>Servers:</b> {self.app_paths.get_servers_dir()}")
        user_data_label.setWordWrap(True)
        user_data_widget.add_widget(user_data_label, stretch=1, alignment=Qt.AlignmentFlag.AlignVCenter)

        open_servers_btn = Button("Open Folder", variant=ButtonVariant.SECONDARY)
        open_servers_btn.clicked.connect(lambda: self._open_folder(self.app_paths.get_servers_dir()))
        user_data_widget.add_widget(open_servers_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(user_data_widget)

        # App Data (Settings) path
        app_data_widget = HBox(spacing=8)
        app_data_label = QLabel(f"<b>Settings:</b> {self.app_paths.get_app_data_dir()}")
        app_data_label.setWordWrap(True)
        app_data_widget.add_widget(app_data_label, stretch=1, alignment=Qt.AlignmentFlag.AlignVCenter)

        open_settings_btn = Button("Open Folder", variant=ButtonVariant.SECONDARY)
        open_settings_btn.clicked.connect(lambda: self._open_folder(self.app_paths.get_app_data_dir()))
        app_data_widget.add_widget(open_settings_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(app_data_widget)

        # Info text
        info_text = QLabel(
            "<i>Server configurations can be manually edited in the Servers folder. "
            "Changes will be loaded when you refresh the server list.</i>"
        )
        info_text.setWordWrap(True)
        layout.addWidget(info_text)

        # Check for Updates button
        update_btn_layout = HBox(spacing=8)
        update_btn_layout.add_stretch()
        check_updates_btn = Button("Check for Server Updates", variant=ButtonVariant.SECONDARY)
        check_updates_btn.clicked.connect(self._check_for_updates)
        update_btn_layout.add_widget(check_updates_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(update_btn_layout)
        layout.addSpacing(8)  # Add extra spacing at the bottom to prevent clipping

        return group

    def _open_folder(self, path) -> None:
        """Open folder in file explorer.

        Args:
            path: Path to open
        """
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)])
            else:
                subprocess.run(["xdg-open", str(path)])
        except Exception as e:
            print(f"Could not open folder: {e}")

    def _check_for_updates(self) -> None:
        """Check for server configuration updates."""
        # Call the main window's update checker
        if self.parent():
            self.parent().check_for_updates_manual()

    def _get_available_themes(self) -> list[str]:
        """Get list of available themes."""
        if self.theme_manager:
            return self.theme_manager.list_themes()
        return ["light", "dark"]

    def _get_theme_display_names(self) -> dict[str, str]:
        """Get mapping of theme IDs to display names."""
        if not self.theme_manager:
            return {"light": "Light", "dark": "Dark"}

        display_map = {}
        for theme_name in self.theme_manager.list_themes():
            theme_info = self.theme_manager.get_theme_info(theme_name)
            if theme_info:
                display_name = theme_info.get("display_name", theme_name.replace("_", " ").title())
            else:
                display_name = theme_name.replace("_", " ").title()
            display_map[theme_name] = display_name

        return display_map

    def _on_theme_changed(self, new_theme: str) -> None:
        """Handle theme change.

        Args:
            new_theme: New theme name
        """
        if self.theme_manager:
            try:
                self.theme_manager.set_theme(new_theme)
            except Exception as e:
                print(f"Error applying theme: {e}")

    def _on_config_changed(self) -> None:
        """Handle configuration changes."""
        # Config changes are automatically saved by ConfigEditorWidget
        pass

    def _on_external_theme_change(self, new_theme: str) -> None:
        """Handle theme changes from external sources (e.g., menu).

        Args:
            new_theme: New theme name
        """
        # Update the config to reflect the new theme
        self.config_manager.set("ui.theme", new_theme)
        # Refresh the appearance editor dropdown to show the correct selection
        if hasattr(self, "appearance_editor"):
            self.appearance_editor.refresh_values()

    def _add_wow_servers(self, games_item: QTreeWidgetItem) -> None:
        """Add WoW servers to sidebar dynamically from config.

        Args:
            games_item: Games tree item to add WoW under
        """
        from pserver_manager.config_loader import ConfigLoader

        # Load servers from config
        config_dir = Path(__file__).parent.parent / "config"
        config_loader = ConfigLoader(
            config_dir=config_dir,
            servers_dir=self.app_paths.get_servers_dir(),
        )
        all_servers = config_loader.load_servers()

        # Filter WoW servers
        wow_servers = [s for s in all_servers if s.game_id == "wow"]

        if not wow_servers:
            return

        # Create WoW parent item
        wow_item = QTreeWidgetItem(games_item, ["World of Warcraft"])
        wow_item.setToolTip(0, "WoW server settings")
        wow_item.setExpanded(True)

        # Store server info for page creation
        self.wow_servers = []

        # Add each server as a sub-item using dynamic page indexing
        for server in sorted(wow_servers, key=lambda s: s.name):
            server_item = QTreeWidgetItem(wow_item, [server.name])
            server_item.setToolTip(0, f"{server.name} client and settings")
            server_item.setData(0, Qt.ItemDataRole.UserRole, self._next_page_index)

            self.wow_servers.append((server, self._next_page_index))
            self._next_page_index += 1

    def _add_runescape_servers(self, games_item: QTreeWidgetItem) -> None:
        """Add RuneScape servers to sidebar dynamically from config.

        Args:
            games_item: Games tree item to add RuneScape under
        """
        from pserver_manager.config_loader import ConfigLoader

        # Load servers from config
        config_dir = Path(__file__).parent.parent / "config"
        config_loader = ConfigLoader(
            config_dir=config_dir,
            servers_dir=self.app_paths.get_servers_dir(),
        )
        all_servers = config_loader.load_servers()

        # Filter RuneScape servers
        runescape_servers = [s for s in all_servers if s.game_id == "runescape"]

        if not runescape_servers:
            return

        # Create RuneScape parent item
        runescape_item = QTreeWidgetItem(games_item, ["RuneScape"])
        runescape_item.setToolTip(0, "RuneScape server settings")
        runescape_item.setExpanded(True)

        # Store server info for page creation
        self.runescape_servers = []

        # Add each server as a sub-item using dynamic page indexing
        for server in sorted(runescape_servers, key=lambda s: s.name):
            server_item = QTreeWidgetItem(runescape_item, [server.name])
            server_item.setToolTip(0, f"{server.name} client and downloads")
            server_item.setData(0, Qt.ItemDataRole.UserRole, self._next_page_index)

            self.runescape_servers.append((server, self._next_page_index))
            self._next_page_index += 1

    def _create_wow_server_pages(self) -> None:
        """Create pages for each WoW server."""
        if not hasattr(self, "wow_servers"):
            return

        for server, page_index in self.wow_servers:
            page = self._create_wow_server_page(server)
            self.pages.addWidget(page)

    def _create_wow_server_page(self, server) -> QWidget:
        """Create a configuration page for a WoW server.

        Args:
            server: ServerDefinition for the server

        Returns:
            Configured page widget
        """
        page, content_layout = self._create_page_container(
            server.name,
            f"Configure {server.name} client and realmlist"
        )

        # Server Information section
        info_group = QGroupBox("Server Information")
        info_layout = QVBoxLayout()

        def add_info_field(label_text: str, value: str, layout=info_layout):
            """Helper to add a read-only info field."""
            if value:
                row = QHBoxLayout()
                label = QLabel(f"{label_text}:")
                label.setMinimumWidth(120)
                row.addWidget(label)

                field = QLineEdit()
                field.setText(value)
                field.setReadOnly(True)
                row.addWidget(field, stretch=1)
                layout.addLayout(row)

        add_info_field("Version", getattr(server, 'version_id', '').replace('_', ' ').title())
        add_info_field("Realm Type", server.get_field('realm_type', ''))
        add_info_field("Rates", server.get_field('rates', ''))
        add_info_field("Population", server.get_field('population', ''))
        add_info_field("Language", server.get_field('language', ''))

        # Description (editable)
        desc_row = QHBoxLayout()
        desc_label = QLabel("Description:")
        desc_label.setMinimumWidth(120)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        desc_row.addWidget(desc_label)

        from PySide6.QtWidgets import QTextEdit
        desc_field = QTextEdit()
        desc_field.setPlainText(server.get_field('description', ''))
        desc_field.setMaximumHeight(80)
        # Track changes when text is modified
        desc_field.textChanged.connect(
            lambda: self._track_server_field_change(server.id, 'description', desc_field.toPlainText())
        )
        desc_row.addWidget(desc_field, stretch=1)
        info_layout.addLayout(desc_row)

        info_group.setLayout(info_layout)
        content_layout.addWidget(info_group)

        # Links section
        links_group = QGroupBox("Server Links")
        links_layout = QVBoxLayout()

        add_info_field("Website", getattr(server, 'website', ''), links_layout)

        if hasattr(server, 'discord') and server.discord:
            add_info_field("Discord", f"https://discord.gg/{server.discord}", links_layout)

        add_info_field("Register URL", getattr(server, 'register_url', ''), links_layout)
        add_info_field("Login URL", getattr(server, 'login_url', ''), links_layout)

        links_group.setLayout(links_layout)
        content_layout.addWidget(links_group)

        # Realmlist section
        realmlist_group = QGroupBox("Realmlist Configuration")
        realmlist_layout = QVBoxLayout()

        add_info_field("Host", server.host, realmlist_layout)

        if hasattr(server, 'realm_name') and server.realm_name:
            add_info_field("Realm Name", server.realm_name, realmlist_layout)

        realmlist_group.setLayout(realmlist_layout)
        content_layout.addWidget(realmlist_group)

        # Client location section
        client_group = QGroupBox("Client Location")
        client_layout = QVBoxLayout()

        config_key = f"games.wow.servers.{server.id.split('.')[1]}.path"
        current_path = self.config_manager.get(config_key, "")

        location_row = QHBoxLayout()

        path_field = QLineEdit()
        path_field.setText(current_path)
        path_field.setPlaceholderText(f"Path to {server.name} WoW client installation")
        path_field.textChanged.connect(
            lambda text: self.config_manager.set(config_key, text)
        )
        location_row.addWidget(path_field, stretch=1)

        # Get the exact height of the text field (account for border)
        field_height = path_field.sizeHint().height() - 2

        browse_btn = Button("Browse...", size=ButtonSize.COMPACT)
        browse_btn.setFixedHeight(field_height)
        # Override button padding to match input field exactly
        browse_btn.setStyleSheet(f"QPushButton {{ padding: 0px 8px; max-height: {field_height}px; min-height: {field_height}px; }}")
        browse_btn.clicked.connect(
            lambda: self._browse_wow_server_folder(server.name, config_key, path_field)
        )
        location_row.addWidget(browse_btn)

        clear_btn = Button("Clear", size=ButtonSize.COMPACT)
        clear_btn.setFixedHeight(field_height)
        # Override button padding to match input field exactly
        clear_btn.setStyleSheet(f"QPushButton {{ padding: 0px 8px; max-height: {field_height}px; min-height: {field_height}px; }}")
        clear_btn.clicked.connect(
            lambda: self._clear_path(config_key, path_field)
        )
        location_row.addWidget(clear_btn)

        client_layout.addLayout(location_row)
        client_group.setLayout(client_layout)
        content_layout.addWidget(client_group)

        content_layout.addStretch()
        return page

    def _browse_wow_server_folder(self, server_name: str, config_key: str, path_field: QLineEdit) -> None:
        """Browse for WoW server client installation folder.

        Args:
            server_name: Server display name
            config_key: Config key to update
            path_field: Path field widget to update
        """
        current_path = path_field.text() or os.path.expanduser("~")

        folder = QFileDialog.getExistingDirectory(
            self,
            f"Select {server_name} WoW Client Folder",
            current_path,
        )

        if folder:
            path_field.setText(folder)
            self.config_manager.set(config_key, folder)

    def _create_runescape_server_pages(self) -> None:
        """Create pages for each RuneScape server."""
        if not hasattr(self, "runescape_servers"):
            return

        for server, page_index in self.runescape_servers:
            page = self._create_runescape_server_page(server)
            self.pages.addWidget(page)

    def _create_runescape_server_page(self, server) -> QWidget:
        """Create a configuration page for a RuneScape server.

        Args:
            server: ServerDefinition for the server

        Returns:
            Configured page widget
        """
        from PySide6.QtWidgets import QComboBox

        page, content_layout = self._create_page_container(
            server.name,
            f"Configure {server.name} client and downloads"
        )

        def add_info_field(label_text: str, value: str, layout):
            """Helper to add a read-only info field."""
            if value:
                row = QHBoxLayout()
                label = QLabel(f"{label_text}:")
                label.setMinimumWidth(120)
                row.addWidget(label)

                field = QLineEdit()
                field.setText(value)
                field.setReadOnly(True)
                row.addWidget(field, stretch=1)
                layout.addLayout(row)

        # Server Information section
        info_group = QGroupBox("Server Information")
        info_layout = QVBoxLayout()

        # Version dropdown (editable)
        version_row = QHBoxLayout()
        version_label = QLabel("Version:")
        version_label.setMinimumWidth(120)
        version_row.addWidget(version_label)

        version_combo = QComboBox()
        # Find RuneScape game definition to get available versions
        runescape_game = next((g for g in self.game_defs if g.id == 'runescape'), None)
        if runescape_game and hasattr(runescape_game, 'versions'):
            for version in runescape_game.versions:
                version_combo.addItem(version.name, version.id)

            # Set current version
            current_index = version_combo.findData(server.version_id)
            if current_index >= 0:
                version_combo.setCurrentIndex(current_index)

        # Track version changes
        version_combo.currentIndexChanged.connect(
            lambda: self._track_server_field_change(server.id, 'version_id', version_combo.currentData())
        )
        version_row.addWidget(version_combo, stretch=1)
        info_layout.addLayout(version_row)

        add_info_field("Server Type", server.get_field('server_type', ''), info_layout)
        add_info_field("Rates", server.get_field('rates', ''), info_layout)
        add_info_field("Population", server.get_field('population', ''), info_layout)
        add_info_field("Language", server.get_field('language', ''), info_layout)

        # Description (editable)
        desc_row = QHBoxLayout()
        desc_label = QLabel("Description:")
        desc_label.setMinimumWidth(120)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        desc_row.addWidget(desc_label)

        from PySide6.QtWidgets import QTextEdit
        desc_field = QTextEdit()
        desc_field.setPlainText(server.get_field('description', ''))
        desc_field.setMaximumHeight(80)
        # Track changes when text is modified
        desc_field.textChanged.connect(
            lambda: self._track_server_field_change(server.id, 'description', desc_field.toPlainText())
        )
        desc_row.addWidget(desc_field, stretch=1)
        info_layout.addLayout(desc_row)

        info_group.setLayout(info_layout)
        content_layout.addWidget(info_group)

        # Links section
        links_group = QGroupBox("Server Links")
        links_layout = QVBoxLayout()

        website = server.get_field('website', '')
        discord = server.get_field('discord', '')
        register_url = server.get_field('register_url', '')
        login_url = server.get_field('login_url', '')

        add_info_field("Website", website, links_layout)

        if discord:
            add_info_field("Discord", f"https://discord.gg/{discord}", links_layout)

        add_info_field("Register URL", register_url, links_layout)
        add_info_field("Login URL", login_url, links_layout)

        # Only show links section if there's at least one link
        if website or discord or register_url or login_url:
            links_group.setLayout(links_layout)
            content_layout.addWidget(links_group)

        # Downloads section
        if server.data.get("downloads"):
            downloads_group = QGroupBox("Client Downloads")
            downloads_layout = QVBoxLayout()

            for download in server.data["downloads"]:
                download_row = QHBoxLayout()

                label = QLabel(download["name"])
                label.setMinimumWidth(200)
                download_row.addWidget(label)

                download_btn = Button(
                    "Download",
                    size=ButtonSize.COMPACT,
                    variant=ButtonVariant.PRIMARY
                )
                # Match the compact style of browse/clear buttons
                download_btn.setStyleSheet("QPushButton { padding: 0px 8px; }")
                download_btn.clicked.connect(
                    lambda url=download["url"]: self._open_download_link(url)
                )
                download_row.addWidget(download_btn)
                download_row.addStretch()

                downloads_layout.addLayout(download_row)

            downloads_group.setLayout(downloads_layout)
            content_layout.addWidget(downloads_group)

        # Client location section
        client_group = QGroupBox("Client Location")
        client_layout = QVBoxLayout()

        config_key = f"games.runescape.servers.{server.id.split('.')[1]}.path"
        current_path = self.config_manager.get(config_key, "")

        location_row = QHBoxLayout()

        path_field = QLineEdit()
        path_field.setText(current_path)
        path_field.setPlaceholderText(f"Path to {server.name} client installation")
        path_field.textChanged.connect(
            lambda text: self.config_manager.set(config_key, text)
        )
        location_row.addWidget(path_field, stretch=1)

        # Get the exact height of the text field (account for border)
        field_height = path_field.sizeHint().height() - 2

        browse_btn = Button("Browse...", size=ButtonSize.COMPACT)
        browse_btn.setFixedHeight(field_height)
        # Override button padding to match input field exactly
        browse_btn.setStyleSheet(f"QPushButton {{ padding: 0px 8px; max-height: {field_height}px; min-height: {field_height}px; }}")
        browse_btn.clicked.connect(
            lambda: self._browse_runescape_folder(server.name, config_key, path_field)
        )
        location_row.addWidget(browse_btn)

        clear_btn = Button("Clear", size=ButtonSize.COMPACT)
        clear_btn.setFixedHeight(field_height)
        # Override button padding to match input field exactly
        clear_btn.setStyleSheet(f"QPushButton {{ padding: 0px 8px; max-height: {field_height}px; min-height: {field_height}px; }}")
        clear_btn.clicked.connect(
            lambda: self._clear_path(config_key, path_field)
        )
        location_row.addWidget(clear_btn)

        client_layout.addLayout(location_row)
        client_group.setLayout(client_layout)
        content_layout.addWidget(client_group)

        content_layout.addStretch()
        return page

    def _open_download_link(self, url: str) -> None:
        """Open a download link in the default browser.

        Args:
            url: Download URL to open
        """
        import webbrowser
        webbrowser.open(url)

    def _browse_runescape_folder(self, server_name: str, config_key: str, path_field: QLineEdit) -> None:
        """Browse for RuneScape client installation folder.

        Args:
            server_name: Server display name
            config_key: Config key to update
            path_field: Path field widget to update
        """
        current_path = path_field.text() or os.path.expanduser("~")

        folder = QFileDialog.getExistingDirectory(
            self,
            f"Select {server_name} Client Folder",
            current_path,
        )

        if folder:
            path_field.setText(folder)
            self.config_manager.set(config_key, folder)

    def _clear_path(self, config_key: str, path_field: QLineEdit) -> None:
        """Clear a path configuration.

        Args:
            config_key: Config key to clear
            path_field: Path field widget to clear
        """
        path_field.clear()
        self.config_manager.set(config_key, "")

    def _on_ok_clicked(self) -> None:
        """Handle OK button click."""
        # Apply any pending changes from all editors
        if hasattr(self, "application_editor"):
            self.application_editor.apply_changes()
        if hasattr(self, "appearance_editor"):
            self.appearance_editor.apply_changes()
        if hasattr(self, "network_editor"):
            self.network_editor.apply_changes()

        # Save server field changes
        self._save_server_changes()

        self.accept()

    def _track_server_field_change(self, server_id: str, field_name: str, new_value: any) -> None:
        """Track a server field change for later saving.

        Args:
            server_id: Server ID
            field_name: Field name to change
            new_value: New value for the field
        """
        if server_id not in self._server_field_changes:
            self._server_field_changes[server_id] = {}
        self._server_field_changes[server_id][field_name] = new_value

    def _save_server_changes(self) -> None:
        """Save all tracked server field changes to YAML files."""
        import yaml

        for server_id, changes in self._server_field_changes.items():
            # Find the server to get its game_id
            server = next((s for s in self.servers if s.id == server_id), None)
            if not server:
                continue

            # Construct path to server YAML file
            server_file = self.app_paths.get_servers_dir() / server.game_id / f"{server_id}.yaml"

            if not server_file.exists():
                continue

            try:
                # Load current YAML
                with open(server_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}

                # Apply changes
                for field_name, new_value in changes.items():
                    data[field_name] = new_value

                # Save back to file
                with open(server_file, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

            except Exception as e:
                print(f"Error saving changes to {server_file}: {e}")
