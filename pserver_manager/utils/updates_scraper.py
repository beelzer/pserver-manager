"""Updates scraper for fetching server updates from websites."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests
from bs4 import BeautifulSoup

# Optional Playwright import for JavaScript-rendered pages
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@dataclass
class ServerUpdate:
    """Represents a server update/news post."""

    title: str
    url: str
    time: str
    preview: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for display.

        Returns:
            Dictionary representation
        """
        return {
            "title": self.title,
            "url": self.url,
            "time": self.time,
            "preview": self.preview,
        }


class UpdatesScraper:
    """Scrapes server updates from websites."""

    def __init__(self, user_agent: str = "PServerManager/1.0"):
        """Initialize updates scraper.

        Args:
            user_agent: User agent string for requests
        """
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    def fetch_updates_with_dropdown(
        self,
        url: str,
        dropdown_selector: str = "select",
        item_selector: str = "article",
        title_selector: str = "h2, h3",
        link_selector: str = "a",
        time_selector: str = "time, .date, .time",
        preview_selector: str = "p",
        limit: int = 10,
        wait_time: int = 2000,
        max_dropdown_options: int | None = None,
    ) -> list[ServerUpdate]:
        """Fetch updates from a dropdown/form-based changelog using Playwright.

        Args:
            url: URL to scrape
            dropdown_selector: CSS selector for the dropdown/select element
            item_selector: CSS selector for update items
            title_selector: CSS selector for title (can select from dropdown option)
            link_selector: CSS selector for link within item
            time_selector: CSS selector for time/date (can select from dropdown option)
            preview_selector: CSS selector for preview text within item
            limit: Maximum number of updates to return (per dropdown option)
            wait_time: Time to wait after selecting dropdown option (milliseconds)
            max_dropdown_options: Maximum number of dropdown options to iterate

        Returns:
            List of ServerUpdate objects aggregated from all dropdown options
        """
        if not PLAYWRIGHT_AVAILABLE:
            print("Playwright not available. Install with: pip install playwright")
            return []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until='networkidle', timeout=15000)
                page.wait_for_timeout(1000)  # Initial wait

                all_updates = []

                # First, extract all dropdown option values (before any navigation)
                options = page.query_selector_all(f"{dropdown_selector} option")
                option_values = []
                for opt in options:
                    val = opt.get_attribute("value")
                    if val:
                        option_values.append(val)

                print(f"Found {len(option_values)} dropdown options")

                # Limit number of options if specified
                if max_dropdown_options:
                    option_values = option_values[:max_dropdown_options]

                # Now iterate through values, re-selecting dropdown each time
                for i, value in enumerate(option_values):
                    try:
                        print(f"Processing dropdown option {i+1}/{len(option_values)}: {value}")

                        # Select the option by value
                        page.select_option(dropdown_selector, value)

                        # Wait for page to reload/update (form submit causes navigation)
                        try:
                            page.wait_for_load_state('networkidle', timeout=10000)
                        except:
                            pass  # Continue even if timeout

                        page.wait_for_timeout(wait_time)

                        # Get page content
                        content = page.content()
                        soup = BeautifulSoup(content, 'html.parser')

                        # Parse updates from this option's content
                        updates = self._parse_updates_from_soup(
                            soup, url, item_selector, title_selector,
                            link_selector, time_selector, preview_selector, limit
                        )

                        all_updates.extend(updates)

                    except Exception as e:
                        print(f"Error processing dropdown option {i}: {e}")
                        continue

                browser.close()
                return all_updates

        except Exception as e:
            print(f"Error fetching updates with dropdown: {e}")
            return []

    def fetch_updates_with_js(
        self,
        url: str,
        item_selector: str = "article",
        title_selector: str = "h2, h3",
        link_selector: str = "a",
        time_selector: str = "time, .date, .time",
        preview_selector: str = "p",
        limit: int = 10,
        wait_time: int = 4000,
    ) -> list[ServerUpdate]:
        """Fetch updates from a JavaScript-rendered website using Playwright.

        Args:
            url: URL to scrape
            item_selector: CSS selector for update items
            title_selector: CSS selector for title within item
            link_selector: CSS selector for link within item
            time_selector: CSS selector for time/date within item
            preview_selector: CSS selector for preview text within item
            limit: Maximum number of updates to return
            wait_time: Time to wait for JS to render (milliseconds)

        Returns:
            List of ServerUpdate objects
        """
        if not PLAYWRIGHT_AVAILABLE:
            print("Playwright not available. Install with: pip install playwright")
            return []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until='networkidle', timeout=15000)
                page.wait_for_timeout(wait_time)

                content = page.content()
                browser.close()

                soup = BeautifulSoup(content, 'html.parser')
                return self._parse_updates_from_soup(
                    soup, url, item_selector, title_selector,
                    link_selector, time_selector, preview_selector, limit
                )
        except Exception as e:
            print(f"Error fetching updates with JavaScript: {e}")
            return []

    def _parse_updates_from_soup(
        self,
        soup: BeautifulSoup,
        base_url: str,
        item_selector: str,
        title_selector: str,
        link_selector: str,
        time_selector: str,
        preview_selector: str,
        limit: int,
    ) -> list[ServerUpdate]:
        """Parse updates from BeautifulSoup object.

        Args:
            soup: BeautifulSoup object
            base_url: Base URL for making relative links absolute
            item_selector: CSS selector for update items
            title_selector: CSS selector for title within item
            link_selector: CSS selector for link within item
            time_selector: CSS selector for time/date within item
            preview_selector: CSS selector for preview text within item
            limit: Maximum number of updates to return

        Returns:
            List of ServerUpdate objects
        """
        items = soup.select(item_selector)
        updates = []

        for item in items[:limit]:
            try:
                # Extract title
                title_elem = item.select_one(title_selector) if title_selector else None
                title = title_elem.get_text(strip=True) if title_elem else "Untitled"

                # Extract link
                link = ""
                if link_selector:
                    link_elem = item.select_one(link_selector)
                    if link_elem and link_elem.get("href"):
                        link = link_elem["href"]
                        # Make absolute URL if relative
                        if link.startswith("/"):
                            url_parts = base_url.split('/')
                            link = f"{url_parts[0]}//{url_parts[2]}{link}"
                        elif not link.startswith("http"):
                            link = f"{base_url.rstrip('/')}/{link.lstrip('/')}"

                # Extract time
                time_elem = item.select_one(time_selector) if time_selector else None
                time_str = "Unknown time"
                if time_elem:
                    # Try to get datetime attribute first
                    time_str = time_elem.get("datetime", time_elem.get_text(strip=True))

                # Extract preview
                preview_elem = item.select_one(preview_selector) if preview_selector else None
                preview = preview_elem.get_text(strip=True) if preview_elem else ""

                updates.append(
                    ServerUpdate(
                        title=title,
                        url=link or base_url,
                        time=time_str,
                        preview=preview,
                    )
                )
            except Exception as e:
                print(f"Error parsing update item: {e}")
                continue

        return updates

    def fetch_updates(
        self,
        url: str,
        item_selector: str = "article",
        title_selector: str = "h2, h3",
        link_selector: str = "a",
        time_selector: str = "time, .date, .time",
        preview_selector: str = "p",
        limit: int = 10,
        use_js: bool = False,
        dropdown_selector: str | None = None,
        max_dropdown_options: int | None = None,
    ) -> list[ServerUpdate]:
        """Fetch updates from a website.

        Args:
            url: URL to scrape
            item_selector: CSS selector for update items (e.g., "article", ".news-item")
            title_selector: CSS selector for title within item
            link_selector: CSS selector for link within item
            time_selector: CSS selector for time/date within item
            preview_selector: CSS selector for preview text within item
            limit: Maximum number of updates to return
            use_js: Whether to use Playwright for JavaScript-rendered pages
            dropdown_selector: CSS selector for dropdown (enables dropdown mode)
            max_dropdown_options: Max number of dropdown options to process

        Returns:
            List of ServerUpdate objects
        """
        # Dropdown mode requires JavaScript
        if dropdown_selector:
            return self.fetch_updates_with_dropdown(
                url, dropdown_selector, item_selector, title_selector,
                link_selector, time_selector, preview_selector, limit,
                max_dropdown_options=max_dropdown_options
            )

        if use_js:
            return self.fetch_updates_with_js(
                url, item_selector, title_selector, link_selector,
                time_selector, preview_selector, limit
            )

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            return self._parse_updates_from_soup(
                soup, url, item_selector, title_selector,
                link_selector, time_selector, preview_selector, limit
            )
        except requests.RequestException as e:
            print(f"Error fetching updates: {e}")
            return []
        except Exception as e:
            print(f"Error parsing updates: {e}")
            return []

    def fetch_rss_updates(self, rss_url: str, limit: int = 10) -> list[ServerUpdate]:
        """Fetch updates from an RSS feed.

        Args:
            rss_url: RSS feed URL
            limit: Maximum number of updates to return

        Returns:
            List of ServerUpdate objects
        """
        try:
            response = self.session.get(rss_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "xml")

            items = soup.find_all("item")[:limit]
            updates = []

            for item in items:
                try:
                    title = item.find("title")
                    title_text = title.get_text(strip=True) if title else "Untitled"

                    link = item.find("link")
                    link_text = link.get_text(strip=True) if link else rss_url

                    pub_date = item.find("pubDate")
                    time_str = pub_date.get_text(strip=True) if pub_date else "Unknown time"

                    description = item.find("description")
                    preview = ""
                    if description:
                        # Strip HTML from description
                        desc_soup = BeautifulSoup(description.get_text(), "html.parser")
                        preview = desc_soup.get_text(strip=True)

                    updates.append(
                        ServerUpdate(
                            title=title_text,
                            url=link_text,
                            time=time_str,
                            preview=preview,
                        )
                    )
                except Exception as e:
                    print(f"Error parsing RSS item: {e}")
                    continue

            return updates
        except requests.RequestException as e:
            print(f"Error fetching RSS feed: {e}")
            return []
        except Exception as e:
            print(f"Error parsing RSS feed: {e}")
            return []
