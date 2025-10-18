"""Web output adapter for gap analysis results.

Formats gap trading analysis results for web/JSON display.
Returns dictionaries suitable for FastAPI JSON serialization.
"""

from typing import Dict, Any

from models.result.gap_result import GapResultsListResult


class WebGapOutputAdapter:
    """Format and display gap analysis results for web/JSON API."""

    def display_gap_results_list(self, result: GapResultsListResult) -> Dict[str, Any]:
        """Display gap results list as JSON-ready dict.

        Args:
            result: GapResultsListResult containing gap analysis results

        Returns:
            Dictionary ready for FastAPI JSON serialization
        """
        results_by_date = []
        for date_group in result.results_by_date:
            results_by_date.append({
                "trading_date": str(date_group.trading_date),
                "total_count": date_group.total_count,
                "shown_count": date_group.shown_count,
                "results": [
                    {
                        "symbol": row.symbol,
                        "name": row.name,
                        "session_type": row.session_type,
                        "gap_percentage": row.gap_percentage,
                        "academic_gap_type": row.academic_gap_type,
                        "volume_ratio": row.volume_ratio,
                        "market_cap": row.market_cap,
                        "status": row.status,
                        "rejection_reason": row.rejection_reason,
                    }
                    for row in date_group.results
                ]
            })

        return {
            "start_date": str(result.start_date),
            "end_date": str(result.end_date),
            "dates_shown": result.dates_shown,
            "total_results_shown": result.total_results_shown,
            "total_results_hidden": result.total_results_hidden,
            "total_count": result.total_count,
            "passed_count": result.passed_count,
            "rejected_count": result.rejected_count,
            "results_by_date": results_by_date,
        }
