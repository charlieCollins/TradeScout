"""
Sentiment Domain Models for TradeScout

Models representing sentiment data for assets and markets.
These models are used by the SentimentDataInterface operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from .models_asset import Asset


class SentimentSource(Enum):
    """Sources of sentiment data"""
    NEWS = "news"
    SOCIAL_MEDIA = "social_media"
    ANALYST = "analyst"
    INSIDER = "insider"
    OPTIONS_FLOW = "options_flow"
    COMBINED = "combined"


class SentimentScore(Enum):
    """Sentiment score categories"""
    VERY_BEARISH = "very_bearish"  # < -0.6
    BEARISH = "bearish"  # -0.6 to -0.2
    NEUTRAL = "neutral"  # -0.2 to 0.2
    BULLISH = "bullish"  # 0.2 to 0.6
    VERY_BULLISH = "very_bullish"  # > 0.6


class AnalystRating(Enum):
    """Analyst rating categories"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


@dataclass
class AssetSentiment:
    """Sentiment data for a specific asset"""
    
    asset: Asset
    timestamp: datetime
    lookback_hours: int
    
    # Overall sentiment
    overall_score: Decimal  # -1.0 to 1.0
    overall_category: SentimentScore
    confidence: Decimal  # 0.0 to 1.0
    
    # Volume metrics
    mention_count: int
    mention_velocity: Decimal  # Rate of change in mentions
    
    # Source breakdown
    news_score: Optional[Decimal] = None
    social_score: Optional[Decimal] = None
    analyst_score: Optional[Decimal] = None
    
    # Trending topics
    positive_keywords: List[str] = field(default_factory=list)
    negative_keywords: List[str] = field(default_factory=list)
    
    # Change metrics
    score_change_24h: Optional[Decimal] = None
    score_change_7d: Optional[Decimal] = None
    
    @property
    def is_trending(self) -> bool:
        """Check if sentiment is trending (high velocity)"""
        return self.mention_velocity > 2.0
    
    @property
    def has_consensus(self) -> bool:
        """Check if different sources agree"""
        scores = [s for s in [self.news_score, self.social_score, self.analyst_score] if s]
        if len(scores) >= 2:
            return all(s > 0 for s in scores) or all(s < 0 for s in scores)
        return False


@dataclass
class MarketSentiment:
    """Overall market sentiment data"""
    
    timestamp: datetime
    lookback_hours: int
    market_segment: str  # "overall", "sp500", "nasdaq", etc.
    
    # Overall metrics
    overall_score: Decimal  # -1.0 to 1.0
    fear_greed_index: int  # 0-100
    bullish_percent: Decimal  # Percentage of bullish indicators
    
    # Breadth metrics
    stocks_bullish: int
    stocks_bearish: int
    stocks_neutral: int
    
    # Themes and concerns
    top_concerns: List[str] = field(default_factory=list)
    top_opportunities: List[str] = field(default_factory=list)
    
    # VIX/Volatility sentiment
    volatility_expectation: Optional[str] = None  # "increasing", "stable", "decreasing"
    
    @property
    def market_mood(self) -> str:
        """Categorize overall market mood"""
        if self.fear_greed_index >= 80:
            return "extreme_greed"
        elif self.fear_greed_index >= 60:
            return "greed"
        elif self.fear_greed_index >= 40:
            return "neutral"
        elif self.fear_greed_index >= 20:
            return "fear"
        else:
            return "extreme_fear"


@dataclass
class NewsItem:
    """Individual news item with sentiment"""
    
    # Required fields first
    headline: str
    source: str
    published_time: datetime
    sentiment_score: Decimal  # -1.0 to 1.0
    relevance_score: Decimal  # 0.0 to 1.0
    
    # Optional fields with defaults
    summary: Optional[str] = None
    url: Optional[str] = None
    mentioned_symbols: List[str] = field(default_factory=list)
    primary_symbol: Optional[str] = None
    
    # Categorization
    categories: List[str] = field(default_factory=list)
    is_breaking: bool = False
    
    @property
    def is_significant(self) -> bool:
        """Check if news is significant"""
        return (
            abs(self.sentiment_score) > 0.5 and
            self.relevance_score > 0.7
        ) or self.is_breaking


@dataclass
class SocialMention:
    """Social media mention with sentiment"""
    
    platform: str  # "reddit", "twitter", "stocktwits"
    author: str
    content: str
    timestamp: datetime
    
    # Metrics
    sentiment_score: Decimal
    reach: int  # followers/subscribers
    engagement: int  # likes + shares + comments
    
    # Influence
    author_reputation: Optional[Decimal] = None
    is_influencer: bool = False
    
    @property
    def impact_score(self) -> Decimal:
        """Calculate potential impact of mention"""
        base_score = abs(self.sentiment_score)
        if self.is_influencer:
            base_score *= 2
        if self.engagement > 1000:
            base_score *= 1.5
        return min(base_score, Decimal("1.0"))


@dataclass
class AnalystReport:
    """Analyst rating and report"""
    
    asset: Asset
    analyst_firm: str
    analyst_name: Optional[str]
    report_date: datetime
    
    # Rating
    rating: AnalystRating
    previous_rating: Optional[AnalystRating] = None
    
    # Price targets
    price_target: Optional[Decimal] = None
    previous_target: Optional[Decimal] = None
    
    # Analysis
    summary: Optional[str] = None
    key_points: List[str] = field(default_factory=list)
    
    # Credibility
    analyst_ranking: Optional[int] = None  # Analyst rank/score
    firm_reputation: Optional[Decimal] = None  # 0.0 to 1.0
    
    @property
    def is_upgrade(self) -> bool:
        """Check if this is an upgrade"""
        if self.previous_rating:
            rating_order = [
                AnalystRating.STRONG_SELL,
                AnalystRating.SELL,
                AnalystRating.HOLD,
                AnalystRating.BUY,
                AnalystRating.STRONG_BUY
            ]
            return rating_order.index(self.rating) > rating_order.index(self.previous_rating)
        return False


@dataclass
class SentimentTrend:
    """Sentiment trend over time"""
    
    asset: Optional[Asset]  # None for market-wide
    time_points: List[datetime]
    sentiment_scores: List[Decimal]
    mention_volumes: List[int]
    
    @property
    def trend_direction(self) -> str:
        """Determine trend direction"""
        if len(self.sentiment_scores) >= 2:
            recent = sum(self.sentiment_scores[-3:]) / min(3, len(self.sentiment_scores[-3:]))
            older = sum(self.sentiment_scores[:-3]) / max(1, len(self.sentiment_scores[:-3]))
            
            if recent > older + 0.1:
                return "improving"
            elif recent < older - 0.1:
                return "deteriorating"
        return "stable"