"""Info panel widget for displaying Reddit and server updates."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import QTabWidget

from qtframework.widgets import VBox
from pserver_manager.widgets.tabs import ServerInfoTab, RedditTab, UpdatesTab


class InfoPanel(VBox):
    """Panel for displaying Reddit and server update information in tabs."""

    collapsed_changed = Signal(bool)  # Emits True when collapsed, False when expanded

    def __init__(self, parent=None):
        """Initialize info panel.

        Args:
            parent: Parent widget
        """
        super().__init__(spacing=0, margins=(0, 0, 0, 0), parent=parent)

        self._is_collapsed = False

        # Create tab widget with clean styling
        self._tab_widget = QTabWidget()
        self._tab_widget.setDocumentMode(False)
        self._update_tab_styling()

        # Create Info tab (always shown, first tab at index 0 - NEVER remove this!)
        self._info_tab = ServerInfoTab()
        self._info_tab_index = self._tab_widget.addTab(self._info_tab, "Info")
        # Info tab index should always be 0
        assert self._info_tab_index == 0, "Info tab must be at index 0"

        # Create Reddit tab
        self._reddit_tab = RedditTab()
        self._reddit_tab_index = -1  # Track tab index (dynamic)

        # Create Updates tab
        self._updates_tab = UpdatesTab()
        self._updates_tab_index = -1  # Track tab index (dynamic)

        self.add_widget(self._tab_widget, stretch=1)

        # Set initial minimum and maximum width to constrain panel
        self.setMinimumWidth(400)
        self.setMaximumWidth(600)

    def _update_tab_styling(self) -> None:
        """Update tab widget styling to match app theme with clean borders."""
        # Let the global stylesheet handle all tab styling
        # This removes custom styling so it uses the same borders as other panels
        self._tab_widget.setStyleSheet("")

    def _ensure_info_tab_present(self) -> None:
        """Ensure Info tab is always present at index 0."""
        # Verify Info tab is still at index 0
        if self._tab_widget.count() == 0 or self._tab_widget.widget(0) != self._info_tab:
            # Info tab is missing or not at index 0 - restore it
            # Remove it if it exists elsewhere
            for i in range(self._tab_widget.count()):
                if self._tab_widget.widget(i) == self._info_tab:
                    self._tab_widget.removeTab(i)
                    break
            # Insert at index 0
            self._tab_widget.insertTab(0, self._info_tab, "Info")
            self._info_tab_index = 0
            # Adjust other indices
            if self._reddit_tab_index != -1:
                self._reddit_tab_index += 1
            if self._updates_tab_index != -1:
                self._updates_tab_index += 1

    def changeEvent(self, event: QEvent) -> None:
        """Handle change events, including palette changes.

        Args:
            event: The change event
        """
        super().changeEvent(event)

        # Re-render content and update styling when palette changes (theme switch)
        if event.type() == QEvent.Type.PaletteChange:
            self._update_tab_styling()

    def set_server_info(self, server) -> None:
        """Set server information to display in Info tab.

        Args:
            server: ServerDefinition object
        """
        self._info_tab.set_server(server)

    def set_subreddit(self, subreddit: str) -> None:
        """Set the subreddit to display.

        Args:
            subreddit: Subreddit name (without r/ prefix)
        """
        if subreddit:
            self._reddit_tab.set_subreddit(subreddit)
            self._ensure_reddit_tab_visible()
        else:
            self._remove_reddit_tab()

    def set_updates_url(self, updates_url: str) -> None:
        """Set the updates URL to fetch from.

        Args:
            updates_url: URL to scrape updates from
        """
        if updates_url:
            self._updates_tab.set_updates_url(updates_url)
            self._ensure_updates_tab_visible()
        else:
            self._remove_updates_tab()

    def _ensure_reddit_tab_visible(self) -> None:
        """Ensure Reddit tab is visible in the tab widget."""
        self._ensure_info_tab_present()  # Safety check
        if self._reddit_tab_index == -1:
            # Tab not added yet, add it
            self._reddit_tab_index = self._tab_widget.addTab(self._reddit_tab, "Reddit")

    def _remove_reddit_tab(self) -> None:
        """Remove Reddit tab from the tab widget."""
        if self._reddit_tab_index != -1:
            self._tab_widget.removeTab(self._reddit_tab_index)
            # Update updates tab index if it was after reddit tab
            if self._updates_tab_index > self._reddit_tab_index:
                self._updates_tab_index -= 1
            self._reddit_tab_index = -1
        self._ensure_info_tab_present()  # Safety check

    def _ensure_updates_tab_visible(self) -> None:
        """Ensure Updates tab is visible in the tab widget."""
        self._ensure_info_tab_present()  # Safety check
        if self._updates_tab_index == -1:
            # Tab not added yet, add it
            self._updates_tab_index = self._tab_widget.addTab(self._updates_tab, "Updates")

    def _remove_updates_tab(self) -> None:
        """Remove Updates tab from the tab widget."""
        if self._updates_tab_index != -1:
            self._tab_widget.removeTab(self._updates_tab_index)
            # Update reddit tab index if it was after updates tab
            if self._reddit_tab_index > self._updates_tab_index:
                self._reddit_tab_index -= 1
            self._updates_tab_index = -1
        self._ensure_info_tab_present()  # Safety check

    def is_collapsed(self) -> bool:
        """Check if panel is collapsed.

        Returns:
            True if collapsed, False otherwise
        """
        return self._is_collapsed

    def collapse(self) -> None:
        """Collapse the panel (hides it completely)."""
        if not self._is_collapsed:
            self._is_collapsed = True
            self.hide()
            self.collapsed_changed.emit(True)

    def expand(self) -> None:
        """Expand the panel (shows it)."""
        if self._is_collapsed:
            self._is_collapsed = False
            self.show()
            self.collapsed_changed.emit(False)

    def set_content(self, content: str) -> None:
        """Set the Reddit content text.

        Args:
            content: Content to display
        """
        self._reddit_tab.set_content(content)

    def set_posts(self, posts: list) -> None:
        """Set Reddit posts to display.

        Args:
            posts: List of RedditPost objects
        """
        self._reddit_tab.set_posts(posts)

    def set_updates(self, updates: list) -> None:
        """Set server updates to display.

        Args:
            updates: List of server update dictionaries
        """
        self._updates_tab.set_updates(updates)

    # Properties for backwards compatibility with controller
    @property
    def _current_server(self):
        """Get current server from Info tab."""
        return self._info_tab._current_server

    @property
    def _updates_url(self):
        """Get updates URL from Updates tab."""
        return self._updates_tab._updates_url

    @property
    def _updates_cards_layout(self):
        """Get updates cards layout from Updates tab."""
        return self._updates_tab._cards_layout

    def _clear_updates_cards(self):
        """Clear updates cards."""
        self._updates_tab.clear_content()
