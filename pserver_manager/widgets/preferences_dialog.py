"""Preferences dialog for PServer Manager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QDialog, QVBoxLayout

from qtframework.widgets import Button, ConfigEditorWidget, ConfigFieldDescriptor
from qtframework.widgets.buttons import ButtonVariant


if TYPE_CHECKING:
    from qtframework.config import ConfigManager


class PreferencesDialog(QDialog):
    """Preferences dialog using ConfigEditorWidget."""

    def __init__(self, config_manager: ConfigManager, theme_manager, parent=None) -> None:
        """Initialize preferences dialog.

        Args:
            config_manager: Application config manager
            theme_manager: Application theme manager
            parent: Parent widget
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self.theme_manager = theme_manager

        self.setWindowTitle("Preferences")
        self.setMinimumSize(700, 600)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Define configuration fields
        fields = [
            # UI Settings
            ConfigFieldDescriptor(
                key="ui.theme",
                label="Theme",
                field_type="choice",
                default="dark",
                choices_callback=self._get_available_themes,
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

    def _get_available_themes(self) -> list[str]:
        """Get list of available themes."""
        if self.theme_manager:
            return self.theme_manager.list_themes()
        return ["light", "dark"]

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

    def _on_ok_clicked(self) -> None:
        """Handle OK button click."""
        # Apply any pending changes
        self.editor_widget.apply_changes()
        self.accept()
