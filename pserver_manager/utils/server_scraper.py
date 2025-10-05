"""Server information scraping utility for WoW servers."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import aiohttp
from bs4 import BeautifulSoup


def normalize_uptime(uptime_str: str) -> str:
    """Normalize uptime to consistent short format (e.g., '4d12h35m').

    Args:
        uptime_str: Uptime string in various formats

    Returns:
        Normalized uptime string
    """
    if not uptime_str:
        return uptime_str

    # Extract numbers and their units
    # Matches patterns like: "4 d. 12 h. 35 m. 56 s.", "5 days 4 hours 51 minutes", etc.
    days = re.search(r'(\d+)\s*(?:d(?:ays?)?\.?)', uptime_str, re.IGNORECASE)
    hours = re.search(r'(\d+)\s*(?:h(?:ours?)?\.?)', uptime_str, re.IGNORECASE)
    minutes = re.search(r'(\d+)\s*(?:m(?:in(?:utes?)?)?\.?)', uptime_str, re.IGNORECASE)

    parts = []
    if days:
        parts.append(f"{days.group(1)}d")
    if hours:
        parts.append(f"{hours.group(1)}h")
    if minutes:
        parts.append(f"{minutes.group(1)}m")

    return ''.join(parts) if parts else uptime_str


if TYPE_CHECKING:
    from pserver_manager.config_loader import ServerDefinition


@dataclass
class ServerScrapeResult:
    """Result of server information scraping."""

    total: int | None = None
    alliance: int | None = None
    horde: int | None = None
    max_players: int | None = None
    uptime: str | None = None
    error: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Check if scraping was successful."""
        return self.error is None


class ScraperProgress:
    """Progress callback for scraping operations."""

    def __init__(self, callback=None):
        """Initialize with optional callback function."""
        self.callback = callback

    def update(self, message: str, step: int = 0, total_steps: int = 0):
        """Update progress."""
        if self.callback:
            self.callback(message, step, total_steps)


@dataclass
class ExtractionRule:
    """Rule for extracting data from HTML."""

    field: str
    regex: str | None = None
    css: str | None = None
    xpath: str | None = None
    extract_type: str = "text"  # text, attribute, next_sibling_text


