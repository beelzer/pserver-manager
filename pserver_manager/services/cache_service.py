"""Cache service for managing server data and updates caching."""

from __future__ import annotations

import time
from typing import Any


class ServerDataCache:
    """Cache entry for server data including Reddit, updates, ping, etc."""

    def __init__(self, server_id: str) -> None:
        """Initialize server data cache entry.

        Args:
            server_id: Server ID
        """
        self.server_id = server_id
        self.scrape_success: bool = False
        self.scrape_data: dict[str, Any] = {}
        self.scrape_error: str | None = None
        self.ping_ms: int = -1
        self.ping_success: bool = False
        self.worlds_data: list[dict] | None = None
        self.reddit_posts: list | None = None
        self.reddit_error: str | None = None
        self.updates: list | None = None
        self.updates_error: str | None = None


class CacheService:
    """Service for managing all caching operations."""

    def __init__(self, cache_hours: int = 24) -> None:
        """Initialize cache service.

        Args:
            cache_hours: Number of hours to cache updates
        """
        self._server_data_cache: dict[str, ServerDataCache] = {}
        self._updates_last_fetch: dict[str, float] = {}
        self._updates_cache: dict[str, list[dict]] = {}
        self._cache_hours = cache_hours

    def get_server_data(self, server_id: str) -> ServerDataCache | None:
        """Get cached server data.

        Args:
            server_id: Server ID

        Returns:
            Cached server data or None if not found
        """
        return self._server_data_cache.get(server_id)

    def set_server_data(self, server_id: str, data: ServerDataCache) -> None:
        """Set cached server data.

        Args:
            server_id: Server ID
            data: Server data cache to store
        """
        self._server_data_cache[server_id] = data

    def get_or_create_server_data(self, server_id: str) -> ServerDataCache:
        """Get or create server data cache entry.

        Args:
            server_id: Server ID

        Returns:
            Server data cache (existing or newly created)
        """
        if server_id not in self._server_data_cache:
            self._server_data_cache[server_id] = ServerDataCache(server_id)
        return self._server_data_cache[server_id]

    def should_fetch_updates(self, url: str) -> bool:
        """Check if updates should be fetched based on cache time.

        Args:
            url: Updates URL

        Returns:
            True if should fetch (cache expired or no cache), False otherwise
        """
        if url not in self._updates_last_fetch:
            return True

        last_fetch = self._updates_last_fetch[url]
        elapsed_hours = (time.time() - last_fetch) / 3600

        return elapsed_hours >= self._cache_hours

    def get_cached_updates(self, url: str) -> list[dict] | None:
        """Get cached updates for a URL.

        Args:
            url: Updates URL

        Returns:
            Cached updates or None if not found
        """
        return self._updates_cache.get(url)

    def cache_updates(self, url: str, updates: list[dict]) -> None:
        """Cache updates for a URL.

        Args:
            url: Updates URL
            updates: Updates to cache
        """
        self._updates_cache[url] = updates
        self._updates_last_fetch[url] = time.time()

    def clear_server_cache(self, server_id: str) -> None:
        """Clear cache for a specific server.

        Args:
            server_id: Server ID
        """
        if server_id in self._server_data_cache:
            del self._server_data_cache[server_id]

    def clear_updates_cache(self, url: str | None = None) -> None:
        """Clear updates cache.

        Args:
            url: Optional specific URL to clear, or None to clear all
        """
        if url:
            if url in self._updates_cache:
                del self._updates_cache[url]
            if url in self._updates_last_fetch:
                del self._updates_last_fetch[url]
        else:
            self._updates_cache.clear()
            self._updates_last_fetch.clear()

    def clear_all(self) -> None:
        """Clear all caches."""
        self._server_data_cache.clear()
        self._updates_cache.clear()
        self._updates_last_fetch.clear()
