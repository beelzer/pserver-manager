"""Reddit posts tab."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from pserver_manager.widgets.tabs.base_tab import InfoPanelTab
from pserver_manager.widgets.reddit_post_card import RedditPostCard


class RedditTab(InfoPanelTab):
    """Tab for displaying Reddit posts."""

    def __init__(self, parent=None) -> None:
        """Initialize the Reddit tab.

        Args:
            parent: Parent widget
        """
        self._subreddit: str = ""
        self._current_posts: list = []
        super().__init__(parent)

    def _setup_ui(self) -> None:
        """Setup the tab's user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 0, 0)
        main_layout.setSpacing(15)

        # Subreddit label
        self._subreddit_label = QLabel("r/wowservers")
        self._subreddit_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self._subreddit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self._subreddit_label)

        # Scroll area for Reddit cards
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setMinimumWidth(300)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Container widget for cards
        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setSpacing(16)
        self._cards_layout.setContentsMargins(0, 0, 10, 0)
        self._cards_layout.addStretch()

        self._scroll_area.setWidget(self._cards_container)
        main_layout.addWidget(self._scroll_area, 1)

    def set_subreddit(self, subreddit: str) -> None:
        """Set the subreddit to display.

        Args:
            subreddit: Subreddit name (without r/ prefix)
        """
        self._subreddit = subreddit
        if subreddit:
            self._subreddit_label.setText(f"r/{subreddit}")
            self.clear_content()

    def set_posts(self, posts: list) -> None:
        """Set Reddit posts to display.

        Args:
            posts: List of RedditPost objects
        """
        # Store posts for re-rendering on theme change
        self._current_posts = posts

        if not posts:
            self.set_content("No posts found.")
            return

        self.clear_content()

        palette = self.palette()
        for post in posts:
            # Use RedditPostCard to create the card
            card = RedditPostCard.create_card(post, palette)
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
        if self._current_posts:
            self.set_posts(self._current_posts)
