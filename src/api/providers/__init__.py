"""API providers for external data sources.

API providers handle:
- External API authentication
- HTTP request/response handling
- Rate limiting and retry logic
- Response parsing into model objects

API providers do NOT:
- Store data to database (that's database manager responsibility)
- Handle TTL logic (that's database manager responsibility)
- Manage caching (that's database manager responsibility)
"""

from .base_provider import BaseAPIProvider
from .polygon_aggregates_provider import PolygonAggregatesProvider
from .polygon_snapshot_provider import PolygonSnapshotProvider
from .polygon_tickers_provider import PolygonTickersProvider
from .polygon_markets_provider import PolygonMarketsProvider
from .polygon_market_status_provider import PolygonMarketStatusProvider
from .polygon_news_provider import PolygonNewsProvider

__all__ = [
    "BaseAPIProvider",
    "PolygonAggregatesProvider",
    "PolygonSnapshotProvider",
    "PolygonTickersProvider",
    "PolygonMarketsProvider",
    "PolygonMarketStatusProvider",
    "PolygonNewsProvider",
]