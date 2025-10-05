"""Reddit panel widget for displaying subreddit information."""

from __future__ import annotations

import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QPalette
from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget

from qtframework.layouts.card import Card
from qtframework.widgets import HBox, VBox


class RedditPanel(VBox):
    """Panel for displaying Reddit subreddit information."""

    collapsed_changed = Signal(bool)  # Emits True when collapsed, False when expanded

    def __init__(self, parent=None):
        """Initialize Reddit panel.

        Args:
            parent: Parent widget
        """
        super().__init__(spacing=2, margins=(10, 5, 10, 10), parent=parent)

        self._subreddit = ""
        self._is_collapsed = False

        # Create loading bar (slim, indeterminate progress)
        self._loading_bar = QProgressBar()
        self._loading_bar.setMaximumHeight(4)
        self._loading_bar.setMinimum(0)
        self._loading_bar.setMaximum(0)  # Indeterminate mode
        self._loading_bar.setTextVisible(False)
        self._loading_bar.hide()  # Hidden by default
        self.add_widget(self._loading_bar)

        # Create content container with increased spacing
        self._content = VBox(spacing=15, margins=(0, 5, 0, 0))

        # Subreddit label
        self._subreddit_label = QLabel("r/wowservers")
        self._subreddit_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self._subreddit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._content.add_widget(self._subreddit_label)

        # Scroll area for Reddit cards
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setMinimumWidth(300)

        # Container widget for cards
        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setSpacing(16)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.addStretch()

        self._scroll_area.setWidget(self._cards_container)
        self._content.add_widget(self._scroll_area, stretch=1)

        self.add_widget(self._content, stretch=1)

        # Set initial minimum width (no maximum to allow expansion)
        self.setMinimumWidth(400)

    def set_subreddit(self, subreddit: str) -> None:
        """Set the subreddit to display.

        Args:
            subreddit: Subreddit name (without r/ prefix)
        """
        self._subreddit = subreddit
        if subreddit:
            self._subreddit_label.setText(f"r/{subreddit}")
            self._clear_cards()
            self.show_loading()
            self.show()
        else:
            self.hide()
            self.hide_loading()

    def _on_collapse_internal(self) -> None:
        """Handle internal collapse (from close button)."""
        self._is_collapsed = True
        self.hide()
        self.collapsed_changed.emit(True)

    def is_collapsed(self) -> bool:
        """Check if panel is collapsed.

        Returns:
            True if collapsed, False otherwise
        """
        return self._is_collapsed

    def collapse(self) -> None:
        """Collapse the panel (hides it completely)."""
        if not self._is_collapsed:
            self._on_collapse_internal()

    def expand(self) -> None:
        """Expand the panel (shows it)."""
        if self._is_collapsed:
            self._is_collapsed = False
            self.show()
            self.collapsed_changed.emit(False)

    def show_loading(self) -> None:
        """Show loading indicator."""
        self._loading_bar.show()

    def hide_loading(self) -> None:
        """Hide loading indicator."""
        self._loading_bar.hide()

    def set_content(self, content: str) -> None:
        """Set the Reddit content text.

        Args:
            content: Content to display
        """
        self._clear_cards()
        # Create a simple label for error messages
        label = QLabel(content)
        label.setWordWrap(True)
        self._cards_layout.insertWidget(0, label)
        self.hide_loading()

    def _clear_cards(self) -> None:
        """Clear all cards from the layout."""
        while self._cards_layout.count() > 1:  # Keep the stretch
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def set_posts(self, posts: list) -> None:
        """Set Reddit posts to display.

        Args:
            posts: List of RedditPost objects
        """
        if not posts:
            self.set_content("No posts found.")
            return

        self._clear_cards()

        for post in posts:
            # Create card for each post
            card = Card(elevated=True, padding=14)

            # Apply theme-aware border styling
            if post.stickied:
                card.setProperty("reddit-pinned", True)
                card.setStyleSheet("Card[reddit-pinned='true'] { border: none; border-left: 4px solid #4CAF50; }")
            else:
                card.setStyleSheet("Card { border: none; }")

            # Title with optional PINNED badge
            title_box = HBox(spacing=8)
            if post.stickied:
                pinned_label = QLabel("PINNED")
                pinned_label.setStyleSheet("""
                    QLabel {
                        background-color: #4CAF50;
                        color: white;
                        font-size: 10px;
                        font-weight: bold;
                        padding: 3px 8px;
                        border-radius: 3px;
                    }
                """)
                pinned_label.setMaximumHeight(20)
                title_box.add_widget(pinned_label)

            # Clickable title with conditional color
            if post.stickied:
                title_color = "#4CAF50"  # Green for pinned posts
            else:
                # Use normal text color for regular posts
                palette = self.palette()
                text_color = palette.color(QPalette.ColorRole.Text)
                title_color = text_color.name()

            title_label = QLabel(f'<a href="{post.full_url}" style="text-decoration: none; color: {title_color};">{html.escape(post.title)}</a>')
            title_label.setOpenExternalLinks(True)
            title_label.setWordWrap(True)
            title_label.setTextFormat(Qt.TextFormat.RichText)
            title_label.setStyleSheet("QLabel { font-size: 16px; font-weight: 600; }")
            title_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            title_box.add_widget(title_label, stretch=1)
            card.add_widget(title_box)

            # Meta information
            meta_label = QLabel(
                f'<a href="https://www.reddit.com/user/{html.escape(post.author)}" style="text-decoration: none; color: #FF6B35; font-weight: 500;">u/{html.escape(post.author)}</a> • '
                f'<span style="color: #FFA07A; font-weight: 500;">↑ {post.score}</span> • '
                f'<span>💬 {post.num_comments}</span> • '
                f'<span style="opacity: 0.7;">{post.time_ago}</span>'
            )
            meta_label.setTextFormat(Qt.TextFormat.RichText)
            meta_label.setStyleSheet("QLabel { font-size: 14px; }")
            meta_label.setOpenExternalLinks(True)
            meta_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            card.add_widget(meta_label)

            # Post preview if available
            if post.selftext and len(post.selftext) > 0:
                preview_text = post.selftext[:200].replace('\n', ' ')
                if len(post.selftext) > 200:
                    preview_text += "..."

                preview_label = QLabel(html.escape(preview_text))
                preview_label.setWordWrap(True)
                preview_label.setStyleSheet("""
                    QLabel {
                        font-size: 14px;
                        padding: 10px;
                        background-color: rgba(128, 128, 128, 0.08);
                        border-left: 2px solid rgba(128, 128, 128, 0.2);
                        border-radius: 4px;
                    }
                """)
                card.add_widget(preview_label)

            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)

        self.hide_loading()
