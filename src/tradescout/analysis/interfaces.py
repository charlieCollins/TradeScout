"""
TradeScout Analysis Interfaces

Abstract interfaces for the analysis engine components.
These define the contracts for momentum detection, trade suggestion,
and performance tracking.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

from data_collection.domain_models_core import (
    Asset,
    MarketQuote,
    ExtendedHoursData,
    NewsItem,
    SocialSentiment,
)
from data_collection.domain_models_analysis import (
    TechnicalIndicators,
    TradeSuggestion,
    ActualTrade,
    PerformanceMetrics,
    MarketEvent,
    ConfidenceLevel,
    TradeSide,
)


class MomentumDetector(ABC):
    """Abstract interface for detecting momentum opportunities"""

    @abstractmethod
    def analyze_gap_momentum(
        self, quote: MarketQuote, extended_data: ExtendedHoursData
    ) -> Dict[str, any]:
        """
        Analyze gap momentum based on price action

        Args:
            quote: Current market quote
            extended_data: Pre-market or after-hours data

        Returns:
            Dictionary with momentum analysis results
        """
        pass

    @abstractmethod
    def analyze_volume_momentum(
        self, quote: MarketQuote, historical_volume: List[int]
    ) -> Dict[str, any]:
        """
        Analyze volume-based momentum

        Args:
            quote: Current market quote
            historical_volume: Historical volume data for comparison

        Returns:
            Dictionary with volume momentum analysis
        """
        pass

    @abstractmethod
    def analyze_news_momentum(
        self, symbol: str, news: List[NewsItem], sentiment: Optional[SocialSentiment]
    ) -> Dict[str, any]:
        """
        Analyze momentum from news and sentiment

        Args:
            symbol: Stock symbol
            news: Recent news items
            sentiment: Social sentiment data

        Returns:
            Dictionary with news/sentiment momentum analysis
        """
        pass

    @abstractmethod
    def calculate_momentum_score(
        self, symbol: str, analysis_data: Dict[str, any]
    ) -> Decimal:
        """
        Calculate overall momentum score

        Args:
            symbol: Stock symbol
            analysis_data: Combined analysis data

        Returns:
            Momentum score (0.0 to 1.0)
        """
        pass


class TechnicalAnalyzer(ABC):
    """Abstract interface for technical analysis"""

    @abstractmethod
    def analyze_trend(self, quotes: List[MarketQuote]) -> Dict[str, any]:
        """
        Analyze price trend

        Args:
            quotes: Historical price quotes

        Returns:
            Trend analysis results
        """
        pass

    @abstractmethod
    def detect_breakout_patterns(self, quotes: List[MarketQuote]) -> List[str]:
        """
        Detect breakout patterns

        Args:
            quotes: Historical price quotes

        Returns:
            List of detected patterns
        """
        pass

    @abstractmethod
    def calculate_support_resistance(
        self, quotes: List[MarketQuote]
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate key support and resistance levels

        Args:
            quotes: Historical price quotes

        Returns:
            Tuple of (support_level, resistance_level)
        """
        pass

    @abstractmethod
    def analyze_indicators(self, quotes: List[MarketQuote]) -> TechnicalIndicators:
        """
        Calculate technical indicators

        Args:
            quotes: Historical price quotes

        Returns:
            Technical indicators object
        """
        pass

    @abstractmethod
    def is_favorable_setup(
        self, indicators: TechnicalIndicators, momentum_score: Decimal
    ) -> bool:
        """
        Determine if technical setup is favorable for trade

        Args:
            indicators: Technical indicators
            momentum_score: Current momentum score

        Returns:
            True if setup is favorable
        """
        pass


