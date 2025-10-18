"""Result models for gap command outputs."""

from dataclasses import dataclass
from datetime import date
from typing import List, Dict


@dataclass
class GapResultRow:
    """Single gap result row for display."""
    symbol: str
    name: str
    session_type: str
    gap_percentage: float
    academic_gap_type: str
    volume_ratio: float
    market_cap: float
    status: str
    rejection_reason: str


@dataclass
class GapResultsByDate:
    """Gap results grouped by trading date."""
    trading_date: date
    results: List[GapResultRow]
    total_count: int  # Total results for this date
    shown_count: int  # Number shown (may be limited)


@dataclass
class GapResultsListResult:
    """Result for gap results list display."""
    results_by_date: List[GapResultsByDate]  # Results grouped by date
    dates_shown: int
    total_results_shown: int
    total_results_hidden: int
    start_date: date
    end_date: date
    total_count: int
    passed_count: int
    rejected_count: int
