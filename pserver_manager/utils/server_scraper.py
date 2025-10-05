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

    def __init__(self, timeout: float = 10.0) -> None:
        """Initialize the scraper.

        Args:
            timeout: Timeout in seconds for HTTP requests
        """
        self.timeout = timeout
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

    async def scrape_server(
        self, server: ServerDefinition
    ) -> ServerScrapeResult:
        """Scrape server information.

        Args:
            server: Server definition with scraping config

        Returns:
            ServerScrapeResult with scraped data
        """
        # Support both 'scraping' and 'player_count' (backward compatibility)
        scraping_config = server.data.get("scraping") or server.data.get("player_count")
        if not scraping_config:
            return ServerScrapeResult(error="No scraping config found")

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
                    html = await self._fetch_with_browser(url)
                else:
                    html = await self._fetch_with_http(url)

                # Extract all fields from this HTML
                soup = BeautifulSoup(html, "lxml")
                for field_name, field_config in fields:
                    try:
                        if field_name in ["total", "alliance", "horde", "max_players"]:
                            value = self._extract_field(html, soup, field_config)
                        else:  # String fields like uptime
                            value = self._extract_string_field(html, soup, field_config)
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

            return result

        except Exception as e:
            return ServerScrapeResult(error=f"Scraping failed: {str(e)}")

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

        async with self._session.get(url) as response:
            response.raise_for_status()
            return await response.text()

    async def _fetch_with_browser(self, url: str) -> str:
        """Fetch page using browser automation (Playwright).

        Args:
            url: URL to fetch

        Returns:
            HTML content

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

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=self.timeout * 1000)
                html = await page.content()
                return html
            finally:
                await browser.close()

    def _extract_field(
        self, html: str, soup: BeautifulSoup, config: dict[str, Any]
    ) -> int | None:
        """Extract a single field using the configured method.

        Args:
            html: Raw HTML content
            soup: BeautifulSoup object
            config: Field extraction config

        Returns:
            Extracted integer value or None
        """
        # Try regex extraction first (works on raw HTML)
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
        self, html: str, soup: BeautifulSoup, config: dict[str, Any]
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
    servers: list[ServerDefinition], timeout: float = 10.0
) -> dict[str, ServerScrapeResult]:
    """Scrape server information for multiple servers concurrently.

    Args:
        servers: List of server definitions
        timeout: Timeout in seconds for each scrape

    Returns:
        Dictionary mapping server IDs to ServerScrapeResult
    """
    async with ServerScraper(timeout=timeout) as scraper:
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
    servers: list[ServerDefinition], timeout: float = 10.0
) -> dict[str, ServerScrapeResult]:
    """Synchronous wrapper for scraping server information.

    Args:
        servers: List of server definitions
        timeout: Timeout in seconds for each scrape

    Returns:
        Dictionary mapping server IDs to ServerScrapeResult
    """
    try:
        return asyncio.run(scrape_servers(servers, timeout))
    except RuntimeError:
        # If event loop is already running, create a new one
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(scrape_servers(servers, timeout))
        finally:
            loop.close()