class ServerScraper:
    """Scraper for extracting server information from websites."""

    # Cache for scraping results (server_id -> (result, timestamp))
    _cache: dict[str, tuple[ServerScrapeResult, float]] = {}
    _cache_duration: float = 300.0  # 5 minutes default

    def __init__(self, timeout: float = 10.0, progress: ScraperProgress | None = None, cache_duration: float = 300.0) -> None:
        """Initialize the scraper.

        Args:
            timeout: Timeout in seconds for HTTP requests
            progress: Optional progress callback
            cache_duration: Cache duration in seconds (default 5 minutes)
        """
        self.timeout = timeout
        self.progress = progress or ScraperProgress()
        self._cache_duration = cache_duration
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> ServerScraper:
        """Enter async context."""
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context."""
        if self._session:
            await self._session.close()
            self._session = None

    @classmethod
    def clear_cache(cls, server_id: str | None = None) -> None:
        """Clear cached scraping results.

        Args:
            server_id: Clear cache for specific server, or all if None
        """
        if server_id:
            cls._cache.pop(server_id, None)
        else:
            cls._cache.clear()

    @classmethod
    def get_cache_info(cls, server_id: str | None = None) -> dict:
        """Get cache information.

        Args:
            server_id: Get info for specific server, or all if None

        Returns:
            Dictionary with cache information
        """
        import time

        if server_id:
            if server_id in cls._cache:
                _, cached_time = cls._cache[server_id]
                age = int(time.time() - cached_time)
                return {server_id: {"age_seconds": age, "cached": True}}
            return {server_id: {"cached": False}}

        info = {}
        for sid, (_, cached_time) in cls._cache.items():
            age = int(time.time() - cached_time)
            info[sid] = {"age_seconds": age, "cached": True}
        return info

    async def scrape_server(
        self, server: ServerDefinition
    ) -> ServerScrapeResult:
        """Scrape server information.

        Args:
            server: Server definition with scraping config

        Returns:
            ServerScrapeResult with scraped data
        """
        import time

        # Support both 'scraping' and 'player_count' (backward compatibility)
        scraping_config = server.data.get("scraping") or server.data.get("player_count")
        if not scraping_config:
            return ServerScrapeResult(error="No scraping config found")

        # Get cache duration (per-server or default)
        cache_duration = scraping_config.get("cache_duration", self._cache_duration)

        # Check cache first
        if server.id in self._cache:
            cached_result, cached_time = self._cache[server.id]
            age = time.time() - cached_time
            if age < cache_duration:
                # Notify that we're using cached data
                self.progress.update(f"Using cached data ({int(age)}s old)", 1, 1)

                # Return cached result with age indicator
                cached_result.raw_data['cache_age_seconds'] = int(age)
                cached_result.raw_data['cache_duration'] = cache_duration
                return cached_result

        # Get default URL and settings
        default_url = scraping_config.get("url") or server.data.get("website")
        if not default_url:
            return ServerScrapeResult(error="No URL configured")

        default_use_browser = scraping_config.get("use_browser", False)

        try:
            # Group fields by their URL to minimize requests
            url_to_fields = {}
            all_field_names = ["total", "alliance", "horde", "max_players", "uptime"]

            for field_name in all_field_names:
                if field_name not in scraping_config:
                    continue

                field_config = scraping_config[field_name]
                if isinstance(field_config, str):
                    field_config = {"regex": field_config}

                # Get field-specific URL or use default
                field_url = field_config.get("url", default_url)
                field_use_browser = field_config.get("use_browser", default_use_browser)

                # Group by URL and browser setting
                key = (field_url, field_use_browser)
                if key not in url_to_fields:
                    url_to_fields[key] = []
                url_to_fields[key].append((field_name, field_config))

            # Fetch each unique URL once
            result = ServerScrapeResult()
            for (url, use_browser), fields in url_to_fields.items():
                if use_browser:
                    html, page_text = await self._fetch_with_browser(url)
                else:
                    html = await self._fetch_with_http(url)
                    page_text = None

                # Extract all fields from this HTML
                soup = BeautifulSoup(html, "lxml")
                for field_name, field_config in fields:
                    try:
                        if field_name in ["total", "alliance", "horde", "max_players"]:
                            value = self._extract_field(html, soup, field_config, page_text)
                        else:  # String fields like uptime
                            value = self._extract_string_field(html, soup, field_config, page_text)
                            # Normalize uptime format
                            if field_name == "uptime" and value:
                                value = normalize_uptime(value)

                        if value is not None:
                            setattr(result, field_name, value)
                            result.raw_data[field_name] = value
                    except Exception as e:
                        result.raw_data[f"{field_name}_error"] = str(e)

            # Calculate total from factions if needed
            if result.total is None and result.alliance is not None and result.horde is not None:
                result.total = result.alliance + result.horde

            # Cache successful results
            if result.success:
                import time
                self._cache[server.id] = (result, time.time())

            return result

        except Exception as e:
            error_msg = str(e)
            # Detect rate limiting
            if "too many requests" in error_msg.lower() or "rate limit" in error_msg.lower():
                # Return result with warning triangles instead of data
                result = ServerScrapeResult()
                result.raw_data['rate_limited'] = True
                result.raw_data['warning'] = '⚠️'
                result.error = f"Rate limited: {error_msg}"
                return result
            return ServerScrapeResult(error=f"Scraping failed: {error_msg}")

    async def _fetch_with_http(self, url: str) -> str:
        """Fetch page using HTTP request.

        Args:
            url: URL to fetch

        Returns:
            HTML content

        Raises:
            aiohttp.ClientError: If request fails
        """
        if not self._session:
            raise RuntimeError("Scraper not initialized (use async with)")

        self.progress.update("Fetching data...", 1, 2)
        async with self._session.get(url) as response:
            response.raise_for_status()
            html = await response.text()
            self.progress.update("Processing...", 2, 2)
            return html

    async def _fetch_with_browser(self, url: str) -> tuple[str, str]:
        """Fetch page using browser automation (Playwright).

        Args:
            url: URL to fetch

        Returns:
            Tuple of (HTML content, rendered page text)

        Raises:
            Exception: If browser automation fails
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "Playwright is required for browser automation. "
                "Install it with: playwright install"
            )

        self.progress.update("Launching browser...", 1, 5)
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']  # Faster startup
            )
            try:
                page = await browser.new_page()

                # Set shorter timeout for faster failure
                page.set_default_timeout(15000)  # 15 seconds max

                self.progress.update("Loading page...", 2, 5)
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)  # Faster than networkidle

                # Try to close cookie dialog (non-blocking)
                self.progress.update("Processing content...", 3, 5)
                try:
                    # Quick check for cookie dialogs (max 1 second)
                    cookie_button = page.locator('button:has-text("Accept"), button:has-text("Confirm"), button:has-text("OK")').first
                    await cookie_button.click(timeout=1000)
                    await asyncio.sleep(0.5)  # Brief wait after clicking
                except:
                    pass  # No dialog or timeout - continue

                # Wait for body to be ready (smarter than fixed sleep)
                self.progress.update("Extracting data...", 4, 5)
                try:
                    await page.wait_for_load_state("load", timeout=5000)
                except:
                    pass  # Continue even if timeout

                # Get content
                html = await page.content()
                page_text = await page.evaluate("document.body.innerText")

                # Get iframe text (parallel)
                iframe_tasks = []
                for frame in page.frames:
                    if frame != page.main_frame:
                        iframe_tasks.append(self._get_iframe_text(frame))

                if iframe_tasks:
                    iframe_texts = await asyncio.gather(*iframe_tasks, return_exceptions=True)
                    for text in iframe_texts:
                        if isinstance(text, str):
                            page_text += "\n" + text

                # Check for error messages in page content
                if "error loading data" in page_text.lower() or "error loading data from api" in page_text.lower():
                    raise Exception("Rate limited: Error loading data from API")

                self.progress.update("Complete!", 5, 5)
                return html, page_text
            finally:
                await browser.close()

    async def _get_iframe_text(self, frame) -> str:
        """Get text from an iframe safely.

        Args:
            frame: Playwright frame object

        Returns:
            Frame text content or empty string
        """
        try:
            return await frame.evaluate("document.body.innerText")
        except:
            return ""

    def _extract_field(
        self, html: str, soup: BeautifulSoup, config: dict[str, Any], page_text: str | None = None
    ) -> int | None:
        """Extract a single field using the configured method.

        Args:
            html: Raw HTML content
            soup: BeautifulSoup object
            config: Field extraction config
            page_text: Rendered page text (from browser)

        Returns:
            Extracted integer value or None
        """
        # If both CSS and regex are specified, use CSS first then apply regex to the element text
        if "css" in config and "regex" in config:
            elements = soup.select(config["css"])
            if elements:
                extract_type = config.get("extract", "text")
                text = self._extract_from_element(elements[0], extract_type)
                if text:
                    pattern = config["regex"]
                    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                    if match:
                        value_str = match.group(1) if match.groups() else match.group(0)
                        digits = re.search(r"\d+", value_str)
                        if digits:
                            return int(digits.group(0))
            return None

        # Try regex extraction on rendered page text first (if available)
        if "regex" in config and page_text:
            pattern = config["regex"]
            match = re.search(pattern, page_text, re.DOTALL | re.IGNORECASE)
            if match:
                value_str = match.group(1) if match.groups() else match.group(0)
                digits = re.search(r"\d+", value_str)
                if digits:
                    return int(digits.group(0))

        # Try regex extraction on raw HTML
        if "regex" in config:
            pattern = config["regex"]
            match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
            if match:
                # Try to extract integer from first group or entire match
                value_str = match.group(1) if match.groups() else match.group(0)
                # Extract digits from the string
                digits = re.search(r"\d+", value_str)
                if digits:
                    return int(digits.group(0))

        # Try CSS selector extraction
        if "css" in config:
            elements = soup.select(config["css"])
            if elements:
                extract_type = config.get("extract", "text")
                text = self._extract_from_element(elements[0], extract_type)
                if text:
                    digits = re.search(r"\d+", text)
                    if digits:
                        return int(digits.group(0))

        return None

    def _extract_string_field(
        self, html: str, soup: BeautifulSoup, config: dict[str, Any], page_text: str | None = None
    ) -> str | None:
        """Extract a string field using the configured method.

        Args:
            html: Raw HTML content
            soup: BeautifulSoup object
            config: Field extraction config

        Returns:
            Extracted string value or None
        """
        # Try regex extraction first (works on raw HTML)
        if "regex" in config:
            pattern = config["regex"]
            match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
            if match:
                # Return first group or entire match
                value_str = match.group(1) if match.groups() else match.group(0)
                return value_str.strip()

        # Try CSS selector extraction
        if "css" in config:
            elements = soup.select(config["css"])
            if elements:
                extract_type = config.get("extract", "text")
                text = self._extract_from_element(elements[0], extract_type)
                if text:
                    return text.strip()

        return None

    def _extract_from_element(self, element, extract_type: str) -> str | None:
        """Extract text from an element based on extract type.

        Args:
            element: BeautifulSoup element
            extract_type: Type of extraction (text, next_sibling_text, etc.)

        Returns:
            Extracted text or None
        """
        if extract_type == "text":
            return element.get_text(strip=True)
        elif extract_type == "next_sibling_text":
            # Get next sibling that contains text
            sibling = element.next_sibling
            while sibling:
                if isinstance(sibling, str):
                    text = sibling.strip()
                    if text:
                        return text
                elif hasattr(sibling, "get_text"):
                    text = sibling.get_text(strip=True)
                    if text:
                        return text
                sibling = sibling.next_sibling
        elif extract_type.startswith("attr:"):
            # Extract attribute value
            attr_name = extract_type.split(":", 1)[1]
            return element.get(attr_name)

        return None


