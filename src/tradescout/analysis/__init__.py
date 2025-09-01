"""
Analysis Package

Core analysis modules:
- Technical analysis and indicators
- Gap detection and momentum analysis
- Trade suggestion engine
- Performance tracking
"""

# Legacy imports (if they exist)
try:
    from .gap_scanner import GapScanner
    from .performance_tracker import PerformanceTracker
    from .suggestion_engine import SuggestionEngine
    from .technical_analysis import TechnicalAnalyzer
except ImportError:
    pass

# New gap trading analysis components
from .academic_gap_analyzer import AcademicGapTypeAnalyzer
from .gap_market_scanner import GapMarketScanner
from .gap_rules_engine import GapRulesEngine
from .gap_suggestion_engine import GapTradeSuggestionEngine

__all__ = [
    # Legacy components (if available)
    "GapScanner",
    "PerformanceTracker", 
    "SuggestionEngine",
    "TechnicalAnalyzer",
    # New gap trading components
    "AcademicGapTypeAnalyzer",
    "GapMarketScanner",
    "GapRulesEngine", 
    "GapTradeSuggestionEngine",
]
