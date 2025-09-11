"""
Sentiment Data Interface for TradeScout

This interface defines sentiment data operations for both individual assets
and overall market sentiment. Sentiment can come from news, social media,
analyst ratings, or other sources.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any


class SentimentDataInterface(ABC):
    """Interface for sentiment data operations spanning assets and markets"""

    @abstractmethod
    def get_asset_sentiment(
        self,
        symbol: str,
        lookback_hours: int = 24
    ) -> Optional[Dict[str, Any]]:
        """
        Get sentiment data for a specific asset.
        
        Args:
            symbol: Stock ticker symbol
            lookback_hours: Hours to look back for sentiment data
            
        Returns:
            Dictionary with sentiment metrics:
            - overall_score: -1.0 to 1.0 (bearish to bullish)
            - volume: Number of mentions/articles
            - sources: Breakdown by source (news, social, analyst)
            - trend: Sentiment change over time
        """
        pass

    @abstractmethod
    def get_market_sentiment(
        self,
        market: str = "overall",
        lookback_hours: int = 24
    ) -> Optional[Dict[str, Any]]:
        """
        Get overall market sentiment.
        
        Args:
            market: Market segment ("overall", "sp500", "nasdaq", "sector:tech", etc.)
            lookback_hours: Hours to look back for sentiment data
            
        Returns:
            Dictionary with market sentiment:
            - overall_score: -1.0 to 1.0
            - bullish_percent: Percentage of bullish indicators
            - fear_greed_index: 0-100 scale
            - top_concerns: List of trending concerns
            - top_optimism: List of positive themes
        """
        pass

    @abstractmethod
    def get_trending_sentiment(
        self,
        limit: int = 20,
        sentiment_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Get assets with strongest sentiment signals (positive or negative).
        
        Args:
            limit: Maximum number of results
            sentiment_threshold: Minimum absolute sentiment score to include
            
        Returns:
            List of trending sentiment stocks with:
            - symbol, sentiment_score, change_24h
            - mention_volume, key_drivers
        """
        pass

    @abstractmethod
    def get_news_sentiment(
        self,
        symbols: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get news items with sentiment analysis.
        
        Args:
            symbols: Filter for specific symbols (None for all)
            limit: Maximum number of news items
            
        Returns:
            List of news items with:
            - headline, summary, sentiment_score
            - symbols_mentioned, published_time, source
        """
        pass

    @abstractmethod
    def get_social_sentiment(
        self,
        symbol: str,
        platforms: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get social media sentiment for an asset.
        
        Args:
            symbol: Stock ticker symbol
            platforms: List of platforms to check (None for all available)
            
        Returns:
            Dictionary with platform-specific sentiment:
            - reddit: {score, volume, top_posts}
            - twitter: {score, volume, influencer_sentiment}
            - stocktwits: {score, volume, bull_bear_ratio}
        """
        pass

    @abstractmethod
    def get_analyst_sentiment(
        self,
        symbol: str,
        days_back: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        Get analyst ratings and sentiment.
        
        Args:
            symbol: Stock ticker symbol
            days_back: Days to look back for ratings changes
            
        Returns:
            Dictionary with analyst sentiment:
            - consensus_rating: (strong_buy, buy, hold, sell, strong_sell)
            - average_target: Average price target
            - recent_changes: List of recent rating changes
            - bullish_percent: Percentage of buy ratings
        """
        pass