"""Bootstrap all tickers from Polygon API into the database."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from provider.data_provider import PolygonDataProvider
from services.data_update_tracker import DataUpdateTracker

logger = logging.getLogger(__name__)


class TickerBootstrapper:
    """Bootstrap all available tickers from Polygon API."""

    def __init__(self, api_key: str, db_manager=None):
        """Initialize with API key and database manager."""
        self.data_provider = PolygonDataProvider(db_manager, api_key)
        self.db_manager = db_manager
        self.last_stats = {}
        self.update_tracker = DataUpdateTracker(self.data_provider) if db_manager else None

    def ensure_providers_exist(self) -> None:
        """Ensure required providers exist in database."""
        if not self.data_provider.ensure_polygon_provider_exists():
            logger.error("Polygon provider not found in database")
            raise ValueError("Provider 'polygon' must be bootstrapped first. Run 'tradescout database bootstrap-providers'")


    def fetch_all_tickers(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch all tickers using data provider."""
        return self.data_provider.fetch_all_tickers(limit)

    def upsert_tickers(self, tickers: List[Dict[str, Any]]) -> Dict[str, int]:
        """Upsert tickers into database using data provider pattern."""
        logger.info(f"Starting upsert of {len(tickers)} tickers...")

        # Transform tickers data to the format expected by data provider
        assets_data = []
        error_count = 0

        for ticker_data in tickers:
            try:
                # Extract data from Polygon response
                symbol = ticker_data.get("ticker")
                name = ticker_data.get("name")
                currency = ticker_data.get("currency_name", "USD")
                is_active = ticker_data.get("active", False)

                # Skip if missing required fields
                if not symbol or not name:
                    error_count += 1
                    continue

                # Get market_id using data provider
                market_id = self.data_provider.get_market_id_by_exchange(
                    ticker_data.get("primary_exchange", "UNKNOWN")
                )

                assets_data.append({
                    'symbol': symbol,
                    'name': name,
                    'market_id': market_id,
                    'currency': currency,
                    'is_active': is_active
                })

            except Exception as e:
                logger.error(f"Error processing ticker {ticker_data.get('ticker', 'unknown')}: {e}")
                error_count += 1

        # Use data provider to upsert the assets
        stats = self.data_provider.upsert_assets(assets_data)
        stats["errors"] += error_count  # Add preprocessing errors

        logger.info(f"Ticker upsert complete: {stats}")
        self.last_stats = stats
        return stats


    def get_bootstrap_stats(self) -> Dict[str, Any]:
        """Get statistics from the last bootstrap run."""
        return self.last_stats.copy()

    def bootstrap_all_tickers(self, limit: Optional[int] = None, force: bool = False) -> bool:
        """Complete bootstrap process: fetch and upsert all tickers.

        Args:
            limit: Optional limit on number of tickers to fetch
            force: If True, skip TTL check and run regardless of freshness
        """
        logger.info("Starting complete ticker bootstrap")

        # Check if data is fresh unless forced
        if not force and self.update_tracker:
            from config.ttl_config import TICKERS_TTL_HOURS

            if not self.update_tracker.is_data_stale("tickers", TICKERS_TTL_HOURS):
                last_update = self.update_tracker.get_last_update("tickers", "bootstrap")
                logger.info(f"Ticker data is fresh (last update: {last_update}), skipping bootstrap. Use --force to refresh anyway.")

                # Still return success stats from last run if available
                history = self.update_tracker.get_operation_history("tickers", limit=1)
                if history:
                    last_stats = history[0].get('stats', {})
                    self.last_stats = {
                        "total_fetched": last_stats.get('fetched', 0),
                        "inserted": last_stats.get('inserted', 0),
                        "updated": last_stats.get('updated', 0),
                        "errors": last_stats.get('errors', 0)
                    }
                return True

        # Start operation tracking
        operation_id = None
        if self.update_tracker:
            operation_params = {"limit": limit, "force": force}
            operation_id = self.update_tracker.start_operation(
                operation_type="tickers",
                operation_subtype="bootstrap",
                operation_params=operation_params
            )

        try:
            # Ensure providers and markets exist first
            self.ensure_providers_exist()

            # Bootstrap markets using dedicated bootstrapper
            from .bootstrapper_market import MarketBootstrapper
            market_bootstrapper = MarketBootstrapper(self.db_manager)
            market_bootstrapper.bootstrap_markets()

            # Fetch all tickers from API
            tickers = self.fetch_all_tickers(limit=limit)

            # Update tracker with total items
            if self.update_tracker and operation_id:
                self.update_tracker.update_progress(
                    operation_id,
                    api_calls_made=1,  # One API call for all tickers
                    stats={"fetched": len(tickers)}
                )

            # Upsert into database
            stats = self.upsert_tickers(tickers)
            self.last_stats["total_fetched"] = len(tickers)

            # Complete operation tracking
            if self.update_tracker and operation_id:
                total_stats = {
                    "fetched": len(tickers),
                    "inserted": stats.get("inserted", 0),
                    "updated": stats.get("updated", 0),
                    "errors": stats.get("errors", 0)
                }
                self.update_tracker.complete_operation(operation_id, total_stats, "completed")

            logger.info(f"Bootstrap complete: {len(tickers)} tickers processed")
            return True

        except Exception as e:
            # Mark operation as failed
            if self.update_tracker and operation_id:
                self.update_tracker.fail_operation(operation_id, str(e))

            logger.error(f"Bootstrap failed: {e}")
            return False