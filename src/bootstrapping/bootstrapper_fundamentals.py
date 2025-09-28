"""Bootstrap fundamentals data from Polygon API ticker overview into the database."""

import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from provider.data_provider import PolygonDataProvider
from config.ttl_config import FUNDAMENTALS_TTL_HOURS
from services.data_update_tracker import DataUpdateTracker
from models.fundamentals import AssetFundamentals

logger = logging.getLogger(__name__)


class FundamentalsBootstrapper:
    """Bootstrap fundamentals data from Polygon API ticker overview."""

    def __init__(self, db_manager=None):
        """Initialize with database manager."""
        self.data_provider = PolygonDataProvider(db_manager)
        self.db_manager = db_manager
        self.last_stats = {}
        self.current_stats = {}  # Live stats for progress display
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
                raise ValueError("Provider 'polygon' must be bootstrapped first. Run 'tradescout database bootstrap-providers'")

    def get_polygon_provider_id(self) -> int:
        """Get Polygon provider ID from database."""
        if not self.db_manager:
            raise ValueError("Database manager required")

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM providers WHERE name = 'polygon'")
            result = cursor.fetchone()
            if not result:
                raise ValueError("Polygon provider not found")
            return result[0]

    def get_all_asset_symbols(self) -> List[Dict[str, Any]]:
        """Get asset symbols and IDs from the active universe."""
        if not self.db_manager:
            raise ValueError("Database manager required")

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            # Get assets from the active universe only
            cursor.execute("""
                SELECT a.id, a.symbol, u.name as universe_name
                FROM assets a
                JOIN universe_memberships um ON a.id = um.asset_id
                JOIN universes u ON um.universe_id = u.id
                WHERE u.is_active = 1 AND a.is_active = 1 AND um.is_active = 1
                ORDER BY a.symbol
            """)

            rows = cursor.fetchall()
            if not rows:
                raise ValueError("No active universe found or active universe is empty. Use 'tradescout universe activate <name>' to set one.")

            assets = [{"id": row[0], "symbol": row[1]} for row in rows]
            universe_name = rows[0][2]  # Get universe name from first row
            logger.debug(f"Found {len(assets)} assets in active universe '{universe_name}'")
            return assets

    def fetch_ticker_overview(self, symbol: str) -> tuple[Optional[Dict[str, Any]], str]:
        """Fetch ticker overview for a single symbol.

        Returns:
            Tuple of (data, status) where status is 'success', 'not_found', or 'error'
        """
        try:
            response = self.data_provider.get_ticker_overview(symbol)
            if response and "results" in response:
                return response["results"], "success"
            logger.warning(f"No results for ticker {symbol}")
            return None, "error"
        except Exception as e:
            error_str = str(e)
            if "404" in error_str and "NOT_FOUND" in error_str:
                # This is a specific 404 NOT_FOUND error from Polygon
                return None, "not_found"
            else:
                logger.error(f"Error fetching ticker overview for {symbol}: {e}")
                return None, "error"

    def map_polygon_to_fundamentals(self, polygon_data: Dict[str, Any], asset_id: int, provider_id: int) -> Optional[AssetFundamentals]:
        """Map Polygon ticker overview data to our AssetFundamentals model."""
        try:
            return AssetFundamentals.from_polygon_data(asset_id, provider_id, polygon_data)
        except Exception as e:
            logger.error(f"Error mapping fundamentals data: {e}")
            return None

    def upsert_fundamentals(self, fundamentals_list: List[AssetFundamentals]) -> Dict[str, int]:
        """Upsert fundamentals into database."""
        if not self.db_manager:
            raise ValueError("Database manager required for upsert operations")

        stats = {"inserted": 0, "updated": 0, "errors": 0}

        if not fundamentals_list:
            return stats

        logger.debug(f"Processing {len(fundamentals_list)} fundamentals records...")

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            for fundamentals in fundamentals_list:
                try:
                    # Check if record exists
                    cursor.execute(
                        "SELECT asset_id FROM asset_fundamentals WHERE asset_id = ?",
                        (fundamentals.asset_id,)
                    )
                    exists = cursor.fetchone()

                    # Convert model to dict for database operations
                    fundamentals_dict = fundamentals.to_dict()

                    if exists:
                        # Update existing record
                        update_fields = []
                        update_values = []
                        for key, value in fundamentals_dict.items():
                            if key != "asset_id":  # Don't update the primary key
                                update_fields.append(f"{key} = ?")
                                update_values.append(value)

                        if update_fields:
                            update_values.append(fundamentals.asset_id)
                            query = f"UPDATE asset_fundamentals SET {', '.join(update_fields)} WHERE asset_id = ?"
                            cursor.execute(query, update_values)
                            stats["updated"] += 1
                    else:
                        # Insert new record
                        fields = list(fundamentals_dict.keys())
                        placeholders = ", ".join(["?" for _ in fields])
                        values = list(fundamentals_dict.values())

                        query = f"INSERT INTO asset_fundamentals ({', '.join(fields)}) VALUES ({placeholders})"
                        cursor.execute(query, values)
                        stats["inserted"] += 1

                except Exception as e:
                    logger.error(f"Error upserting fundamentals for asset_id {fundamentals.asset_id}: {e}")
                    stats["errors"] += 1

            conn.commit()

        logger.debug(f"Fundamentals upsert complete: {stats}")
        return stats

    def bootstrap_fundamentals(self, symbol: Optional[str] = None, force: bool = False, limit: Optional[int] = None, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Bootstrap fundamentals data for all assets or a specific symbol.

        Args:
            symbol: Optional specific symbol to bootstrap
            force: If True, refresh existing data
            limit: Optional limit on number of assets to process
            progress_callback: Optional callback for progress updates (symbol, current, total)

        Returns:
            Dict with statistics about the bootstrap operation
        """
        logger.debug("Starting fundamentals bootstrap")

        # Check if data is fresh unless forced (only for bulk operations, not single symbols)
        if not force and not symbol and self.update_tracker:
            if not self.is_fundamentals_data_stale():
                last_update = self.get_last_fundamentals_update()
                logger.info(f"Fundamentals data is fresh (last update: {last_update}), skipping bootstrap. Use --force to refresh anyway.")

                # Return success stats from last run if available
                history = self.update_tracker.get_operation_history("fundamentals", limit=1)
                if history:
                    last_stats = history[0].get('stats', {})
                    return {
                        "inserted": last_stats.get('inserted', 0),
                        "updated": last_stats.get('updated', 0),
                        "errors": last_stats.get('errors', 0),
                        "api_calls": last_stats.get('api_calls', 0),
                        "skipped": last_stats.get('skipped', 0)
                    }
                else:
                    return {"inserted": 0, "updated": 0, "errors": 0, "api_calls": 0, "skipped": 0}

        # Start operation tracking
        operation_id = None
        if self.update_tracker:
            operation_subtype = "single_symbol" if symbol else "bootstrap"
            operation_params = {
                "symbol": symbol,
                "force": force,
                "limit": limit
            }

        try:
            # Ensure providers exist
            self.ensure_providers_exist()
            provider_id = self.get_polygon_provider_id()

            # Get assets to process
            if symbol:
                # Single symbol
                with self.db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, symbol FROM assets WHERE symbol = ? AND is_active = 1", (symbol,))
                    row = cursor.fetchone()
                    if not row:
                        raise ValueError(f"Asset {symbol} not found or inactive")
                    assets = [{"id": row[0], "symbol": row[1]}]
            else:
                # All assets
                assets = self.get_all_asset_symbols()
                if limit:
                    assets = assets[:limit]

            # Start operation tracking with known total
            if self.update_tracker:
                operation_id = self.update_tracker.start_operation(
                    operation_type="fundamentals",
                    operation_subtype=operation_subtype,
                    operation_params=operation_params,
                    total_items=len(assets)
                )

            logger.debug(f"Processing {len(assets)} assets for fundamentals data")

            # Process assets individually with progress reporting
            total_stats = {"inserted": 0, "updated": 0, "errors": 0, "api_calls": 0, "skipped": 0, "not_found": 0}
            not_found_symbols = []  # Track symbols that return 404
            fundamentals_batch = []
            group_size = 100  # Process records in groups for efficiency

            # Initialize current stats for progress display
            self.current_stats = total_stats.copy()

            for i, asset in enumerate(assets):
                asset_id = asset["id"]
                symbol = asset["symbol"]

                # Report progress
                if progress_callback:
                    progress_callback(symbol, i + 1, len(assets))

                # Skip if already exists and not forcing refresh
                if not force:
                    with self.db_manager.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT last_updated FROM asset_fundamentals WHERE asset_id = ?", (asset_id,))
                        if cursor.fetchone():
                            total_stats["skipped"] += 1
                            # Update tracker progress
                            if self.update_tracker and operation_id:
                                self.update_tracker.update_progress(
                                    operation_id,
                                    processed_items=i + 1,
                                    stats=total_stats
                                )
                            continue

                # Fetch ticker overview
                ticker_data, status = self.fetch_ticker_overview(symbol)
                total_stats["api_calls"] += 1

                if status == "success" and ticker_data:
                    fundamentals = self.map_polygon_to_fundamentals(ticker_data, asset_id, provider_id)
                    if fundamentals:
                        fundamentals_batch.append(fundamentals)
                elif status == "not_found":
                    total_stats["not_found"] += 1
                    not_found_symbols.append(symbol)
                else:
                    total_stats["errors"] += 1

                # Update current stats for progress display
                self.current_stats = total_stats.copy()

                # Update tracker progress periodically
                if self.update_tracker and operation_id and (i + 1) % 10 == 0:
                    self.update_tracker.update_progress(
                        operation_id,
                        processed_items=i + 1,
                        api_calls_made=total_stats["api_calls"],
                        stats=total_stats
                    )

                # Process group when it's full or at the end
                if len(fundamentals_batch) >= group_size or i == len(assets) - 1:
                    if fundamentals_batch:
                        batch_stats = self.upsert_fundamentals(fundamentals_batch)
                        total_stats["inserted"] += batch_stats["inserted"]
                        total_stats["updated"] += batch_stats["updated"]
                        total_stats["errors"] += batch_stats["errors"]
                        fundamentals_batch = []  # Clear batch

            # Complete operation tracking
            if self.update_tracker and operation_id:
                # Final progress update
                self.update_tracker.update_progress(
                    operation_id,
                    processed_items=len(assets),
                    api_calls_made=total_stats["api_calls"],
                    stats=total_stats
                )
                # Mark as completed
                status = 'completed' if total_stats["errors"] == 0 else 'partial'
                self.update_tracker.complete_operation(operation_id, total_stats, status)

            # Add not found symbols list to stats
            total_stats["not_found_symbols"] = not_found_symbols

            logger.debug(f"Fundamentals bootstrap complete: {total_stats}")
            self.last_stats = total_stats
            return total_stats

        except Exception as e:
            # Mark operation as failed
            if self.update_tracker and operation_id:
                self.update_tracker.fail_operation(operation_id, str(e))

            logger.error(f"Fundamentals bootstrap failed: {e}")
            raise

    def get_bootstrap_stats(self) -> Dict[str, Any]:
        """Get statistics from last bootstrap operation."""
        return self.last_stats

    def is_fundamentals_data_stale(self, max_age_hours: int = FUNDAMENTALS_TTL_HOURS) -> bool:
        """Check if fundamentals data is stale (default: 1 week).

        Args:
            max_age_hours: Maximum age in hours before considering stale

        Returns:
            True if data is stale or never updated, False if fresh
        """
        if not self.update_tracker:
            return True  # Can't check without tracker

        return self.update_tracker.is_data_stale("fundamentals", max_age_hours)

    def get_last_fundamentals_update(self) -> Optional[datetime]:
        """Get timestamp of last successful fundamentals update."""
        if not self.update_tracker:
            return None

        return self.update_tracker.get_last_update("fundamentals")