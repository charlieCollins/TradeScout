"""Bootstrap all tickers from Polygon API into the database."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from provider.data_provider import PolygonDataProvider

logger = logging.getLogger(__name__)


class TickerBootstrapper:
    """Bootstrap all available tickers from Polygon API."""

    def __init__(self, api_key: str, db_manager=None):
        """Initialize with API key and database manager."""
        self.data_provider = PolygonDataProvider(api_key)
        self.db_manager = db_manager
        self.last_stats = {}

    def bootstrap_providers(self) -> None:
        """Ensure required providers exist in database."""
        if not self.db_manager:
            raise ValueError("Database manager required for provider bootstrap")

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            # Insert polygon provider if it doesn't exist
            cursor.execute("""
                INSERT OR IGNORE INTO providers (name, is_active)
                VALUES ('polygon', TRUE)
            """)

            conn.commit()
            logger.info("Provider bootstrap complete")

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
                    polygon_provider_id = cursor.fetchone()[0]

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
                cursor.execute("SELECT id FROM markets WHERE code = ? OR name = ?", (exchange, exchange))
                result = cursor.fetchone()
                return result[0] if result else 1  # Default to 1 if not found
        except Exception as e:
            logger.warning(f"Could not lookup market_id for {exchange}: {e}")
            return 1

    def get_bootstrap_stats(self) -> Dict[str, Any]:
        """Get statistics from the last bootstrap run."""
        return self.last_stats.copy()

    def bootstrap_all_tickers(self, limit: Optional[int] = None) -> bool:
        """Complete bootstrap process: fetch and upsert all tickers."""
        logger.info("Starting complete ticker bootstrap")

        try:
            # Ensure providers exist first
            self.bootstrap_providers()

            # Fetch all tickers from API
            tickers = self.fetch_all_tickers(limit=limit)

            # Upsert into database
            stats = self.upsert_tickers(tickers)
            self.last_stats["total_fetched"] = len(tickers)

            logger.info(f"Bootstrap complete: {len(tickers)} tickers processed")
            return True

        except Exception as e:
            logger.error(f"Bootstrap failed: {e}")
            return False