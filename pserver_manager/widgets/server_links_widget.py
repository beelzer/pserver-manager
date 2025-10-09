"""Widget for displaying server links with clickable icons."""

from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton

if TYPE_CHECKING:
    from pserver_manager.config_loader import ServerDefinition


class ServerLinksWidget(QWidget):
    """Widget with clickable link icons for a server."""

    def __init__(self, server: ServerDefinition, parent=None) -> None:
        """Initialize the server links widget.

        Args:
            server: Server definition
            parent: Parent widget
        """
        super().__init__(parent)
        self.setStyleSheet("QWidget { background: transparent; }")

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(4, 2, 4, 2)
        self._layout.setSpacing(4)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._create_links(server)

    def _create_links(self, server: ServerDefinition) -> None:
        """Create link buttons for the server.

        Args:
            server: Server definition
        """
        from pserver_manager.utils.svg_icon_loader import get_svg_loader

        # Get SVG icon loader
        svg_loader = get_svg_loader()
        brands_dir = Path(__file__).parent.parent / "assets" / "brands"

        # Define link types and their icons
        links = [
            ("🌐", None, server.get_field('website', ''), "Visit website"),
            ("📚", None, server.get_field('wiki', ''), "Visit wiki"),
            (None, "discord.svg", f"https://discord.gg/{server.get_field('discord', '')}" if server.get_field('discord', '') else None, "Join Discord"),
            (None, "reddit.svg", f"https://reddit.com/r/{server.get_field('reddit', '')}" if server.get_field('reddit', '') else None, "Visit Reddit"),
        ]

        # Add repository links (support multiple repositories)
        repositories = server.get_field('repository', [])
        if isinstance(repositories, list):
            repo_type_map = {
                'github': ('github.svg', 'https://github.com/{}', 'View on GitHub'),
                'gitlab': ('gitlab.svg', 'https://gitlab.com/{}', 'View on GitLab'),
                'bitbucket': ('bitbucket.svg', 'https://bitbucket.org/{}', 'View on Bitbucket'),
                'gitea': ('gitea.svg', 'https://gitea.com/{}', 'View on Gitea'),
            }
            for repo in repositories:
                if isinstance(repo, dict):
                    repo_type = repo.get('type', '').lower()
                    repo_id = repo.get('id', '')
                    if repo_type in repo_type_map and repo_id:
                        svg_file, url_template, tooltip = repo_type_map[repo_type]
                        links.append((None, svg_file, url_template.format(repo_id), tooltip))

        links.extend([
            ("📝", None, server.get_field('register_url', ''), "Register account"),
            ("🔑", None, server.get_field('login_url', ''), "Login/manage account"),
        ])

        for emoji, svg_file, url, tooltip in links:
            if url:
                btn = self._create_link_button(emoji, svg_file, url, tooltip, brands_dir)
                self._layout.addWidget(btn)

        self._layout.addStretch()

    def _create_link_button(
        self,
        emoji: str | None,
        svg_file: str | None,
        url: str,
        tooltip: str,
        brands_dir: Path
    ) -> QPushButton:
        """Create a single link button.

        Args:
            emoji: Emoji to use for the button (if no SVG)
            svg_file: SVG file name to use for the button
            url: URL to open when clicked
            tooltip: Tooltip text
            brands_dir: Directory containing brand SVG files

        Returns:
            Configured QPushButton
        """
        btn = QPushButton()

        # Use SVG icon if available, otherwise use emoji
        if svg_file:
            svg_path = brands_dir / svg_file
            if svg_path.exists():
                # Load icon without recoloring to preserve brand colors
                pixmap = QPixmap(str(svg_path))
                # Scale to 16x16 if needed
                if pixmap.width() != 16 or pixmap.height() != 16:
                    pixmap = pixmap.scaled(
                        16, 16,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                icon = QIcon(pixmap)
                btn.setIcon(icon)
                btn.setIconSize(QSize(16, 16))
            else:
                btn.setText(emoji if emoji else "")
        else:
            btn.setText(emoji)

        btn.setToolTip(tooltip)
        btn.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                font-size: 14px;
                padding: 0px;
                margin: 0px;
                min-height: 0px;
                max-height: 20px;
            }
            QPushButton:hover {
                background: transparent;
            }
        """)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda checked=False, u=url: webbrowser.open(u))

        return btn
