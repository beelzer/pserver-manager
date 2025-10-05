"""Reddit scraper for fetching subreddit posts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests


@dataclass
class RedditPost:
    """Represents a Reddit post."""

    title: str
    author: str
    url: str
    score: int
    num_comments: int
    created_utc: float
    selftext: str = ""
    permalink: str = ""
    stickied: bool = False

    @property
    def time_ago(self) -> str:
        """Get human-readable time since post was created."""
        now = datetime.now(timezone.utc)
        created = datetime.fromtimestamp(self.created_utc, timezone.utc)
        diff = now - created

        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds >= 3600:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds >= 60:
            return f"{diff.seconds // 60}m ago"
        else:
            return "just now"

    @property
    def full_url(self) -> str:
        """Get full Reddit URL."""
        return f"https://reddit.com{self.permalink}"


class RedditScraper:
    """Scrapes Reddit posts from a subreddit."""

    def __init__(self, user_agent: str = "PServerManager/1.0"):
        """Initialize Reddit scraper.

        Args:
            user_agent: User agent string for requests
        """
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    def fetch_hot_posts(self, subreddit: str, limit: int = 10) -> list[RedditPost]:
        """Fetch hot posts from a subreddit.

        Args:
            subreddit: Subreddit name (without r/ prefix)
            limit: Number of posts to fetch (max 100)

        Returns:
            List of RedditPost objects
        """
        url = f"https://www.reddit.com/r/{subreddit}/hot.json"
        params = {"limit": min(limit, 100)}

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            posts = []
            for child in data.get("data", {}).get("children", []):
                post_data = child.get("data", {})
                posts.append(
                    RedditPost(
                        title=post_data.get("title", ""),
                        author=post_data.get("author", ""),
                        url=post_data.get("url", ""),
                        score=post_data.get("score", 0),
                        num_comments=post_data.get("num_comments", 0),
                        created_utc=post_data.get("created_utc", 0),
                        selftext=post_data.get("selftext", ""),
                        permalink=post_data.get("permalink", ""),
                        stickied=post_data.get("stickied", False),
                    )
                )

            return posts
        except requests.RequestException as e:
            print(f"Error fetching Reddit posts: {e}")
            return []
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing Reddit response: {e}")
            return []

    def fetch_new_posts(self, subreddit: str, limit: int = 10) -> list[RedditPost]:
        """Fetch new posts from a subreddit.

        Args:
            subreddit: Subreddit name (without r/ prefix)
            limit: Number of posts to fetch (max 100)

        Returns:
            List of RedditPost objects
        """
        url = f"https://www.reddit.com/r/{subreddit}/new.json"
        params = {"limit": min(limit, 100)}

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            posts = []
            for child in data.get("data", {}).get("children", []):
                post_data = child.get("data", {})
                posts.append(
                    RedditPost(
                        title=post_data.get("title", ""),
                        author=post_data.get("author", ""),
                        url=post_data.get("url", ""),
                        score=post_data.get("score", 0),
                        num_comments=post_data.get("num_comments", 0),
                        created_utc=post_data.get("created_utc", 0),
                        selftext=post_data.get("selftext", ""),
                        permalink=post_data.get("permalink", ""),
                        stickied=post_data.get("stickied", False),
                    )
                )

            return posts
        except requests.RequestException as e:
            print(f"Error fetching Reddit posts: {e}")
            return []
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing Reddit response: {e}")
            return []
