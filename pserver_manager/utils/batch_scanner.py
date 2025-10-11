"""Batch scanner for running all server scans in parallel."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QThread, Signal

if TYPE_CHECKING:
    from pserver_manager.config_loader import ServerDefinition


class ServerDataResult:
    """Complete data result for a server including scraping, ping, reddit, and updates."""

    def __init__(self, server_id: str):
        """Initialize server data result.

        Args:
            server_id: Server ID
        """
        self.server_id = server_id

        # Scraping data (player counts, uptime)
        self.scrape_success: bool = False
        self.scrape_data: dict[str, Any] = {}
        self.scrape_error: str | None = None

        # Ping data
        self.ping_ms: int = -1
        self.ping_success: bool = False

        # Worlds data (for servers with multiple worlds like Vidyascape)
        self.worlds_data: list[dict] | None = None

        # Reddit data
        self.reddit_posts: list | None = None
        self.reddit_error: str | None = None

        # Updates data
        self.updates: list | None = None
        self.updates_error: str | None = None


class BatchScanWorker(QObject):
    """Worker for batch scanning servers in parallel."""

    progress = Signal(int, int, str)  # current, total, task_description
    data_complete = Signal(str, object)  # server_id, ServerDataResult
    finished = Signal(dict)  # all_results: dict[server_id, ServerDataResult]
    error = Signal(str)

    def __init__(self, servers: list[ServerDefinition], max_workers: int = 5):
        """Initialize batch scan worker.

        Args:
            servers: List of servers to scan
            max_workers: Maximum number of concurrent scans
        """
        super().__init__()
        self.servers = servers
        self.max_workers = max_workers
        self._cancelled = False

    def cancel(self):
        """Cancel the scanning operation."""
        self._cancelled = True

    def run(self):
        """Run batch data fetching for all servers."""
        from pserver_manager.utils import scrape_servers_sync, ping_multiple_servers_sync
        from pserver_manager.utils.reddit_scraper import RedditScraper
        from pserver_manager.utils.updates_scraper import UpdatesScraper

        results = {}
        total_tasks = 0
        current_task = 0

        print("[BatchScan] Starting batch data fetch...")

        # Count total tasks
        servers_with_scraping = [s for s in self.servers if s.scraping]
        # Include servers with host OR worlds
        servers_with_host = [
            s for s in self.servers
            if s.host or (isinstance(s.get_field('worlds', []), list) and len(s.get_field('worlds', [])) > 0)
        ]
        servers_with_reddit = [s for s in self.servers if s.reddit]
        servers_with_updates = [s for s in self.servers if s.updates_url]

        print(f"[BatchScan] Found {len(servers_with_scraping)} servers with scraping")
        print(f"[BatchScan] Found {len(servers_with_host)} servers with hosts")
        print(f"[BatchScan] Found {len(servers_with_reddit)} servers with reddit")
        print(f"[BatchScan] Found {len(servers_with_updates)} servers with updates")

        total_tasks = (
            len(servers_with_scraping)
            + len(servers_with_host)
            + len(servers_with_reddit)
            + len(servers_with_updates)
        )

        print(f"[BatchScan] Total tasks: {total_tasks}")

        if total_tasks == 0:
            print("[BatchScan] No tasks to perform, finishing...")
            self.finished.emit(results)
            return

        # Initialize results for all servers
        for server in self.servers:
            results[server.id] = ServerDataResult(server.id)

        try:
            # 1. Scrape player counts/uptime for all servers with scraping config
            if servers_with_scraping and not self._cancelled:
                print(f"[BatchScan] Starting scraping for {len(servers_with_scraping)} servers...")
                self.progress.emit(current_task, total_tasks, "Scraping player counts...")
                scrape_results = scrape_servers_sync(servers_with_scraping, timeout=10.0)
                print(f"[BatchScan] Scraping complete, got {len(scrape_results)} results")

                for server in servers_with_scraping:
                    if self._cancelled:
                        break

                    result = results[server.id]
                    if server.id in scrape_results:
                        scrape_result = scrape_results[server.id]
                        result.scrape_success = scrape_result.success
                        print(f"[BatchScan] {server.name}: scrape_success={scrape_result.success}")

                        if scrape_result.success:
                            data = {}
                            if scrape_result.total is not None:
                                data['total'] = scrape_result.total
                            if scrape_result.alliance is not None:
                                data['alliance_count'] = scrape_result.alliance
                            if scrape_result.horde is not None:
                                data['horde_count'] = scrape_result.horde
                            if scrape_result.uptime is not None:
                                data['uptime'] = scrape_result.uptime
                            result.scrape_data = data
                            print(f"[BatchScan] {server.name}: data={data}")
                        else:
                            result.scrape_error = scrape_result.error
                            print(f"[BatchScan] {server.name}: error={scrape_result.error}")
                    else:
                        print(f"[BatchScan] {server.name}: NO RESULT FOUND")

                    current_task += 1
                    self.progress.emit(current_task, total_tasks, f"Scraped {server.name}")

            # 2. Ping all servers with hosts (and worlds)
            if servers_with_host and not self._cancelled:
                print(f"[BatchScan] Starting pinging for {len(servers_with_host)} servers...")
                self.progress.emit(current_task, total_tasks, "Pinging servers...")
                ping_results = ping_multiple_servers_sync(servers_with_host, timeout=3.0)
                print(f"[BatchScan] Pinging complete, got {len(ping_results)} results")

                for server in servers_with_host:
                    if self._cancelled:
                        break

                    result = results[server.id]
                    if server.id in ping_results:
                        # ping_results returns (ServerStatus, latency_ms) tuples
                        status, latency_ms = ping_results[server.id]
                        result.ping_ms = latency_ms
                        result.ping_success = latency_ms >= 0
                        print(f"[BatchScan] {server.name}: ping={latency_ms}ms, success={latency_ms >= 0}")
                    else:
                        print(f"[BatchScan] {server.name}: NO PING RESULT")

                    # Also ping individual worlds if they exist
                    worlds = server.get_field('worlds', [])
                    if isinstance(worlds, list) and len(worlds) > 0:
                        print(f"[BatchScan] {server.name}: Found {len(worlds)} worlds to ping")
                        # Collect world hosts to ping
                        world_hosts = [world.get('host', '') for world in worlds if world.get('host')]

                        if world_hosts:
                            # Ping all world hosts
                            from pserver_manager.utils import ping_multiple_hosts_sync
                            from pserver_manager.models import ServerStatus as SS
                            world_ping_results = ping_multiple_hosts_sync(world_hosts, timeout=3.0)

                            # Store ping results in the world dicts
                            online_count = 0
                            for world in worlds:
                                world_host = world.get('host', '')
                                if world_host and world_host in world_ping_results:
                                    status, ping_ms = world_ping_results[world_host]
                                    world['_ping_status'] = status
                                    world['_ping_ms'] = ping_ms
                                    if status.name == 'ONLINE':
                                        online_count += 1
                                    print(f"[BatchScan]   - {world.get('name', 'Unknown')}: {ping_ms}ms")

                            # Store worlds data in result
                            result.worlds_data = worlds

                            # If this server only has worlds (no main host), update result with world info
                            if not server.host and online_count > 0:
                                # Use average ping of online worlds
                                online_pings = [w.get('_ping_ms', 0) for w in worlds
                                               if w.get('_ping_status') and w.get('_ping_status').name == 'ONLINE']
                                if online_pings:
                                    avg_ping = sum(online_pings) // len(online_pings)
                                    result.ping_ms = avg_ping
                                    result.ping_success = True
                                    print(f"[BatchScan] {server.name}: {online_count}/{len(worlds)} worlds online, avg={avg_ping}ms")

                    current_task += 1
                    self.progress.emit(current_task, total_tasks, f"Pinged {server.name}")

            # 3. Fetch Reddit posts for all servers with reddit
            if servers_with_reddit and not self._cancelled:
                print(f"[BatchScan] Starting Reddit fetch for {len(servers_with_reddit)} servers...")
                reddit_scraper = RedditScraper()

                for server in servers_with_reddit:
                    if self._cancelled:
                        break

                    self.progress.emit(current_task, total_tasks, f"Fetching Reddit for {server.name}...")
                    result = results[server.id]

                    try:
                        print(f"[BatchScan] Fetching Reddit for {server.name} (r/{server.reddit})...")
                        posts = reddit_scraper.fetch_hot_posts(server.reddit, limit=15)
                        result.reddit_posts = posts
                        print(f"[BatchScan] {server.name}: Got {len(posts)} Reddit posts")
                    except Exception as e:
                        result.reddit_error = str(e)
                        print(f"[BatchScan] {server.name}: Reddit error: {e}")

                    current_task += 1
                    self.progress.emit(current_task, total_tasks, f"Fetched Reddit for {server.name}")

            # 4. Fetch updates for all servers with updates_url
            if servers_with_updates and not self._cancelled:
                print(f"[BatchScan] Starting updates fetch for {len(servers_with_updates)} servers...")
                updates_scraper = UpdatesScraper()

                for server in servers_with_updates:
                    if self._cancelled:
                        break

                    self.progress.emit(current_task, total_tasks, f"Fetching updates for {server.name}...")
                    result = results[server.id]

                    try:
                        updates_limit = getattr(server, 'updates_limit', 10)
                        print(f"[BatchScan] Fetching updates for {server.name} (limit={updates_limit}, url={server.updates_url})...")

                        if server.updates_is_rss:
                            # RSS feed
                            updates = updates_scraper.fetch_rss_updates(server.updates_url, limit=updates_limit)
                        elif server.updates_forum_mode:
                            # Forum scraping
                            updates = updates_scraper.fetch_forum_threads(
                                url=server.updates_url,
                                thread_selector=server.updates_selectors.get("item", "li"),
                                title_selector=server.updates_selectors.get("title", "a"),
                                link_selector=server.updates_selectors.get("link", "a"),
                                time_selector=server.updates_selectors.get("time", "time"),
                                preview_selector=server.updates_selectors.get("preview", ""),
                                pagination_selector=server.updates_forum_pagination_selector,
                                page_limit=server.updates_forum_page_limit,
                                thread_limit=updates_limit,
                                use_js=server.updates_use_js,
                                fetch_thread_content=server.updates_fetch_thread_content,
                                thread_content_selector=server.updates_thread_content_selector,
                            )
                        else:
                            # Regular webpage scraping (including wiki mode)
                            updates = updates_scraper.fetch_updates(
                                url=server.updates_url,
                                use_js=server.updates_use_js,
                                item_selector=server.updates_selectors.get("item", "article"),
                                title_selector=server.updates_selectors.get("title", "h2, h3"),
                                link_selector=server.updates_selectors.get("link", "a"),
                                time_selector=server.updates_selectors.get("time", "time"),
                                preview_selector=server.updates_selectors.get("preview", "p"),
                                limit=updates_limit,
                                dropdown_selector=server.updates_selectors.get("dropdown"),
                                max_dropdown_options=server.updates_max_dropdown_options,
                                auto_detect_date=server.data.get('updates_auto_detect_date', False),
                                wiki_mode=server.data.get('updates_wiki_mode', False),
                                wiki_update_link_selector=server.data.get('updates_wiki_link_selector', "a[href*='/wiki/Updates/']"),
                                wiki_content_selector=server.data.get('updates_wiki_content_selector', ".mw-parser-output"),
                            )
                        result.updates = updates
                        print(f"[BatchScan] {server.name}: Got {len(updates)} updates")
                    except Exception as e:
                        result.updates_error = str(e)
                        print(f"[BatchScan] {server.name}: Updates error: {e}")

                    current_task += 1
                    self.progress.emit(current_task, total_tasks, f"Fetched updates for {server.name}")

            # Emit completion for each server
            if not self._cancelled:
                print(f"[BatchScan] Emitting completion for {len(results)} servers...")
                for server_id, result in results.items():
                    self.data_complete.emit(server_id, result)

                print("[BatchScan] All done, emitting finished signal")
                self.finished.emit(results)
        except Exception as e:
            print(f"[BatchScan] EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            self.error.emit(f"Batch data fetch error: {e}")


class BatchScanHelper(QObject):
    """Helper for managing batch data fetch worker and thread."""

    progress = Signal(int, int, str)  # current, total, task_description
    data_complete = Signal(str, object)  # server_id, ServerDataResult
    finished = Signal(dict)  # all_results: dict[server_id, ServerDataResult]
    error = Signal(str)

    def __init__(self):
        """Initialize batch scan helper."""
        super().__init__()
        self.worker = None
        self.thread = None

    def start_batch_fetch(self, servers: list[ServerDefinition], max_workers: int = 5):
        """Start batch data fetching for servers.

        Args:
            servers: List of servers to fetch data for
            max_workers: Maximum number of concurrent operations
        """
        # Clean up previous fetch if running
        self.stop_fetch()

        # Create worker and thread
        self.worker = BatchScanWorker(servers, max_workers)
        self.thread = QThread()

        # Move worker to thread
        self.worker.moveToThread(self.thread)

        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.progress.emit)
        self.worker.data_complete.connect(self.data_complete.emit)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self.error.emit)

        # Start thread
        self.thread.start()

    def stop_fetch(self):
        """Stop current data fetching."""
        if self.worker:
            self.worker.cancel()

        if self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait(2000)

        self.worker = None
        self.thread = None

    def _on_finished(self, results: dict):
        """Handle fetch completion.

        Args:
            results: Dictionary of server data results
        """
        self.finished.emit(results)

        # Clean up thread
        if self.thread:
            self.thread.quit()
            self.thread.wait()
