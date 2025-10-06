"""Reddit panel widget for displaying subreddit information."""

from __future__ import annotations

import html
import re

from PySide6.QtCore import QEvent, Qt, Signal
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
        self._current_posts = []  # Store posts for re-rendering on theme change

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
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Container widget for cards
        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setSpacing(16)
        self._cards_layout.setContentsMargins(0, 0, 10, 0)  # Add 10px right margin for scrollbar spacing
        self._cards_layout.addStretch()

        self._scroll_area.setWidget(self._cards_container)
        self._content.add_widget(self._scroll_area, stretch=1)

        self.add_widget(self._content, stretch=1)

        # Set initial minimum and maximum width to constrain panel
        self.setMinimumWidth(400)
        self.setMaximumWidth(600)

    def _add_url_breaks(self, match: re.Match) -> str:
        """Add zero-width spaces to URLs to allow breaking.

        Args:
            match: Regex match object containing the URL

        Returns:
            URL with zero-width spaces inserted
        """
        url = match.group(0)
        # Insert zero-width space after common URL delimiters
        url = url.replace('/', '/\u200B')  # After slashes
        url = url.replace('?', '?\u200B')  # After question marks
        url = url.replace('&', '&\u200B')  # After ampersands
        url = url.replace('=', '=\u200B')  # After equals signs
        return url

    def changeEvent(self, event: QEvent) -> None:
        """Handle change events, including palette changes.

        Args:
            event: The change event
        """
        super().changeEvent(event)

        # Re-render posts when palette changes (theme switch)
        if event.type() == QEvent.Type.PaletteChange:
            if self._current_posts:
                self.set_posts(self._current_posts)

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
        # Store posts for re-rendering on theme change
        self._current_posts = posts

        if not posts:
            self.set_content("No posts found.")
            return

        self._clear_cards()

        for post in posts:
            # Create card for each post
            card = Card(elevated=True, padding=14)
            card.setMaximumWidth(580)  # Constrain card to fit within panel (600 - margins)

            # Get theme colors
            palette = self.palette()
            highlight_color = palette.color(QPalette.ColorRole.Highlight).name()
            highlight_text_color = palette.color(QPalette.ColorRole.HighlightedText).name()
            text_color = palette.color(QPalette.ColorRole.Text).name()

            # Create card background that adapts to theme brightness
            window_color = palette.color(QPalette.ColorRole.Window)
            # Check if theme is light or dark based on window color brightness
            is_dark_theme = window_color.lightness() < 128

            # Adjust card background to provide contrast
            card_bg_color = palette.color(QPalette.ColorRole.Window)
            if is_dark_theme:
                # In dark themes, lighten the window color for cards
                card_bg_color = card_bg_color.lighter(125)  # 25% lighter for better distinction
            else:
                # In light themes, darken the window color for cards
                card_bg_color = card_bg_color.darker(110)  # 10% darker for better distinction
            card_bg = card_bg_color.name()

            # Create subtle border color
            border_color = palette.color(QPalette.ColorRole.Mid)
            border_color.setAlpha(80)
            border_hex = border_color.name(format=border_color.NameFormat.HexArgb)

            # Apply theme-aware card styling with background
            if post.stickied:
                card.setProperty("reddit-pinned", True)
                card.setStyleSheet(f"Card[reddit-pinned='true'] {{ background-color: {card_bg}; border: 1px solid {border_hex}; border-left: 4px solid {highlight_color}; border-radius: 6px; }}")
            else:
                card.setStyleSheet(f"Card {{ background-color: {card_bg}; border: 1px solid {border_hex}; border-radius: 6px; }}")

            # Title with optional PINNED badge
            title_box = HBox(spacing=8)
            if post.stickied:
                pinned_label = QLabel("PINNED")
                pinned_label.setStyleSheet(f"""
                    QLabel {{
                        background-color: {highlight_color};
                        color: {highlight_text_color};
                        font-size: 10px;
                        font-weight: bold;
                        padding: 3px 8px;
                        border-radius: 3px;
                    }}
                """)
                pinned_label.setMaximumHeight(20)
                title_box.add_widget(pinned_label)

            # Clickable title with conditional color
            if post.stickied:
                title_color = highlight_color  # Use theme highlight color for pinned posts
            else:
                # Use normal text color for regular posts
                title_color = text_color

            title_label = QLabel(f'<a href="{post.full_url}" style="text-decoration: none; color: {title_color};">{html.escape(post.title)}</a>')
            title_label.setOpenExternalLinks(True)
            title_label.setWordWrap(True)
            title_label.setTextFormat(Qt.TextFormat.RichText)
            title_label.setStyleSheet("QLabel { font-size: 16px; font-weight: 600; word-wrap: break-word; word-break: break-word; }")
            title_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            title_box.add_widget(title_label, stretch=1)
            card.add_widget(title_box)

            # Meta information - use themed colors
            accent_color = palette.color(QPalette.ColorRole.Highlight).name()

            # Score color: orange-ish for positive, blue-ish for negative (derived from theme)
            score_color = palette.color(QPalette.ColorRole.Highlight)
            if post.score > 0:
                # Positive score: shift hue toward orange/red (warm)
                h, s, v, a = score_color.getHsv()
                score_color.setHsv(20, min(255, int(s * 1.2)), v, a)  # Orange hue ~20 degrees
            elif post.score < 0:
                # Negative score: shift hue toward blue (cool)
                h, s, v, a = score_color.getHsv()
                score_color.setHsv(210, min(255, int(s * 1.2)), v, a)  # Blue hue ~210 degrees
            else:
                # Zero score: use muted text color
                score_color = palette.color(QPalette.ColorRole.Text)
            score_color_hex = score_color.name()

            meta_label = QLabel(
                f'<a href="https://www.reddit.com/user/{html.escape(post.author)}" style="color: {accent_color}; text-decoration: none; font-weight: 500;">u/{html.escape(post.author)}</a> • '
                f'<span style="color: {score_color_hex}; font-weight: 500;">↑ {post.score}</span> • '
                f'<span>💬 {post.num_comments}</span> • '
                f'<span style="opacity: 0.7;">{post.time_ago}</span>'
            )
            meta_label.setTextFormat(Qt.TextFormat.RichText)
            meta_label.setWordWrap(True)
            meta_label.setStyleSheet("QLabel { font-size: 14px; word-wrap: break-word; word-break: break-word; }")
            meta_label.setOpenExternalLinks(True)
            meta_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            card.add_widget(meta_label)

            # Post preview if available
            if post.selftext and len(post.selftext) > 0:
                preview_text = post.selftext[:200].replace('\n', ' ')
                if len(post.selftext) > 200:
                    preview_text += "..."

                # Escape HTML to prevent injection, but preserve markdown
                preview_text = html.escape(preview_text)

                # Convert markdown formatting to HTML
                # Links: [text](url) -> <a href="url">text</a>
                preview_text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', preview_text)

                # Bold: **text** -> <strong>text</strong>
                preview_text = re.sub(r'\*\*([^\*]+)\*\*', r'<strong>\1</strong>', preview_text)

                # Italic: *text* -> <em>text</em> (but not ** which is already handled)
                preview_text = re.sub(r'(?<!\*)\*([^\*]+)\*(?!\*)', r'<em>\1</em>', preview_text)

                # Insert zero-width spaces in bare URLs to allow breaking
                # This prevents long URLs from overflowing (but not in <a> tags)
                preview_text = re.sub(r'(?<!href=")(https?://[^\s<"]+)(?!")', self._add_url_breaks, preview_text)

                # Get theme colors for preview background and border
                # Use a darker/lighter version of the card background for subtle distinction
                preview_bg_color = palette.color(QPalette.ColorRole.Window)
                if is_dark_theme:
                    preview_bg_color = preview_bg_color.lighter(110)  # Slightly lighter
                else:
                    preview_bg_color = preview_bg_color.darker(103)  # Slightly darker
                preview_bg_color.setAlpha(128)  # Semi-transparent
                bg_color = preview_bg_color.name(format=preview_bg_color.NameFormat.HexArgb)

                # Use highlight color for left border (matching pinned posts concept)
                preview_border_color = palette.color(QPalette.ColorRole.Highlight)
                preview_border_color.setAlpha(80)  # More visible than before
                border_color = preview_border_color.name(format=preview_border_color.NameFormat.HexArgb)

                preview_label = QLabel(preview_text)
                preview_label.setWordWrap(True)
                preview_label.setTextFormat(Qt.TextFormat.RichText)  # Enable HTML rendering
                preview_label.setOpenExternalLinks(True)  # Make links clickable
                preview_label.setStyleSheet(f"""
                    QLabel {{
                        font-size: 14px;
                        padding: 10px;
                        background-color: {bg_color};
                        border-left: 2px solid {border_color};
                        border-radius: 4px;
                        word-wrap: break-word;
                        word-break: break-word;
                    }}
                """)
                card.add_widget(preview_label)

            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)

        self.hide_loading()
