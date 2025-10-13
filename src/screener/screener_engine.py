"""Screener engine that executes screener queries based on YAML definitions.

IMPORTANT: This is a GENERIC engine designed to derive rules from config YAML files.
DO NOT PUT BUSINESS RULES OR HARDCODED LOGIC IN THIS FILE.

All field definitions, calculations, and business logic should be defined in the
YAML configuration files (configs/screeners/*.yaml), NOT hardcoded in this engine.

Note: Specialized screeners (such as gaps) may use analyzers along with screeners
to combine forces for output.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytz

from screener.template_resolver import TemplateResolver
from models.dataclass.market_context import MarketContext


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

    def execute_screener(
        self,
        screener_def: Dict,
        market_context: MarketContext
    ) -> List[Dict[str, Any]]:
        """Execute a screener based on its YAML definition.

        Args:
            screener_def: Screener configuration dictionary from YAML
            market_context: Market context (REQUIRED - all screeners must be context-aware)

        Returns:
            List of matching stocks as dictionaries

        Raises:
            ValueError: If screener is not valid for current session or missing field_mapping
        """
        # Check if screener is valid for current session
        self._validate_session(screener_def)

        # All screeners must be context-aware
        if 'field_mapping' not in screener_def:
            raise ValueError(
                f"Screener '{screener_def.get('name', 'unknown')}' must have 'field_mapping' section"
            )

        # Resolve templates
        session = market_context.session_name
        resolver = TemplateResolver(screener_def, session)

        # Resolve templates in filters and sort
        screener_def = screener_def.copy()  # Don't modify original
        screener_def['filters'] = resolver.resolve_filters()
        screener_def['sort'] = resolver.resolve_sort()

        # Build the SQL query from screener definition
        query = self._build_query(screener_def)

        # Execute query through data provider
        results = self.data_provider.execute_screener_query(query)

        # Add computed fields to each result
        enhanced_results = []
        for result in results:
            enhanced_result = self._add_computed_fields(result)
            enhanced_results.append(enhanced_result)

        # Stage 2: Volume validation using Aggregates API (if enabled)
        if screener_def.get('volume_validation', {}).get('enabled', False):
            validated_results = self._validate_volume(
                results=enhanced_results,
                volume_config=screener_def['volume_validation'],
                market_context=market_context
            )
            return validated_results

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
            "ap.prevday_volume",
            "ap.day_open",
            "ap.day_close",
            "ap.day_volume",
            "ap.min_close",
            "ap.min_volume",
            "ap.min_accumulated_volume",
            "ap.min_timestamp",
        ]

        # Start building query
        query = f"""
        WITH latest_prices AS (
            SELECT
                asset_id,
                prevday_close,
                prevday_volume,
                day_open,
                day_close,
                day_volume,
                min_close,
                min_volume,
                min_accumulated_volume,
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

            # YAML must contain actual SQL expressions (e.g., "ap.min_close", not "min_close")
            # No field mapping - engine is generic

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

                # YAML must contain actual SQL expressions
                # No field mapping - engine is generic

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

    def _validate_volume(
        self,
        results: List[Dict[str, Any]],
        volume_config: Dict[str, Any],
        market_context: MarketContext
    ) -> List[Dict[str, Any]]:
        """Validate volume using Aggregates API (Stage 2 filtering).

        Args:
            results: Price-qualified candidates from Stage 1
            volume_config: Volume validation configuration from YAML
            market_context: Market context for session/date info

        Returns:
            List of volume-validated candidates with aggregates data added
        """
        import logging
        logger = logging.getLogger(__name__)

        min_ratio = volume_config.get('min_volume_ratio', 1.5)
        session = volume_config.get('session', market_context.session_name)
        trading_date = market_context.current_date if market_context.is_trading_day else market_context.prev_trading_date

        logger.info(
            f"Volume validation: {len(results)} candidates, "
            f"min_ratio={min_ratio}, session={session}, date={trading_date}"
        )

        validated = []
        skipped_no_agg = 0
        skipped_no_prevday = 0
        skipped_low_volume = 0

        for result in results:
            symbol = result.get('symbol')
            prevday_volume = result.get('prevday_volume')

            # Skip if no previous day volume (can't calculate ratio)
            if not prevday_volume or prevday_volume == 0:
                skipped_no_prevday += 1
                continue

            # Query Aggregates API for trade-eligible volume
            try:
                agg_volume = self.data_provider.calculate_extended_hours_volume(
                    symbol=symbol,
                    trading_date=trading_date,
                    session=session
                )

                if agg_volume is None:
                    skipped_no_agg += 1
                    continue

                # Calculate volume ratio vs previous day average
                # Session hours: premarket=5.5h (4:00-9:30), afterhours=4h (4:00-8:00)
                session_hours = 5.5 if session == "premarket" else 4.0
                prev_day_hourly_avg = prevday_volume / 6.5  # Regular session is 6.5 hours
                expected_volume = prev_day_hourly_avg * session_hours
                volume_ratio = agg_volume / expected_volume if expected_volume > 0 else 0

                # Filter by volume ratio threshold
                if volume_ratio >= min_ratio:
                    # Add aggregates data to result
                    result['agg_volume'] = agg_volume
                    result['volume_ratio'] = volume_ratio
                    result['snapshot_volume'] = result.get('min_accumulated_volume', 0)  # For comparison
                    validated.append(result)
                else:
                    skipped_low_volume += 1

            except Exception as e:
                logger.error(f"Error validating volume for {symbol}: {e}")
                skipped_no_agg += 1
                continue

        logger.info(
            f"Volume validation complete: {len(validated)} passed, "
            f"{skipped_low_volume} below threshold, {skipped_no_agg} no aggregates, "
            f"{skipped_no_prevday} no prev volume"
        )

        return validated