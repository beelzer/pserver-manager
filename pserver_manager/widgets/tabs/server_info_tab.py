"""Server information tab."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget

from pserver_manager.widgets.tabs.base_tab import InfoPanelTab
from pserver_manager.widgets.server_info_card import ServerInfoCard

if TYPE_CHECKING:
    from pserver_manager.config_loader import ServerDefinition


class ServerInfoTab(InfoPanelTab):
    """Tab for displaying server information."""

    def __init__(self, parent=None) -> None:
        """Initialize the server info tab.

        Args:
            parent: Parent widget
        """
        self._current_server: ServerDefinition | None = None
        super().__init__(parent)

    def _setup_ui(self) -> None:
        """Setup the tab's user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll area for info content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setMinimumWidth(300)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Container widget for info content
        self._info_container = QWidget()
        self._info_layout = QVBoxLayout(self._info_container)
        self._info_layout.setSpacing(16)
        self._info_layout.setContentsMargins(10, 10, 10, 10)
        self._info_layout.addStretch()

        scroll_area.setWidget(self._info_container)
        layout.addWidget(scroll_area)

    def set_server(self, server: ServerDefinition | None) -> None:
        """Set the server to display information for.

        Args:
            server: Server definition to display
        """
        # Store server for re-rendering on theme change
        self._current_server = server

        # Clear existing content
        self.clear_content()

        # Only create cards if we have a server
        if server:
            # Use ServerInfoCard to create all info cards, pass self as parent for palette
            ServerInfoCard.create_info_cards(server, self._info_layout, parent_widget=self._info_container)

    def clear_content(self) -> None:
        """Clear the tab's content."""
        while self._info_layout.count() > 1:  # Keep the stretch
            item = self._info_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def refresh_theme(self) -> None:
        """Refresh tab styling when theme changes."""
        if self._current_server:
            self.set_server(self._current_server)
