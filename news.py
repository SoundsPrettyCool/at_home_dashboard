"""
News data source using RSS feeds.

Fetches headlines from configurable RSS feeds. Defaults to AP News and Reuters.
No API key required.

Requires: pip install feedparser
"""

try:
    import feedparser

    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

import re

import requests

from .base import DataSource

DEFAULT_FEEDS = [
    ("AP", "https://rsshub.app/apnews/topics/apf-topnews"),
    ("Reuters", "https://rsshub.app/reuters/world"),
    ("NPR", "https://feeds.npr.org/1001/rss.xml"),
    ("BBC", "http://feeds.bbci.co.uk/news/rss.xml"),
]


# Fallback: parse RSS with basic XML if feedparser not available
def _parse_rss_simple(content: str) -> list[dict]:
    """Minimal RSS parser using regex (fallback)."""
    items = []
    for match in re.finditer(r"<item>(.*?)</item>", content, re.DOTALL):
        block = match.group(1)
        title_m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", block)
        pub_m = re.search(r"<pubDate>(.*?)</pubDate>", block)
        if title_m:
            items.append(
                {
                    "title": title_m.group(1).strip(),
                    "published": pub_m.group(1).strip() if pub_m else "",
                }
            )
    return items


class NewsDataSource(DataSource):
    name = "News"
    refresh_interval_seconds = 300  # 5 minutes

    def __init__(self, feeds: list[tuple[str, str]] | None = None, max_headlines: int = 15):
        """
        Args:
            feeds: List of (source_name, rss_url) tuples.
            max_headlines: Max headlines to keep.
        """
        super().__init__()
        self.feeds = feeds or DEFAULT_FEEDS
        self.max_headlines = max_headlines

    def fetch_data(self) -> list:
        headlines = []

        for source_name, url in self.feeds:
            try:
                resp = requests.get(url, timeout=10, headers={"User-Agent": "NYC-Dashboard/1.0"})
                resp.raise_for_status()

                if HAS_FEEDPARSER:
                    feed = feedparser.parse(resp.content)
                    for entry in feed.entries[:5]:
                        headlines.append(
                            {
                                "source": source_name,
                                "title": entry.get("title", "").strip(),
                                "time": entry.get("published", ""),
                            }
                        )
                else:
                    items = _parse_rss_simple(resp.text)
                    for item in items[:5]:
                        headlines.append(
                            {
                                "source": source_name,
                                "title": item["title"],
                                "time": item["published"],
                            }
                        )
            except Exception:
                continue

        return headlines[: self.max_headlines]

    def format_for_display(self, width: int, height: int) -> list[str]:
        data = self._cached_data
        if not data:
            return [" No news available"]

        lines: list[str] = []
        for item in data:
            if len(lines) >= height:
                break
            src = item["source"]
            title = item["title"]
            # Clean HTML entities
            title = title.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            title = title.replace("&#39;", "'").replace("&quot;", '"')

            line = f" [{src}] {title}"
            lines.append(self.truncate(line, width))

        return lines[:height]
