"""NewsArticle domain model - represents a news article with sentiment insights."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class SentimentInsight:
    """Sentiment insight for a specific ticker within an article."""

    ticker: str
    sentiment: str  # 'positive', 'negative', 'neutral', 'mixed'
    sentiment_score: float  # -1.0 to 1.0
    sentiment_reasoning: Optional[str] = None


@dataclass
class NewsArticle:
    """Domain model representing a news article with sentiment data.

    This is the clean interface between API providers and business logic.
    Providers transform their API responses into this standard format.
    """

    # Identification
    id: str  # External ID from news source
    article_url: str

    # Content
    title: str
    publisher_name: str
    published_utc: datetime

    # Optional content fields
    description: Optional[str] = None
    author: Optional[str] = None

    # Related stocks
    tickers: List[str] = field(default_factory=list)

    # Sentiment analysis
    insights: List[SentimentInsight] = field(default_factory=list)

    # Metadata
    keywords: List[str] = field(default_factory=list)

    def get_insight_for_ticker(self, ticker: str) -> Optional[SentimentInsight]:
        """Get sentiment insight for a specific ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            SentimentInsight if found, None otherwise
        """
        ticker = ticker.upper()
        for insight in self.insights:
            if insight.ticker.upper() == ticker:
                return insight
        return None
