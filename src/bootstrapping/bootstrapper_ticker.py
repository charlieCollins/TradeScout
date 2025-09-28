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
        self.data_provider = PolygonDataProvider(api_key)
        self.db_manager = db_manager
        self.last_stats = {}
        self.update_tracker = DataUpdateTracker(db_manager) if db_manager else None

    def ensure_providers_exist(self) -> None:
        """Ensure required providers exist in database."""
        if not self.db_manager:
            raise ValueError("Database manager required for provider check")

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            # Check if polygon provider exists
            cursor.execute("SELECT id FROM providers WHERE name = 'polygon'")
            if not cursor.fetchone():
                logger.error("Polygon provider not found in database")
                raise ValueError("Provider 'polygon' must be bootstrapped first. Run 'tradescout bootstrap providers init'")


    def fetch_all_tickers(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch all tickers using data provider."""
        return self.data_provider.fetch_all_tickers(limit)

    def upsert_tickers(self, tickers: List[Dict[str, Any]]) -> Dict[str, int]:
        """Upsert tickers into database using batch operations. Returns statistics."""
        if not self.db_manager:
            raise ValueError("Database manager required for upsert operations")

        stats = {"inserted": 0, "updated": 0, "errors": 0}

        logger.info(f"Starting batch upsert of {len(tickers)} tickers...")

        # Process in batches to avoid memory issues
        batch_size = 1000
        current_time = datetime.now().isoformat()

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            for i in range(0, len(tickers), batch_size):
                batch = tickers[i:i + batch_size]
                logger.info(f"Processing batch {i // batch_size + 1}/{(len(tickers) + batch_size - 1) // batch_size}")

                # Prepare batch data
                batch_data = []
                for ticker_data in batch:
                    try:
                        # Extract data from Polygon response
                        symbol = ticker_data.get("ticker")
                        name = ticker_data.get("name")
                        currency = ticker_data.get("currency_name", "USD")
                        is_active = ticker_data.get("active", False)

                        # Skip if missing required fields
                        if not symbol or not name:
                            stats["errors"] += 1
                            continue

                        # Get market_id from database (default to 1 if not found)
                        market_id = self._get_market_id(ticker_data.get("primary_exchange", "UNKNOWN"))

                        batch_data.append({
                            'symbol': symbol,
                            'name': name,
                            'market_id': market_id,
                            'currency': currency,
                            'is_active': is_active
                        })

                    except Exception as e:
                        logger.error(f"Error processing ticker {ticker_data.get('ticker', 'unknown')}: {e}")
                        stats["errors"] += 1

                # Use SQLite UPSERT (INSERT OR REPLACE) for batch processing
                if batch_data:
                    # Get the polygon provider ID once
                    cursor.execute("SELECT id FROM providers WHERE name = 'polygon'")
                    provider_result = cursor.fetchone()
                    if not provider_result:
                        logger.error("Polygon provider not found in database")
                        raise ValueError("Polygon provider must be bootstrapped first")
                    polygon_provider_id = provider_result[0]

                    upsert_sql = """
                        INSERT OR IGNORE INTO assets (
                            symbol, name, market_id, asset_type, asset_class,
                            currency, is_active, provider_id, created_at, updated_at
                        ) VALUES (?, ?, ?, 'stock', 'equity', ?, ?, ?, ?, ?)
                    """

                    upsert_params = [
                        (
                            item['symbol'], item['name'], item['market_id'],
                            item['currency'], item['is_active'], polygon_provider_id, current_time, current_time
                        )
                        for item in batch_data
                    ]

                    try:
                        cursor.executemany(upsert_sql, upsert_params)
                        stats["inserted"] += len(batch_data)  # SQLite REPLACE counts as insert
                    except Exception as e:
                        logger.error(f"SQL Error in batch: {e}")
                        logger.error(f"First few batch items: {batch_data[:3]}")
                        logger.error(f"Sample params: {upsert_params[:3]}")
                        raise

                conn.commit()

        logger.info(f"Batch upsert complete: {stats}")
        self.last_stats = stats
        return stats

    def _get_market_id(self, exchange: str) -> int:
        """Get market_id from database based on exchange name."""
        if not self.db_manager:
            return 1  # Default fallback

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                # First try exact match
                cursor.execute("SELECT id FROM markets WHERE code = ? OR name = ?", (exchange, exchange))
                result = cursor.fetchone()
                if result:
                    return result[0]

                # If not found, use UNKNOWN market
                cursor.execute("SELECT id FROM markets WHERE code = 'UNKNOWN'")
                result = cursor.fetchone()
                if result:
                    logger.debug(f"Exchange '{exchange}' not found, using UNKNOWN market")
                    return result[0]

                # This should never happen if markets are bootstrapped
                logger.error(f"No markets found in database, not even UNKNOWN")
                raise ValueError("Markets must be bootstrapped first")
        except Exception as e:
            logger.warning(f"Could not lookup market_id for {exchange}: {e}")
            raise

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