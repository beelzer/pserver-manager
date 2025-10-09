"""Base class for info panel tabs."""

from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QWidget


class InfoPanelTab(QWidget):
    """Base class for info panel tabs."""

    def __init__(self, parent=None) -> None:
        """Initialize the tab.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the tab's user interface.

        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement _setup_ui()")

    def refresh_theme(self) -> None:
        """Refresh tab styling when theme changes.

        Can be overridden by subclasses that need to respond to theme changes.
        """
        pass

    def clear_content(self) -> None:
        """Clear the tab's content.

        Can be overridden by subclasses that need to clear their content.
        """
        pass

    def changeEvent(self, event: QEvent) -> None:
        """Handle change events, including palette changes.

        Args:
            event: The change event
        """
        super().changeEvent(event)

        # Refresh theme when palette changes (theme switch)
        if event.type() == QEvent.Type.PaletteChange:
            self.refresh_theme()
