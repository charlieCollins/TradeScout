"""Web output adapter for news results.

Formats news operation results for web/JSON display.
Returns dictionaries suitable for FastAPI JSON serialization.
"""

from typing import Dict, Any

from models.result.news_result import NewsResult


class WebNewsOutputAdapter:
    """Format and display news results for web/JSON API."""

    def display_news_result(self, result: NewsResult) -> Dict[str, Any]:
        """Display news result as JSON-ready dict.

        Args:
            result: NewsResult containing news fetch and sentiment statistics

        Returns:
            Dictionary ready for FastAPI JSON serialization
        """
        return {
            "symbol": result.symbol,
            "source": result.source,
            "articles_found": result.articles_found,
            "sentiment_events_created": result.sentiment_events_created,
            "sentiment_events_stored": result.sentiment_events_stored,
            "sentiment_events_duplicates": result.sentiment_events_duplicates,
            "sentiment_events": result.sentiment_events,
            "errors": result.errors,
            "timestamp": result.timestamp.isoformat(),
            "has_articles": result.has_articles,
            "storage_success_rate": result.storage_success_rate,
        }
