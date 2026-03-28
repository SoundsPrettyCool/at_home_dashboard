# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A curses-based terminal dashboard for Raspberry Pi that displays NYC subway arrivals, weather, Dodgers baseball scores, and news in a 2x2 grid. Runs as a systemd service on TTY1.

## Commands

```bash
# Run the dashboard
python dashboard.py
python dashboard.py --stops '120N:96 St Uptown' --refresh 30 --lat 40.7128 --lon -74.0060

# Lint
ruff check .
ruff check --fix .

# Install dependencies
pip install -e ".[dev]"

# Manage on Raspberry Pi
sudo systemctl restart dashboard
sudo systemctl status dashboard
sudo systemctl daemon-reload  # after editing dashboard.service
```

## Architecture

**`dashboard.py`** — Main entry point. Contains `Dashboard` (curses rendering, refresh loop, input handling) and `DashboardPanel` (grid position + data source binding). Renders a 2x2 grid: left column splits into two rows (subway, baseball), right column spans full height (weather). Supports inline color markup via `{color:name}...{/color}` tags.

**`data_sources/`** — Modular data source package. Each source subclasses `DataSource` (in `base.py`) and implements:
- `fetch_data()` — pulls raw data from an API
- `format_for_display(width, height)` — returns lines of text fitting panel dimensions

Sources are registered in `data_sources/__init__.py` via the `SOURCES` dict.

**Current sources:** `subway.py` (MTA GTFS-RT), `weather.py` (Open-Meteo), `baseball.py` (MLB Stats API), `news.py` (RSS feeds via feedparser).

## Key Patterns

- Data sources refresh in parallel via threads; `Dashboard._refresh_all()` spawns one thread per panel
- `DataSource.get_display_lines()` handles error/loading states so individual sources don't need to
- `base.py` has color-tag-aware truncation helpers (`_truncate_preserving_tags`, `truncate`) — use these when formatting colored output
- No API keys required — all data sources use free/public APIs

## Linting

Uses **ruff** with rules: E, W, F, I, N, UP, B, SIM, RUF. Line length 100. Target Python 3.12. `SIM105` is ignored (try/except/pass is intentional for curses).
