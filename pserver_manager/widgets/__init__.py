"""Custom widgets for PServer Manager."""

from __future__ import annotations

from pserver_manager.widgets.game_sidebar import GameSidebar
from pserver_manager.widgets.reddit_panel import InfoPanel
from pserver_manager.widgets.server_table import ServerTable

# Backwards compatibility alias
RedditPanel = InfoPanel

__all__ = ["GameSidebar", "InfoPanel", "RedditPanel", "ServerTable"]
