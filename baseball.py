"""
Baseball data source - Dodgers games and World Baseball Classic.

Uses the free MLB Stats API (no key required):
  - https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId=119  (Dodgers)
  - https://statsapi.mlb.com/api/v1/schedule?sportId=51            (WBC, sportId may vary)

Also fetches live game data when a game is in progress.
"""

from datetime import datetime, timedelta

import requests

from .base import DataSource

DODGERS_TEAM_ID = 119
MLB_BASE = "https://statsapi.mlb.com/api/v1"

# Game status codes
STATUS_LIVE = ("In Progress", "Live")
STATUS_FINAL = ("Final", "Game Over", "Completed Early")


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

        lines: list[str] = []

        for game in games:
            if len(lines) >= height - 1:
                break

            status = game["status"]
            is_live = any(s in status for s in STATUS_LIVE)
            is_final = any(s in status for s in STATUS_FINAL)

            # Source tag
            tag = f"[{game['source']}]"

            if is_live:
                inn = f"{game['inning_state']} {game['inning']}" if game["inning"] else ""
                score_line = f" \033[92m⚾ LIVE\033[0m {tag} {inn}"
                matchup = (
                    f"  {game['away']} {game['away_score']} @ {game['home']} {game['home_score']}"
                )
            elif is_final:
                score_line = f" ✓ FINAL {tag}"
                matchup = (
                    f"  {game['away']} {game['away_score']} @ {game['home']} {game['home_score']}"
                )
            else:
                score_line = f" 📅 {game['time']} {tag}"
                matchup = f"  {game['away']} @ {game['home']}"

            lines.append(self.truncate(score_line, width))
            lines.append(self.truncate(matchup, width))
            lines.append("")

        return lines[:height]
