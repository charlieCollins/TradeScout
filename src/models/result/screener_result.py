"""Screener result model - output-agnostic data structure for screener results.

This model contains all data needed to display screener results in any format
(CLI, Web, JSON, etc.). Commands create this model and pass it to output adapters.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class ScreenerListItem:
    """Single screener item for list display."""
    name: str
    description: str


@dataclass
class ScreenerListResult:
    """Result for screener list display - output-agnostic."""
    screeners: List[ScreenerListItem]


@dataclass
class ScreenerResult:
    """Result of a screener execution - output-agnostic.

    Attributes:
        screener_name: Name of the screener that was run
        results: List of stock results matching criteria
        screener_def: Screener configuration/definition
        resolved_config: Session-resolved configuration (field mappings, thresholds)
        market_context: MarketContext at time of execution
        excluded_count: Number of assets excluded due to no data
        snapshot_time: Optional snapshot time string
        sessions_text: Optional valid sessions text
        warnings: List of warning messages
        data_date_summary: Summary of actual data dates in database
    """

    screener_name: str
    results: List[Dict[str, Any]]
    screener_def: Dict[str, Any]
    resolved_config: Dict[str, Any]
    market_context: Any  # MarketContext object
    excluded_count: int
    snapshot_time: Optional[str] = None
    sessions_text: Optional[str] = None
    warnings: Optional[List[str]] = None
    data_date_summary: Optional[Dict[str, Any]] = None
