"""Updates scraper for fetching server updates from websites."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Optional Playwright import for JavaScript-rendered pages
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class UpdateNormalizer:
    """Utilities for normalizing update data to consistent formats."""

    # Standard output format for dates
    OUTPUT_DATE_FORMAT = "%B %d, %Y"  # e.g., "January 15, 2025"
    OUTPUT_DATETIME_FORMAT = "%B %d, %Y at %I:%M %p"  # e.g., "January 15, 2025 at 03:30 PM"

    # Common date formats to try parsing
    DATE_FORMATS = [
        # ISO 8601
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        # Common formats with full month names
        "%B %d, %Y",
        "%B %dth, %Y",
        "%B %dst, %Y",
        "%B %dnd, %Y",
        "%B %drd, %Y",
        # Common formats with abbreviated month names
        "%d %b %Y",
        "%b %d, %Y",
        "%d %B %Y",
        # US formats
        "%m/%d/%Y",
        "%m-%d-%Y",
        # European formats
        "%d/%m/%Y",
        "%d-%m-%Y",
    ]

    @staticmethod
    def parse_date(date_str: str) -> datetime | None:
        """Parse a date string into a datetime object.

        Args:
            date_str: Date string in various formats

        Returns:
            datetime object or None if parsing fails
        """
        if not date_str or date_str == "Unknown time":
            return None

        # Clean the string
        date_str = date_str.strip()

        # Remove ordinal suffixes (1st, 2nd, 3rd, 4th, etc.) for better parsing
        date_str = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)

        # Try each format
        for fmt in UpdateNormalizer.DATE_FORMATS:
            try:
                return datetime.strptime(date_str, fmt)
            except (ValueError, AttributeError):
                continue

        # If all parsing fails, try dateutil as fallback (if available)
        try:
            from dateutil import parser
            return parser.parse(date_str, fuzzy=True)
        except (ImportError, ValueError, AttributeError):
            pass

        return None

    @staticmethod
    def extract_dates_from_text(text: str) -> list[str]:
        """Extract all date-like strings from text.

        Args:
            text: Text to search for dates

        Returns:
            List of potential date strings found
        """
        if not text:
            return []

        dates = []

        # Pattern 1: MM/DD/YY or MM/DD/YYYY or DD/MM/YY or DD/MM/YYYY
        date_patterns = [
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # 10/04/25, 10-04-2025
            r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',    # 2025-10-04
            # Month name patterns
            r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
            r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
            r'\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b',  # October 4, 2025
            r'\b\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|'
            r'May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|'
            r'Dec(?:ember)?)\s+\d{4}\b',  # 4 October 2025
        ]

        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            dates.extend(matches)

        # Return unique dates, preserving order
        seen = set()
        unique_dates = []
        for date in dates:
            if date not in seen:
                seen.add(date)
                unique_dates.append(date)

        return unique_dates

    @staticmethod
    def format_date(dt: datetime | None, include_time: bool = False) -> str:
        """Format a datetime object to a consistent string format.

        Args:
            dt: datetime object to format
            include_time: Whether to include time in output

        Returns:
            Formatted date string or "Unknown date" if dt is None
        """
        if dt is None:
            return "Unknown date"

        if include_time and dt.hour != 0 and dt.minute != 0:
            return dt.strftime(UpdateNormalizer.OUTPUT_DATETIME_FORMAT)
        else:
            return dt.strftime(UpdateNormalizer.OUTPUT_DATE_FORMAT)

    @staticmethod
    def normalize_text(text: str, max_length: int | None = None) -> str:
        """Normalize text content.

        Args:
            text: Text to normalize
            max_length: Maximum length (adds ellipsis if exceeded)

        Returns:
            Normalized text
        """
        if not text:
            return ""

        # Strip HTML tags if present
        text = re.sub(r'<[^>]+>', '', text)

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        # Truncate if needed
        if max_length and len(text) > max_length:
            text = text[:max_length].rstrip() + "..."

        return text

    @staticmethod
    def strip_date_from_title(title: str) -> str:
        """Strip date patterns from title (common in forum posts).

        Removes date patterns like:
        - [July 25th, 2025] Title → Title
        - (July 25, 2025) Title → Title
        - [10/10/25] Title → Title
        - (MM/DD/YY) Title → Title
        - July 25, 2025 - Title → Title
        - Title - July 25, 2025 → Title

        Args:
            title: Title to clean

        Returns:
            Title with date patterns removed
        """
        if not title:
            return title

        # Pattern 1: [MM/DD/YY] or [MM/DD/YYYY] or similar numeric dates in brackets/parens at start
        # Matches: [10/10/25], [10-10-2025], (12/31/24), etc.
        title = re.sub(r'^[\[\(]\d{1,2}[/-]\d{1,2}[/-]\d{2,4}[\]\)]\s*[-|:–—]?\s*', '', title)

        # Pattern 2: [Date] or (Date) with 4-digit year at the start
        # Matches: [anything with 4-digit year], (anything with 4-digit year)
        title = re.sub(r'^[\[\(][^\]\)]*\d{4}[^\]\)]*[\]\)]\s*[-|:–—]?\s*', '', title)

        # Pattern 3: Date followed by separator at start
        # Matches: Month Day(ordinal), Year - or similar
        # Captures common month names (full or abbreviated) + day + year + separator
        title = re.sub(
            r'^(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
            r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+'
            r'\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\s*[-|:–—]\s*',
            '', title, flags=re.IGNORECASE
        )

        # Pattern 4: Separator followed by date at end
        # Matches: - July 25, 2025 at end
        title = re.sub(
            r'\s*[-|:–—]\s*(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
            r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+'
            r'\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}$',
            '', title, flags=re.IGNORECASE
        )

        # Pattern 5: Simple year in brackets/parens at start or end
        title = re.sub(r'^[\[\(]\d{4}[\]\)]\s*', '', title)
        title = re.sub(r'\s*[\[\(]\d{4}[\]\)]$', '', title)

        return title.strip()

    @staticmethod
    def normalize_url(url: str, base_url: str) -> str:
        """Normalize and make URLs absolute.

        Args:
            url: URL to normalize (may be relative)
            base_url: Base URL to resolve relative URLs against

        Returns:
            Absolute normalized URL
        """
        if not url:
            return base_url

        # Make absolute if relative
        url = urljoin(base_url, url)

        # Ensure valid scheme
        parsed = urlparse(url)
        if not parsed.scheme:
            url = "https://" + url

        return url


@dataclass
class ServerUpdate:
    """Represents a server update/news post with normalized data."""

    title: str
    url: str
    time_raw: str  # Raw time string from source
    preview: str = ""
    _parsed_date: datetime | None = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Parse and normalize data after initialization."""
        # Parse the date
        self._parsed_date = UpdateNormalizer.parse_date(self.time_raw)

        # Normalize text fields
        self.title = UpdateNormalizer.normalize_text(self.title)
        self.preview = UpdateNormalizer.normalize_text(self.preview)

        # Strip date patterns from title (common in forum posts like RuneX)
        self.title = UpdateNormalizer.strip_date_from_title(self.title)

    @property
    def time(self) -> str:
        """Get formatted time string.

        Returns:
            Consistently formatted date string
        """
        # Determine if original had time component
        has_time = ':' in self.time_raw or 'T' in self.time_raw
        return UpdateNormalizer.format_date(self._parsed_date, include_time=has_time)

    @property
    def date(self) -> datetime | None:
        """Get parsed datetime object.

        Returns:
            Parsed datetime or None if parsing failed
        """
        return self._parsed_date

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for display.

        Returns:
            Dictionary representation with normalized data
        """
        return {
            "title": self.title,
            "url": self.url,
            "time": self.time,  # Use the formatted property
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
        parallel_browsers: int = 4,
        auto_detect_date: bool = False,
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
            parallel_browsers: Number of parallel browser instances to use

        Returns:
            List of ServerUpdate objects aggregated from all dropdown options
        """
        if not PLAYWRIGHT_AVAILABLE:
            print("Playwright not available. Install with: pip install playwright")
            return []

        try:
            import concurrent.futures
            import threading

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until='networkidle', timeout=15000)
                page.wait_for_timeout(1000)  # Initial wait

                # First, extract all dropdown option values (before any navigation)
                options = page.query_selector_all(f"{dropdown_selector} option")
                option_values = []
                for opt in options:
                    val = opt.get_attribute("value")
                    if val:
                        option_values.append(val)

                page.close()

                print(f"Found {len(option_values)} dropdown options")

                # Limit number of options if specified
                if max_dropdown_options:
                    option_values = option_values[:max_dropdown_options]

                print(f"Processing {len(option_values)} options with {parallel_browsers} parallel browsers")

                all_updates = []
                updates_lock = threading.Lock()

                def process_option(value_index_tuple):
                    i, value = value_index_tuple
                    try:
                        # Each thread creates its own playwright context and browser
                        # This prevents greenlet threading issues
                        with sync_playwright() as p:
                            browser = p.chromium.launch(headless=True)
                            page = browser.new_page()
                            page.goto(url, wait_until='networkidle', timeout=15000)
                            page.wait_for_timeout(500)

                            print(f"Processing dropdown option {i+1}/{len(option_values)}: {value}")

                            # Select the option by value
                            page.select_option(dropdown_selector, value)

                            # Wait for page to reload/update
                            try:
                                page.wait_for_load_state('networkidle', timeout=10000)
                            except:
                                pass

                            page.wait_for_timeout(wait_time)

                            # Get page content
                            content = page.content()
                            soup = BeautifulSoup(content, 'html.parser')

                            # Parse updates from this option's content
                            updates = self._parse_updates_from_soup(
                                soup, url, item_selector, title_selector,
                                link_selector, time_selector, preview_selector, limit,
                                auto_detect_date=auto_detect_date
                            )

                            page.close()
                            browser.close()

                            # Thread-safe append
                            with updates_lock:
                                all_updates.extend(updates)

                    except Exception as e:
                        print(f"Error processing dropdown option {i}: {e}")

                # Process in parallel using thread pool
                # Each thread has its own browser so no shared browser to close
                with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_browsers) as executor:
                    executor.map(process_option, enumerate(option_values))

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
        auto_detect_date: bool = False,
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
            auto_detect_date: If True, scan update content for dates if time selector fails

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
                    link_selector, time_selector, preview_selector, limit,
                    auto_detect_date=auto_detect_date
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
        auto_detect_date: bool = False,
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
            auto_detect_date: If True, scan update content for dates if time selector fails

        Returns:
            List of ServerUpdate objects with normalized data
        """
        items = soup.select(item_selector)
        updates = []

        for item in items[:limit]:
            try:
                # Extract title
                title_elem = item.select_one(title_selector) if title_selector else None
                title = title_elem.get_text(strip=True) if title_elem else ""

                # Extract link
                link = ""
                if link_selector:
                    link_elem = item.select_one(link_selector)
                    if link_elem and link_elem.get("href"):
                        link = link_elem["href"]

                # Normalize URL
                link = UpdateNormalizer.normalize_url(link, base_url)

                # Extract time
                time_elem = item.select_one(time_selector) if time_selector else None
                time_str = "Unknown time"
                if time_elem:
                    # Try to get datetime attribute first
                    time_str = time_elem.get("datetime", time_elem.get_text(strip=True))

                # Auto-detect date if enabled and (time not found OR time cannot be parsed)
                should_auto_detect = auto_detect_date and (
                    time_str == "Unknown time"
                    or not time_str
                    or UpdateNormalizer.parse_date(time_str) is None
                )

                if should_auto_detect:
                    # Get all text from the update item
                    item_text = item.get_text(separator=' ', strip=True)

                    # Extract all dates from the text
                    found_dates = UpdateNormalizer.extract_dates_from_text(item_text)

                    # If exactly one date found, use it
                    if len(found_dates) == 1:
                        time_str = found_dates[0]
                        print(f"Auto-detected date: {time_str}")
                    elif len(found_dates) > 1:
                        # Multiple dates found - use the first parseable one
                        for date_candidate in found_dates:
                            if UpdateNormalizer.parse_date(date_candidate):
                                time_str = date_candidate
                                print(f"Auto-detected date (multiple found, using first valid): {time_str}")
                                break

                # Extract preview
                preview_elem = item.select_one(preview_selector) if preview_selector else None
                preview = preview_elem.get_text(strip=True) if preview_elem else ""

                # Handle cases where title is empty or is the same as date
                # (e.g., Vidyascape where the date is used as the header)
                if not title or title == time_str:
                    # Use first meaningful line of preview as title if available
                    if preview:
                        # Split preview into lines and find first meaningful line
                        lines = [l.strip() for l in preview.split('\n') if l.strip()]
                        if lines:
                            first_line = lines[0]
                            # Use first line as title (truncate if too long)
                            title = first_line if len(first_line) <= 60 else first_line[:57] + "..."
                        else:
                            title = "Patch Notes"
                    else:
                        title = "Patch Notes"

                # Create update (normalization happens in __post_init__)
                updates.append(
                    ServerUpdate(
                        title=title,
                        url=link,
                        time_raw=time_str,
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
        forum_mode: bool = False,
        forum_pagination_selector: str = ".ipsPagination_next",
        forum_page_limit: int = 1,
        fetch_thread_content: bool = False,
        thread_content_selector: str = "",
        auto_detect_date: bool = False,
        wiki_mode: bool = False,
        wiki_update_link_selector: str = "a[href*='/wiki/Updates/']",
        wiki_content_selector: str = ".mw-parser-output",
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
            forum_mode: Whether to scrape forum threads (enables pagination)
            forum_pagination_selector: CSS selector for next page link in forum mode
            forum_page_limit: Maximum number of forum pages to scrape
            auto_detect_date: If True, scan update content for dates if time selector fails
            wiki_mode: Whether to scrape MediaWiki-based updates
            wiki_update_link_selector: CSS selector for update page links in wiki mode
            wiki_content_selector: CSS selector for content within wiki update pages

        Returns:
            List of ServerUpdate objects
        """
        # Wiki mode
        if wiki_mode:
            return self.fetch_wiki_updates(
                url,
                update_link_selector=wiki_update_link_selector,
                update_content_selector=wiki_content_selector,
                limit=limit,
            )

        # Forum mode
        if forum_mode:
            return self.fetch_forum_threads(
                url,
                thread_selector=item_selector,
                title_selector=title_selector,
                link_selector=link_selector,
                time_selector=time_selector,
                preview_selector=preview_selector,
                pagination_selector=forum_pagination_selector,
                page_limit=forum_page_limit,
                thread_limit=limit,
                use_js=use_js,
                fetch_thread_content=fetch_thread_content,
                thread_content_selector=thread_content_selector,
            )

        # Dropdown mode requires JavaScript
        if dropdown_selector:
            return self.fetch_updates_with_dropdown(
                url, dropdown_selector, item_selector, title_selector,
                link_selector, time_selector, preview_selector, limit,
                max_dropdown_options=max_dropdown_options,
                auto_detect_date=auto_detect_date
            )

        if use_js:
            return self.fetch_updates_with_js(
                url, item_selector, title_selector, link_selector,
                time_selector, preview_selector, limit,
                auto_detect_date=auto_detect_date
            )

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            return self._parse_updates_from_soup(
                soup, url, item_selector, title_selector,
                link_selector, time_selector, preview_selector, limit,
                auto_detect_date=auto_detect_date
            )
        except requests.RequestException as e:
            print(f"Error fetching updates: {e}")
            return []
        except Exception as e:
            print(f"Error parsing updates: {e}")
            return []

    def _fetch_thread_content(self, thread_url: str, content_selector: str) -> str:
        """Fetch content from a forum thread page.

        Args:
            thread_url: URL of the thread
            content_selector: CSS selector for the post content

        Returns:
            Thread content as string
        """
        try:
            response = self.session.get(thread_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            # Get the first post content
            content_elem = soup.select_one(content_selector)
            if content_elem:
                return content_elem.get_text(strip=True)
            return ""
        except Exception as e:
            print(f"Error fetching thread content from {thread_url}: {e}")
            return ""

    def fetch_forum_threads(
        self,
        url: str,
        thread_selector: str = "li",
        title_selector: str = ".ipsDataItem_title a",
        link_selector: str = ".ipsDataItem_title a",
        time_selector: str = "time",
        preview_selector: str = "",
        pagination_selector: str = ".ipsPagination_next",
        page_limit: int = 1,
        thread_limit: int = 20,
        use_js: bool = False,
        fetch_thread_content: bool = False,
        thread_content_selector: str = "",
    ) -> list[ServerUpdate]:
        """Fetch updates from forum threads across multiple pages.

        Args:
            url: Forum URL to scrape
            thread_selector: CSS selector for thread container/item
            title_selector: CSS selector for thread title
            link_selector: CSS selector for thread link
            time_selector: CSS selector for thread date/time
            preview_selector: CSS selector for thread preview/excerpt (optional)
            pagination_selector: CSS selector for next page link
            page_limit: Maximum number of pages to scrape
            thread_limit: Maximum total number of threads to return
            use_js: Whether to use Playwright for JavaScript-rendered forums
            fetch_thread_content: Whether to fetch full content from thread pages
            thread_content_selector: CSS selector for content within thread page

        Returns:
            List of ServerUpdate objects representing forum threads
        """
        all_threads = []
        current_url = url
        pages_scraped = 0

        while current_url and pages_scraped < page_limit and len(all_threads) < thread_limit:
            try:
                print(f"Scraping forum page {pages_scraped + 1}: {current_url}")

                if use_js:
                    if not PLAYWRIGHT_AVAILABLE:
                        print("Playwright not available. Install with: pip install playwright")
                        break

                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=True)
                        page = browser.new_page()
                        page.goto(current_url, wait_until='networkidle', timeout=15000)
                        page.wait_for_timeout(2000)
                        content = page.content()
                        browser.close()
                        soup = BeautifulSoup(content, 'html.parser')
                else:
                    response = self.session.get(current_url, timeout=10)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, "html.parser")

                # Extract threads from current page
                threads = soup.select(thread_selector)
                print(f"Found {len(threads)} threads on page {pages_scraped + 1}")

                for thread in threads:
                    if len(all_threads) >= thread_limit:
                        break

                    try:
                        # Extract title
                        title_elem = thread.select_one(title_selector) if title_selector else None
                        title = title_elem.get_text(strip=True) if title_elem else ""

                        # Extract link
                        link = ""
                        if link_selector:
                            link_elem = thread.select_one(link_selector)
                            if link_elem and link_elem.get("href"):
                                link = link_elem["href"]

                        # Normalize URL
                        link = UpdateNormalizer.normalize_url(link, current_url)

                        # Extract time
                        time_elem = thread.select_one(time_selector) if time_selector else None
                        time_str = "Unknown time"
                        if time_elem:
                            # Try to get datetime attribute first, then text content
                            time_str = time_elem.get("datetime", time_elem.get_text(strip=True))

                        # Extract preview
                        preview = ""
                        if preview_selector:
                            preview_elem = thread.select_one(preview_selector)
                            preview = preview_elem.get_text(strip=True) if preview_elem else ""

                        # Fetch full thread content if enabled
                        if fetch_thread_content and thread_content_selector and link:
                            print(f"Fetching thread content from: {link}")
                            thread_content = self._fetch_thread_content(link, thread_content_selector)
                            if thread_content:
                                preview = thread_content

                        # Handle cases where title is empty or is the same as date
                        if not title or title == time_str:
                            # Use first meaningful line of preview as title if available
                            if preview:
                                # Split preview into lines and find first meaningful line
                                lines = [l.strip() for l in preview.split('\n') if l.strip()]
                                if lines:
                                    first_line = lines[0]
                                    # Use first line as title (truncate if too long)
                                    title = first_line if len(first_line) <= 60 else first_line[:57] + "..."
                                else:
                                    title = "Patch Notes"
                            else:
                                title = "Patch Notes"

                        # Create update (normalization happens in __post_init__)
                        all_threads.append(
                            ServerUpdate(
                                title=title,
                                url=link,
                                time_raw=time_str,
                                preview=preview,
                            )
                        )
                    except Exception as e:
                        print(f"Error parsing forum thread: {e}")
                        continue

                pages_scraped += 1

                # Check if we've reached the thread limit
                if len(all_threads) >= thread_limit:
                    break

                # Find next page link
                if pagination_selector:
                    next_link = soup.select_one(pagination_selector)
                    if next_link and next_link.get("href"):
                        next_url = next_link["href"]
                        # Make absolute URL if relative
                        if next_url.startswith("/"):
                            url_parts = url.split('/')
                            current_url = f"{url_parts[0]}//{url_parts[2]}{next_url}"
                        elif not next_url.startswith("http"):
                            current_url = f"{url.rstrip('/')}/{next_url.lstrip('/')}"
                        else:
                            current_url = next_url
                    else:
                        current_url = None  # No more pages
                else:
                    current_url = None  # Pagination not configured

            except requests.RequestException as e:
                print(f"Error fetching forum page: {e}")
                break
            except Exception as e:
                print(f"Error parsing forum page: {e}")
                break

        print(f"Scraped {len(all_threads)} total threads from {pages_scraped} pages")
        return all_threads[:thread_limit]

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
                    title_text = title.get_text(strip=True) if title else ""

                    link = item.find("link")
                    link_text = link.get_text(strip=True) if link else ""

                    # Normalize URL
                    link_text = UpdateNormalizer.normalize_url(link_text, rss_url)

                    pub_date = item.find("pubDate")
                    time_str = pub_date.get_text(strip=True) if pub_date else "Unknown time"

                    description = item.find("description")
                    preview = ""
                    if description:
                        # Get description text (HTML will be stripped by normalizer)
                        preview = description.get_text()

                    # Handle cases where title is empty or is the same as date
                    if not title_text or title_text == time_str:
                        # Use first meaningful line of preview as title if available
                        if preview:
                            # Split preview into lines and find first meaningful line
                            lines = [l.strip() for l in preview.split('\n') if l.strip()]
                            if lines:
                                first_line = lines[0]
                                # Use first line as title (truncate if too long)
                                title_text = first_line if len(first_line) <= 60 else first_line[:57] + "..."
                            else:
                                title_text = "Patch Notes"
                        else:
                            title_text = "Patch Notes"

                    # Create update (normalization happens in __post_init__)
                    updates.append(
                        ServerUpdate(
                            title=title_text,
                            url=link_text,
                            time_raw=time_str,
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

    def fetch_wiki_updates(
        self,
        wiki_url: str,
        update_link_selector: str = "a[href*='/wiki/Updates/']",
        update_content_selector: str = ".mw-parser-output",
        limit: int = 10,
        title_from_url: bool = True,
    ) -> list[ServerUpdate]:
        """Fetch updates from a MediaWiki-based update listing.

        Args:
            wiki_url: Wiki main page URL containing update links
            update_link_selector: CSS selector for update page links
            update_content_selector: CSS selector for content within update pages
            limit: Maximum number of updates to return
            title_from_url: Extract date from URL path (e.g., Updates/2025-09-26)

        Returns:
            List of ServerUpdate objects
        """
        try:
            # Fetch the main wiki page with update links
            response = self.session.get(wiki_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            # Find all update links
            update_links = soup.select(update_link_selector)
            print(f"Found {len(update_links)} update links on wiki page")

            updates = []
            for link in update_links[:limit]:
                try:
                    update_url = link.get("href", "")
                    if not update_url:
                        continue

                    # Make absolute URL
                    update_url = UpdateNormalizer.normalize_url(update_url, wiki_url)

                    # Extract date from URL if enabled (e.g., /wiki/Updates/2025-09-26)
                    time_str = "Unknown time"
                    if title_from_url:
                        # Extract date from URL path
                        url_match = re.search(r'/Updates/(\d{4}-\d{1,2}-\d{1,2})', update_url)
                        if url_match:
                            time_str = url_match.group(1)

                    # Get the link text as potential title
                    link_text = link.get_text(strip=True)

                    print(f"Fetching wiki update from: {update_url}")

                    # Fetch the update page content
                    update_response = self.session.get(update_url, timeout=10)
                    update_response.raise_for_status()
                    update_soup = BeautifulSoup(update_response.content, "html.parser")

                    # Get the main content
                    content_elem = update_soup.select_one(update_content_selector)
                    if not content_elem:
                        print(f"Warning: No content found for {update_url}")
                        continue

                    # Remove table of contents and navigation elements
                    for toc in content_elem.select("#toc, .toc, .mw-editsection"):
                        toc.decompose()

                    # Get all text content
                    preview = content_elem.get_text(separator=' ', strip=True)

                    # Try to find a better title from the first heading in content
                    first_heading = content_elem.select_one("h1, h2")
                    if first_heading:
                        title = first_heading.get_text(strip=True)
                    else:
                        # Fallback to link text
                        title = link_text if link_text else "Update"

                    # Create update (normalization happens in __post_init__)
                    updates.append(
                        ServerUpdate(
                            title=title,
                            url=update_url,
                            time_raw=time_str,
                            preview=preview,
                        )
                    )

                except Exception as e:
                    print(f"Error fetching wiki update page: {e}")
                    continue

            return updates

        except requests.RequestException as e:
            print(f"Error fetching wiki main page: {e}")
            return []
        except Exception as e:
            print(f"Error parsing wiki updates: {e}")
            return []