class RiskCalculator(ABC):
    """Abstract interface for risk/reward calculations"""

    @abstractmethod
    def calculate_position_size(
        self,
        account_balance: Decimal,
        risk_per_trade: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
    ) -> int:
        """
        Calculate appropriate position size

        Args:
            account_balance: Current account balance
            risk_per_trade: Risk percentage (e.g., 0.02 for 2%)
            entry_price: Planned entry price
            stop_loss: Stop loss price

        Returns:
            Number of shares to trade
        """
        pass

    @abstractmethod
    def calculate_stop_loss(
        self,
        entry_price: Decimal,
        side: TradeSide,
        volatility: Decimal,
        support_resistance: Tuple[Decimal, Decimal],
    ) -> Decimal:
        """
        Calculate optimal stop loss level

        Args:
            entry_price: Entry price
            side: Trade side (LONG/SHORT)
            volatility: Current volatility measure
            support_resistance: Support and resistance levels

        Returns:
            Stop loss price
        """
        pass

    @abstractmethod
    def calculate_take_profit_levels(
        self,
        entry_price: Decimal,
        stop_loss: Decimal,
        side: TradeSide,
        target_ratio: Decimal = Decimal(1.5),
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate take profit levels

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            side: Trade side
            target_ratio: Risk/reward ratio target

        Returns:
            Tuple of (take_profit_1, take_profit_2)
        """
        pass

    @abstractmethod
    def validate_risk_reward(
        self,
        entry: Decimal,
        stop: Decimal,
        take_profit: Decimal,
        min_ratio: Decimal = Decimal(1.0),
    ) -> bool:
        """
        Validate risk/reward ratio meets minimum requirements

        Args:
            entry: Entry price
            stop: Stop loss price
            take_profit: Take profit price
            min_ratio: Minimum acceptable risk/reward ratio

        Returns:
            True if ratio is acceptable
        """
        pass


class SuggestionEngine(ABC):
    """Abstract interface for generating trade suggestions"""

    @abstractmethod
    def generate_suggestion(
        self, symbol: str, analysis_data: Dict[str, any]
    ) -> Optional[TradeSuggestion]:
        """
        Generate a trade suggestion based on analysis

        Args:
            symbol: Stock symbol
            analysis_data: Combined analysis results

        Returns:
            Trade suggestion or None if no valid setup
        """
        pass

    @abstractmethod
    def rank_suggestions(
        self, suggestions: List[TradeSuggestion]
    ) -> List[TradeSuggestion]:
        """
        Rank suggestions by quality/confidence

        Args:
            suggestions: List of trade suggestions

        Returns:
            Sorted list (best first)
        """
        pass

    @abstractmethod
    def filter_suggestions(
        self, suggestions: List[TradeSuggestion], max_suggestions: int = 5
    ) -> List[TradeSuggestion]:
        """
        Filter suggestions to top candidates

        Args:
            suggestions: List of trade suggestions
            max_suggestions: Maximum number to return

        Returns:
            Filtered list of best suggestions
        """
        pass

    @abstractmethod
    def validate_suggestion(self, suggestion: TradeSuggestion) -> bool:
        """
        Validate that suggestion meets quality criteria

        Args:
            suggestion: Trade suggestion to validate

        Returns:
            True if suggestion is valid
        """
        pass


class PerformanceTracker(ABC):
    """Abstract interface for tracking performance"""

    @abstractmethod
    def track_suggestion_performance(self, suggestion: TradeSuggestion) -> None:
        """
        Track performance of a trade suggestion

        Args:
            suggestion: Trade suggestion to track
        """
        pass

    @abstractmethod
    def record_actual_trade(self, trade: ActualTrade) -> None:
        """
        Record an actual trade execution

        Args:
            trade: Actual trade details
        """
        pass

    @abstractmethod
    def update_suggestion_outcome(
        self, suggestion_id: str, max_profit: Decimal, max_loss: Decimal
    ) -> None:
        """
        Update suggestion with actual market performance

        Args:
            suggestion_id: ID of the suggestion
            max_profit: Maximum profit reached
            max_loss: Maximum loss reached
        """
        pass

    @abstractmethod
    def calculate_period_performance(
        self, start_date: datetime, end_date: datetime
    ) -> PerformanceMetrics:
        """
        Calculate performance metrics for a period

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period

        Returns:
            Performance metrics
        """
        pass

    @abstractmethod
    def get_suggestion_accuracy(self, lookback_days: int = 30) -> Dict[str, Decimal]:
        """
        Get suggestion accuracy statistics

        Args:
            lookback_days: Days to look back

        Returns:
            Dictionary with accuracy metrics
        """
        pass


class MarketSessionManager(ABC):
    """Abstract interface for managing market sessions and timing"""

    @abstractmethod
    def get_current_session(self) -> str:
        """Get current market session"""
        pass

    @abstractmethod
    def is_market_open(self) -> bool:
        """Check if market is currently open"""
        pass

    @abstractmethod
    def time_until_market_open(self) -> timedelta:
        """Calculate time until market opens"""
        pass

    @abstractmethod
    def time_until_market_close(self) -> timedelta:
        """Calculate time until market closes"""
        pass

    @abstractmethod
    def should_run_analysis(self, analysis_type: str) -> bool:
        """
        Determine if analysis should run based on market timing

        Args:
            analysis_type: Type of analysis (e.g., "morning", "evening", "realtime")

        Returns:
            True if analysis should run
        """
        pass


class AlertManager(ABC):
    """Abstract interface for managing alerts and notifications"""

    @abstractmethod
    def send_morning_report(
        self, suggestions: List[TradeSuggestion], performance: PerformanceMetrics
    ) -> bool:
        """
        Send morning report with suggestions

        Args:
            suggestions: Trade suggestions for the day
            performance: Recent performance metrics

        Returns:
            True if sent successfully
        """
        pass

    @abstractmethod
    def send_trade_alert(self, suggestion: TradeSuggestion) -> bool:
        """
        Send immediate trade alert

        Args:
            suggestion: Urgent trade suggestion

        Returns:
            True if sent successfully
        """
        pass

    @abstractmethod
    def send_performance_update(self, metrics: PerformanceMetrics) -> bool:
        """
        Send performance update

        Args:
            metrics: Performance metrics

        Returns:
            True if sent successfully
        """
        pass


class MarketScanner(ABC):
    """Abstract interface for scanning the market for opportunities"""

    @abstractmethod
    def scan_pre_market_gaps(
        self, min_gap_percent: Decimal = Decimal(1.0)
    ) -> List[MarketQuote]:
        """
        Scan for pre-market gaps

        Args:
            min_gap_percent: Minimum gap percentage to include

        Returns:
            List of stocks with significant gaps
        """
        pass

    @abstractmethod
    def scan_volume_spikes(
        self, min_volume_ratio: Decimal = Decimal(2.0)
    ) -> List[MarketQuote]:
        """
        Scan for unusual volume activity

        Args:
            min_volume_ratio: Minimum volume ratio vs average

        Returns:
            List of stocks with volume spikes
        """
        pass

    @abstractmethod
    def scan_news_catalysts(
        self, max_age_hours: int = 24
    ) -> List[Tuple[str, List[NewsItem]]]:
        """
        Scan for stocks with recent news catalysts

        Args:
            max_age_hours: Maximum age of news to consider

        Returns:
            List of (symbol, news_items) tuples
        """
        pass

    @abstractmethod
    def scan_earnings_plays(self, days_ahead: int = 1) -> List[MarketEvent]:
        """
        Scan for upcoming earnings that could create momentum

        Args:
            days_ahead: Days to look ahead for earnings

        Returns:
            List of earnings events
        """
        pass


class AnalysisOrchestrator(ABC):
    """
    Main orchestrator that coordinates all analysis components
    """

    @abstractmethod
    def run_morning_analysis(self) -> List[TradeSuggestion]:
        """
        Run comprehensive morning analysis

        Returns:
            List of trade suggestions for the day
        """
        pass

    @abstractmethod
    def run_evening_analysis(self) -> Dict[str, any]:
        """
        Run evening analysis to prepare for next day

        Returns:
            Analysis results and preparation data
        """
        pass

    @abstractmethod
    def run_realtime_scan(self, symbols: List[str]) -> List[TradeSuggestion]:
        """
        Run real-time opportunity scan

        Args:
            symbols: Symbols to scan

        Returns:
            List of immediate trade opportunities
        """
        pass

    @abstractmethod
    def analyze_symbol(self, symbol: str) -> Optional[TradeSuggestion]:
        """
        Perform comprehensive analysis on a single symbol

        Args:
            symbol: Stock symbol to analyze

        Returns:
            Trade suggestion if opportunity found
        """
        pass
