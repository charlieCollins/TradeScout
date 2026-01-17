"""Finnhub API adapter for news and sentiment data.

Implements NewsProvider protocol using Finnhub's company news API.
"""

import logging
from typing import Optional, List
from datetime import date, datetime

import finnhub

from models.dataclass.news_article import NewsArticle, SentimentInsight
from api.providers.protocols.news_provider import NewsProvider

logger = logging.getLogger(__name__)


class FinnhubNewsAdapter(NewsProvider):
    """Adapter for Finnhub news and sentiment API.

    Implements NewsProvider protocol using finnhub-python library.
    Transforms Finnhub's news data to TradeScout's domain models.

    Free tier limits: 60 API calls/minute
    """

    def __init__(self, api_key: str):
        """Initialize Finnhub news adapter.

        Args:
            api_key: Finnhub API key

        Raises:
            ValueError: If API key is empty
        """
        if not api_key or not api_key.strip():
            raise ValueError("Finnhub API key is required")

        self.api_key = api_key
        self.client = finnhub.Client(api_key=api_key)

    def fetch_news_for_ticker(
        self,
        ticker: str,
        limit: int = 10,
        published_after: Optional[date] = None
    ) -> Optional[List[NewsArticle]]:
        """Fetch news articles for a specific ticker.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')
            limit: Maximum number of articles to fetch (default: 10)
            published_after: Only fetch articles published after this date

        Returns:
            List of NewsArticle objects, or None if error
        """
        try:
            # Calculate date range
            if published_after:
                from_date = published_after.strftime('%Y-%m-%d')
            else:
                # Default to last 30 days
                from datetime import timedelta
                from_date = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')

            to_date = date.today().strftime('%Y-%m-%d')

            # Fetch news from Finnhub
            logger.debug(f"Fetching Finnhub news for {ticker} from {from_date} to {to_date}")
            finnhub_news = self.client.company_news(ticker.upper(), _from=from_date, to=to_date)

            if not finnhub_news:
                logger.warning(f"No news returned from Finnhub for {ticker}")
                return []

            # Limit results
            finnhub_news = finnhub_news[:limit]

            # Transform to NewsArticle objects
            articles = []
            for news_item in finnhub_news:
                try:
                    article = self._transform_finnhub_news(ticker, news_item)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.warning(f"Failed to transform Finnhub news item: {e}")
                    continue

            logger.debug(f"Fetched {len(articles)} news articles for {ticker} from Finnhub")
            return articles

        except Exception as e:
            logger.error(f"Error fetching news from Finnhub for {ticker}: {e}")
            return None

    def _transform_finnhub_news(self, ticker: str, news_item: dict) -> Optional[NewsArticle]:
        """Transform Finnhub news item to NewsArticle.

        Finnhub news format:
        {
            "id": 123456,
            "headline": "...",
            "summary": "...",
            "source": "Reuters",
            "url": "https://...",
            "datetime": 1234567890,  # Unix timestamp
            "category": "company",
            "image": "https://...",
            "related": "AAPL"
        }

        Args:
            ticker: Stock ticker symbol
            news_item: Finnhub news dictionary

        Returns:
            NewsArticle or None if transformation fails
        """
        try:
            # Parse timestamp
            timestamp = news_item.get('datetime', 0)
            if timestamp:
                published_utc = datetime.fromtimestamp(timestamp)
            else:
                logger.warning("News item missing timestamp")
                published_utc = datetime.now()

            # Extract tickers (Finnhub uses 'related' field)
            related = news_item.get('related', '')
            if related:
                # Can be comma-separated
                tickers = [t.strip() for t in related.split(',')]
            else:
                tickers = [ticker.upper()]

            # Create NewsArticle
            # Note: Finnhub doesn't provide sentiment in news endpoint
            # Would need to call separate sentiment endpoint if needed
            article = NewsArticle(
                id=str(news_item.get('id', '')),
                article_url=news_item.get('url', ''),
                title=news_item.get('headline', ''),
                description=news_item.get('summary'),
                author=None,  # Finnhub doesn't provide author
                publisher_name=news_item.get('source', 'Unknown'),
                published_utc=published_utc,
                tickers=tickers,
                insights=[],  # Finnhub company_news doesn't include sentiment
                keywords=[]  # Finnhub doesn't provide keywords in news
            )

            return article

        except Exception as e:
            logger.error(f"Error transforming Finnhub news item: {e}")
            return None

    def fetch_news_sentiment(self, ticker: str) -> Optional[dict]:
        """Fetch news sentiment for a ticker from Finnhub.

        This is a supplementary method that can be used to get sentiment
        separately from news articles.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with sentiment data or None if error
        """
        try:
            sentiment = self.client.news_sentiment(ticker.upper())

            if sentiment:
                logger.debug(f"Fetched news sentiment for {ticker} from Finnhub")
                return sentiment

            return None

        except Exception as e:
            logger.error(f"Error fetching sentiment from Finnhub for {ticker}: {e}")
            return None

    def get_provider_name(self) -> str:
        """Get provider name for logging/debugging.

        Returns:
            Provider identifier string
        """
        return "finnhub"
