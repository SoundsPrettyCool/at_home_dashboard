#!/usr/bin/env python3
"""
NYC Terminal Dashboard
======================

A modular, auto-refreshing terminal dashboard with a 2x2 grid layout.

Layout:
  ┌───────────────────┬───────────────────┐
  │   NYC Subway      │     Weather       │
  │   (top-left)      │     (top-right)   │
  ├───────────────────┼───────────────────┤
  │   Baseball        │     News          │
  │   (bottom-left)   │     (bottom-right)│
  └───────────────────┴───────────────────┘

Usage:
    python dashboard.py

    # With custom watched subway stops:
    python dashboard.py --stops 120N:"96 St Uptown" A27N:"59 St Columbus"

Requirements:
    pip install requests gtfs-realtime-bindings feedparser

Press 'q' to quit, 'r' to force refresh.
"""

import argparse
import curses
import re
import threading
import time
from datetime import datetime

from data_sources import SOURCES
from data_sources.base import DataSource

# Regex to parse {color:name}...{/color} markers
_COLOR_TAG_RE = re.compile(r"\{color:(\w+)\}(.*?)\{/color\}")

# Named colors -> curses color pair IDs (initialized in run())
COLOR_PAIR_MAP = {
    "blue": 10,
    "orange": 11,
    "green": 12,
    "red": 13,
    "yellow": 14,
    "magenta": 15,
    "gray": 16,
}


class DashboardPanel:
    """Represents one panel in the grid with a data source and position."""

    def __init__(self, source: DataSource, title: str, row: int, col: int, rowspan: int = 1):
        self.source = source
        self.title = title
        self.row = row  # 0 = top, 1 = bottom
        self.col = col  # 0 = left, 1 = right
        self.rowspan = rowspan  # how many rows this panel spans


