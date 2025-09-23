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

    def bootstrap_markets(self) -> None:
        """Ensure required markets exist in database."""
        if not self.db_manager:
            raise ValueError("Database manager required for markets bootstrap")

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            # Common US stock exchanges - add as needed when we encounter them
            markets = [
                ('XNYS', 'New York Stock Exchange', 'America/New_York'),
                ('XNAS', 'NASDAQ', 'America/New_York'),
                ('ARCX', 'NYSE Arca', 'America/New_York'),
                ('XNMS', 'NASDAQ Small Cap', 'America/New_York'),
                ('XASE', 'NYSE American', 'America/New_York'),
                ('BATS', 'BATS Exchange', 'America/New_York'),
                ('UNKNOWN', 'Unknown Market', 'America/New_York'),  # Default fallback
            ]

            for code, name, timezone in markets:
                cursor.execute("""
                    INSERT OR IGNORE INTO markets (code, name, timezone)
                    VALUES (?, ?, ?)
                """, (code, name, timezone))

            conn.commit()
            logger.info("Markets bootstrap complete")

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

    def bootstrap_all_tickers(self, limit: Optional[int] = None) -> bool:
        """Complete bootstrap process: fetch and upsert all tickers."""
        logger.info("Starting complete ticker bootstrap")

        try:
            # Ensure providers and markets exist first
            self.ensure_providers_exist()
            self.bootstrap_markets()

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