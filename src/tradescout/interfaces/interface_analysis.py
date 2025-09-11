"""
Analysis Interface for TradeScout

This interface defines analysis operations that work on top of market and asset data.
Analysis providers implement trading strategies, pattern detection, and market insights.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, List, Optional, Any


class AnalysisInterface(ABC):
    """Interface for market analysis and trading strategy operations"""

    @abstractmethod
    def get_gap_candidates(
        self,
        min_gap_percent: Decimal = Decimal("2.0"),
        max_gap_percent: Optional[Decimal] = None,
        session_type: str = "all"
    ) -> List[Dict[str, Any]]:
        """
        Identify stocks showing gap patterns in extended hours.
        
        Args:
            min_gap_percent: Minimum gap percentage to qualify
            max_gap_percent: Maximum gap percentage (None for no limit)
            session_type: "pre_market", "after_hours", or "all"
            
        Returns:
            List of gap candidates with analysis including:
            - symbol, current_price, gap_percent, volume
            - gap_direction (up/down), session, catalyst_score
        """
        pass

    @abstractmethod
    def analyze_gap_fill_probability(
        self,
        symbol: str,
        gap_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze the probability of a gap filling during regular session.
        
        Args:
            symbol: Stock ticker symbol
            gap_data: Gap information from get_gap_candidates
            
        Returns:
            Analysis including fill_probability, historical_fill_rate,
            volume_analysis, and recommended_action
        """
        pass

    @abstractmethod
    def get_trade_suggestions(
        self,
        analysis_type: str = "gap",
        limit: int = 10,
        risk_level: str = "moderate"
    ) -> List[Dict[str, Any]]:
        """
        Generate trade suggestions based on analysis.
        
        Args:
            analysis_type: Type of analysis ("gap", "momentum", "reversal")
            limit: Maximum number of suggestions
            risk_level: "conservative", "moderate", or "aggressive"
            
        Returns:
            List of trade suggestions with entry/exit points and risk metrics
        """
        pass

    @abstractmethod
    def scan_extended_hours_activity(
        self,
        min_volume: int = 100000,
        min_price_change_pct: Decimal = Decimal("1.0")
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Scan for significant extended hours activity.
        
        Args:
            min_volume: Minimum volume threshold
            min_price_change_pct: Minimum price change percentage
            
        Returns:
            Dictionary with "pre_market" and "after_hours" lists of active stocks
        """
        pass


class GapAnalysisInterface(ABC):
    """Specialized interface for gap trading analysis"""

    @abstractmethod
    def identify_gaps(
        self,
        market_data: Dict[str, Any],
        min_gap_percent: Decimal = Decimal("2.0")
    ) -> List[Dict[str, Any]]:
        """Identify gap opportunities from market data"""
        pass

    @abstractmethod
    def classify_gap_type(
        self,
        gap_data: Dict[str, Any]
    ) -> str:
        """
        Classify gap type: breakaway, runaway, exhaustion, or common.
        """
        pass

    @abstractmethod
    def calculate_gap_metrics(
        self,
        symbol: str,
        current_price: Decimal,
        previous_close: Decimal,
        volume: int
    ) -> Dict[str, Any]:
        """Calculate detailed gap metrics and statistics"""
        pass