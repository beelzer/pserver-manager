"""Card widget for displaying server information."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QLabel, QVBoxLayout

from qtframework.layouts.card import Card
from qtframework.widgets import HBox
from pserver_manager.widgets.card_style_provider import CardStyleProvider

if TYPE_CHECKING:
    from pserver_manager.config_loader import ServerDefinition


class ServerInfoCard:
    """Builder for server information cards."""

    @staticmethod
    def create_info_cards(server: ServerDefinition, layout: QVBoxLayout, parent_widget=None) -> None:
        """Create and add server information cards to layout.

        Args:
            server: Server definition
            layout: Layout to add cards to
            parent_widget: Parent widget to get palette from (optional)
        """
        if not server:
            return

        # Get style from parent widget or first widget in layout
        palette = None
        if parent_widget:
            palette = parent_widget.palette()
        else:
            widgets_in_layout = [layout.itemAt(i).widget() for i in range(layout.count()) if layout.itemAt(i).widget()]
            if widgets_in_layout:
                palette = widgets_in_layout[0].palette()

        if not palette:
            # Fallback to default palette if no widget available
            from PySide6.QtWidgets import QApplication
            palette = QApplication.palette()

        style = CardStyleProvider.get_card_style(palette)

        # Server name header
        name_label = QLabel(html.escape(server.name))
        name_label.setStyleSheet("font-weight: bold; font-size: 18px;")
        name_label.setWordWrap(True)
        layout.insertWidget(layout.count() - 1, name_label)

        # Description if available
        if server.description:
            desc_label = QLabel(html.escape(server.description))
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("font-size: 14px; opacity: 0.8;")
            layout.insertWidget(layout.count() - 1, desc_label)

        # Create basic info card
        ServerInfoCard._create_basic_info_card(server, layout, style)

        # Create connection info card if available
        if server.host or server.patchlist:
            ServerInfoCard._create_connection_card(server, layout, style)

        # Create links card if available
        has_links = any([
            server.get_field("website", ""),
            server.get_field("discord", ""),
            server.get_field("register_url", ""),
            server.get_field("login_url", ""),
            server.get_field("download_url", "")
        ])
        if has_links:
            ServerInfoCard._create_links_card(server, layout, style)

        # Create rates card if available
        rates_data = server.data.get("rates", {})
        if rates_data and isinstance(rates_data, dict):
            ServerInfoCard._create_rates_card(rates_data, layout, style)

    @staticmethod
    def _create_basic_info_card(server, layout: QVBoxLayout, style) -> None:
        """Create basic info card with status, players, etc.

        Args:
            server: Server definition
            layout: Layout to add card to
            style: CardStyle object
        """
        basic_card = Card(elevated=True, padding=14)
        basic_card.setStyleSheet(
            f"Card {{ background-color: {style.card_bg}; "
            f"border: 1px solid {style.border_hex}; border-radius: 6px; }}"
        )

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

        layout.insertWidget(layout.count() - 1, basic_card)

    @staticmethod
    def _create_connection_card(server, layout: QVBoxLayout, style) -> None:
        """Create connection info card.

        Args:
            server: Server definition
            layout: Layout to add card to
            style: CardStyle object
        """
        conn_card = Card(elevated=True, padding=14)
        conn_card.setStyleSheet(
            f"Card {{ background-color: {style.card_bg}; "
            f"border: 1px solid {style.border_hex}; border-radius: 6px; }}"
        )

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
            patch_value = QLabel(
                f'<a href="{server.patchlist}" style="color: {style.highlight_color};">View</a>'
            )
            patch_value.setTextFormat(Qt.TextFormat.RichText)
            patch_value.setOpenExternalLinks(True)
            patch_value.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            patch_row.add_widget(patch_value)
            patch_row.add_stretch()
            conn_card.add_widget(patch_row)

        layout.insertWidget(layout.count() - 1, conn_card)

    @staticmethod
    def _create_links_card(server, layout: QVBoxLayout, style) -> None:
        """Create links card.

        Args:
            server: Server definition
            layout: Layout to add card to
            style: CardStyle object
        """
        links_card = Card(elevated=True, padding=14)
        links_card.setStyleSheet(
            f"Card {{ background-color: {style.card_bg}; "
            f"border: 1px solid {style.border_hex}; border-radius: 6px; }}"
        )

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
                link_value = QLabel(
                    f'<a href="{link_url}" style="color: {style.highlight_color};">Open</a>'
                )
                link_value.setTextFormat(Qt.TextFormat.RichText)
                link_value.setOpenExternalLinks(True)
                link_value.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                link_row.add_widget(link_value)
                link_row.add_stretch()
                links_card.add_widget(link_row)

        layout.insertWidget(layout.count() - 1, links_card)

    @staticmethod
    def _create_rates_card(rates_data: dict, layout: QVBoxLayout, style) -> None:
        """Create rates card.

        Args:
            rates_data: Dictionary of rate information
            layout: Layout to add card to
            style: CardStyle object
        """
        rates_card = Card(elevated=True, padding=14)
        rates_card.setStyleSheet(
            f"Card {{ background-color: {style.card_bg}; "
            f"border: 1px solid {style.border_hex}; border-radius: 6px; }}"
        )

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

        layout.insertWidget(layout.count() - 1, rates_card)
