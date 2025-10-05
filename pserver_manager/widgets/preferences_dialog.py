"""Preferences dialog for PServer Manager."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from qtframework.utils.search import SearchHighlighter, collect_searchable_text
from qtframework.widgets import Button, ConfigEditorWidget, ConfigFieldDescriptor, HBox
from qtframework.widgets.buttons import ButtonVariant


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
        parent=None,
    ) -> None:
        """Initialize preferences dialog.

        Args:
            config_manager: Application config manager
            theme_manager: Application theme manager
            app_paths: Application paths manager
            parent: Parent widget
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self.theme_manager = theme_manager
        self.app_paths = app_paths

        # Initialize search highlighter
        self.search_highlighter = SearchHighlighter()
        self.current_search = ""

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

        # Content area with stacked pages
        self.pages = QStackedWidget()
        self.pages.setObjectName("preferencesContent")
        content_layout.addWidget(self.pages, stretch=1)

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

        # Navigation list
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("preferencesNav")
        self.nav_list.setFrameShape(QListWidget.Shape.NoFrame)
        self.nav_list.setSpacing(4)

        # Add categories (reorganized)
        self.categories = [
            ("Application", "Application settings, paths, and updates"),
            ("Appearance", "Theme and visual display options"),
            ("Network", "Connection and ping settings"),
        ]

        for name, tooltip in self.categories:
            item = QListWidgetItem(name)
            item.setToolTip(tooltip)
            self.nav_list.addItem(item)

        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self._on_category_changed)

        layout.addWidget(self.nav_list)
        layout.addStretch()

        return sidebar

    def _create_pages(self) -> None:
        """Create all category pages."""
        # Application page
        application_page = self._create_application_page()
        self.pages.addWidget(application_page)

        # Appearance page
        appearance_page = self._create_appearance_page()
        self.pages.addWidget(appearance_page)

        # Network page
        network_page = self._create_network_page()
        self.pages.addWidget(network_page)

    def _create_page_container(self, title: str, description: str = None) -> tuple[QWidget, QVBoxLayout]:
        """Create a standard page container.

        Args:
            title: Page title
            description: Optional page description

        Returns:
            Tuple of (page widget, content layout)
        """
        page = QWidget()
        layout = QVBoxLayout(page)
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

        return page, layout

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

    def _on_category_changed(self, index: int) -> None:
        """Handle category selection change.

        Args:
            index: Selected category index
        """
        if index >= 0:
            self.pages.setCurrentIndex(index)
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

        # If empty, show all categories and clear highlights
        if not search_text:
            for i in range(self.nav_list.count()):
                item = self.nav_list.item(i)
                item.setHidden(False)
            self._highlight_current_page()
            return

        # Filter categories and track which ones are visible
        first_visible_index = -1
        current_index = self.nav_list.currentRow()
        current_is_visible = False

        for i in range(self.nav_list.count()):
            item = self.nav_list.item(i)
            category_name = item.text()

            # Check if category name matches
            category_matches = search_text in category_name.lower()

            # Check if any content in the page matches
            content_matches = self._search_page_content(i, search_text)

            # Show item if either category name or content matches
            matches = category_matches or content_matches
            item.setHidden(not matches)

            # Track first visible item
            if matches and first_visible_index == -1:
                first_visible_index = i

            # Check if current selection is still visible
            if i == current_index and matches:
                current_is_visible = True

        # If current selection is hidden, select the first visible category
        if not current_is_visible and first_visible_index >= 0:
            self.nav_list.setCurrentRow(first_visible_index)
        # If current selection is still visible, just update highlights
        elif current_is_visible:
            self._highlight_current_page()
        # If no matches, clear the selection and highlights
        elif first_visible_index == -1:
            self.nav_list.setCurrentRow(-1)
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

    def _on_ok_clicked(self) -> None:
        """Handle OK button click."""
        # Apply any pending changes from all editors
        if hasattr(self, "application_editor"):
            self.application_editor.apply_changes()
        if hasattr(self, "appearance_editor"):
            self.appearance_editor.apply_changes()
        if hasattr(self, "network_editor"):
            self.network_editor.apply_changes()
        self.accept()
