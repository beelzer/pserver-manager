"""Custom widgets for PServer Manager."""

from __future__ import annotations

from pserver_manager.widgets.game_sidebar import GameSidebar
from pserver_manager.widgets.info_panel import InfoPanel
from pserver_manager.widgets.server_table import ServerTable
from pserver_manager.widgets.server_links_widget import ServerLinksWidget
from pserver_manager.widgets.server_data_formatter import ServerDataFormatter
from pserver_manager.widgets.card_style_provider import CardStyleProvider, CardStyle
from pserver_manager.widgets.server_info_card import ServerInfoCard
from pserver_manager.widgets.reddit_post_card import RedditPostCard
from pserver_manager.widgets.update_card import UpdateCard

# Import tab classes
from pserver_manager.widgets.tabs import (
    InfoPanelTab,
    ServerInfoTab,
    RedditTab,
    UpdatesTab,
)

# Backwards compatibility alias
RedditPanel = InfoPanel

__all__ = [
    "GameSidebar",
    "InfoPanel",
    "RedditPanel",
    "ServerTable",
    "ServerLinksWidget",
    "ServerDataFormatter",
    "CardStyleProvider",
    "CardStyle",
    "ServerInfoCard",
    "RedditPostCard",
    "UpdateCard",
    "InfoPanelTab",
    "ServerInfoTab",
    "RedditTab",
    "UpdatesTab",
]
