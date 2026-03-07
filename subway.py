"""
NYC Subway real-time arrival data source.

Uses the MTA's GTFS-Realtime feeds (public, no API key required for basic access).
Fetches trip updates for all subway lines and displays upcoming arrivals.

MTA Feed URLs (GTFS-RT protobuf):
  - https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs       (1,2,3,4,5,6,7,S)
  - https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace   (A,C,E)
  - https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw  (N,Q,R,W)
  - https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm  (B,D,F,M)
  - https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-jz    (J,Z)
  - https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-g     (G)
  - https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-l     (L)
  - https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-si    (SIR)

Requires: pip install gtfs-realtime-bindings requests
"""

import time
from collections import defaultdict

import requests

try:
    from google.transit import gtfs_realtime_pb2

    HAS_GTFS = True
except ImportError:
    HAS_GTFS = False

from .base import DataSource

# MTA GTFS-RT feed URLs (public, no key needed)
MTA_FEEDS = {
    "1/2/3/4/5/6/7/S": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs",
    "A/C/E": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace",
    "N/Q/R/W": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw",
    "B/D/F/M": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm",
    "J/Z": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-jz",
    "G": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-g",
    "L": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-l",
    "SIR": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-si",
}

# ANSI color codes for subway line bullets
LINE_COLORS = {
    "1": "\033[91m",
    "2": "\033[91m",
    "3": "\033[91m",  # Red
    "4": "\033[92m",
    "5": "\033[92m",
    "6": "\033[92m",  # Green
    "7": "\033[95m",  # Purple
    "A": "\033[94m",
    "C": "\033[94m",
    "E": "\033[94m",  # Blue
    "B": "\033[93m",
    "D": "\033[93m",
    "F": "\033[93m",
    "M": "\033[93m",  # Orange/Yellow
    "N": "\033[93m",
    "Q": "\033[93m",
    "R": "\033[93m",
    "W": "\033[93m",
    "G": "\033[32m",  # Lime green
    "J": "\033[33m",
    "Z": "\033[33m",  # Brown
    "L": "\033[90m",  # Gray
    "S": "\033[90m",  # Gray
}
RESET = "\033[0m"


def _color_line(line: str) -> str:
    """Wrap a line letter in its ANSI color."""
    color = LINE_COLORS.get(line, "")
    return f"{color}●{line}{RESET}" if color else f"●{line}"


class SubwayDataSource(DataSource):
    name = "NYC Subway"
    refresh_interval_seconds = 60

    def __init__(self, watched_stops: dict[str, str] | None = None):
        """
        Args:
            watched_stops: Optional dict mapping stop_id -> display_name.
                If None, shows a summary of active trains per line.
                Example: {"120N": "96 St (1/2/3) Northbound", "A27N": "59 St-Columbus Northbound"}
        """
        super().__init__()
        self.watched_stops = watched_stops

    def fetch_data(self) -> dict:
        if not HAS_GTFS:
            return {"error": "Install: pip install gtfs-realtime-bindings"}

        now = int(time.time())
        # line -> count of active trips
        active_trips: dict[str, int] = defaultdict(int)
        # If watching specific stops: stop_id -> list of (line, minutes_away)
        stop_arrivals: dict[str, list] = defaultdict(list) if self.watched_stops else None

        for _feed_label, url in MTA_FEEDS.items():
            try:
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                feed = gtfs_realtime_pb2.FeedMessage()
                feed.ParseFromString(resp.content)

                for entity in feed.entity:
                    if not entity.HasField("trip_update"):
                        continue
                    tu = entity.trip_update
                    route = tu.trip.route_id.replace("SS", "S")  # Normalize shuttle

                    active_trips[route] += 1

                    if self.watched_stops and tu.stop_time_update:
                        for stu in tu.stop_time_update:
                            sid = stu.stop_id
                            if sid in self.watched_stops:
                                arr = stu.arrival.time or stu.departure.time
                                if arr and arr > now:
                                    mins = (arr - now) // 60
                                    stop_arrivals[sid].append((route, mins))
            except Exception:
                continue  # Skip feeds that fail; show what we have

        data = {"active_trips": dict(active_trips), "timestamp": now}
        if stop_arrivals is not None:
            # Sort arrivals by time
            for sid in stop_arrivals:
                stop_arrivals[sid].sort(key=lambda x: x[1])
            data["stop_arrivals"] = dict(stop_arrivals)
        return data

    def format_for_display(self, width: int, height: int) -> list[str]:
        data = self._cached_data
        if not data:
            return ["No data"]
        if "error" in data:
            return [data["error"]]

        lines: list[str] = []

        # If watching specific stops, show arrivals
        if self.watched_stops and "stop_arrivals" in data:
            for sid, display_name in self.watched_stops.items():
                arrivals = data["stop_arrivals"].get(sid, [])
                lines.append(f" {display_name}")
                if arrivals:
                    parts = []
                    for route, mins in arrivals[:4]:
                        parts.append(f"{_color_line(route)} {mins}m")
                    lines.append("   " + "  ".join(parts))
                else:
                    lines.append("   No upcoming arrivals")
                if len(lines) >= height - 1:
                    break
        else:
            # Summary view: active trains per line
            trips = data.get("active_trips", {})
            sorted_lines = sorted(trips.keys())

            # Group into rows of N items
            cols = max(1, width // 12)
            row_items = []
            for route in sorted_lines:
                count = trips[route]
                entry = f"{_color_line(route)} {count:>3} trains"
                row_items.append(entry)

                if len(row_items) >= cols:
                    lines.append("  ".join(row_items))
                    row_items = []
            if row_items:
                lines.append("  ".join(row_items))

        # Pad to height
        while len(lines) < height:
            lines.append("")
        return lines[:height]
