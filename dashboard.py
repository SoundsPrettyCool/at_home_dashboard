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
import threading
import time
from datetime import datetime

from data_sources import SOURCES
from data_sources.base import DataSource


class DashboardPanel:
    """Represents one panel in the grid with a data source and position."""

    def __init__(self, source: DataSource, title: str, row: int, col: int):
        self.source = source
        self.title = title
        self.row = row  # 0 = top, 1 = bottom
        self.col = col  # 0 = left, 1 = right


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

        # Calculate panel sizes
        mid_x = max_x // 2
        mid_y = (max_y - 2) // 2  # Reserve 2 rows for header + status

        header_y = 0
        content_start_y = 1
        status_y = max_y - 1

        # Draw header bar
        now_str = datetime.now().strftime("%a %b %d %Y  %I:%M:%S %p")
        header = f" NYC DASHBOARD │ {now_str} │ [q]uit [r]efresh "
        header = header.center(max_x)
        try:
            stdscr.addnstr(header_y, 0, header, max_x, curses.color_pair(3) | curses.A_BOLD)
        except curses.error:
            pass

        # Draw each panel
        for panel in self.panels:
            if panel.col == 0:
                px = 0
                pw = mid_x - 1
            else:
                px = mid_x
                pw = max_x - mid_x - 1

            if panel.row == 0:
                py = content_start_y
                ph = mid_y
            else:
                py = content_start_y + mid_y
                ph = max_y - 2 - mid_y

            self._render_panel(stdscr, panel, px, py, pw, ph)

        # Draw divider lines
        border_color = curses.color_pair(2)

        # Vertical divider
        for y in range(content_start_y, max_y - 1):
            try:
                stdscr.addch(y, mid_x - 1, "│", border_color)
            except curses.error:
                pass

        # Horizontal divider
        horiz_y = content_start_y + mid_y
        for x in range(max_x - 1):
            try:
                if x == mid_x - 1:
                    stdscr.addch(horiz_y, x, "┼", border_color)
                else:
                    stdscr.addch(horiz_y, x, "─", border_color)
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
            try:
                # Use addnstr to handle wide characters and avoid overflow
                stdscr.addnstr(ly, x, line[:width], width, content_color)
            except curses.error:
                pass


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
    watched_stops = None
    if args.stops:
        watched_stops = {}
        for s in args.stops:
            if ":" in s:
                sid, name = s.split(":", 1)
                watched_stops[sid] = name.strip('"').strip("'")

    # Create data sources
    subway_src = SOURCES["subway"](watched_stops=watched_stops)
    weather_src = SOURCES["weather"](latitude=args.lat, longitude=args.lon)
    baseball_src = SOURCES["baseball"]()
    news_src = SOURCES["news"]()

    # Build panels:  (row, col) -> (0,0)=top-left, (0,1)=top-right, etc.
    panels = [
        DashboardPanel(subway_src, "🚇 NYC SUBWAY", row=0, col=0),
        DashboardPanel(weather_src, "🌤  WEATHER", row=0, col=1),
        DashboardPanel(baseball_src, "⚾ DODGERS / WBC", row=1, col=0),
        DashboardPanel(news_src, "📰 NEWS", row=1, col=1),
    ]

    dashboard = Dashboard(panels, refresh_interval=args.refresh)

    try:
        curses.wrapper(dashboard.run)
    except KeyboardInterrupt:
        pass

    print("\nDashboard closed. Goodbye!")


if __name__ == "__main__":
    main()
