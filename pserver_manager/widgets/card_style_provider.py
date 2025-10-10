"""Provider for card styling based on theme."""

from __future__ import annotations

from dataclasses import dataclass
from PySide6.QtGui import QPalette, QColor


@dataclass
class CardStyle:
    """Style information for cards."""

    card_bg: str
    border_hex: str
    text_color: str
    highlight_color: str
    highlight_text_color: str
    is_dark_theme: bool


class CardStyleProvider:
    """Provider for card styling based on theme."""

    @staticmethod
    def get_card_style(palette: QPalette) -> CardStyle:
        """Get card styling based on the current palette.

        Args:
            palette: QPalette to extract colors from

        Returns:
            CardStyle object with all necessary colors
        """
        # Get base colors
        text_color = palette.color(QPalette.ColorRole.Text).name()
        highlight_color = palette.color(QPalette.ColorRole.Highlight).name()
        highlight_text_color = palette.color(QPalette.ColorRole.HighlightedText).name()

        # Determine if theme is dark or light
        window_color = palette.color(QPalette.ColorRole.Window)
        is_dark_theme = window_color.lightness() < 128

        # Create card background that adapts to theme brightness
        card_bg_color = palette.color(QPalette.ColorRole.Window)
        if is_dark_theme:
            # In dark themes, lighten the window color for cards
            card_bg_color = card_bg_color.lighter(125)  # 25% lighter
        else:
            # In light themes, darken the window color for cards
            card_bg_color = card_bg_color.darker(110)  # 10% darker
        card_bg = card_bg_color.name()

        # Create subtle border color
        border_color = palette.color(QPalette.ColorRole.Mid)
        border_color.setAlpha(80)
        border_hex = border_color.name(format=border_color.NameFormat.HexArgb)

        return CardStyle(
            card_bg=card_bg,
            border_hex=border_hex,
            text_color=text_color,
            highlight_color=highlight_color,
            highlight_text_color=highlight_text_color,
            is_dark_theme=is_dark_theme,
        )

    @staticmethod
    def get_preview_style(palette: QPalette, is_dark_theme: bool) -> tuple[str, str]:
        """Get preview background and border colors.

        Args:
            palette: QPalette to extract colors from
            is_dark_theme: Whether the theme is dark

        Returns:
            Tuple of (background_color, border_color) as hex strings
        """
        # Get preview background color
        preview_bg_color = palette.color(QPalette.ColorRole.Window)
        if is_dark_theme:
            preview_bg_color = preview_bg_color.lighter(110)  # Slightly lighter
        else:
            preview_bg_color = preview_bg_color.darker(103)  # Slightly darker
        preview_bg_color.setAlpha(128)  # Semi-transparent
        bg_color = preview_bg_color.name(format=preview_bg_color.NameFormat.HexArgb)

        # Use highlight color for left border
        preview_border_color = palette.color(QPalette.ColorRole.Highlight)
        preview_border_color.setAlpha(80)
        border_color = preview_border_color.name(format=preview_border_color.NameFormat.HexArgb)

        return bg_color, border_color

    @staticmethod
    def get_footer_bg_color(palette: QPalette, is_dark_theme: bool) -> str:
        """Get footer background color (like status bar).

        Args:
            palette: QPalette to extract colors from
            is_dark_theme: Whether the theme is dark

        Returns:
            Footer background color as hex string
        """
        # Get base window color
        footer_bg_color = palette.color(QPalette.ColorRole.Window)

        # Make it slightly darker in dark themes, slightly lighter in light themes
        # to create subtle separation like status bar
        if is_dark_theme:
            footer_bg_color = footer_bg_color.darker(108)  # 8% darker
        else:
            footer_bg_color = footer_bg_color.lighter(102)  # 2% lighter

        return footer_bg_color.name()

    @staticmethod
    def get_score_color(palette: QPalette, score: int) -> str:
        """Get color for a Reddit score based on its value.

        Args:
            palette: QPalette to extract base colors from
            score: Score value (positive, negative, or zero)

        Returns:
            Color as hex string
        """
        score_color = palette.color(QPalette.ColorRole.Highlight)

        if score > 0:
            # Positive score: shift hue toward orange/red (warm)
            h, s, v, a = score_color.getHsv()
            score_color.setHsv(20, min(255, int(s * 1.2)), v, a)  # Orange hue ~20 degrees
        elif score < 0:
            # Negative score: shift hue toward blue (cool)
            h, s, v, a = score_color.getHsv()
            score_color.setHsv(210, min(255, int(s * 1.2)), v, a)  # Blue hue ~210 degrees
        else:
            # Zero score: use muted text color
            score_color = palette.color(QPalette.ColorRole.Text)

        return score_color.name()
