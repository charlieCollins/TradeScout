"""Screener engine that executes screener queries based on YAML definitions."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytz


logger = logging.getLogger(__name__)


class ScreenerEngine:
    """Execute screener queries based on YAML configuration."""

    def __init__(self, data_provider, config=None):
        """Initialize screener engine.

        Args:
            data_provider: Data provider instance
            config: Optional config object to get active universe
        """
        self.data_provider = data_provider
        self.config = config

    def execute_screener(self, screener_def: Dict) -> List[Dict[str, Any]]:
        """Execute a screener based on its YAML definition.

        Args:
            screener_def: Screener configuration dictionary from YAML

        Returns:
            List of matching stocks as dictionaries

        Raises:
            ValueError: If screener is not valid for current session
        """
        # Check if screener is valid for current session
        self._validate_session(screener_def)

        # Build the SQL query from screener definition
        query = self._build_query(screener_def)

        # Execute query through data provider
        results = self.data_provider.execute_screener_query(query)

        # Add computed fields to each result
        enhanced_results = []
        for result in results:
            enhanced_result = self._add_computed_fields(result)
            enhanced_results.append(enhanced_result)

        return enhanced_results

    def _validate_session(self, screener_def: Dict):
        """Validate that screener can run during current session.

        Args:
            screener_def: Screener configuration

        Raises:
            ValueError: If screener is not valid for current session or missing session config
        """
        screener_name = screener_def.get("name", "unknown")

        # Require valid_sessions field in every YAML
        if "valid_sessions" not in screener_def:
            raise ValueError(
                f"Screener '{screener_name}' missing required 'valid_sessions' configuration"
            )

        valid_sessions = screener_def["valid_sessions"]
        if not valid_sessions or not isinstance(valid_sessions, list):
            raise ValueError(
                f"Screener '{screener_name}' has invalid 'valid_sessions' - must be a non-empty list"
            )

        current_session = self._get_current_session()
        if current_session not in valid_sessions:
            raise ValueError(
                f"Screener '{screener_name}' is not available during {current_session} session. "
                f"Valid sessions: {', '.join(valid_sessions)}"
            )

    def _get_current_session(self) -> str:
        """Get current market session from data provider.

        Returns:
            Session name: 'premarket', 'regular', 'afterhours', or 'closed'

        Raises:
            RuntimeError: If market status API call fails
        """
        # Use the data provider to get current session
        return self.data_provider.get_current_market_session()

    def _build_query(self, screener_def: Dict) -> str:
        """Build SQL query from screener definition.

        Args:
            screener_def: Screener configuration

        Returns:
            SQL query string
        """
        data_source = screener_def.get("data_source", {})
        # Use active universe from config if available, otherwise fall back to YAML or default
        if self.config:
            universe = data_source.get("universe", self.config.get_active_universe())
        else:
            universe = data_source.get("universe", "default_universe")
        require_recent_trading = data_source.get("require_recent_trading", True)

        # Build SELECT clause with all available fields
        select_fields = [
            "a.symbol",
            "a.name",
            "ap.prevday_close",
            "ap.day_open",
            "ap.day_close",
            "ap.day_volume",
            "ap.min_close",
            "ap.min_volume",
            "ap.min_timestamp",
            "(ap.min_close - ap.prevday_close) as change_dollar",
            "CASE WHEN ap.prevday_close > 0 THEN ((ap.min_close - ap.prevday_close) / ap.prevday_close * 100) ELSE 0 END as change_percent",
            "(ap.min_close - ap.day_close) as ah_change_dollar",
            "CASE WHEN ap.day_close > 0 THEN ((ap.min_close - ap.day_close) / ap.day_close * 100) ELSE 0 END as ah_change_percent"
        ]

        # Start building query
        query = f"""
        WITH latest_prices AS (
            SELECT
                asset_id,
                prevday_close,
                day_open,
                day_close,
                day_volume,
                min_close,
                min_volume,
                min_timestamp,
                provider_updated_at,
                ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY updated_at DESC) as rn
            FROM asset_prices
        )
        SELECT {', '.join(select_fields)}
        FROM assets a
        JOIN universe_memberships um ON a.id = um.asset_id
        JOIN universes u ON um.universe_id = u.id
        JOIN latest_prices ap ON a.id = ap.asset_id AND ap.rn = 1
        WHERE u.name = '{universe}'
        """

        # Add require_recent_trading filter
        if require_recent_trading:
            query += " AND ap.provider_updated_at > 0"

        # Add custom filters
        filters = screener_def.get("filters", [])
        for filter_def in filters:
            field = filter_def["field"]
            operator = filter_def["operator"]
            value = filter_def["value"]

            # Handle special fields - map YAML field names to SQL
            if field == "change_percent":
                field = "((ap.min_close - ap.prevday_close) / ap.prevday_close * 100)"
            elif field == "ABS(change_percent)":
                field = "ABS((ap.min_close - ap.prevday_close) / ap.prevday_close * 100)"
            elif field == "change_dollar":
                field = "(ap.min_close - ap.prevday_close)"
            elif field == "((min_close - day_close) / day_close * 100)":
                # After-hours change percent vs regular session close
                field = "((ap.min_close - ap.day_close) / ap.day_close * 100)"
            elif field == "min_close":
                field = "ap.min_close"
            elif field == "min_volume":
                field = "ap.min_volume"
            elif field == "day_open":
                field = "ap.day_open"
            elif field == "day_close":
                field = "ap.day_close"
            elif field == "day_volume":
                field = "ap.day_volume"
            elif field == "prevday_close":
                field = "ap.prevday_close"

            # Add WHERE clause
            if isinstance(value, list):
                value_str = f"({','.join(map(str, value))})"
                query += f" AND {field} {operator} {value_str}"
            elif value is None and operator in ["IS NOT NULL", "IS NULL"]:
                query += f" AND {field} {operator}"
            else:
                query += f" AND {field} {operator} {value}"

        # Add sorting
        sort_config = screener_def.get("sort", [])
        if sort_config:
            order_by_parts = []
            for sort_def in sort_config:
                field = sort_def["field"]
                direction = sort_def.get("direction", "desc").upper()

                # Handle special fields
                if field == "change_percent":
                    field = "((ap.min_close - ap.prevday_close) / ap.prevday_close * 100)"
                elif field == "ABS(change_percent)":
                    field = "ABS((ap.min_close - ap.prevday_close) / ap.prevday_close * 100)"
                elif field == "((min_close - day_close) / day_close * 100)":
                    # After-hours change percent vs regular session close
                    field = "((ap.min_close - ap.day_close) / ap.day_close * 100)"
                elif field == "min_volume":
                    field = "ap.min_volume"

                order_by_parts.append(f"{field} {direction}")

            if order_by_parts:
                query += f" ORDER BY {', '.join(order_by_parts)}"

        # Add limit
        display = screener_def.get("display", {})
        limit = display.get("limit", 50)
        query += f" LIMIT {limit}"

        return query

    def _add_computed_fields(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Add computed/formatted fields to result.

        Args:
            result: Single result row

        Returns:
            Enhanced result dictionary
        """
        # Format timestamp if present
        if result.get("min_timestamp"):
            try:
                # Convert milliseconds to datetime
                timestamp = datetime.fromtimestamp(
                    result["min_timestamp"] / 1000,
                    tz=pytz.UTC
                )
                et_tz = pytz.timezone('America/New_York')
                timestamp_et = timestamp.astimezone(et_tz)
                result["min_timestamp_formatted"] = timestamp_et.strftime("%I:%M %p")
            except Exception as e:
                result["min_timestamp_formatted"] = "N/A"
        else:
            result["min_timestamp_formatted"] = "N/A"

        return result