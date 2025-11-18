"""Screener engine that executes screener queries based on YAML definitions.

IMPORTANT: This is a GENERIC engine designed to derive rules from config YAML files.
DO NOT PUT BUSINESS RULES OR HARDCODED LOGIC IN THIS FILE.

All field definitions, calculations, and business logic should be defined in the
YAML configuration files (configs/screeners/*.yaml), NOT hardcoded in this engine.

Note: Specialized screeners (such as gaps) may use analyzers along with screeners
to combine forces for output.
"""

import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional

import pytz

from utils.config_loader import ConfigLoader
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
        self._validate_session(screener_def, market_context)

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

        # Get data source configuration
        data_source = screener_def.get("data_source", {})
        if self.config:
            universe = data_source.get("universe", self.config.get_active_universe())
        else:
            universe = data_source.get("universe", "default")
        require_recent_trading = data_source.get("require_recent_trading", True)

        # Count excluded assets (before filtering by date)
        excluded_count = self.data_provider.screener_repository.count_excluded_by_date(
            universe_name=universe,
            expected_date=market_context.expected_data_date
        )

        # Get filters and sort from resolved screener definition
        filters = screener_def.get("filters", [])
        sort = screener_def.get("sort", [])
        display = screener_def.get("display", {})

        # Load default limit from config
        defaults_config = ConfigLoader().load_yaml("screener_defaults.yaml")
        default_limit = defaults_config["screener_defaults"]["display"]["default_limit"]
        limit = display.get("limit", default_limit)

        # Execute query through screener repository
        results = self.data_provider.screener_repository.execute_screener_query(
            universe=universe,
            expected_date=market_context.expected_data_date,
            filters=filters,
            sort=sort,
            limit=limit,
            require_recent_trading=require_recent_trading,
            previous_trading_date=market_context.previous_trading_date
        )

        # If no results, check if reference price data is missing
        if not results:
            self._check_missing_reference_data(
                screener_def=screener_def,
                session=session,
                universe=universe,
                expected_date=market_context.expected_data_date,
                previous_trading_date=market_context.previous_trading_date
            )

        # Add computed fields to each result
        enhanced_results = []
        for result in results:
            enhanced_result = self._add_computed_fields(result)
            enhanced_results.append(enhanced_result)

        # Add exclusion metadata to results (stored in a special way that display can access)
        if hasattr(enhanced_results, '__dict__'):
            enhanced_results.excluded_count = excluded_count
        else:
            # Store it in the first result if we have results
            if enhanced_results and isinstance(enhanced_results, list):
                # We'll pass this separately to display instead
                pass

        # Stage 2: Volume validation using Aggregates API (if enabled)
        if screener_def.get('volume_validation', {}).get('enabled', False):
            validated_results = self._validate_volume(
                results=enhanced_results,
                volume_config=screener_def['volume_validation'],
                market_context=market_context
            )
            return validated_results, excluded_count

        return enhanced_results, excluded_count

    def _validate_session(self, screener_def: Dict, market_context: MarketContext):
        """Validate that screener can run during current session.

        Args:
            screener_def: Screener configuration
            market_context: Market context with session information

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

        # Convert market session to screener-compatible name (closed_pre/closed_post → closed)
        current_session = market_context.current_session.to_screener_session()
        if current_session not in valid_sessions:
            raise ValueError(
                f"Screener '{screener_name}' is not available during {current_session} session. "
                f"Valid sessions: {', '.join(valid_sessions)}"
            )

    def _check_missing_reference_data(
        self,
        screener_def: Dict,
        session: str,
        universe: str,
        expected_date: date,
        previous_trading_date: date
    ):
        """Check if reference price data is missing for all assets.

        Args:
            screener_def: Screener configuration
            session: Current session name
            universe: Universe name
            expected_date: Expected data date

        Raises:
            ValueError: If reference price is missing for all assets
        """
        # Get reference_price field for this session
        field_mapping = screener_def.get("field_mapping", {})
        reference_price_config = field_mapping.get("reference_price", {})

        if not reference_price_config or session not in reference_price_config:
            return  # No reference price configured, nothing to check

        reference_field_expr = reference_price_config[session]

        # Extract the actual field name (e.g., "ap.prevday_close" -> "prevday_close")
        if "." in reference_field_expr:
            reference_field = reference_field_expr.split(".")[-1]
        else:
            reference_field = reference_field_expr

        # Query to check if any assets have non-NULL reference price (with fallback)
        count_query = self.data_provider.screener_repository.count_assets_with_reference_price(
            universe=universe,
            expected_date=expected_date,
            reference_field=reference_field,
            previous_trading_date=previous_trading_date
        )

        if count_query == 0:
            screener_name = screener_def.get("name", "unknown")
            raise ValueError(
                f"No {reference_field.replace('_', ' ')} data available for screener '{screener_name}'. "
                f"Cannot calculate gains without reference price data. "
                f"Run 'tradescout snapshot update' to fetch latest market data."
            )

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
        trading_date = market_context.current_date if market_context.is_trading_day else market_context.previous_trading_date

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