async def scrape_servers(
    servers: list[ServerDefinition],
    timeout: float = 10.0,
    progress: ScraperProgress | None = None,
    use_thread: bool = False
) -> dict[str, ServerScrapeResult]:
    """Scrape server information for multiple servers concurrently.

    Args:
        servers: List of server definitions
        timeout: Timeout in seconds for each scrape
        progress: Optional progress callback
        use_thread: Run browser-based scraping in separate thread (prevents UI freezing)

    Returns:
        Dictionary mapping server IDs to ServerScrapeResult
    """
    if use_thread:
        # Run in thread pool to avoid blocking UI
        import concurrent.futures
        loop = asyncio.get_event_loop()

        def run_sync():
            """Run scraping in sync mode within thread."""
            return asyncio.run(_scrape_servers_internal(servers, timeout, progress))

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return await loop.run_in_executor(executor, run_sync)
    else:
        return await _scrape_servers_internal(servers, timeout, progress)


async def _scrape_servers_internal(
    servers: list[ServerDefinition], timeout: float, progress: ScraperProgress | None
) -> dict[str, ServerScrapeResult]:
    """Internal scraping implementation."""
    async with ServerScraper(timeout=timeout, progress=progress) as scraper:
        tasks = [scraper.scrape_server(server) for server in servers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = {}
        for server, result in zip(servers, results):
            if isinstance(result, Exception):
                output[server.id] = ServerScrapeResult(error=str(result))
            else:
                output[server.id] = result

        return output


def scrape_servers_sync(
    servers: list[ServerDefinition], timeout: float = 10.0, progress: ScraperProgress | None = None
) -> dict[str, ServerScrapeResult]:
    """Synchronous wrapper for scraping server information.

    Args:
        servers: List of server definitions
        timeout: Timeout in seconds for each scrape
        progress: Optional progress callback

    Returns:
        Dictionary mapping server IDs to ServerScrapeResult
    """
    try:
        return asyncio.run(scrape_servers(servers, timeout, progress))
    except RuntimeError:
        # If event loop is already running, create a new one
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(scrape_servers(servers, timeout, progress))
        finally:
            loop.close()
