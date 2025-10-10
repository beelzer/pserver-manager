"""Card widget for displaying server updates."""

from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QPalette
from PySide6.QtWidgets import QLabel

from qtframework.layouts.card import Card
from pserver_manager.widgets.card_style_provider import CardStyleProvider


class UpdateCard:
    """Builder for server update cards."""

    @staticmethod
    def create_card(update: dict, palette: QPalette) -> Card:
        """Create a card for a server update.

        Args:
            update: Update dictionary with 'title', 'url', 'time', 'preview'
            palette: QPalette to extract colors from

        Returns:
            Card widget with update content
        """
        # Create card for each update
        card = Card(elevated=True, padding=14)

        # Get style
        style = CardStyleProvider.get_card_style(palette)

        # Apply theme-aware card styling
        card.setStyleSheet(
            f"Card {{ "
            f"background-color: {style.card_bg}; "
            f"border: 1px solid {style.border_hex}; "
            f"border-radius: 6px; }}"
        )

        # Add title
        UpdateCard._add_title(card, update, style)

        # Add preview if available
        if update.get("preview"):
            UpdateCard._add_preview(card, update, palette, style)

        # Add date at bottom
        UpdateCard._add_date(card, update)

        return card

    @staticmethod
    def _add_title(card: Card, update: dict, style) -> None:
        """Add title to the card.

        Args:
            card: Card to add title to
            update: Update dictionary
            style: CardStyle object
        """
        title_label = QLabel(
            f'<a href="{update.get("url", "#")}" style="text-decoration: none; color: {style.text_color};">'
            f'{html.escape(update.get("title", "Untitled"))}</a>'
        )
        title_label.setOpenExternalLinks(True)
        title_label.setWordWrap(True)
        title_label.setTextFormat(Qt.TextFormat.RichText)
        title_label.setStyleSheet(
            "QLabel { font-size: 16px; font-weight: 600; "
            "word-wrap: break-word; word-break: break-word; }"
        )
        title_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        card.add_widget(title_label)

    @staticmethod
    def _add_date(card: Card, update: dict) -> None:
        """Add date to the card.

        Args:
            card: Card to add date to
            update: Update dictionary
        """
        time_str = update.get("time", "Unknown time")
        date_label = QLabel(f'<span style="opacity: 0.7;">{html.escape(time_str)}</span>')
        date_label.setTextFormat(Qt.TextFormat.RichText)
        date_label.setWordWrap(True)
        date_label.setStyleSheet(
            "QLabel { font-size: 12px; word-wrap: break-word; word-break: break-word; }"
        )
        card.add_widget(date_label)

    @staticmethod
    def _add_preview(card: Card, update: dict, palette: QPalette, style) -> None:
        """Add preview text to the card.

        Args:
            card: Card to add preview to
            update: Update dictionary
            palette: QPalette for color extraction
            style: CardStyle object
        """
        preview_text = update["preview"][:200].replace('\n', ' ')
        if len(update["preview"]) > 200:
            preview_text += "..."

        # Escape HTML to prevent injection
        preview_text = html.escape(preview_text)

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