class Dashboard:
    """Main dashboard controller: manages panels, refresh cycles, and rendering."""

    def __init__(self, panels: list[DashboardPanel], refresh_interval: int = 60):
        self.panels = panels
        self.refresh_interval = refresh_interval
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._last_refresh = 0.0

    def _refresh_all(self):
        """Refresh all data sources in parallel threads."""
        threads = []
        for panel in self.panels:
            t = threading.Thread(target=panel.source.refresh, daemon=True)
            threads.append(t)
            t.start()
        for t in threads:
            t.join(timeout=30)
        self._last_refresh = time.time()

    def _background_refresh(self):
        """Background thread that refreshes data periodically."""
        while not self._stop_event.is_set():
            with self._lock:
                self._refresh_all()
            self._stop_event.wait(self.refresh_interval)

    def run(self, stdscr):
        """Main curses loop."""
        curses.curs_set(0)  # Hide cursor
        stdscr.timeout(1000)  # getch timeout = 1s (for responsive key handling)
        stdscr.nodelay(True)

        # Init color pairs
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)  # Title
        curses.init_pair(2, curses.COLOR_GREEN, -1)  # Border
        curses.init_pair(3, curses.COLOR_YELLOW, -1)  # Status bar
        curses.init_pair(4, curses.COLOR_WHITE, -1)  # Content

        # Subway line colors (use 256-color orange if supported)
        curses.init_pair(10, curses.COLOR_BLUE, -1)
        if curses.COLORS >= 256:
            curses.init_color(20, 1000, 600, 0)  # true orange
            curses.init_pair(11, 20, -1)
        else:
            curses.init_pair(11, curses.COLOR_YELLOW, -1)
        curses.init_pair(12, curses.COLOR_GREEN, -1)
        curses.init_pair(13, curses.COLOR_RED, -1)
        curses.init_pair(14, curses.COLOR_YELLOW, -1)
        curses.init_pair(15, curses.COLOR_MAGENTA, -1)
        curses.init_pair(16, curses.COLOR_WHITE, -1)  # gray (closest in 8-color)

        # Initial fetch
        self._refresh_all()

        # Start background refresh thread
        refresh_thread = threading.Thread(target=self._background_refresh, daemon=True)
        refresh_thread.start()

        try:
            while True:
                # Handle input
                key = stdscr.getch()
                if key == ord("q") or key == ord("Q"):
                    break
                elif key == ord("r") or key == ord("R"):
                    with self._lock:
                        self._refresh_all()

                # Render
                with self._lock:
                    self._render(stdscr)

        finally:
            self._stop_event.set()

    def _render(self, stdscr):
        """Render the full dashboard."""
        stdscr.erase()
        max_y, max_x = stdscr.getmaxyx()

        if max_y < 10 or max_x < 40:
            stdscr.addstr(0, 0, "Terminal too small! Resize to at least 80x24.")
            stdscr.refresh()
            return

        mid_x = max_x // 2
        header_y = 0
        content_start_y = 1
        status_y = max_y - 1
        available_height = max_y - 2  # minus header and status bar

        # Draw header bar
        now_str = datetime.now().strftime("%a %b %d %Y  %I:%M:%S %p")
        header = f" NYC DASHBOARD │ {now_str} │ [q]uit [r]efresh "
        header = header.center(max_x)
        try:
            stdscr.addnstr(header_y, 0, header, max_x, curses.color_pair(3) | curses.A_BOLD)
        except curses.error:
            pass

        # Determine how many rows the left column needs
        left_rows = max((p.row + p.rowspan for p in self.panels if p.col == 0), default=1)
        # Split left column evenly, with 1 row for each horizontal divider
        left_dividers = max(0, left_rows - 1)
        left_usable = available_height - left_dividers
        left_row_height = max(3, left_usable // left_rows)

        # Build y-offset for each left-column row
        row_y = {}
        y_cursor = content_start_y
        for r in range(left_rows):
            row_y[r] = y_cursor
            y_cursor += left_row_height
            if r < left_rows - 1:
                y_cursor += 1  # divider row

        # Draw each panel
        for panel in self.panels:
            if panel.col == 0:
                px = 0
                pw = mid_x - 1
                py = row_y[panel.row]
                ph = left_row_height * panel.rowspan + (panel.rowspan - 1)
            else:
                px = mid_x
                pw = max_x - mid_x - 1
                py = content_start_y
                ph = available_height  # full height for spanning panels

            self._render_panel(stdscr, panel, px, py, pw, ph)

        # Draw divider lines
        border_color = curses.color_pair(2)

        # Vertical divider
        for y in range(content_start_y, max_y - 1):
            try:
                stdscr.addch(y, mid_x - 1, "│", border_color)
            except curses.error:
                pass

        # Horizontal dividers (left column only)
        for r in range(left_rows - 1):
            horiz_y = row_y[r] + left_row_height
            for x in range(mid_x - 1):
                try:
                    if x == mid_x - 2:
                        stdscr.addch(horiz_y, x, "─", border_color)
                    else:
                        stdscr.addch(horiz_y, x, "─", border_color)
                except curses.error:
                    pass
            # Junction with vertical divider
            try:
                stdscr.addch(horiz_y, mid_x - 1, "┤", border_color)
            except curses.error:
                pass

        # Status bar
        elapsed = int(time.time() - self._last_refresh)
        next_in = max(0, self.refresh_interval - elapsed)
        status = (
            f" Last refresh: {elapsed}s ago │ Next in: {next_in}s │ Sources: {len(self.panels)} "
        )
        try:
            stdscr.addnstr(status_y, 0, status.ljust(max_x), max_x, curses.color_pair(3))
        except curses.error:
            pass

        stdscr.refresh()

    @staticmethod
    def _addstr_colored(stdscr, ly, x, line, width, default_color):
        """Render a line with inline {color:name}...{/color} markup."""
        if "{color:" not in line:
            try:
                stdscr.addnstr(ly, x, line[:width], width, default_color)
            except curses.error:
                pass
            return

        col = x
        remaining = width
        pos = 0
        for m in _COLOR_TAG_RE.finditer(line):
            # Draw text before this tag
            before = line[pos : m.start()]
            # Strip any prior tags from 'before' (shouldn't have any, but safe)
            before_clean = _COLOR_TAG_RE.sub(lambda mm: mm.group(2), before)
            if before_clean and remaining > 0:
                segment = before_clean[:remaining]
                try:
                    stdscr.addnstr(ly, col, segment, remaining, default_color)
                except curses.error:
                    pass
                col += len(segment)
                remaining -= len(segment)

            # Draw colored text
            color_name = m.group(1)
            text = m.group(2)
            if text and remaining > 0:
                pair_id = COLOR_PAIR_MAP.get(color_name, 4)
                segment = text[:remaining]
                try:
                    attr = curses.color_pair(pair_id) | curses.A_BOLD
                    stdscr.addnstr(ly, col, segment, remaining, attr)
                except curses.error:
                    pass
                col += len(segment)
                remaining -= len(segment)

            pos = m.end()

        # Draw any text after the last tag
        after = line[pos:]
        after_clean = _COLOR_TAG_RE.sub(lambda mm: mm.group(2), after)
        if after_clean and remaining > 0:
            segment = after_clean[:remaining]
            try:
                stdscr.addnstr(ly, col, segment, remaining, default_color)
            except curses.error:
                pass

    def _render_panel(self, stdscr, panel: DashboardPanel, x: int, y: int, width: int, height: int):
        """Render a single panel at the given position."""
        if height < 2 or width < 5:
            return

        title_color = curses.color_pair(1) | curses.A_BOLD
        content_color = curses.color_pair(4)

        # Title line
        title = f" ◆ {panel.title} "
        try:
            stdscr.addnstr(y, x, title[:width], width, title_color)
        except curses.error:
            pass

        # Content lines (leave 1 row for title, 1 for padding after horizontal divider)
        content_height = height - 2
        content_y = y + 1

        lines = panel.source.get_display_lines(width - 1, content_height)

        for i, line in enumerate(lines):
            ly = content_y + i
            if ly >= y + height:
                break
            self._addstr_colored(stdscr, ly, x, line, width, content_color)


def parse_args():
    parser = argparse.ArgumentParser(description="NYC Terminal Dashboard")
    parser.add_argument(
        "--refresh", type=int, default=60, help="Refresh interval in seconds (default: 60)"
    )
    parser.add_argument(
        "--stops",
        nargs="*",
        default=None,
        help='Watched subway stops as stop_id:"Display Name" pairs. '
        'Example: 120N:"96 St Uptown" A27N:"59 St"',
    )
    parser.add_argument(
        "--lat", type=float, default=40.7128, help="Weather latitude (default: NYC 40.7128)"
    )
    parser.add_argument(
        "--lon", type=float, default=-74.0060, help="Weather longitude (default: NYC -74.0060)"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Parse watched stops
    if args.stops:
        watched_stops = {}
        for s in args.stops:
            if ":" in s:
                sid, name = s.split(":", 1)
                watched_stops[sid] = name.strip('"').strip("'")
    else:
        # Default: downtown Brooklyn stops
        watched_stops = {
            "F18N": "York St (F) Manhattan-bound",
            "F18S": "York St (F) Coney Island-bound",
            "A40N": "High St (A/C) Manhattan-bound",
            "A40S": "High St (A/C) Brooklyn-bound",
            "A41N": "Jay St-MetroTech (F) Manhattan-bound",
            "A41S": "Jay St-MetroTech (F) Brooklyn-bound",
            "423N": "Borough Hall (4/5) Manhattan-bound",
            "423S": "Borough Hall (4/5) Brooklyn-bound",
        }
        # Cycle: F stops, then A/C stops, then 4/5 stops
        stop_groups = [
            ["F18N", "F18S", "A41N", "A41S"],  # F line
            ["A40N", "A40S"],  # A/C line
            ["423N", "423S"],  # 4/5 line
        ]

    # Create data sources
    subway_src = SOURCES["subway"](
        watched_stops=watched_stops,
        stop_groups=stop_groups if not args.stops else None,
    )
    weather_src = SOURCES["weather"](latitude=args.lat, longitude=args.lon)
    baseball_src = SOURCES["baseball"]()

    # Layout: left column split (subway top, baseball bottom), weather full right
    panels = [
        DashboardPanel(subway_src, "🚇 NYC SUBWAY", row=0, col=0),
        DashboardPanel(baseball_src, "⚾ DODGERS / WBC", row=1, col=0),
        DashboardPanel(weather_src, "🌤  WEATHER", row=0, col=1, rowspan=2),
    ]

    dashboard = Dashboard(panels, refresh_interval=args.refresh)

    try:
        curses.wrapper(dashboard.run)
    except KeyboardInterrupt:
        pass

    print("\nDashboard closed. Goodbye!")


if __name__ == "__main__":
    main()
