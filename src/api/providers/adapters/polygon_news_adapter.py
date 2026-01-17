"""Polygon adapter for news and sentiment data."""

from typing import Optional, List
from datetime import date
from api.providers.polygon_news_provider import PolygonNewsProvider
from models.dataclass.news_article import NewsArticle


class PolygonNewsAdapter:
    """Adapter for Polygon News API.

    Wraps PolygonNewsProvider to implement NewsProvider protocol.
    """

    def __init__(self, api_key: str):
        """Initialize adapter with Polygon API key.

        Args:
            api_key: Polygon API key

        Raises:
            ValueError: If API key is empty or None
        """
        if not api_key or not api_key.strip():
            raise ValueError("Polygon API key is required")
        self._provider = PolygonNewsProvider(api_key)

    def fetch_news_for_ticker(
        self,
        ticker: str,
        limit: int = 10,
        published_after: Optional[date] = None
    ) -> Optional[List[NewsArticle]]:
        """Delegate to Polygon provider."""
        return self._provider.fetch_news_for_ticker(ticker, limit, published_after)

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "polygon"
