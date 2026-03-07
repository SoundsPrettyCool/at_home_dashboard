"""
Abstract base class for all data sources.
"""

from abc import ABC, abstractmethod


class DataSource(ABC):
    """
    Base class for all data sources.

    To create a new data source:
    1. Subclass DataSource
    2. Set `name` and `refresh_interval_seconds`
    3. Implement `fetch_data()` to pull raw data (from API, RSS, scraping, etc.)
    4. Implement `format_for_display(width, height)` to return a list of strings
       that fit within the given terminal panel dimensions.
    """

    name: str = "Unnamed Source"
    refresh_interval_seconds: int = 60

    def __init__(self):
        self._cached_data = None
        self._last_error: str | None = None

    @abstractmethod
    def fetch_data(self) -> dict | list | None:
        """
        Fetch raw data from the source (API, RSS, file, etc.).
        Returns structured data or None on failure.
        """
        ...

    @abstractmethod
    def format_for_display(self, width: int, height: int) -> list[str]:
        """
        Format cached data into lines of text that fit in (width x height).
        Each string in the list is one line. Truncate/pad to `width`.
        Return at most `height` lines.
        """
        ...

    def refresh(self) -> None:
        """Fetch new data and cache it. Captures errors gracefully."""
        try:
            self._cached_data = self.fetch_data()
            self._last_error = None
        except Exception as e:
            self._last_error = str(e)

    def get_display_lines(self, width: int, height: int) -> list[str]:
        """Return formatted lines, or error/loading message if unavailable."""
        if self._last_error:
            return self._wrap_lines(f"[Error: {self._last_error}]", width, height)
        if self._cached_data is None:
            return self._wrap_lines("Loading...", width, height)
        try:
            lines = self.format_for_display(width, height)
            return [line[:width].ljust(width) for line in lines[:height]]
        except Exception as e:
            return self._wrap_lines(f"[Display Error: {e}]", width, height)

    @staticmethod
    def _wrap_lines(msg: str, width: int, height: int) -> list[str]:
        """Wrap a simple message into padded lines."""
        lines = []
        while msg and len(lines) < height:
            lines.append(msg[:width].ljust(width))
            msg = msg[width:]
        while len(lines) < height:
            lines.append(" " * width)
        return lines

    @staticmethod
    def truncate(text: str, width: int) -> str:
        """Truncate text to width, adding ellipsis if needed."""
        if len(text) <= width:
            return text
        return text[: width - 1] + "…"
