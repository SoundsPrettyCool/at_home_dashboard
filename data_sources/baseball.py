"""
Baseball data source - Dodgers games and World Baseball Classic.

Uses the free MLB Stats API (no key required):
  - https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId=119  (Dodgers)
  - https://statsapi.mlb.com/api/v1/schedule?sportId=51            (WBC, sportId may vary)

Also fetches live game data when a game is in progress.
"""

import re
import time
from datetime import datetime, timedelta

import requests

from .base import DataSource

_COLOR_TAG_RE = re.compile(r"\{color:\w+\}|\{/color\}")

DODGERS_TEAM_ID = 119
MLB_BASE = "https://statsapi.mlb.com/api/v1"

# Game status codes
STATUS_LIVE = ("In Progress", "Live")
STATUS_FINAL = ("Final", "Game Over", "Completed Early")


def color_live(text: str) -> str:
    """Wrap text in green color markup for curses rendering."""
    return f"{{color:green}}{text}{{/color}}"


class BaseballDataSource(DataSource):
    name = "Baseball"
    refresh_interval_seconds = 60

    def __init__(self, team_ids: list[int] | None = None, include_wbc: bool = True):
        """
        Args:
            team_ids: MLB team IDs to track. Default: [119] (Dodgers)
            include_wbc: Whether to also fetch World Baseball Classic schedule
        """
        super().__init__()
        self.team_ids = team_ids or [DODGERS_TEAM_ID]
        self.include_wbc = include_wbc
        # Upcoming schedule paging
        self._schedule_page = 0
        self._games_per_page = 3
        self._schedule_interval = 10
        self._schedule_last_page = 0.0
        # Live games paging
        self._live_page = 0
        self._live_interval = 20
        self._live_last_page = 0.0
        # Recent/final games paging
        self._recent_page = 0
        self._recent_interval = 7
        self._recent_last_page = 0.0
        self._left_per_page = 3

    def fetch_data(self) -> dict:
        today = datetime.now().strftime("%Y-%m-%d")
        end = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

        games = []

        # Fetch MLB games for tracked teams
        for team_id in self.team_ids:
            try:
                url = f"{MLB_BASE}/schedule"
                params = {
                    "sportId": 1,
                    "teamId": team_id,
                    "startDate": today,
                    "endDate": end,
                    "hydrate": "team,linescore",
                }
                resp = requests.get(url, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                for date_entry in data.get("dates", []):
                    for game in date_entry.get("games", []):
                        games.append(self._parse_game(game, source="MLB"))
            except Exception:
                continue

        # Fetch WBC if enabled (sportId=51 for international events)
        if self.include_wbc:
            for sport_id in (51, 158):  # Try different sport IDs for WBC
                try:
                    url = f"{MLB_BASE}/schedule"
                    params = {
                        "sportId": sport_id,
                        "startDate": today,
                        "endDate": end,
                        "hydrate": "team,linescore",
                    }
                    resp = requests.get(url, params=params, timeout=10)
                    resp.raise_for_status()
                    data = resp.json()

                    for date_entry in data.get("dates", []):
                        for game in date_entry.get("games", []):
                            games.append(self._parse_game(game, source="WBC"))
                except Exception:
                    continue

        return {"games": games, "fetched_at": today}

    def _parse_game(self, game: dict, source: str = "MLB") -> dict:
        """Parse a game entry from the MLB API."""
        teams = game.get("teams", {})
        away = teams.get("away", {}).get("team", {}).get("name", "TBD")
        home = teams.get("home", {}).get("team", {}).get("name", "TBD")
        away_score = teams.get("away", {}).get("score", "-")
        home_score = teams.get("home", {}).get("score", "-")

        status = game.get("status", {})
        status_text = status.get("detailedState", "Scheduled")

        linescore = game.get("linescore", {})
        inning = linescore.get("currentInning", "")
        inning_state = linescore.get("inningHalf", "")

        game_date = game.get("gameDate", "")
        try:
            dt = datetime.fromisoformat(game_date.replace("Z", "+00:00"))
            local_time = dt.strftime("%-m/%-d %-I:%M%p")
        except Exception:
            local_time = game_date[:16] if game_date else "TBD"

        return {
            "source": source,
            "away": away,
            "home": home,
            "away_score": away_score,
            "home_score": home_score,
            "status": status_text,
            "inning": inning,
            "inning_state": inning_state,
            "time": local_time,
        }

    def format_for_display(self, width: int, height: int) -> list[str]:
        data = self._cached_data
        if not data:
            return ["No baseball data"]

        games = data.get("games", [])
        if not games:
            return [" No upcoming games found"]

        # Split into live, final, and scheduled games
        live_games = []
        recent_games = []
        scheduled_games = []
        for game in games:
            status = game["status"]
            if any(s in status for s in STATUS_LIVE):
                live_games.append(game)
            elif any(s in status for s in STATUS_FINAL):
                recent_games.append(game)
            else:
                scheduled_games.append(game)

        # Build left column (live/recent) and right column (schedule)
        col_width = (width - 3) // 2  # 3 chars for " │ " divider
        now = time.monotonic()

        left_lines = []
        if live_games or recent_games:
            # Page through live games
            live_batch = []
            if live_games:
                if now - self._live_last_page >= self._live_interval:
                    self._live_page += 1
                    self._live_last_page = now
                live_total = len(live_games)
                live_pages = max(1, (live_total + self._left_per_page - 1) // self._left_per_page)
                lp = self._live_page % live_pages
                live_batch = live_games[lp * self._left_per_page : (lp + 1) * self._left_per_page]

            # Page through recent games, fill remaining slots
            remaining = self._left_per_page - len(live_batch)
            recent_batch = []
            if recent_games and remaining > 0:
                if now - self._recent_last_page >= self._recent_interval:
                    self._recent_page += 1
                    self._recent_last_page = now
                recent_total = len(recent_games)
                recent_pages = max(1, (recent_total + remaining - 1) // remaining)
                rp = self._recent_page % recent_pages
                recent_batch = recent_games[rp * remaining : (rp + 1) * remaining]

            if live_batch:
                left_lines.append("LIVE")
                for game in live_batch:
                    tag = f"[{game['source']}]"
                    inn = f"{game['inning_state']} {game['inning']}" if game["inning"] else ""
                    left_lines.append(f" {color_live('LIVE')} {tag} {inn}")
                    matchup = (
                        f"  {game['away']} {game['away_score']}"
                        f" @ {game['home']} {game['home_score']}"
                    )
                    left_lines.append(self.truncate(matchup, col_width))
                    left_lines.append("")

            if recent_batch:
                left_lines.append("RECENT")
                for game in recent_batch:
                    tag = f"[{game['source']}]"
                    left_lines.append(f" FINAL {tag}")
                    matchup = (
                        f"  {game['away']} {game['away_score']}"
                        f" @ {game['home']} {game['home_score']}"
                    )
                    left_lines.append(self.truncate(matchup, col_width))
                    left_lines.append("")
        else:
            left_lines.append("NO LIVE GAMES")

        right_lines = []
        if scheduled_games:
            if now - self._schedule_last_page >= self._schedule_interval:
                self._schedule_page += 1
                self._schedule_last_page = now

            total = len(scheduled_games)
            total_pages = max(1, (total + self._games_per_page - 1) // self._games_per_page)
            page = self._schedule_page % total_pages
            start = page * self._games_per_page
            batch = scheduled_games[start : start + self._games_per_page]

            right_lines.append(f"UPCOMING ({page + 1}/{total_pages})")
            for game in batch:
                tag = f"[{game['source']}]"
                right_lines.append(f" {game['time']} {tag}")
                matchup = f"  {game['away']} @ {game['home']}"
                right_lines.append(self.truncate(matchup, col_width))
                right_lines.append("")
        else:
            right_lines.append("NO UPCOMING GAMES")

        # Merge columns side by side
        max_rows = max(len(left_lines), len(right_lines), height)
        lines = []
        for i in range(min(max_rows, height)):
            left = left_lines[i] if i < len(left_lines) else ""
            right = right_lines[i] if i < len(right_lines) else ""
            # Pad left column accounting for color tag markup
            visible_len = len(_COLOR_TAG_RE.sub("", left))
            pad = max(0, col_width - visible_len)
            left_padded = left + " " * pad
            right_trimmed = self.truncate(right, col_width)
            lines.append(f"{left_padded} │ {right_trimmed}")

        return lines
