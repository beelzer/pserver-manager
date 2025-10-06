"""Utility modules."""

from pserver_manager.utils.paths import AppPaths, get_app_paths
from pserver_manager.utils.schema_migrations import ServerSchemaMigrator, migrate_user_servers
from pserver_manager.utils.server_ping import (
    ping_multiple_servers,
    ping_multiple_servers_sync,
    ping_server,
    ping_server_sync,
)
from pserver_manager.utils.server_scraper import (
    ScraperProgress,
    ServerScrapeResult,
    scrape_servers,
    scrape_servers_sync,
)
from pserver_manager.utils.svg_icon_loader import SvgIconLoader, get_svg_loader

# Qt integration (optional import)
try:
    from pserver_manager.utils.qt_scraper_worker import AsyncScraperHelper, ScraperWorker
    _has_qt = True
except ImportError:
    _has_qt = False
    AsyncScraperHelper = None
    ScraperWorker = None
from pserver_manager.utils.updates import ServerUpdateChecker, UpdateInfo

__all__ = [
    "AppPaths",
    "get_app_paths",
    "ping_server",
    "ping_server_sync",
    "ping_multiple_servers",
    "ping_multiple_servers_sync",
    "ScraperProgress",
    "ServerScrapeResult",
    "scrape_servers",
    "scrape_servers_sync",
    "AsyncScraperHelper",
    "ScraperWorker",
    "ServerSchemaMigrator",
    "migrate_user_servers",
    "ServerUpdateChecker",
    "UpdateInfo",
    "SvgIconLoader",
    "get_svg_loader",
]
