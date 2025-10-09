"""Server updates tab."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from pserver_manager.widgets.tabs.base_tab import InfoPanelTab
from pserver_manager.widgets.update_card import UpdateCard


class UpdatesTab(InfoPanelTab):
    """Tab for displaying server updates."""

    def __init__(self, parent=None) -> None:
        """Initialize the updates tab.

        Args:
            parent: Parent widget
        """
        self._updates_url: str = ""
        self._current_updates: list = []
        super().__init__(parent)

    def _setup_ui(self) -> None:
        """Setup the tab's user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 0, 0)
        main_layout.setSpacing(15)

        # Updates label
        self._updates_label = QLabel("Server Updates")
        self._updates_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self._updates_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self._updates_label)

        # Scroll area for update cards
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setMinimumWidth(300)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Container widget for update cards
        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setSpacing(16)
        self._cards_layout.setContentsMargins(0, 0, 10, 0)
        self._cards_layout.addStretch()

        self._scroll_area.setWidget(self._cards_container)
        main_layout.addWidget(self._scroll_area, 1)

    def set_updates_url(self, updates_url: str) -> None:
        """Set the updates URL.

        Args:
            updates_url: URL to scrape updates from
        """
        self._updates_url = updates_url
        if updates_url:
            self._updates_label.setText("Server Updates")
            self.clear_content()

    def set_updates(self, updates: list) -> None:
        """Set server updates to display.

        Args:
            updates: List of server update dictionaries
        """
        # Store updates for re-rendering on theme change
        self._current_updates = updates

        if not updates:
            self.clear_content()
            label = QLabel("No updates found.")
            label.setWordWrap(True)
            self._cards_layout.insertWidget(0, label)
            return

        self.clear_content()

        palette = self.palette()
        for update in updates:
            # Use UpdateCard to create the card
            card = UpdateCard.create_card(update, palette)
            # Insert before the stretch
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)

    def set_content(self, content: str) -> None:
        """Set simple text content.

        Args:
            content: Content to display
        """
        self.clear_content()
        # Create a simple label for error messages
        label = QLabel(content)
        label.setWordWrap(True)
        self._cards_layout.insertWidget(0, label)

    def clear_content(self) -> None:
        """Clear the tab's content."""
        while self._cards_layout.count() > 1:  # Keep the stretch
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def refresh_theme(self) -> None:
        """Refresh tab styling when theme changes."""
        if self._current_updates:
            self.set_updates(self._current_updates)
