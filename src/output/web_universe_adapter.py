"""Web output adapter for universe results.

Formats universe operation results for web/JSON display.
Returns dictionaries suitable for FastAPI JSON serialization.
"""

from typing import Dict, Any

from models.result.universe_result import UniverseListResult, UniverseInfoResult


class WebUniverseOutputAdapter:
    """Format and display universe results for web/JSON API."""

    def display_universe_list(self, result: UniverseListResult) -> Dict[str, Any]:
        """Display universe list as JSON-ready dict.

        Args:
            result: UniverseListResult containing list of universes

        Returns:
            Dictionary ready for FastAPI JSON serialization
        """
        return {
            "universes": [
                {
                    "name": item.universe.name,
                    "description": item.universe.description,
                    "active": item.universe.active,
                    "asset_count": item.asset_count,
                }
                for item in result.universes
            ],
            "count": len(result.universes),
        }

    def display_universe_info(self, result: UniverseInfoResult) -> Dict[str, Any]:
        """Display universe info as JSON-ready dict.

        Args:
            result: UniverseInfoResult containing universe details

        Returns:
            Dictionary ready for FastAPI JSON serialization
        """
        return {
            "universe": {
                "name": result.universe.name,
                "description": result.universe.description,
                "active": result.universe.active,
            },
            "stats": {
                "total_members": result.stats.total_members,
                "active_members": result.stats.active_members,
                "inactive_members": result.stats.inactive_members,
            },
        }
