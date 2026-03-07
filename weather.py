"""
Weather data source using Open-Meteo API (free, no API key required).

Fetches current conditions and hourly forecast for a given location.
Default: New York City.
"""

from datetime import datetime

import requests

from .base import DataSource

# WMO Weather interpretation codes -> short descriptions
WMO_CODES = {
    0: "Clear",
    1: "Mostly Clear",
    2: "Partly Cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime Fog",
    51: "Lt Drizzle",
    53: "Drizzle",
    55: "Hvy Drizzle",
    56: "Frzg Drizzle",
    57: "Hvy Frzg Drizzle",
    61: "Lt Rain",
    63: "Rain",
    65: "Heavy Rain",
    66: "Frzg Rain",
    67: "Hvy Frzg Rain",
    71: "Lt Snow",
    73: "Snow",
    75: "Heavy Snow",
    77: "Snow Grains",
    80: "Lt Showers",
    81: "Showers",
    82: "Hvy Showers",
    85: "Lt Snow Shwr",
    86: "Hvy Snow Shwr",
    95: "Thunderstorm",
    96: "T-Storm w/ Hail",
    99: "T-Storm Hvy Hail",
}

# Simple weather icons (ASCII)
WEATHER_ICONS = {
    "Clear": "☀️ ",
    "Mostly Clear": "🌤 ",
    "Partly Cloudy": "⛅",
    "Overcast": "☁️ ",
    "Fog": "🌫 ",
    "Rain": "🌧 ",
    "Lt Rain": "🌦 ",
    "Heavy Rain": "🌧 ",
    "Snow": "❄️ ",
    "Thunderstorm": "⛈ ",
}


class WeatherDataSource(DataSource):
    name = "Weather"
    refresh_interval_seconds = 300  # Every 5 minutes

    def __init__(
        self,
        latitude: float = 40.7128,
        longitude: float = -74.0060,
        location_name: str = "New York City",
    ):
        super().__init__()
        self.lat = latitude
        self.lon = longitude
        self.location_name = location_name

    def fetch_data(self) -> dict:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": self.lat,
            "longitude": self.lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
            "weather_code,wind_speed_10m,wind_gusts_10m",
            "hourly": "temperature_2m,weather_code,precipitation_probability",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "forecast_days": 1,
            "timezone": "America/New_York",
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def format_for_display(self, width: int, height: int) -> list[str]:
        data = self._cached_data
        if not data:
            return ["No weather data"]

        current = data.get("current", {})
        hourly = data.get("hourly", {})

        temp = current.get("temperature_2m", "?")
        feels = current.get("apparent_temperature", "?")
        humidity = current.get("relative_humidity_2m", "?")
        wind = current.get("wind_speed_10m", "?")
        gusts = current.get("wind_gusts_10m", "?")
        code = current.get("weather_code", 0)
        condition = WMO_CODES.get(code, "Unknown")
        icon = WEATHER_ICONS.get(condition, "  ")

        lines: list[str] = []
        lines.append(f" {self.location_name}")
        lines.append(f" {icon} {condition}")
        lines.append(f" Temp: {temp}°F  Feels: {feels}°F")
        lines.append(f" Humidity: {humidity}%  Wind: {wind} mph")
        if gusts:
            lines.append(f" Gusts: {gusts} mph")
        lines.append("")

        # Hourly forecast (next few hours)
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        codes = hourly.get("weather_code", [])
        precip = hourly.get("precipitation_probability", [])

        now_hour = datetime.now().hour
        lines.append(" Upcoming:")
        count = 0
        for i, t in enumerate(times):
            try:
                hr = int(t.split("T")[1].split(":")[0])
            except (IndexError, ValueError):
                continue
            if hr <= now_hour:
                continue
            cond = WMO_CODES.get(codes[i] if i < len(codes) else 0, "?")
            tp = temps[i] if i < len(temps) else "?"
            pp = precip[i] if i < len(precip) else 0
            hr_label = f"{hr % 12 or 12}{'AM' if hr < 12 else 'PM'}"
            rain_str = f" 💧{pp}%" if pp and pp > 0 else ""
            line = f"  {hr_label:>5}  {tp:>3}°F  {cond:<15}{rain_str}"
            lines.append(self.truncate(line, width))
            count += 1
            if count >= height - len(lines) + count:
                break

        return lines[:height]
