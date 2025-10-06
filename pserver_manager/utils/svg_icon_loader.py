"""SVG icon loader with theme-aware coloring.

This module provides utilities for loading SVG icons and dynamically
recoloring them based on the current theme.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QByteArray, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtSvg import QSvgRenderer

if TYPE_CHECKING:
    pass


class SvgIconLoader:
    """Loads and caches theme-aware SVG icons."""

    def __init__(self, theme_manager=None) -> None:
        """Initialize SVG icon loader.

        Args:
            theme_manager: Optional theme manager for color information
        """
        self.theme_manager = theme_manager
        self._cache: dict[tuple[str, str], QIcon] = {}

    def load_icon(
        self, svg_path: str | Path, color: str | None = None, size: tuple[int, int] = (16, 16)
    ) -> QIcon:
        """Load an SVG icon and optionally recolor it.

        Args:
            svg_path: Path to SVG file
            color: Optional color to apply (hex format like "#FF0000")
                   If None, uses theme's icon color
            size: Icon size as (width, height)

        Returns:
            QIcon with the styled SVG
        """
        svg_path = Path(svg_path)

        # Get color from theme if not provided
        if color is None and self.theme_manager:
            # Try to get icon color from theme
            color = self.theme_manager.get_value("icon_color", "#FFFFFF")

        # Check cache
        cache_key = (str(svg_path), color or "default")
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Load SVG content
        if not svg_path.exists():
            # Return empty icon if file doesn't exist
            return QIcon()

        svg_content = svg_path.read_text(encoding="utf-8")

        # Apply color transformation if specified
        if color:
            svg_content = self._recolor_svg(svg_content, color)

        # Render SVG to QIcon
        icon = self._render_svg(svg_content, size)

        # Cache and return
        self._cache[cache_key] = icon
        return icon

    def _recolor_svg(self, svg_content: str, color: str) -> str:
        """Recolor an SVG by replacing fill and stroke colors.

        Args:
            svg_content: SVG XML content
            color: Target color (hex format)

        Returns:
            Modified SVG content
        """
        import re

        # Replace fill colors (including fill="..." and style="fill:...")
        svg_content = re.sub(
            r'fill\s*=\s*"[^"]*"',
            f'fill="{color}"',
            svg_content,
        )
        svg_content = re.sub(
            r'fill\s*:\s*[^;"]+',
            f'fill:{color}',
            svg_content,
        )

        # Replace stroke colors
        svg_content = re.sub(
            r'stroke\s*=\s*"[^"]*"',
            f'stroke="{color}"',
            svg_content,
        )
        svg_content = re.sub(
            r'stroke\s*:\s*[^;"]+',
            f'stroke:{color}',
            svg_content,
        )

        return svg_content

    def _render_svg(self, svg_content: str, size: tuple[int, int]) -> QIcon:
        """Render SVG content to a QIcon.

        Args:
            svg_content: SVG XML content
            size: Icon size as (width, height)

        Returns:
            Rendered QIcon
        """
        from PySide6.QtGui import QPainter

        # Create SVG renderer
        svg_bytes = QByteArray(svg_content.encode("utf-8"))
        renderer = QSvgRenderer(svg_bytes)

        # Create pixmap and render
        pixmap = QPixmap(QSize(size[0], size[1]))
        pixmap.fill(0x00000000)  # Transparent background

        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        return QIcon(pixmap)

    def clear_cache(self) -> None:
        """Clear the icon cache."""
        self._cache.clear()


# Global instance
_svg_loader: SvgIconLoader | None = None


def get_svg_loader() -> SvgIconLoader:
    """Get the global SVG icon loader instance.

    Returns:
        SvgIconLoader instance
    """
    global _svg_loader
    if _svg_loader is None:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        theme_manager = getattr(app, "theme_manager", None) if app else None
        _svg_loader = SvgIconLoader(theme_manager)
    return _svg_loader
