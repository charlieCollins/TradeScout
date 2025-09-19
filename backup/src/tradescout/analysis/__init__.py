"""
Analysis Package

Core analysis modules for gap trading and market analysis:
- Gap detection and classification
- Market scanning for opportunities
- Rules-based trading decisions
- Trade suggestion generation
"""

from .gap_analyzer import GapAnalyzer

__all__ = [
    "GapAnalyzer",
]
