"""Web output adapter for market results.

Formats market operation results for web/JSON display.
Returns dictionaries suitable for FastAPI JSON serialization.
"""

from typing import Dict, Any

from models.result.market_result import MarketUpdateResult, MarketBackfillResult, MarketContextResult


class WebMarketOutputAdapter:
    """Format and display market results for web/JSON API."""

    def display_market_update_result(self, result: MarketUpdateResult) -> Dict[str, Any]:
        """Display market update result as JSON-ready dict.

        Args:
            result: MarketUpdateResult containing snapshot update statistics

        Returns:
            Dictionary ready for FastAPI JSON serialization
        """
        return {
            "mode": "snapshot",
            "data_was_fresh": result.data_was_fresh,
            "total_tickers": result.total_tickers,
            "matched_symbols": result.matched_symbols,
            "unmatched_symbols": result.unmatched_symbols,
            "transformed": result.transformed,
            "saved": result.saved,
            "duplicates": result.duplicates,
            "invalid": result.invalid,
            "invalid_no_timestamp": result.invalid_no_timestamp,
            "invalid_exception": result.invalid_exception,
            "duration_seconds": result.duration_seconds,
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "last_snapshot_time": result.last_snapshot_time.isoformat() if result.last_snapshot_time else None,
            "age_minutes": result.age_minutes,
            "ttl_minutes": result.ttl_minutes,
            "total_historical_records": result.total_historical_records,
        }

    def display_market_backfill_result(self, result: MarketBackfillResult) -> Dict[str, Any]:
        """Display market backfill result as JSON-ready dict.

        Args:
            result: MarketBackfillResult containing backfill statistics

        Returns:
            Dictionary ready for FastAPI JSON serialization
        """
        return {
            "mode": "backfill",
            "target_date": str(result.target_date),
            "force_refresh": result.force_refresh,
            "total_tickers": result.total_tickers,
            "matched_symbols": result.matched_symbols,
            "unmatched_symbols": result.unmatched_symbols,
            "transformed": result.transformed,
            "saved": result.saved,
            "duplicates": result.duplicates,
            "invalid": result.invalid,
            "invalid_no_timestamp": result.invalid_no_timestamp,
            "invalid_exception": result.invalid_exception,
            "duration_seconds": result.duration_seconds,
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "total_historical_records": result.total_historical_records,
        }

    def display_market_context(self, result: MarketContextResult) -> Dict[str, Any]:
        """Display market context as JSON-ready dict.

        Args:
            result: MarketContextResult containing market context information

        Returns:
            Dictionary ready for FastAPI JSON serialization
        """
        ctx = result.market_context

        # Calculate market distribution percentages
        market_breakdown = [
            {
                "code": code,
                "name": name,
                "count": count,
                "percentage": (count / result.total_universe * 100) if result.total_universe > 0 else 0
            }
            for code, name, count in result.universe_markets
        ]

        # Get session times
        session_times = ctx.get_session_times()
        session_times_formatted = {
            session_name: time_val.strftime("%H:%M") if time_val else None
            for session_name, time_val in session_times.items()
        }

        return {
            "universe": {
                "name": result.universe_name,
                "total_assets": result.total_universe,
                "market_breakdown": market_breakdown,
            },
            "primary_market": {
                "code": ctx.market.code,
                "name": ctx.market.name,
                "timezone": ctx.market.timezone,
                "currency": ctx.market.currency,
                "has_extended_hours": ctx.market.has_extended_hours,
            },
            "trading_status": {
                "is_trading_day": ctx.is_trading_day,
                "is_market_open": ctx.is_market_open,
                "is_regular_hours": ctx.is_regular_hours,
                "is_extended_hours": ctx.is_extended_hours,
                "current_session": ctx.current_session.value,
                "session_name": ctx.session_name,
                "day_type": ctx.day_type.value,
            },
            "dates": {
                "current_date": str(ctx.current_date),
                "current_time": ctx.current_time.isoformat(),
                "previous_trading_date": str(ctx.previous_trading_date),
                "next_trading_date": str(ctx.next_trading_date) if ctx.next_trading_date else None,
            },
            "session_times": session_times_formatted,
            "last_snapshot": {
                "time": result.last_snapshot_time.isoformat() if result.last_snapshot_time else None,
                "age": result.last_snapshot_age_str,
                "status": result.last_snapshot_status,
            },
        }
