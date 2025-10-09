"""Info panel tabs."""

from __future__ import annotations

from pserver_manager.widgets.tabs.base_tab import InfoPanelTab
from pserver_manager.widgets.tabs.server_info_tab import ServerInfoTab
from pserver_manager.widgets.tabs.reddit_tab import RedditTab
from pserver_manager.widgets.tabs.updates_tab import UpdatesTab

__all__ = [
    "InfoPanelTab",
    "ServerInfoTab",
    "RedditTab",
    "UpdatesTab",
]
