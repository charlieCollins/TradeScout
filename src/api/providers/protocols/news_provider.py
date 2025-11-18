"""Protocol for news and sentiment data providers."""

from typing import Protocol, Optional, List
from datetime import date
from models.dataclass.news_article import NewsArticle


class NewsProvider(Protocol):
    """Protocol for news and sentiment data providers.

    Provides financial news articles with optional sentiment analysis.

    Implementations:
    - PolygonNewsAdapter (wraps PolygonNewsProvider)
    - AlphaVantageNewsAdapter (future)
    """

    def fetch_news_for_ticker(
        self,
        ticker: str,
        limit: int = 10,
        published_after: Optional[date] = None
    ) -> Optional[List[NewsArticle]]:
        """Fetch news articles for a specific ticker.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')
            limit: Maximum number of articles to fetch
            published_after: Only fetch articles published after this date

        Returns:
            List of NewsArticle objects, or None if error
        """
        ...

    def get_provider_name(self) -> str:
        """Get provider name for logging/debugging."""
        ...
