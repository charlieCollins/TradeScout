"""Polygon API provider for news and sentiment data.

Handles fetching news articles from Polygon's /v2/reference/news endpoint.
Transforms Polygon's news data into our SentimentEvent models (requires sentiment analysis).
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, date
from .base_provider import BaseAPIProvider

logger = logging.getLogger(__name__)


class PolygonNewsProvider(BaseAPIProvider):
    """API provider for Polygon news data.

    Handles ONLY news API calls - no database operations, no caching.
    Fetches from /v2/reference/news endpoint and returns raw news articles.

    Note: Sentiment analysis (positive/negative/neutral classification) happens
    in the service layer, not in the provider.
    """

    def __init__(self, api_key: str):
        """Initialize Polygon news provider.

        Args:
            api_key: Polygon API key
        """
        super().__init__(api_key, "https://api.polygon.io")

    # ============================================================================
    # AUTHENTICATION
    # ============================================================================

    def _add_authentication(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add Polygon API key to request parameters.

        Args:
            params: Request parameters

        Returns:
            Parameters with apikey added
        """
        params["apikey"] = self.api_key
        return params

    def _get_health_endpoint(self) -> str:
        """Get health check endpoint.

        Returns:
            Endpoint for health checking
        """
        return "/v1/marketstatus/now"

    # ============================================================================
    # NEWS API CALLS
    # ============================================================================

    def fetch_news_for_ticker(
        self,
        ticker: str,
        limit: int = 10,
        published_after: Optional[date] = None
    ) -> Optional[List["NewsArticle"]]:
        """Fetch news articles for a specific ticker.

        Endpoint: GET /v2/reference/news

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')
            limit: Maximum number of articles to fetch (default: 10)
            published_after: Only fetch articles published after this date

        Returns:
            List of NewsArticle domain objects, or None if error
        """
        from models.dataclass.news_article import NewsArticle, SentimentInsight
        from datetime import datetime

        try:
            params = {
                "ticker": ticker.upper(),
                "limit": limit,
                "order": "desc"  # Most recent first
            }

            if published_after:
                # Polygon expects YYYY-MM-DD format
                params["published_utc.gte"] = published_after.isoformat()

            data = self._make_request("/v2/reference/news", params)

            # Polygon returns {"status": "OK", "results": [...]}
            if not isinstance(data, dict) or "results" not in data:
                logger.warning(f"Unexpected response format from news API: {data}")
                return []

            raw_articles = data["results"]
            articles = []

            # Transform raw API response to NewsArticle domain objects
            for raw in raw_articles:
                try:
                    # Parse published timestamp
                    published_utc_str = raw.get("published_utc", "")
                    try:
                        published_utc = datetime.fromisoformat(published_utc_str.replace('Z', '+00:00'))
                    except Exception:
                        logger.warning(f"Failed to parse published_utc: {published_utc_str}")
                        continue

                    # Transform insights
                    insights = []
                    for insight_data in raw.get("insights", []):
                        insight = SentimentInsight(
                            ticker=insight_data.get("ticker", ""),
                            sentiment=insight_data.get("sentiment", "neutral"),
                            sentiment_score=insight_data.get("sentiment_score", 0.0),
                            sentiment_reasoning=insight_data.get("sentiment_reasoning")
                        )
                        insights.append(insight)

                    # Create NewsArticle
                    article = NewsArticle(
                        id=raw.get("id", ""),
                        article_url=raw.get("article_url", ""),
                        title=raw.get("title", ""),
                        description=raw.get("description"),
                        author=raw.get("author"),
                        publisher_name=raw.get("publisher", {}).get("name", ""),
                        published_utc=published_utc,
                        tickers=raw.get("tickers", []),
                        insights=insights,
                        keywords=raw.get("keywords", [])
                    )
                    articles.append(article)

                except Exception as e:
                    logger.warning(f"Failed to transform article {raw.get('id', 'unknown')}: {e}")
                    continue

            logger.debug(f"Transformed {len(articles)} news articles for {ticker}")
            return articles

        except Exception as e:
            logger.error(f"Error fetching news for {ticker}: {e}")
            return None

    def fetch_recent_market_news(
        self,
        limit: int = 50
    ) -> Optional[List[Dict[str, Any]]]:
        """Fetch recent market-wide news (not ticker-specific).

        Endpoint: GET /v2/reference/news

        Args:
            limit: Maximum number of articles to fetch (default: 50)

        Returns:
            List of raw news article dictionaries, or None if error
        """
        try:
            params = {
                "limit": limit,
                "order": "desc"  # Most recent first
            }

            data = self._make_request("/v2/reference/news", params)

            if isinstance(data, dict) and "results" in data:
                articles = data["results"]
                logger.debug(f"Fetched {len(articles)} recent market news articles")
                return articles
            else:
                logger.warning(f"Unexpected response format from news API: {data}")
                return []

        except Exception as e:
            logger.error(f"Error fetching recent market news: {e}")
            return None

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def extract_sentiment_from_article(self, article: Dict[str, Any], ticker: str) -> Optional[Dict[str, Any]]:
        """Extract sentiment data for a specific ticker from article insights.

        Polygon's news API includes sentiment analysis in the "insights" field.
        This helper extracts the relevant sentiment data for our ticker.

        Args:
            article: Raw article dict from Polygon
            ticker: Ticker symbol to extract sentiment for

        Returns:
            Dict with sentiment info, or None if not available

        Example return:
        {
            "sentiment": "positive",  # "positive", "negative", "neutral"
            "sentiment_score": 0.75,  # -1.0 to 1.0
            "reasoning": "Strong earnings beat expectations"
        }
        """
        # Check if article has insights
        insights = article.get("insights", [])
        if not insights:
            logger.debug(f"No insights found in article {article.get('id', 'unknown')}")
            return None

        # Find insight for our ticker
        ticker_upper = ticker.upper()
        for insight in insights:
            if insight.get("ticker", "").upper() == ticker_upper:
                return {
                    "sentiment": insight.get("sentiment", "neutral"),
                    "sentiment_score": insight.get("sentiment_score", 0.0),
                    "reasoning": insight.get("sentiment_reasoning", "")
                }

        logger.debug(f"No sentiment found for {ticker} in article insights")
        return None

    # ============================================================================
    # PROVIDER INFO
    # ============================================================================

    def get_provider_name(self) -> str:
        """Get provider name for logging/debugging.

        Returns:
            Provider identifier string
        """
        return "polygon_news"

    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information.

        Returns:
            Dictionary with provider details
        """
        return {
            "name": self.get_provider_name(),
            "base_url": self.base_url,
            "endpoints": {
                "news": "/v2/reference/news"
            },
            "features": [
                "ticker_news",
                "market_news",
                "sentiment_analysis"
            ]
        }
