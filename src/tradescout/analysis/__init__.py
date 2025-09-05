"""
Analysis Package

Core analysis modules for gap trading and market analysis:
- Gap detection and classification
- Market scanning for opportunities
- Rules-based trading decisions
- Trade suggestion generation
"""

from .academic_gap_analyzer import AcademicGapTypeAnalyzer
from .gap_market_scanner import GapMarketScanner
from .gap_rules_engine import GapRulesEngine
from .gap_suggestion_engine import GapTradeSuggestionEngine

__all__ = [
    "AcademicGapTypeAnalyzer",
    "GapMarketScanner",
    "GapRulesEngine",
    "GapTradeSuggestionEngine",
]
