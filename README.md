# NYC Terminal Dashboard 🗽

A modular, auto-refreshing terminal dashboard that displays NYC subway data, weather, baseball scores, and news in a 2x2 grid layout.

```
┌──────────────────────────────┬──────────────────────────────┐
│  🚇 NYC SUBWAY               │  🌤  WEATHER                  │
│  Active trains per line       │  Current conditions & forecast│
│  or arrivals at your stops    │  (Open-Meteo, no key needed) │
├──────────────────────────────┼──────────────────────────────┤
│  ⚾ DODGERS / WBC             │  📰 NEWS                      │
│  Upcoming & live games        │  Headlines from RSS feeds     │
│  (MLB Stats API)              │  (AP, Reuters, NPR, BBC)     │
└──────────────────────────────┴──────────────────────────────┘
```

## Setup

```bash
pip install requests gtfs-realtime-bindings feedparser
```

## Usage

```bash
# Basic (summary of all active subway trains)
python dashboard.py

# Watch specific subway stops
python dashboard.py --stops '120N:96 St Uptown (1/2/3)' 'A27N:59 St Columbus Circle'

# Custom refresh interval (seconds)
python dashboard.py --refresh 30

# Custom weather location
python dashboard.py --lat 34.0522 --lon -118.2437
```

## Controls

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Force refresh all panels |

## Architecture: Adding New Data Sources

The dashboard is designed to be modular. Each panel is powered by a **DataSource** subclass.

### Step 1: Create a new source

```python
# data_sources/crypto.py
from .base import DataSource

class CryptoDataSource(DataSource):
    name = "Crypto"
    refresh_interval_seconds = 30

    def fetch_data(self):
        # Fetch from any API, RSS, file, websocket, etc.
        resp = requests.get("https://api.example.com/prices")
        return resp.json()

    def format_for_display(self, width, height):
        # Return list of strings, each fitting in `width` chars
        lines = []
        for coin in self._cached_data[:height]:
            lines.append(f" {coin['symbol']}: ${coin['price']:,.2f}")
        return lines
```

### Step 2: Register it

In `data_sources/__init__.py`:
```python
from .crypto import CryptoDataSource
SOURCES["crypto"] = CryptoDataSource
```

### Step 3: Add a panel

In `dashboard.py`:
```python
crypto_src = SOURCES["crypto"]()
panels.append(DashboardPanel(crypto_src, "₿ CRYPTO", row=1, col=1))
```

## Data Sources

| Source | API | Key Required? |
|--------|-----|---------------|
| Subway | MTA GTFS-RT | No |
| Weather | Open-Meteo | No |
| Baseball | MLB Stats API | No |
| News | RSS (AP, Reuters, NPR, BBC) | No |

## Subway Stop IDs

To watch specific stops, you'll need MTA stop IDs. Append `N` (north/uptown) or `S` (south/downtown):

| Stop ID | Station |
|---------|---------|
| `120N` | 96 St (1/2/3) Northbound |
| `127N` | Times Sq-42 St (1/2/3) Northbound |
| `A27N` | 59 St-Columbus Circle (A/B/C/D) Northbound |
| `631N` | Grand Central (4/5/6) Northbound |
| `R20N` | Times Sq-42 St (N/Q/R/W) Northbound |
| `L03N` | 14 St-Union Sq (L) Eastbound |

Full stop list: [MTA GTFS Static Data](https://new.mta.info/developers)

# commands to run the code
sudo nano /etc/systemctl/system/dashboard.service (to see the configuration of the task)

sudo systemctl daemon-reload (to restart the systemctl daemon)

sudo systemctl restart dashboard (to restart the dashboard)

sudo systemctl status dashboard (to see the status of the dashboard)

CTRL + ALT + F1 ( to see the terminal the code is running on)
CTRL + ALT + F2 (to go to terminal to run commands)
startx inside of terminal when you run CTRL + ALT + F2 will open on the rasberry pi UI
