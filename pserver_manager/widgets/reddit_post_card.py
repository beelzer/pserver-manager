"""Card widget for displaying Reddit posts."""

from __future__ import annotations

import html
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QPalette
from PySide6.QtWidgets import QLabel

from qtframework.layouts.card import Card
from qtframework.widgets import HBox
from pserver_manager.widgets.card_style_provider import CardStyleProvider


class RedditPostCard:
    """Builder for Reddit post cards."""

    @staticmethod
    def create_card(post, palette: QPalette) -> Card:
        """Create a card for a Reddit post.

        Args:
            post: RedditPost object
            palette: QPalette to extract colors from

        Returns:
            Card widget with post content
        """
        # Create card for each post
        card = Card(elevated=True, padding=14)

        # Get style
        style = CardStyleProvider.get_card_style(palette)

        # Apply theme-aware card styling with background
        if post.stickied:
            card.setProperty("reddit-pinned", True)
            card.setStyleSheet(
                f"Card[reddit-pinned='true'] {{ "
                f"background-color: {style.card_bg}; "
                f"border: 1px solid {style.border_hex}; "
                f"border-left: 4px solid {style.highlight_color}; "
                f"border-radius: 6px; }}"
            )
        else:
            card.setStyleSheet(
                f"Card {{ "
                f"background-color: {style.card_bg}; "
                f"border: 1px solid {style.border_hex}; "
                f"border-radius: 6px; }}"
            )

        # Add title
        RedditPostCard._add_title(card, post, style)

        # Add metadata
        RedditPostCard._add_metadata(card, post, palette, style)

        # Add preview if available
        if post.selftext and len(post.selftext) > 0:
            RedditPostCard._add_preview(card, post, palette, style)

        return card

    @staticmethod
    def _add_title(card: Card, post, style) -> None:
        """Add title to the card.

        Args:
            card: Card to add title to
            post: RedditPost object
            style: CardStyle object
        """
        # Title with optional PINNED badge
        title_box = HBox(spacing=8)
        if post.stickied:
            pinned_label = QLabel("PINNED")
            pinned_label.setStyleSheet(
                f"QLabel {{ "
                f"background-color: {style.highlight_color}; "
                f"color: {style.highlight_text_color}; "
                f"font-size: 10px; "
                f"font-weight: bold; "
                f"padding: 3px 8px; "
                f"border-radius: 3px; }}"
            )
            pinned_label.setMaximumHeight(20)
            title_box.add_widget(pinned_label)

        # Clickable title with conditional color
        if post.stickied:
            title_color = style.highlight_color
        else:
            title_color = style.text_color

        title_label = QLabel(
            f'<a href="{post.full_url}" style="text-decoration: none; color: {title_color};">'
            f'{html.escape(post.title)}</a>'
        )
        title_label.setOpenExternalLinks(True)
        title_label.setWordWrap(True)
        title_label.setTextFormat(Qt.TextFormat.RichText)
        title_label.setStyleSheet(
            "QLabel { font-size: 16px; font-weight: 600; "
            "word-wrap: break-word; word-break: break-word; }"
        )
        title_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        title_box.add_widget(title_label, stretch=1)
        card.add_widget(title_box)

    @staticmethod
    def _add_metadata(card: Card, post, palette: QPalette, style) -> None:
        """Add metadata to the card.

        Args:
            card: Card to add metadata to
            post: RedditPost object
            palette: QPalette for color extraction
            style: CardStyle object
        """
        # Get score color
        score_color_hex = CardStyleProvider.get_score_color(palette, post.score)

        meta_label = QLabel(
            f'<a href="https://www.reddit.com/user/{html.escape(post.author)}" '
            f'style="color: {style.highlight_color}; text-decoration: none; font-weight: 500;">'
            f'u/{html.escape(post.author)}</a> • '
            f'<span style="color: {score_color_hex}; font-weight: 500;">↑ {post.score}</span> • '
            f'<span>💬 {post.num_comments}</span> • '
            f'<span style="opacity: 0.7;">{post.time_ago}</span>'
        )
        meta_label.setTextFormat(Qt.TextFormat.RichText)
        meta_label.setWordWrap(True)
        meta_label.setStyleSheet(
            "QLabel { font-size: 14px; word-wrap: break-word; word-break: break-word; }"
        )
        meta_label.setOpenExternalLinks(True)
        meta_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        card.add_widget(meta_label)

    @staticmethod
    def _add_preview(card: Card, post, palette: QPalette, style) -> None:
        """Add preview text to the card.

        Args:
            card: Card to add preview to
            post: RedditPost object
            palette: QPalette for color extraction
            style: CardStyle object
        """
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
        preview_text = re.sub(
            r'(?<!href=")(https?://[^\s<"]+)(?!")',
            RedditPostCard._add_url_breaks,
            preview_text
        )

        # Get preview styling
        bg_color, border_color = CardStyleProvider.get_preview_style(palette, style.is_dark_theme)

        preview_label = QLabel(preview_text)
        preview_label.setWordWrap(True)
        preview_label.setTextFormat(Qt.TextFormat.RichText)
        preview_label.setOpenExternalLinks(True)
        preview_label.setStyleSheet(
            f"QLabel {{ "
            f"font-size: 14px; "
            f"padding: 10px; "
            f"background-color: {bg_color}; "
            f"border-left: 2px solid {border_color}; "
            f"border-radius: 4px; "
            f"word-wrap: break-word; "
            f"word-break: break-word; }}"
        )
        card.add_widget(preview_label)

    @staticmethod
    def _add_url_breaks(match: re.Match) -> str:
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
