"""Sentiment analyzer for calculating overall sentiment scores from news articles.

Pure business logic - no database, no API calls, just calculations on model objects.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from dataclasses import dataclass

from models.dataclass.sentiment_event import SentimentEvent

logger = logging.getLogger(__name__)


@dataclass
class SentimentScore:
    """Result of sentiment analysis calculation."""

    symbol: str
    overall_score: float  # -1.0 (very negative) to +1.0 (very positive)
    articles_analyzed: int
    sentiment_breakdown: dict  # {"positive": 5, "negative": 2, "neutral": 2, "mixed": 1}
    time_window_days: int
    oldest_article_date: Optional[datetime]
    newest_article_date: Optional[datetime]
    score_thresholds: dict  # Thresholds for sentiment labels
    confidence_thresholds: dict  # Thresholds for confidence levels

    @property
    def sentiment_label(self) -> str:
        """Get human-readable sentiment label.

        Uses thresholds passed at initialization (from configs/sentiment.yaml)
        """
        score = self.overall_score
        thresholds = self.score_thresholds

        if score >= thresholds["very_positive"]:
            return "Very Positive"
        elif score >= thresholds["positive"]:
            return "Positive"
        elif score >= thresholds["neutral_high"]:
            return "Neutral"
        elif score > thresholds["neutral_low"]:
            return "Neutral"
        elif score > thresholds["negative"]:
            return "Negative"
        elif score > thresholds["very_negative"]:
            return "Negative"
        else:
            return "Very Negative"

    @property
    def confidence_level(self) -> str:
        """Get confidence level based on number of articles.

        Uses thresholds passed at initialization (from configs/sentiment.yaml)
        """
        count = self.articles_analyzed
        thresholds = self.confidence_thresholds

        if count >= thresholds["very_high"]:
            return "Very High"
        elif count >= thresholds["high"]:
            return "High"
        elif count >= thresholds["medium"]:
            return "Medium"
        elif count >= thresholds["low"]:
            return "Low"
        else:
            return "Very Low"


class SentimentAnalyzer:
    """Analyze sentiment from news articles to produce overall sentiment score.

    This is pure business logic - takes model objects, returns calculated results.
    """

    # Sentiment value mappings (categorical → numeric)
    SENTIMENT_VALUES = {
        "positive": 1.0,
        "negative": -1.0,
        "neutral": 0.0,
        "mixed": 0.0,  # Mixed sentiment = neutral in aggregate
    }

    def __init__(self, time_window_days: int = 5):
        """Initialize sentiment analyzer.

        Loads and validates sentiment config at initialization time.

        Args:
            time_window_days: Only analyze articles within this many days (default: 5)

        Raises:
            ConfigValidationError: If sentiment config is invalid
        """
        from utils.config_loader import get_config_loader

        self.time_window_days = time_window_days

        # Load and validate config once at initialization
        config_loader = get_config_loader()
        sentiment_config = config_loader.load_sentiment_config()

        # Store thresholds for use in SentimentScore objects
        self.score_thresholds = sentiment_config["score_thresholds"]
        self.confidence_thresholds = sentiment_config["confidence_thresholds"]

    def calculate_sentiment_score(
        self, symbol: str, sentiment_events: List[SentimentEvent]
    ) -> SentimentScore:
        """Calculate overall sentiment score from sentiment events.

        Args:
            symbol: Stock symbol
            sentiment_events: List of SentimentEvent objects (max 10, but may use fewer)

        Returns:
            SentimentScore with overall score and breakdown
        """
        if not sentiment_events:
            return SentimentScore(
                symbol=symbol,
                overall_score=0.0,
                articles_analyzed=0,
                sentiment_breakdown={},
                time_window_days=self.time_window_days,
                oldest_article_date=None,
                newest_article_date=None,
                score_thresholds=self.score_thresholds,
                confidence_thresholds=self.confidence_thresholds,
            )

        # Filter sentiment events by time window
        cutoff_date = datetime.now().date() - timedelta(days=self.time_window_days)
        recent_events = [
            event
            for event in sentiment_events
            if event.event_date >= cutoff_date
        ]

        if not recent_events:
            logger.debug(
                f"No sentiment events within {self.time_window_days} day window for {symbol}"
            )
            return SentimentScore(
                symbol=symbol,
                overall_score=0.0,
                articles_analyzed=0,
                sentiment_breakdown={},
                time_window_days=self.time_window_days,
                oldest_article_date=None,
                newest_article_date=None,
                score_thresholds=self.score_thresholds,
                confidence_thresholds=self.confidence_thresholds,
            )

        # Calculate sentiment breakdown and scores
        sentiment_breakdown = {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0}
        sentiment_values = []

        for event in recent_events:
            sentiment = event.get_detail("sentiment")
            if sentiment:
                sentiment_lower = sentiment.lower()
                sentiment_breakdown[sentiment_lower] = (
                    sentiment_breakdown.get(sentiment_lower, 0) + 1
                )

                # Convert to numeric value
                numeric_value = self.SENTIMENT_VALUES.get(sentiment_lower, 0.0)
                sentiment_values.append(numeric_value)

        # Calculate average sentiment score
        if sentiment_values:
            overall_score = sum(sentiment_values) / len(sentiment_values)
        else:
            overall_score = 0.0

        # Get date range
        sorted_events = sorted(recent_events, key=lambda e: (e.event_date, e.event_time or datetime.min.time()))
        oldest = None
        newest = None
        if sorted_events:
            oldest_event = sorted_events[0]
            newest_event = sorted_events[-1]
            oldest = datetime.combine(oldest_event.event_date, oldest_event.event_time or datetime.min.time())
            newest = datetime.combine(newest_event.event_date, newest_event.event_time or datetime.min.time())

        logger.debug(
            f"Sentiment analysis for {symbol}: {len(recent_events)} events, "
            f"score={overall_score:.2f}, breakdown={sentiment_breakdown}"
        )

        return SentimentScore(
            symbol=symbol,
            overall_score=round(overall_score, 3),
            articles_analyzed=len(recent_events),
            sentiment_breakdown=sentiment_breakdown,
            time_window_days=self.time_window_days,
            oldest_article_date=oldest,
            newest_article_date=newest,
            score_thresholds=self.score_thresholds,
            confidence_thresholds=self.confidence_thresholds,
        )

    def calculate_weighted_sentiment_score(
        self, symbol: str, sentiment_events: List[SentimentEvent], recency_weight: float = 0.3
    ) -> SentimentScore:
        """Calculate sentiment score with recency weighting (newer events weighted more).

        Args:
            symbol: Stock symbol
            sentiment_events: List of SentimentEvent objects
            recency_weight: Weight factor for recency (0.0-1.0, default 0.3)

        Returns:
            SentimentScore with weighted overall score
        """
        if not sentiment_events:
            return self.calculate_sentiment_score(symbol, sentiment_events)

        # Filter by time window
        cutoff_date = datetime.now().date() - timedelta(days=self.time_window_days)
        recent_events = [
            event
            for event in sentiment_events
            if event.event_date >= cutoff_date
        ]

        if not recent_events:
            return self.calculate_sentiment_score(symbol, sentiment_events)

        # Sort by date (oldest first)
        sorted_events = sorted(recent_events, key=lambda e: (e.event_date, e.event_time or datetime.min.time()))

        # Calculate weighted scores
        sentiment_breakdown = {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0}
        total_weighted_score = 0.0
        total_weight = 0.0

        for i, event in enumerate(sorted_events):
            sentiment = event.get_detail("sentiment")
            if sentiment:
                sentiment_lower = sentiment.lower()
                sentiment_breakdown[sentiment_lower] = (
                    sentiment_breakdown.get(sentiment_lower, 0) + 1
                )

                # Calculate weight (more recent = higher weight)
                # Linear weighting: oldest event gets weight 1.0, newest gets 1.0 + recency_weight
                position_factor = i / max(len(sorted_events) - 1, 1)
                weight = 1.0 + (recency_weight * position_factor)

                # Get numeric sentiment value
                numeric_value = self.SENTIMENT_VALUES.get(sentiment_lower, 0.0)

                total_weighted_score += numeric_value * weight
                total_weight += weight

        # Calculate weighted average
        overall_score = total_weighted_score / total_weight if total_weight > 0 else 0.0

        oldest = None
        newest = None
        if sorted_events:
            oldest_event = sorted_events[0]
            newest_event = sorted_events[-1]
            oldest = datetime.combine(oldest_event.event_date, oldest_event.event_time or datetime.min.time())
            newest = datetime.combine(newest_event.event_date, newest_event.event_time or datetime.min.time())

        logger.info(
            f"Weighted sentiment analysis for {symbol}: {len(recent_events)} events, "
            f"score={overall_score:.2f} (recency_weight={recency_weight}), "
            f"breakdown={sentiment_breakdown}"
        )

        return SentimentScore(
            symbol=symbol,
            overall_score=round(overall_score, 3),
            articles_analyzed=len(recent_events),
            sentiment_breakdown=sentiment_breakdown,
            time_window_days=self.time_window_days,
            oldest_article_date=oldest,
            newest_article_date=newest,
            score_thresholds=self.score_thresholds,
            confidence_thresholds=self.confidence_thresholds,
        )
