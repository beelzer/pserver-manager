"""Update dialog for server configs and app updates."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from qtframework.widgets import Button, HBox
from qtframework.widgets.buttons import ButtonVariant


if TYPE_CHECKING:
    from pserver_manager.utils.updates import ServerUpdateChecker, UpdateInfo


class UpdateDialog(QDialog):
    """Dialog for reviewing and applying server and theme updates."""

    def __init__(
        self,
        update_info: UpdateInfo,
        update_checker: ServerUpdateChecker,
        parent=None,
    ) -> None:
        """Initialize update dialog.

        Args:
            update_info: Information about available updates
            update_checker: Update checker instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.update_info = update_info
        self.update_checker = update_checker
        self.selected_imports = []
        self.selected_updates = []
        self.conflict_resolutions = {}  # server_id -> "keep" or "update"

        self.setWindowTitle("Updates Available")
        self.setMinimumSize(700, 600)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        from PySide6.QtWidgets import QScrollArea, QWidget

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Content widget inside scroll area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)

        # Summary
        summary = self._create_summary()
        content_layout.addWidget(summary)

        # New Servers Section
        if self.update_info.new_servers:
            new_group = self._create_new_servers_section()
            content_layout.addWidget(new_group)

        # Updated Servers Section
        if self.update_info.updated_servers:
            updated_group = self._create_updated_servers_section()
            content_layout.addWidget(updated_group)

        # Removed Servers Section
        if self.update_info.removed_servers:
            removed_group = self._create_removed_servers_section()
            content_layout.addWidget(removed_group)

        # Conflicts Section
        if self.update_info.conflicts:
            conflicts_group = self._create_conflicts_section()
            content_layout.addWidget(conflicts_group)

        # New Themes Section
        if self.update_info.new_themes:
            new_themes_group = self._create_new_themes_section()
            content_layout.addWidget(new_themes_group)

        # Updated Themes Section
        if self.update_info.updated_themes:
            updated_themes_group = self._create_updated_themes_section()
            content_layout.addWidget(updated_themes_group)

        content_layout.addStretch()

        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area, stretch=1)

        # Buttons - fixed at bottom outside scroll area
        button_layout = HBox()
        button_layout.set_margins(16, 12, 16, 12)
        button_layout.add_stretch()

        cancel_btn = Button("Cancel", variant=ButtonVariant.SECONDARY)
        cancel_btn.clicked.connect(self.reject)
        button_layout.add_widget(cancel_btn)

        apply_btn = Button("Apply Updates", variant=ButtonVariant.PRIMARY)
        apply_btn.clicked.connect(self._apply_updates)
        button_layout.add_widget(apply_btn)

        layout.addWidget(button_layout)

    def _create_summary(self) -> QLabel:
        """Create summary label.

        Returns:
            Summary label widget
        """
        parts = []
        if self.update_info.new_servers:
            parts.append(f"<b>{len(self.update_info.new_servers)}</b> new server(s)")
        if self.update_info.updated_servers:
            parts.append(f"<b>{len(self.update_info.updated_servers)}</b> server update(s)")
        if self.update_info.removed_servers:
            parts.append(f"<b>{len(self.update_info.removed_servers)}</b> removed server(s)")
        if self.update_info.conflicts:
            parts.append(f"<b>{len(self.update_info.conflicts)}</b> server conflict(s)")
        if self.update_info.new_themes:
            parts.append(f"<b>{len(self.update_info.new_themes)}</b> new theme(s)")
        if self.update_info.updated_themes:
            parts.append(f"<b>{len(self.update_info.updated_themes)}</b> theme update(s)")

        summary_text = "Updates available: " + ", ".join(parts) if parts else "No updates available"

        label = QLabel(summary_text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def _create_new_servers_section(self) -> QGroupBox:
        """Create new servers section.

        Returns:
            GroupBox with new servers
        """
        group = QGroupBox(f"New Servers ({len(self.update_info.new_servers)})")
        layout = QVBoxLayout(group)

        info = QLabel(
            "<i>These servers are included with this version but not in your collection. "
            "Select which ones to import:</i>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.new_servers_list = QListWidget()

        for server_id in self.update_info.new_servers:
            item = QListWidgetItem(server_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)  # Default: import all
            self.new_servers_list.addItem(item)

        layout.addWidget(self.new_servers_list)

        return group

    def _create_updated_servers_section(self) -> QGroupBox:
        """Create updated servers section.

        Returns:
            GroupBox with updated servers
        """
        group = QGroupBox(f"Updated Servers ({len(self.update_info.updated_servers)})")
        layout = QVBoxLayout(group)

        info = QLabel(
            "<i>These bundled servers have been updated and you haven't modified them. "
            "Select which ones to update:</i>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.updated_servers_list = QListWidget()

        for server_id in self.update_info.updated_servers:
            item = QListWidgetItem(server_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)  # Default: update all
            self.updated_servers_list.addItem(item)

        layout.addWidget(self.updated_servers_list)

        return group

    def _create_removed_servers_section(self) -> QGroupBox:
        """Create removed servers section.

        Returns:
            GroupBox with removed servers
        """
        group = QGroupBox(f"Removed Servers ({len(self.update_info.removed_servers)})")
        layout = QVBoxLayout(group)

        info = QLabel(
            "<b>Warning:</b> These servers were previously bundled but have been removed from the official configuration. "
            "They will no longer receive updates. Select which ones to remove from your collection:"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.removed_servers_list = QListWidget()

        for server_id in self.update_info.removed_servers:
            item = QListWidgetItem(server_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item.setCheckState(Qt.CheckState.Unchecked)  # Default: keep (user decides)
            self.removed_servers_list.addItem(item)

        layout.addWidget(self.removed_servers_list)

        return group

    def _create_conflicts_section(self) -> QGroupBox:
        """Create conflicts section.

        Returns:
            GroupBox with conflict resolution
        """
        group = QGroupBox(f"Conflicts ({len(self.update_info.conflicts)})")
        layout = QVBoxLayout(group)

        info = QLabel(
            "<b>Warning:</b> These servers have updates available, but you've modified them. "
            "Choose how to resolve each conflict:"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.conflict_widgets = {}

        for server_id in self.update_info.conflicts:
            conflict_widget = self._create_conflict_item(server_id)
            layout.addWidget(conflict_widget)
            self.conflict_resolutions[server_id] = "keep"  # Default: keep user version

        return group

    def _create_conflict_item(self, server_id: str) -> QGroupBox:
        """Create conflict resolution widget for a server.

        Args:
            server_id: Server ID

        Returns:
            Widget for conflict resolution
        """
        group = QGroupBox(server_id)
        layout = QVBoxLayout(group)

        desc = QLabel(
            "You've modified this server, but a new bundled version is available. "
            "What would you like to do?"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Radio buttons for choice
        keep_radio = QCheckBox("Keep my version (ignore update)")
        keep_radio.setChecked(True)
        keep_radio.toggled.connect(
            lambda checked, sid=server_id: self._on_conflict_choice(sid, "keep" if checked else None)
        )
        layout.addWidget(keep_radio)

        update_radio = QCheckBox("Use new version (overwrite my changes)")
        update_radio.toggled.connect(
            lambda checked, sid=server_id: self._on_conflict_choice(sid, "update" if checked else None)
        )
        layout.addWidget(update_radio)

        # Make them mutually exclusive
        def on_keep_toggled(checked, sid=server_id):
            if checked:
                update_radio.setChecked(False)
                self.conflict_resolutions[sid] = "keep"

        def on_update_toggled(checked, sid=server_id):
            if checked:
                keep_radio.setChecked(False)
                self.conflict_resolutions[sid] = "update"

        keep_radio.toggled.connect(on_keep_toggled)
        update_radio.toggled.connect(on_update_toggled)

        self.conflict_widgets[server_id] = (keep_radio, update_radio)

        return group

    def _on_conflict_choice(self, server_id: str, choice: str | None) -> None:
        """Handle conflict choice.

        Args:
            server_id: Server ID
            choice: "keep", "update", or None
        """
        if choice:
            self.conflict_resolutions[server_id] = choice

    def _create_new_themes_section(self) -> QGroupBox:
        """Create new themes section.

        Returns:
            GroupBox with new themes
        """
        group = QGroupBox(f"New Themes ({len(self.update_info.new_themes)})")
        layout = QVBoxLayout(group)

        info = QLabel(
            "<i>These themes are included with this version but not in your collection. "
            "Select which ones to import:</i>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.new_themes_list = QListWidget()

        for theme_name in self.update_info.new_themes:
            item = QListWidgetItem(theme_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)  # Default: import all
            self.new_themes_list.addItem(item)

        layout.addWidget(self.new_themes_list)

        return group

    def _create_updated_themes_section(self) -> QGroupBox:
        """Create updated themes section.

        Returns:
            GroupBox with updated themes
        """
        group = QGroupBox(f"Updated Themes ({len(self.update_info.updated_themes)})")
        layout = QVBoxLayout(group)

        info = QLabel(
            "<i>These bundled themes have been updated. "
            "Select which ones to update:</i>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.updated_themes_list = QListWidget()

        for theme_name in self.update_info.updated_themes:
            item = QListWidgetItem(theme_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)  # Default: update all
            self.updated_themes_list.addItem(item)

        layout.addWidget(self.updated_themes_list)

        return group

    def _apply_updates(self) -> None:
        """Apply selected updates."""
        success_count = 0
        error_count = 0

        # Import new servers
        if hasattr(self, "new_servers_list"):
            for i in range(self.new_servers_list.count()):
                item = self.new_servers_list.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    server_id = item.text()
                    if self.update_checker.import_server(server_id):
                        success_count += 1
                    else:
                        error_count += 1

        # Update servers
        if hasattr(self, "updated_servers_list"):
            for i in range(self.updated_servers_list.count()):
                item = self.updated_servers_list.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    server_id = item.text()
                    if self.update_checker.update_server(server_id):
                        success_count += 1
                    else:
                        error_count += 1

        # Remove servers
        if hasattr(self, "removed_servers_list"):
            for i in range(self.removed_servers_list.count()):
                item = self.removed_servers_list.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    server_id = item.text()
                    if self.update_checker.remove_server(server_id):
                        success_count += 1
                    else:
                        error_count += 1

        # Handle conflicts
        for server_id, resolution in self.conflict_resolutions.items():
            if resolution == "update":
                if self.update_checker.update_server(server_id, force=True):
                    success_count += 1
                else:
                    error_count += 1

        # Import new themes
        if hasattr(self, "new_themes_list"):
            for i in range(self.new_themes_list.count()):
                item = self.new_themes_list.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    theme_name = item.text()
                    if self.update_checker.import_theme(theme_name):
                        success_count += 1
                    else:
                        error_count += 1

        # Update themes
        if hasattr(self, "updated_themes_list"):
            for i in range(self.updated_themes_list.count()):
                item = self.updated_themes_list.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    theme_name = item.text()
                    if self.update_checker.update_theme(theme_name):
                        success_count += 1
                    else:
                        error_count += 1

        # Show result and close
        if success_count > 0:
            self.accept()
        else:
            self.reject()
