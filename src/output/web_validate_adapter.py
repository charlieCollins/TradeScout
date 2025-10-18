"""Web output adapter for validate results.

Formats validation operation results for web/JSON display.
Returns dictionaries suitable for FastAPI JSON serialization.
"""

from typing import Dict, Any

from models.result.validate_result import VolumeValidationResult


class WebValidateOutputAdapter:
    """Format and display validation results for web/JSON API."""

    def display_volume_validation_result(self, result: VolumeValidationResult) -> Dict[str, Any]:
        """Display volume validation result as JSON-ready dict.

        Args:
            result: VolumeValidationResult containing volume comparison data

        Returns:
            Dictionary ready for FastAPI JSON serialization
        """
        return {
            "session": result.session,
            "trading_date": str(result.trading_date),
            "is_extended_hours": result.is_extended_hours,
            "rows": [
                {
                    "symbol": row.symbol,
                    "snapshot_volume": row.snapshot_volume,
                    "snapshot_time": row.snapshot_time.isoformat() if row.snapshot_time else None,
                    "aggregates_volume": row.aggregates_volume,
                    "aggregates_time": row.aggregates_time.isoformat() if row.aggregates_time else None,
                    "diff_percent": row.diff_percent,
                    "status": row.status,
                }
                for row in result.rows
            ],
            "count": len(result.rows),
        }
