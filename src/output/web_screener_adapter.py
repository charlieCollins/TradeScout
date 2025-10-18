"""Web output adapter for screener results.

Formats screener operation results for web/JSON display.
Returns dictionaries suitable for FastAPI JSON serialization.
"""

from typing import Dict, Any

from models.result.screener_result import ScreenerResult, ScreenerListResult


class WebScreenerOutputAdapter:
    """Format and display screener results for web/JSON API."""

    def display_screener_results(self, result: ScreenerResult) -> Dict[str, Any]:
        """Display screener results as JSON-ready dict.

        Args:
            result: ScreenerResult model containing all screener data

        Returns:
            Dictionary ready for FastAPI JSON serialization
        """
        # Get display columns from screener_def
        from screener.template_resolver import TemplateResolver
        resolver = TemplateResolver(result.screener_def, result.market_context.session_name)
        display_columns = resolver.resolve_display_columns()

        return {
            "screener": result.screener_name,
            "description": result.screener_def.get("description", ""),
            "market_context": {
                "session": result.market_context.session_name,
                "market": result.market_context.market.name,
                "market_code": result.market_context.market.code,
                "date": str(result.market_context.current_date),
                "is_trading_day": result.market_context.is_trading_day,
                "data_date": str(result.market_context.expected_data_date),
            },
            "resolved_config": result.resolved_config,
            "display_columns": display_columns,
            "results": result.results,
            "count": len(result.results),
            "excluded_count": result.excluded_count,
            "warnings": result.warnings or [],
        }

    def display_screener_list(self, result: ScreenerListResult) -> Dict[str, Any]:
        """Display screener list as JSON-ready dict.

        Args:
            result: ScreenerListResult containing list of available screeners

        Returns:
            Dictionary ready for FastAPI JSON serialization
        """
        return {
            "screeners": [
                {
                    "name": item.name,
                    "description": item.description,
                }
                for item in result.screeners
            ],
            "count": len(result.screeners),
        }
