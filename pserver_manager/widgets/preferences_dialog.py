"""Preferences dialog for PServer Manager."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QGroupBox, QLabel, QVBoxLayout

from qtframework.widgets import Button, ConfigEditorWidget, ConfigFieldDescriptor, HBox
from qtframework.widgets.buttons import ButtonVariant


if TYPE_CHECKING:
    from qtframework.config import ConfigManager

    from pserver_manager.utils.paths import AppPaths


class PreferencesDialog(QDialog):
    """Preferences dialog using ConfigEditorWidget."""

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

        self.setWindowTitle("Preferences")
        self.setMinimumSize(800, 700)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Path Information Section
        path_group = self._create_path_section()
        layout.addWidget(path_group)

        # Define configuration fields
        fields = [
            # UI Settings
            ConfigFieldDescriptor(
                key="ui.theme",
                label="Theme",
                field_type="choice",
                default="dark",
                choices_callback=self._get_available_themes,
                choices_display_callback=self._get_theme_display_names,
                on_change=self._on_theme_changed,
                group="User Interface",
            ),
            ConfigFieldDescriptor(
                key="ui.auto_refresh_interval",
                label="Auto-Refresh Interval (seconds)",
                field_type="int",
                default=300,
                min_value=0,
                max_value=3600,
                group="User Interface",
            ),
            ConfigFieldDescriptor(
                key="ui.show_offline_servers",
                label="Show Offline Servers",
                field_type="bool",
                default=True,
                group="User Interface",
            ),
            # Network Settings
            ConfigFieldDescriptor(
                key="network.ping_timeout",
                label="Ping Timeout (seconds)",
                field_type="int",
                default=3,
                min_value=1,
                max_value=30,
                group="Network",
            ),
            ConfigFieldDescriptor(
                key="network.max_retries",
                label="Max Connection Retries",
                field_type="int",
                default=3,
                min_value=0,
                max_value=10,
                group="Network",
            ),
            ConfigFieldDescriptor(
                key="network.concurrent_pings",
                label="Concurrent Pings",
                field_type="int",
                default=10,
                min_value=1,
                max_value=50,
                group="Network",
            ),
            # Display Settings
            ConfigFieldDescriptor(
                key="display.compact_view",
                label="Compact View",
                field_type="bool",
                default=False,
                group="Display",
            ),
            ConfigFieldDescriptor(
                key="display.show_icons",
                label="Show Server Icons",
                field_type="bool",
                default=True,
                group="Display",
            ),
        ]

        # Create config editor widget (without file buttons and JSON view for preferences)
        self.editor_widget = ConfigEditorWidget(
            config_manager=self.config_manager,
            fields=fields,
            show_json_view=False,
            show_file_buttons=False,
        )

        layout.addWidget(self.editor_widget)

        # Custom buttons
        from PySide6.QtWidgets import QHBoxLayout

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = Button("Cancel", variant=ButtonVariant.SECONDARY)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = Button("OK", variant=ButtonVariant.PRIMARY)
        ok_btn.clicked.connect(self._on_ok_clicked)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

        # Connect config changed signal
        self.editor_widget.config_changed.connect(self._on_config_changed)

        # Connect to theme manager's signal to update dropdown when theme changes externally
        if self.theme_manager:
            self.theme_manager.theme_changed.connect(self._on_external_theme_change)

    def _create_path_section(self) -> QGroupBox:
        """Create path information and management section.

        Returns:
            QGroupBox with path controls
        """
        group = QGroupBox("Data Locations")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

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
        update_btn_layout.add_widget(check_updates_btn)
        layout.addWidget(update_btn_layout)

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
        # Refresh the dropdown to show the correct selection
        self.editor_widget.refresh_values()

    def _on_ok_clicked(self) -> None:
        """Handle OK button click."""
        # Apply any pending changes
        self.editor_widget.apply_changes()
        self.accept()
