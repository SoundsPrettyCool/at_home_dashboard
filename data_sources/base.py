"""
Abstract base class for all data sources.
"""

import re
from abc import ABC, abstractmethod

_COLOR_TAG_RE = re.compile(r"\{color:\w+\}|\{/color\}")


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
            return [self._truncate_preserving_tags(line, width) for line in lines[:height]]
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
    def _truncate_preserving_tags(text: str, width: int) -> str:
        """Truncate by visible length, keeping color tags intact."""
        if "{color:" not in text:
            return text[:width].ljust(width)

        result = []
        visible = 0
        i = 0
        in_tag = False
        tag_buf = []
        while i < len(text) and visible < width:
            ch = text[i]
            if ch == "{" and (text[i:].startswith("{color:") or text[i:].startswith("{/color}")):
                in_tag = True
                tag_buf = [ch]
            elif in_tag:
                tag_buf.append(ch)
                if ch == "}":
                    result.append("".join(tag_buf))
                    in_tag = False
                    tag_buf = []
            else:
                result.append(ch)
                visible += 1
            i += 1

        # Close any unclosed color tag
        out = "".join(result)
        if "{color:" in out and out.count("{color:") > out.count("{/color}"):
            out += "{/color}"

        return out

    @staticmethod
    def truncate(text: str, width: int) -> str:
        """Truncate text to width, adding ellipsis if needed."""
        visible_len = len(_COLOR_TAG_RE.sub("", text))
        if visible_len <= width:
            return text
        # Truncate by visible chars, preserving tags
        result = []
        visible = 0
        i = 0
        in_tag = False
        tag_buf = []
        while i < len(text) and visible < width - 1:
            ch = text[i]
            if ch == "{" and (text[i:].startswith("{color:") or text[i:].startswith("{/color}")):
                in_tag = True
                tag_buf = [ch]
            elif in_tag:
                tag_buf.append(ch)
                if ch == "}":
                    result.append("".join(tag_buf))
                    in_tag = False
                    tag_buf = []
            else:
                result.append(ch)
                visible += 1
            i += 1
        out = "".join(result)
        if "{color:" in out and out.count("{color:") > out.count("{/color}"):
            out += "{/color}"
        return out + "…"
