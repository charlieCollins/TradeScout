"""
Polygon Ticker Bootstrapper

Fetches all available tickers from Polygon.io and populates the local asset database.
This should be run manually/periodically to keep ticker data up to date.

Ticker Bootstrapper (polygon_ticker_bootstrapper.py):
  - Only applies basic API-level filtering: market=stocks, active=true
  - No filtering for exchange, ticker type, symbol format, etc.
  - Stores ALL ~11,700 tickers that match basic criteria

API Documentation: https://polygon.io/docs/rest/stocks/tickers/all-tickers
"""

import logging
import requests
import time
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from ..config.data_source_config import get_simple_config
from ..config.universe_config import get_supported_exchanges, get_exchange_info
from ..data_models.models_asset import Asset, AssetType
from ..data_models.models_market import Market, MarketType
from ..storage.sqlite_repository import SQLiteDatabaseManager

logger = logging.getLogger(__name__)


class PolygonTickerBootstrapper:
    """Bootstrapper for fetching and storing ticker/asset data from Polygon API"""

    def __init__(self, db_manager: Optional[SQLiteDatabaseManager] = None):
        """
        Initialize bootstrapper

        Args:
            db_manager: Database manager instance (creates new if None)
        """
        self.config = get_simple_config()
        self.api_key = self.config.get_polygon_key()
        self.db_manager = db_manager or SQLiteDatabaseManager()
        self.base_url = "https://api.polygon.io"

        if not self.api_key:
            raise ValueError("Polygon API key is required for universe bootstrapping")

    def bootstrap_tickers(
        self,
        market_types: Optional[List[str]] = None,
        active_only: bool = True,
        min_market_cap: Optional[int] = None,
    ) -> Dict[str, int]:
        """
        Fetch all tickers from Polygon and populate database

        Args:
            market_types: Filter by market types (e.g., ['stocks', 'etf'])
            active_only: Only include active tickers
            min_market_cap: Minimum market cap filter (in USD)

        Returns:
            Dictionary with counts: {total_fetched, inserted, updated, skipped}
        """
        logger.info("Starting Polygon universe bootstrap...")

        stats = {
            "total_fetched": 0,
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
        }

        try:
            # Ensure markets exist first
            self._ensure_markets_exist()

            # Fetch all tickers with pagination
            all_tickers = self._fetch_all_tickers(
                market_types=market_types, active_only=active_only
            )

            stats["total_fetched"] = len(all_tickers)
            logger.info(f"Fetched {stats['total_fetched']} tickers from Polygon API")

            # Process tickers in batches
            batch_size = 1000
            for i in range(0, len(all_tickers), batch_size):
                batch = all_tickers[i : i + batch_size]
                batch_stats = self._process_ticker_batch(batch, min_market_cap)

                # Aggregate stats
                for key in ["inserted", "updated", "skipped", "errors"]:
                    stats[key] += batch_stats[key]

                logger.info(
                    f"Processed batch {i//batch_size + 1}: "
                    f"{batch_stats['inserted']} inserted, "
                    f"{batch_stats['updated']} updated, "
                    f"{batch_stats['skipped']} skipped"
                )

            logger.info(f"Universe bootstrap completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Universe bootstrap failed: {e}")
            raise

    def _fetch_all_tickers(
        self, market_types: Optional[List[str]] = None, active_only: bool = True
    ) -> List[Dict]:
        """Fetch all tickers with pagination"""
        all_tickers = []
        cursor = None
        page = 0

        while True:
            page += 1
            logger.debug(f"Fetching page {page} of tickers...")

            # Build query parameters
            params = {
                "apikey": self.api_key,
                "limit": 1000,  # Maximum allowed by Polygon
            }

            if cursor:
                params["cursor"] = cursor

            if market_types:
                params["market"] = ",".join(market_types)
                logger.info(
                    f"Filtering by market types: {market_types} -> market={params['market']}"
                )

            if active_only:
                params["active"] = "true"

            # Make API request
            url = f"{self.base_url}/v3/reference/tickers"
            logger.debug(f"API request: {url} with params: {params}")
            response = requests.get(url, params=params)
            time.sleep(0.12)  # Rate limiting (5 calls per minute = 12 seconds apart)

            if response.status_code != 200:
                if response.status_code == 429:
                    logger.warning("Rate limit hit, waiting 60 seconds...")
                    time.sleep(60)
                    continue
                else:
                    raise Exception(
                        f"Polygon API error: {response.status_code} - {response.text}"
                    )

            data = response.json()

            if "results" not in data or not data["results"]:
                logger.info("No more results, pagination complete")
                break

            # Add to collection
            page_results = data["results"]
            all_tickers.extend(page_results)
            logger.debug(f"Page {page}: {len(page_results)} tickers")

            # Check for next page
            cursor = data.get("next_url")
            if not cursor:
                logger.info("No next_url, pagination complete")
                break

            # Extract cursor from next_url
            if "cursor=" in cursor:
                cursor = cursor.split("cursor=")[1].split("&")[0]
            else:
                logger.warning("Could not extract cursor from next_url")
                break

        logger.info(f"Total tickers fetched: {len(all_tickers)} across {page} pages")
        return all_tickers

    def _process_ticker_batch(
        self, tickers: List[Dict], min_market_cap: Optional[int] = None
    ) -> Dict[str, int]:
        """Process a batch of tickers and insert/update in database"""
        batch_stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            for ticker_data in tickers:
                try:
                    # Filter by market cap if specified
                    if (
                        min_market_cap
                        and ticker_data.get("market_cap", 0) < min_market_cap
                    ):
                        batch_stats["skipped"] += 1
                        continue

                    # Convert Polygon data to Asset model
                    asset = self._convert_polygon_ticker_to_asset(ticker_data)
                    if not asset:
                        batch_stats["skipped"] += 1
                        continue

                    # Check if asset already exists
                    cursor.execute(
                        "SELECT id FROM assets WHERE symbol = ?", (asset.symbol,)
                    )
                    existing = cursor.fetchone()

                    if existing:
                        # Update existing asset
                        self._update_asset_in_db(cursor, asset, existing[0])
                        batch_stats["updated"] += 1
                    else:
                        # Insert new asset
                        self._insert_asset_in_db(cursor, asset)
                        batch_stats["inserted"] += 1

                except Exception as e:
                    logger.error(
                        f"Error processing ticker {ticker_data.get('ticker', 'unknown')}: {e}"
                    )
                    batch_stats["errors"] += 1
                    continue

            conn.commit()

        except Exception as e:
            conn.rollback()
            logger.error(f"Batch processing failed: {e}")
            raise
        finally:
            conn.close()

        return batch_stats

    def _convert_polygon_ticker_to_asset(self, ticker_data: Dict) -> Optional[Asset]:
        """Convert Polygon ticker data to Asset model"""
        try:
            symbol = ticker_data.get("ticker", "").upper()
            if not symbol:
                return None

            # Map Polygon asset types to our enum
            polygon_type = ticker_data.get("type", "").upper()
            asset_type = self._map_polygon_asset_type(polygon_type)

            # Determine market
            primary_exchange = ticker_data.get("primary_exchange", "UNKNOWN")
            market = self._get_market_for_exchange(primary_exchange)

            # Create Asset
            asset = Asset(
                symbol=symbol,
                name=ticker_data.get("name", f"{symbol} Corp"),
                asset_type=asset_type,
                market=market,
                currency=ticker_data.get("currency_name", "USD"),
                is_active=ticker_data.get("active", True),
            )

            return asset

        except Exception as e:
            logger.error(f"Error converting ticker data: {e}")
            return None

    def _map_polygon_asset_type(self, polygon_type: str) -> AssetType:
        """Map Polygon asset type to our AssetType enum"""
        type_mapping = {
            "CS": AssetType.COMMON_STOCK,
            "STOCK": AssetType.COMMON_STOCK,
            "ETF": AssetType.ETF,
            "ETN": AssetType.ETF,  # Exchange Traded Note
            "FUND": AssetType.MUTUAL_FUND,
            "REIT": AssetType.COMMON_STOCK,  # Treat REITs as stocks
            "PFD": AssetType.PREFERRED_STOCK,
            "WARRANT": AssetType.OPTION,  # Close enough
            "RIGHT": AssetType.OPTION,
            "UNIT": AssetType.COMMON_STOCK,  # Units often contain stocks
        }

        return type_mapping.get(polygon_type, AssetType.COMMON_STOCK)

    def _get_market_for_exchange(self, exchange: str) -> Market:
        """Get Market object for exchange code using centralized config"""
        exchange_info = get_exchange_info(exchange)

        if exchange_info:
            return Market(
                id=exchange_info["id"],
                name=exchange_info["name"],
                market_type=MarketType.STOCK,
                timezone=exchange_info["timezone"],
                currency=exchange_info["currency"],
                regular_open=exchange_info["regular_open"],
                regular_close=exchange_info["regular_close"],
                pre_market_start=exchange_info["pre_market_start"],
                after_hours_end=exchange_info["after_hours_end"],
            )

        # Default fallback to NASDAQ if exchange not found
        default_info = get_exchange_info("XNAS")
        return Market(
            id=default_info["id"],
            name=default_info["name"],
            market_type=MarketType.STOCK,
            timezone=default_info["timezone"],
            currency=default_info["currency"],
            regular_open=default_info["regular_open"],
            regular_close=default_info["regular_close"],
            pre_market_start=default_info["pre_market_start"],
            after_hours_end=default_info["after_hours_end"],
        )

    def _ensure_markets_exist(self) -> None:
        """Ensure all required markets exist in database using centralized config"""
        supported_exchanges = get_supported_exchanges()
        markets_to_ensure = []

        # Create unique markets from exchange definitions
        unique_markets = {}
        for exchange_code, exchange_info in supported_exchanges.items():
            market_id = exchange_info["id"]
            if market_id not in unique_markets:
                unique_markets[market_id] = Market(
                    id=market_id,
                    name=exchange_info["name"],
                    market_type=MarketType.STOCK,
                    timezone=exchange_info["timezone"],
                    currency=exchange_info["currency"],
                    regular_open=exchange_info["regular_open"],
                    regular_close=exchange_info["regular_close"],
                    pre_market_start=exchange_info["pre_market_start"],
                    after_hours_end=exchange_info["after_hours_end"],
                )

        markets_to_ensure = list(unique_markets.values())

        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            for market in markets_to_ensure:
                cursor.execute("SELECT id FROM markets WHERE id = ?", (market.id,))
                if not cursor.fetchone():
                    cursor.execute(
                        "INSERT INTO markets (id, name, market_type) VALUES (?, ?, ?)",
                        (market.id, market.name, market.market_type.value),
                    )
                    logger.debug(f"Created market: {market.id}")

            conn.commit()

        except Exception as e:
            conn.rollback()
            logger.error(f"Error ensuring markets exist: {e}")
            raise
        finally:
            conn.close()

    def _insert_asset_in_db(self, cursor, asset: Asset) -> None:
        """Insert new asset into database"""
        cursor.execute(
            """
            INSERT INTO assets (
                symbol, name, asset_type, market_id, currency, 
                isin, cusip, is_active, min_order_size
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                asset.symbol,
                asset.name,
                asset.asset_type.value,
                asset.market.id,
                asset.currency,
                asset.isin,
                asset.cusip,
                asset.is_active,
                float(asset.min_order_size),
            ),
        )

    def _update_asset_in_db(self, cursor, asset: Asset, asset_id: int) -> None:
        """Update existing asset in database"""
        cursor.execute(
            """
            UPDATE assets SET
                name = ?, asset_type = ?, market_id = ?, currency = ?,
                isin = ?, cusip = ?, is_active = ?, min_order_size = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (
                asset.name,
                asset.asset_type.value,
                asset.market.id,
                asset.currency,
                asset.isin,
                asset.cusip,
                asset.is_active,
                float(asset.min_order_size),
                asset_id,
            ),
        )

    def get_universe_stats(self) -> Dict[str, int]:
        """Get statistics about current asset universe"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()

            stats = {}

            # Total assets
            cursor.execute("SELECT COUNT(*) FROM assets")
            stats["total_assets"] = cursor.fetchone()[0]

            # Active assets
            cursor.execute("SELECT COUNT(*) FROM assets WHERE is_active = 1")
            stats["active_assets"] = cursor.fetchone()[0]

            # By asset type
            cursor.execute(
                """
                SELECT asset_type, COUNT(*) 
                FROM assets 
                WHERE is_active = 1 
                GROUP BY asset_type
            """
            )
            for asset_type, count in cursor.fetchall():
                stats[f"{asset_type}_count"] = count

            # By market
            cursor.execute(
                """
                SELECT a.market_id, COUNT(*) 
                FROM assets a
                WHERE a.is_active = 1 
                GROUP BY a.market_id
            """
            )
            for market_id, count in cursor.fetchall():
                stats[f"{market_id.lower()}_count"] = count

            conn.close()
            return stats

        except Exception as e:
            logger.error(f"Error getting universe stats: {e}")
            return {}

    def cleanup_inactive_assets(self, days_inactive: int = 90) -> int:
        """Remove assets that have been inactive for specified days"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()

            # Mark as inactive instead of deleting (safer)
            cursor.execute(
                """
                UPDATE assets 
                SET is_active = 0 
                WHERE is_active = 1 
                AND updated_at < datetime('now', '-{} days')
            """.format(
                    days_inactive
                )
            )

            affected = cursor.rowcount
            conn.commit()
            conn.close()

            logger.info(f"Marked {affected} assets as inactive")
            return affected

        except Exception as e:
            logger.error(f"Error cleaning up inactive assets: {e}")
            return 0


def main():
    """CLI entry point for manual bootstrapping"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Bootstrap asset universe from Polygon.io"
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Only show current universe statistics",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        bootstrapper = PolygonTickerBootstrapper()

        if args.stats_only:
            stats = bootstrapper.get_universe_stats()
            print("Current Asset Universe Statistics:")
            for key, value in stats.items():
                print(f"  {key}: {value:,}")
        else:
            print("Starting Polygon universe bootstrap...")
            print("Market types: stocks only")

            stats = bootstrapper.bootstrap_tickers(market_types=["stocks"])

            print("\nBootstrap Results:")
            print(f"  Total fetched: {stats['total_fetched']:,}")
            print(f"  Inserted: {stats['inserted']:,}")
            print(f"  Updated: {stats['updated']:,}")
            print(f"  Skipped: {stats['skipped']:,}")
            print(f"  Errors: {stats['errors']:,}")

            # Show final stats
            print("\nFinal Universe Statistics:")
            final_stats = bootstrapper.get_universe_stats()
            for key, value in final_stats.items():
                print(f"  {key}: {value:,}")

    except Exception as e:
        print(f"Bootstrap failed: {e}")
        import sys

        sys.exit(1)


if __name__ == "__main__":
    main()
