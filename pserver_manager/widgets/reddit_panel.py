"""Info panel widget for displaying Reddit and server updates."""

from __future__ import annotations

import html
import re

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QCursor, QPalette
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QTabWidget, QVBoxLayout, QWidget

from qtframework.layouts.card import Card
from qtframework.widgets import HBox, VBox


class InfoPanel(VBox):
    """Panel for displaying Reddit and server update information in tabs."""

    collapsed_changed = Signal(bool)  # Emits True when collapsed, False when expanded

    def __init__(self, parent=None):
        """Initialize info panel.

        Args:
            parent: Parent widget
        """
        super().__init__(spacing=0, margins=(0, 0, 0, 0), parent=parent)

        self._subreddit = ""
        self._updates_url = ""
        self._is_collapsed = False
        self._current_posts = []  # Store posts for re-rendering on theme change
        self._current_updates = []  # Store updates for re-rendering on theme change
        self._current_server = None  # Store current server for re-rendering

        # Create tab widget with clean styling
        self._tab_widget = QTabWidget()
        self._tab_widget.setDocumentMode(False)
        self._update_tab_styling()

        # Create Info tab (always shown, first tab)
        self._info_tab = self._create_info_tab()
        self._info_tab_index = self._tab_widget.addTab(self._info_tab, "Info")

        # Create Reddit tab
        self._reddit_tab = self._create_reddit_tab()
        self._reddit_tab_index = -1  # Track tab index

        # Create Updates tab
        self._updates_tab = self._create_updates_tab()
        self._updates_tab_index = -1  # Track tab index

        self.add_widget(self._tab_widget, stretch=1)

        # Set initial minimum and maximum width to constrain panel
        self.setMinimumWidth(400)
        self.setMaximumWidth(600)

    def _create_info_tab(self) -> QWidget:
        """Create the Info tab content.

        Returns:
            Info tab widget
        """
        # Scroll area for info content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setMinimumWidth(300)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Container widget for info content
        self._info_container = QWidget()
        self._info_layout = QVBoxLayout(self._info_container)
        self._info_layout.setSpacing(16)
        self._info_layout.setContentsMargins(10, 10, 10, 10)
        self._info_layout.addStretch()

        scroll_area.setWidget(self._info_container)
        return scroll_area

    def _create_reddit_tab(self) -> QWidget:
        """Create the Reddit tab content.

        Returns:
            Reddit tab widget
        """
        tab = VBox(spacing=15, margins=(10, 5, 0, 0))

        # Subreddit label
        self._subreddit_label = QLabel("r/wowservers")
        self._subreddit_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self._subreddit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tab.add_widget(self._subreddit_label)

        # Scroll area for Reddit cards
        self._reddit_scroll_area = QScrollArea()
        self._reddit_scroll_area.setWidgetResizable(True)
        self._reddit_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._reddit_scroll_area.setMinimumWidth(300)
        self._reddit_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Container widget for cards
        self._reddit_cards_container = QWidget()
        self._reddit_cards_layout = QVBoxLayout(self._reddit_cards_container)
        self._reddit_cards_layout.setSpacing(16)
        self._reddit_cards_layout.setContentsMargins(0, 0, 10, 0)  # Add 10px right margin for scrollbar spacing
        self._reddit_cards_layout.addStretch()

        self._reddit_scroll_area.setWidget(self._reddit_cards_container)
        tab.add_widget(self._reddit_scroll_area, stretch=1)

        return tab

    def _create_updates_tab(self) -> QWidget:
        """Create the Updates tab content.

        Returns:
            Updates tab widget
        """
        tab = VBox(spacing=15, margins=(10, 5, 0, 0))

        # Updates label
        self._updates_label = QLabel("Server Updates")
        self._updates_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self._updates_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tab.add_widget(self._updates_label)

        # Scroll area for update cards
        self._updates_scroll_area = QScrollArea()
        self._updates_scroll_area.setWidgetResizable(True)
        self._updates_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._updates_scroll_area.setMinimumWidth(300)
        self._updates_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Container widget for update cards
        self._updates_cards_container = QWidget()
        self._updates_cards_layout = QVBoxLayout(self._updates_cards_container)
        self._updates_cards_layout.setSpacing(16)
        self._updates_cards_layout.setContentsMargins(0, 0, 10, 0)
        self._updates_cards_layout.addStretch()

        self._updates_scroll_area.setWidget(self._updates_cards_container)
        tab.add_widget(self._updates_scroll_area, stretch=1)

        return tab

    def _update_tab_styling(self) -> None:
        """Update tab widget styling to match app theme with clean borders."""
        # Let the global stylesheet handle all tab styling
        # This removes custom styling so it uses the same borders as other panels
        self._tab_widget.setStyleSheet("")

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

        # Re-render content and update styling when palette changes (theme switch)
        if event.type() == QEvent.Type.PaletteChange:
            self._update_tab_styling()
            if self._current_server:
                self.set_server_info(self._current_server)
            if self._current_posts:
                self.set_posts(self._current_posts)
            if self._current_updates:
                self.set_updates(self._current_updates)

    def set_server_info(self, server) -> None:
        """Set server information to display in Info tab.

        Args:
            server: ServerDefinition object
        """
        # Store server for re-rendering on theme change
        self._current_server = server

        # Clear existing content
        while self._info_layout.count() > 1:  # Keep the stretch
            item = self._info_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not server:
            return

        # Get theme colors
        palette = self.palette()
        window_color = palette.color(QPalette.ColorRole.Window)
        is_dark_theme = window_color.lightness() < 128
        highlight_color = palette.color(QPalette.ColorRole.Highlight).name()

        # Card background
        card_bg_color = palette.color(QPalette.ColorRole.Window)
        if is_dark_theme:
            card_bg_color = card_bg_color.lighter(125)
        else:
            card_bg_color = card_bg_color.darker(110)
        card_bg = card_bg_color.name()

        # Border color
        border_color = palette.color(QPalette.ColorRole.Mid)
        border_color.setAlpha(80)
        border_hex = border_color.name(format=border_color.NameFormat.HexArgb)

        # Server name header
        name_label = QLabel(html.escape(server.name))
        name_label.setStyleSheet("font-weight: bold; font-size: 18px;")
        name_label.setWordWrap(True)
        self._info_layout.insertWidget(self._info_layout.count() - 1, name_label)

        # Description if available
        if server.description:
            desc_label = QLabel(html.escape(server.description))
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("font-size: 14px; opacity: 0.8;")
            self._info_layout.insertWidget(self._info_layout.count() - 1, desc_label)

        # Basic info card
        basic_card = Card(elevated=True, padding=14)
        basic_card.setMaximumWidth(580)
        basic_card.setStyleSheet(f"Card {{ background-color: {card_bg}; border: 1px solid {border_hex}; border-radius: 6px; }}")

        # Status
        status_row = HBox(spacing=8)
        status_label = QLabel("Status:")
        status_label.setStyleSheet("font-weight: 600;")
        status_row.add_widget(status_label)

        status_value = QLabel(server.status.value.title())
        if server.status.value == "online":
            status_value.setStyleSheet("color: #4CAF50; font-weight: 500;")
        elif server.status.value == "offline":
            status_value.setStyleSheet("color: #F44336; font-weight: 500;")
        else:
            status_value.setStyleSheet("opacity: 0.7;")
        status_row.add_widget(status_value)
        status_row.add_stretch()
        basic_card.add_widget(status_row)

        # Players
        if server.players >= 0 or server.max_players > 0:
            players_row = HBox(spacing=8)
            players_label = QLabel("Players:")
            players_label.setStyleSheet("font-weight: 600;")
            players_row.add_widget(players_label)

            players_text = f"{server.players}" if server.players >= 0 else "?"
            if server.max_players > 0:
                players_text += f" / {server.max_players}"
            players_value = QLabel(players_text)
            players_value.setStyleSheet("opacity: 0.8;")
            players_row.add_widget(players_value)
            players_row.add_stretch()
            basic_card.add_widget(players_row)

        # Faction counts if available
        if server.alliance_count is not None or server.horde_count is not None:
            faction_row = HBox(spacing=8)
            faction_label = QLabel("Factions:")
            faction_label.setStyleSheet("font-weight: 600;")
            faction_row.add_widget(faction_label)

            faction_parts = []
            if server.alliance_count is not None:
                faction_parts.append(f"Alliance: {server.alliance_count}")
            if server.horde_count is not None:
                faction_parts.append(f"Horde: {server.horde_count}")
            faction_value = QLabel(" | ".join(faction_parts))
            faction_value.setStyleSheet("opacity: 0.8;")
            faction_row.add_widget(faction_value)
            faction_row.add_stretch()
            basic_card.add_widget(faction_row)

        # Uptime
        if server.uptime and server.uptime != "-":
            uptime_row = HBox(spacing=8)
            uptime_label = QLabel("Uptime:")
            uptime_label.setStyleSheet("font-weight: 600;")
            uptime_row.add_widget(uptime_label)
            uptime_value = QLabel(server.uptime)
            uptime_value.setStyleSheet("opacity: 0.8;")
            uptime_row.add_widget(uptime_value)
            uptime_row.add_stretch()
            basic_card.add_widget(uptime_row)

        # Version
        version_row = HBox(spacing=8)
        version_label = QLabel("Version:")
        version_label.setStyleSheet("font-weight: 600;")
        version_row.add_widget(version_label)
        version_value = QLabel(server.version_id)
        version_value.setStyleSheet("opacity: 0.8;")
        version_row.add_widget(version_value)
        version_row.add_stretch()
        basic_card.add_widget(version_row)

        self._info_layout.insertWidget(self._info_layout.count() - 1, basic_card)

        # Connection info card (if available)
        if server.host or server.patchlist:
            conn_card = Card(elevated=True, padding=14)
            conn_card.setMaximumWidth(580)
            conn_card.setStyleSheet(f"Card {{ background-color: {card_bg}; border: 1px solid {border_hex}; border-radius: 6px; }}")

            conn_header = QLabel("Connection")
            conn_header.setStyleSheet("font-weight: bold; font-size: 16px;")
            conn_card.add_widget(conn_header)

            if server.host:
                host_row = HBox(spacing=8)
                host_label = QLabel("Host:")
                host_label.setStyleSheet("font-weight: 600;")
                host_row.add_widget(host_label)
                host_value = QLabel(server.host)
                host_value.setStyleSheet("font-family: monospace; opacity: 0.8;")
                host_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                host_row.add_widget(host_value)
                host_row.add_stretch()
                conn_card.add_widget(host_row)

            if server.patchlist:
                patch_row = HBox(spacing=8)
                patch_label = QLabel("Patchlist:")
                patch_label.setStyleSheet("font-weight: 600;")
                patch_row.add_widget(patch_label)
                patch_value = QLabel(f'<a href="{server.patchlist}" style="color: {highlight_color};">View</a>')
                patch_value.setTextFormat(Qt.TextFormat.RichText)
                patch_value.setOpenExternalLinks(True)
                patch_value.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                patch_row.add_widget(patch_value)
                patch_row.add_stretch()
                conn_card.add_widget(patch_row)

            self._info_layout.insertWidget(self._info_layout.count() - 1, conn_card)

        # Links card (if available)
        has_links = any([
            server.get_field("website", ""),
            server.get_field("discord", ""),
            server.get_field("register_url", ""),
            server.get_field("login_url", ""),
            server.get_field("download_url", "")
        ])

        if has_links:
            links_card = Card(elevated=True, padding=14)
            links_card.setMaximumWidth(580)
            links_card.setStyleSheet(f"Card {{ background-color: {card_bg}; border: 1px solid {border_hex}; border-radius: 6px; }}")

            links_header = QLabel("Links")
            links_header.setStyleSheet("font-weight: bold; font-size: 16px;")
            links_card.add_widget(links_header)

            links = [
                ("Website", server.get_field("website", "")),
                ("Discord", server.get_field("discord", "")),
                ("Register", server.get_field("register_url", "")),
                ("Login", server.get_field("login_url", "")),
                ("Download", server.get_field("download_url", ""))
            ]

            for link_name, link_url in links:
                if link_url:
                    link_row = HBox(spacing=8)
                    link_label = QLabel(f"{link_name}:")
                    link_label.setStyleSheet("font-weight: 600;")
                    link_row.add_widget(link_label)
                    link_value = QLabel(f'<a href="{link_url}" style="color: {highlight_color};">Open</a>')
                    link_value.setTextFormat(Qt.TextFormat.RichText)
                    link_value.setOpenExternalLinks(True)
                    link_value.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                    link_row.add_widget(link_value)
                    link_row.add_stretch()
                    links_card.add_widget(link_row)

            self._info_layout.insertWidget(self._info_layout.count() - 1, links_card)

        # Rates card (if available)
        rates_data = server.data.get("rates", {})
        if rates_data and isinstance(rates_data, dict):
            rates_card = Card(elevated=True, padding=14)
            rates_card.setMaximumWidth(580)
            rates_card.setStyleSheet(f"Card {{ background-color: {card_bg}; border: 1px solid {border_hex}; border-radius: 6px; }}")

            rates_header = QLabel("Rates")
            rates_header.setStyleSheet("font-weight: bold; font-size: 16px;")
            rates_card.add_widget(rates_header)

            for rate_key, rate_value in rates_data.items():
                rate_row = HBox(spacing=8)
                rate_label = QLabel(f"{rate_key.replace('_', ' ').title()}:")
                rate_label.setStyleSheet("font-weight: 600;")
                rate_row.add_widget(rate_label)
                rate_val = QLabel(str(rate_value))
                rate_val.setStyleSheet("opacity: 0.8;")
                rate_row.add_widget(rate_val)
                rate_row.add_stretch()
                rates_card.add_widget(rate_row)

            self._info_layout.insertWidget(self._info_layout.count() - 1, rates_card)

    def set_subreddit(self, subreddit: str) -> None:
        """Set the subreddit to display.

        Args:
            subreddit: Subreddit name (without r/ prefix)
        """
        self._subreddit = subreddit
        if subreddit:
            self._subreddit_label.setText(f"r/{subreddit}")
            self._clear_reddit_cards()
            self._ensure_reddit_tab_visible()
        else:
            self._remove_reddit_tab()
            # Don't hide panel - Info tab is always present

    def set_updates_url(self, updates_url: str) -> None:
        """Set the updates URL to fetch from.

        Args:
            updates_url: URL to scrape updates from
        """
        self._updates_url = updates_url
        if updates_url:
            self._updates_label.setText("Server Updates")
            self._clear_updates_cards()
            self._ensure_updates_tab_visible()
        else:
            self._remove_updates_tab()
            # Don't hide panel - Info tab is always present

    def _ensure_reddit_tab_visible(self) -> None:
        """Ensure Reddit tab is visible in the tab widget."""
        if self._reddit_tab_index == -1:
            # Tab not added yet, add it
            self._reddit_tab_index = self._tab_widget.addTab(self._reddit_tab, "Reddit")

    def _remove_reddit_tab(self) -> None:
        """Remove Reddit tab from the tab widget."""
        if self._reddit_tab_index != -1:
            self._tab_widget.removeTab(self._reddit_tab_index)
            self._reddit_tab_index = -1
            # Update updates tab index if it was after reddit tab
            if self._updates_tab_index > 0:
                self._updates_tab_index -= 1

    def _ensure_updates_tab_visible(self) -> None:
        """Ensure Updates tab is visible in the tab widget."""
        if self._updates_tab_index == -1:
            # Tab not added yet, add it
            self._updates_tab_index = self._tab_widget.addTab(self._updates_tab, "Updates")

    def _remove_updates_tab(self) -> None:
        """Remove Updates tab from the tab widget."""
        if self._updates_tab_index != -1:
            self._tab_widget.removeTab(self._updates_tab_index)
            self._updates_tab_index = -1
            # Update reddit tab index if it was after updates tab
            if self._reddit_tab_index > 0:
                self._reddit_tab_index -= 1

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


    def set_content(self, content: str) -> None:
        """Set the Reddit content text.

        Args:
            content: Content to display
        """
        self._clear_reddit_cards()
        # Create a simple label for error messages
        label = QLabel(content)
        label.setWordWrap(True)
        self._reddit_cards_layout.insertWidget(0, label)

    def _clear_reddit_cards(self) -> None:
        """Clear all Reddit cards from the layout."""
        while self._reddit_cards_layout.count() > 1:  # Keep the stretch
            item = self._reddit_cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _clear_updates_cards(self) -> None:
        """Clear all update cards from the layout."""
        while self._updates_cards_layout.count() > 1:  # Keep the stretch
            item = self._updates_cards_layout.takeAt(0)
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

        self._clear_reddit_cards()

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

            self._reddit_cards_layout.insertWidget(self._reddit_cards_layout.count() - 1, card)

    def set_updates(self, updates: list) -> None:
        """Set server updates to display.

        Args:
            updates: List of server update dictionaries
        """
        # Store updates for re-rendering on theme change
        self._current_updates = updates

        if not updates:
            self._clear_updates_cards()
            label = QLabel("No updates found.")
            label.setWordWrap(True)
            self._updates_cards_layout.insertWidget(0, label)
            return

        self._clear_updates_cards()

        for update in updates:
            # Create card for each update
            card = Card(elevated=True, padding=14)
            card.setMaximumWidth(580)  # Constrain card to fit within panel (600 - margins)

            # Get theme colors
            palette = self.palette()
            text_color = palette.color(QPalette.ColorRole.Text).name()
            highlight_color = palette.color(QPalette.ColorRole.Highlight).name()

            # Create card background that adapts to theme brightness
            window_color = palette.color(QPalette.ColorRole.Window)
            is_dark_theme = window_color.lightness() < 128

            # Adjust card background to provide contrast
            card_bg_color = palette.color(QPalette.ColorRole.Window)
            if is_dark_theme:
                card_bg_color = card_bg_color.lighter(125)
            else:
                card_bg_color = card_bg_color.darker(110)
            card_bg = card_bg_color.name()

            # Create subtle border color
            border_color = palette.color(QPalette.ColorRole.Mid)
            border_color.setAlpha(80)
            border_hex = border_color.name(format=border_color.NameFormat.HexArgb)

            # Apply theme-aware card styling
            card.setStyleSheet(f"Card {{ background-color: {card_bg}; border: 1px solid {border_hex}; border-radius: 6px; }}")

            # Title
            title_label = QLabel(f'<a href="{update.get("url", "#")}" style="text-decoration: none; color: {text_color};">{html.escape(update.get("title", "Untitled"))}</a>')
            title_label.setOpenExternalLinks(True)
            title_label.setWordWrap(True)
            title_label.setTextFormat(Qt.TextFormat.RichText)
            title_label.setStyleSheet("QLabel { font-size: 16px; font-weight: 600; word-wrap: break-word; word-break: break-word; }")
            title_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            card.add_widget(title_label)

            # Meta information (date/time)
            time_str = update.get("time", "Unknown time")
            meta_label = QLabel(f'<span style="opacity: 0.7;">{html.escape(time_str)}</span>')
            meta_label.setTextFormat(Qt.TextFormat.RichText)
            meta_label.setWordWrap(True)
            meta_label.setStyleSheet("QLabel { font-size: 14px; word-wrap: break-word; word-break: break-word; }")
            card.add_widget(meta_label)

            # Preview if available
            if update.get("preview"):
                preview_text = update["preview"][:200].replace('\n', ' ')
                if len(update["preview"]) > 200:
                    preview_text += "..."

                # Escape HTML to prevent injection
                preview_text = html.escape(preview_text)

                # Get theme colors for preview background and border
                preview_bg_color = palette.color(QPalette.ColorRole.Window)
                if is_dark_theme:
                    preview_bg_color = preview_bg_color.lighter(110)
                else:
                    preview_bg_color = preview_bg_color.darker(103)
                preview_bg_color.setAlpha(128)
                bg_color = preview_bg_color.name(format=preview_bg_color.NameFormat.HexArgb)

                preview_border_color = palette.color(QPalette.ColorRole.Highlight)
                preview_border_color.setAlpha(80)
                border_color = preview_border_color.name(format=preview_border_color.NameFormat.HexArgb)

                preview_label = QLabel(preview_text)
                preview_label.setWordWrap(True)
                preview_label.setTextFormat(Qt.TextFormat.RichText)
                preview_label.setOpenExternalLinks(True)
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

            self._updates_cards_layout.insertWidget(self._updates_cards_layout.count() - 1, card)
