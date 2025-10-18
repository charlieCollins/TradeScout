"""Application context for TradeScout.

This module provides AppContext - a shared runtime context that manages:
- Database connections
- API clients
- Cached services (market context, data service)
- Active universe tracking

This context can be used by CLI, web apps, or any other interface.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AppContext:
    """Application runtime context - holds shared state and services.

    This is NOT a config file - it's a runtime object that provides:
    - Database connections (SQLModel engine)
    - API clients (Polygon API key)
    - Cached services (market context, data service)
    - Active universe tracking

    Can be used by CLI, web apps, or any other interface.
    """

    def __init__(self, db_path: str = "data/tradescout.db", verbose: bool = False, presentation=None):
        """Initialize application context.

        Args:
            db_path: Path to SQLite database
            verbose: Enable verbose logging
            presentation: PresentationContext for output adapters (injected by CLI/Web layer)
        """
        self.db_path = db_path
        self.verbose = verbose
        self.presentation = presentation  # PresentationContext injected by CLI/Web layer
        self._market_context = None
        self._market_context_service = None
        self._active_universe = None
        self._polygon_api_key = None
        self._sqlmodel_engine = None
        self._data_service_v2 = None

    @property
    def polygon_api_key(self):
        """Get Polygon API key."""
        if self._polygon_api_key is None:
            from api.config.api_keys import POLYGON_API_KEY
            self._polygon_api_key = POLYGON_API_KEY
        return self._polygon_api_key

    @property
    def market_context(self):
        """Get current market context (lazy-loaded and cached).

        Makes a live API call to Polygon to get real-time market status.
        Results are cached for the lifetime of this AppContext instance.

        The market code is determined by the active universe's primary market.
        """
        if self._market_context is None:
            # Get primary market from active universe
            primary_market_code = self._get_primary_market_from_universe()

            # Get market context for that market
            service = self.get_market_context_service()
            self._market_context = service.get_context(market_code=primary_market_code)

            # Log context for debugging
            logger.info(f"Market Context: {self._market_context}")

        return self._market_context

    def get_market_context_service(self):
        """Get market context service (creates if needed)."""
        if self._market_context_service is None:
            from services.market_context_service import MarketContextService

            # Use DataServiceV2 as data provider
            data_service_v2 = self.get_data_service_v2()

            # Create service
            self._market_context_service = MarketContextService(data_service_v2)

        return self._market_context_service

    def get_sqlmodel_engine(self):
        """Get or create SQLModel engine for DataServiceV2."""
        if self._sqlmodel_engine is None:
            from sqlmodel import create_engine
            database_url = f"sqlite:///{self.db_path}"
            self._sqlmodel_engine = create_engine(
                database_url,
                echo=False,
                connect_args={"check_same_thread": False}
            )
        return self._sqlmodel_engine

    def get_data_service_v2(self):
        """Get DataServiceV2 instance (new architecture).

        This creates DataServiceV2 with a SQLModel session.
        Cached for the lifetime of the AppContext object.

        Note: The session is long-lived for CLI use. For web apps,
        use per-request sessions instead.
        """
        if self._data_service_v2 is None:
            from sqlmodel import Session
            from services.data_service_v2 import DataServiceV2
            from api.config.api_keys import POLYGON_API_KEY

            # Create engine if needed
            engine = self.get_sqlmodel_engine()

            # Create session (long-lived for CLI)
            # Note: For web apps, use per-request sessions instead
            session = Session(engine)

            # Create DataServiceV2
            self._data_service_v2 = DataServiceV2(
                session=session,
                polygon_api_key=POLYGON_API_KEY,
                db_path=self.db_path
            )

        return self._data_service_v2

    def get_active_universe(self) -> str:
        """Get the currently active universe name."""
        if self._active_universe is None:
            try:
                data_service = self.get_data_service_v2()
                active_universe = data_service.get_active_universe()
                if active_universe:
                    self._active_universe = active_universe.name
                else:
                    # Fallback if no universe is active
                    self._active_universe = "default_universe"
            except Exception as e:
                logger.debug(f"Error getting active universe: {e}")
                self._active_universe = "default_universe"

        return self._active_universe

    def set_active_universe(self, universe_name: str) -> bool:
        """Set the active universe in database."""
        try:
            data_service = self.get_data_service_v2()
            success = data_service.set_active_universe(universe_name)

            if success:
                # Update cache
                self._active_universe = universe_name

            return success

        except Exception as e:
            logger.error(f"Failed to set active universe: {e}")
            return False

    def _get_primary_market_from_universe(self) -> str:
        """Get the primary market code from the active universe.

        The primary market is the first market in the universe's market breakdown.

        Returns:
            Market code (e.g., 'XNYS', 'XNAS')

        Raises:
            RuntimeError: If no active universe or universe has no markets
        """
        # Get active universe name
        active_universe = self.get_active_universe()
        if not active_universe:
            raise RuntimeError("No active universe found - cannot determine market context")

        # Get market breakdown for the universe
        data_service = self.get_data_service_v2()
        market_breakdown = data_service.get_universe_market_breakdown(active_universe)

        if not market_breakdown:
            raise RuntimeError(
                f"Universe '{active_universe}' has no markets - cannot determine market context"
            )

        # Return the first market code
        primary_market_code = market_breakdown[0][0]  # (market_code, market_name, asset_count)
        logger.info(f"Using primary market '{primary_market_code}' from universe '{active_universe}'")

        return primary_market_code
