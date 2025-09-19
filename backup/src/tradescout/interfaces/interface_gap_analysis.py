"""
Gap Analysis Interface for TradeScout

Specialized interface for gap trading analysis operations.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Any, List, Optional

from ..data_models.models_asset import PriceData
from ..data_models.models_analysis import GapRules, GapCandidate, GapAssessment
from ..data_models.models_market import MarketStatus


class GapAnalysisInterface(ABC):
    """Specialized interface for gap trading analysis"""

    @abstractmethod
    def identify_gap_candidates(
        self,
        price_data_list: List[PriceData],
        rules: GapRules,
        session_type: MarketStatus,
    ) -> List[GapCandidate]:
        """
        Identify gap candidates from a list of price data using specified rules.

        Args:
            price_data_list: List of PriceData objects to analyze
            rules: GapRules configuration for filtering candidates
            session_type: Current market session type

        Returns:
            List of GapCandidate objects for stocks meeting the gap criteria
        """
        pass

    @abstractmethod
    def process_gap_candidate(self, gap_candidate: GapCandidate) -> GapAssessment:
        """
        Analyze risk assessment for a single gap candidate.

        Args:
            gap_candidate: GapCandidate object from identify_gap_candidates

        Returns:
            GapAssessment with comprehensive risk analysis and trade parameters
        """
        pass

    @abstractmethod
    def process_gap_candidates(
        self, gap_candidates: List[GapCandidate]
    ) -> List[GapAssessment]:
        """
        Analyze risk assessment for multiple gap candidates.

        Args:
            gap_candidates: List of GapCandidate objects from identify_gap_candidates

        Returns:
            List of GapAssessment objects with risk analysis for each candidate
        """
        pass

    @abstractmethod
    def get_gap_suggestions(
        self,
        gap_candidates: List[GapCandidate],
        limit: int = 5,
        min_gap_percent: float = 2.0,
    ) -> List[GapAssessment]:
        """
        Get comprehensive gap trading suggestions from identified gap candidates.

        This method processes already identified gap candidates:
        1. Process candidates for risk assessment
        2. Filter and rank results based on criteria

        Args:
            gap_candidates: List of GapCandidate objects already identified
            limit: Maximum number of suggestions to return
            min_gap_percent: Minimum gap percentage threshold

        Returns:
            List of GapAssessment objects representing trading suggestions,
            filtered and ranked by quality and risk parameters
        """
        pass
