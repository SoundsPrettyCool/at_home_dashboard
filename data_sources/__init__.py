"""
Data Sources Package - Modular data fetching for the terminal dashboard.

To add a new data source:
1. Create a new file in this package
2. Subclass DataSource
3. Implement fetch_data() and format_for_display()
4. Register it in the SOURCES dict below or dynamically
"""

from .base import DataSource
from .baseball import BaseballDataSource
from .news import NewsDataSource
from .subway import SubwayDataSource
from .weather import WeatherDataSource

# Registry of all available data sources
SOURCES = {
    "subway": SubwayDataSource,
    "weather": WeatherDataSource,
    "baseball": BaseballDataSource,
    "news": NewsDataSource,
}

__all__ = ["SOURCES", "DataSource"]
