"""Data service orchestration layer.

Wires together database managers (storage/TTL) and API providers (external calls).
Provides clean interface for business logic to access data.
"""

import logging
import re
from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from api.providers import (
    PolygonAggregatesProvider,
    PolygonMarketsProvider,
    PolygonMarketStatusProvider,
    PolygonNewsProvider,
    PolygonSnapshotProvider,
    PolygonTickersProvider,
)
from utils.config_loader import get_config_loader
from database.managers import (
    AssetManager,
    AssetPriceManager,
    DataUpdateMetadataManager,
    FedDataManager,
    FundamentalsManager,
    MarketHolidaysManager,
    MarketsManager,
    MarketSnapshotManager,
    ProviderManager,
    SentimentEventsManager,
    SentimentTypesManager,
    TickerSnapshotManager,
    UniverseManager,
)
from models.asset import Asset
from models.fundamentals import AssetFundamentals
from models.market import Market
from models.market_context import MarketContext
from models.market_holiday import MarketHoliday
from models.results import BootstrapResult, FetchResult, UpdateResult, NewsResult
from models.sentiment_event import SentimentEvent
from models.sentiment_type import SentimentType
from models.snapshot import MarketSnapshot, TickerSnapshot
from models.universe import Universe
from protocols.progress import ProgressReporter
from services.market_context_service import MarketContextService

logger = logging.getLogger(__name__)


class DataService:
    """Orchestrates data access between database managers and API providers.

    Responsibilities:
    - Initialize database managers and API providers
    - Coordinate between storage layer and API layer
    - Provide clean interface for data access
    - Handle force refresh parameters

    This layer does NOT:
    - Make database calls directly (that's manager responsibility)
    - Make API calls directly (that's provider responsibility)
    - Implement TTL logic (that's manager responsibility)
    """

    def __init__(self, db_manager, polygon_api_key: str):
        """Initialize data service with dependencies.

        Args:
            db_manager: Database manager for SQLite operations
            polygon_api_key: Polygon API key for API providers
        """
        self.db_manager = db_manager

        # Initialize metadata manager for TTL tracking
        self.metadata_manager = DataUpdateMetadataManager(db_manager)

        # Initialize database managers (with metadata manager for TTL tracking)
        self.ticker_snapshot_manager = TickerSnapshotManager(
            db_manager, self.metadata_manager
        )
        self.market_snapshot_manager = MarketSnapshotManager(
            db_manager, self.metadata_manager
        )
        self.asset_manager = AssetManager(db_manager, self.metadata_manager)
        self.asset_price_manager = AssetPriceManager(db_manager, self.metadata_manager)
        self.universe_manager = UniverseManager(db_manager, self.metadata_manager)
        self.provider_manager = ProviderManager(db_manager, self.metadata_manager)
        self.fundamentals_manager = FundamentalsManager(
            db_manager, self.metadata_manager
        )
        self.markets_manager = MarketsManager(db_manager, self.metadata_manager)
        self.market_holidays_manager = MarketHolidaysManager(
            db_manager, self.metadata_manager
        )

        # Initialize sentiment managers (no metadata tracking - see docs/DATA_UPDATE_METADATA.md)
        self.sentiment_types_manager = SentimentTypesManager(
            db_manager, None  # No metadata tracking for config tables
        )
        self.sentiment_events_manager = SentimentEventsManager(
            db_manager, None  # No metadata tracking for continuous events
        )

        # Initialize Fed data manager (economic data from Federal Reserve)
        self.fed_data_manager = FedDataManager(db_manager, self.metadata_manager)

        # Initialize API providers
        self.polygon_snapshot_provider = PolygonSnapshotProvider(polygon_api_key)
        self.polygon_tickers_provider = PolygonTickersProvider(polygon_api_key)
        self.polygon_markets_provider = PolygonMarketsProvider(polygon_api_key)
        self.polygon_market_status_provider = PolygonMarketStatusProvider(
            polygon_api_key
        )
        self.polygon_news_provider = PolygonNewsProvider(polygon_api_key)
        self.polygon_aggregates_provider = PolygonAggregatesProvider(polygon_api_key)

        # Initialize market context service
        self.market_context_service = MarketContextService(self)

        logger.debug("DataService initialized with managers and providers")

    # ============================================================================
    # TICKER SNAPSHOT OPERATIONS
    # ============================================================================

    def get_ticker_snapshot(
        self, symbol: str, force_refresh: bool = False
    ) -> Optional[TickerSnapshot]:
        """Get ticker snapshot with automatic cache/refresh logic.

        This is the main entry point for ticker snapshot access. It:
        1. Checks if force_refresh is requested
        2. Delegates to manager which checks TTL
        3. Manager calls API provider if data is stale or forced
        4. Manager stores fresh data to database
        5. Returns the ticker snapshot

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            force_refresh: If True, bypass cache and always fetch fresh data

        Returns:
            TickerSnapshot object or None if error
        """
        logger.debug(
            f"Getting ticker snapshot for {symbol} (force_refresh={force_refresh})"
        )

        # The manager handles all the logic:
        # - Check TTL (unless force_refresh)
        # - Decide whether to fetch or use cached
        # - Store fresh data if fetched
        # We just provide the API fetch function
        return self.ticker_snapshot_manager.get_or_fetch(
            key=symbol,
            fetch_fn=lambda: self.polygon_snapshot_provider.fetch_single_ticker_snapshot(
                symbol
            ),
            force_refresh=force_refresh,
        )

    # ============================================================================
    # MARKET SNAPSHOT OPERATIONS (BULK REFRESH)
    # ============================================================================

    def get_market_snapshot(
        self, symbols: Optional[List[str]] = None, force_refresh: bool = False
    ) -> Optional[MarketSnapshot]:
        """Get bulk market snapshot via Polygon API.

        This is a bulk operation that fetches snapshots for many tickers in a single
        API call, then stores each ticker individually to asset_prices table.

        The MarketSnapshotManager tracks WHEN bulk refreshes occur (metadata only)
        to prevent excessive API calls. It does NOT cache the snapshot data itself.

        Args:
            symbols: Optional list of symbols to fetch (None = all tickers)
            force_refresh: If True, bypass TTL and always fetch fresh data

        Returns:
            MarketSnapshot object with bulk data, or None if refresh was skipped (within TTL)
        """
        # Use "all" as key for full market snapshot, or comma-separated symbols
        cache_key = "all" if not symbols else ",".join(sorted(symbols))

        logger.debug(
            f"Getting market snapshot for {len(symbols) if symbols else 'all'} symbols "
            f"(force_refresh={force_refresh})"
        )

        # The manager handles TTL logic and decides whether to fetch
        market_snapshot = self.market_snapshot_manager.get_or_fetch(
            key=cache_key,
            fetch_fn=lambda: self.polygon_snapshot_provider.fetch_bulk_market_snapshot(
                symbols
            ),
            force_refresh=force_refresh,
        )

        # Note: Individual ticker storage is handled by the caller (e.g., CLI batch operations)
        # to allow for more efficient bulk inserts
        return market_snapshot

    def _store_individual_tickers_from_market_snapshot(
        self, market_snapshot: MarketSnapshot
    ) -> None:
        """Store individual ticker snapshots from a bulk market snapshot.

        This is a helper to cache individual tickers after a bulk fetch,
        enabling subsequent single-ticker queries to use cached data.

        Args:
            market_snapshot: MarketSnapshot containing ticker data to store
        """
        if not market_snapshot or not market_snapshot.tickers:
            return

        stored_count = 0
        for symbol, ticker_snapshot in market_snapshot.tickers.items():
            try:
                success = self.ticker_snapshot_manager.set_entity_to_database(
                    symbol, ticker_snapshot
                )
                if success:
                    stored_count += 1
            except Exception as e:
                logger.warning(
                    f"Failed to store ticker {symbol} from market snapshot: {e}"
                )

        logger.debug(
            f"Stored {stored_count}/{len(market_snapshot.tickers)} individual tickers from market snapshot"
        )

    # ============================================================================
    # ASSET PRICE OPERATIONS
    # ============================================================================

    def get_latest_asset_price(self, asset_id: int) -> Optional["AssetPrice"]:
        """Get the most recent price record for an asset.

        Args:
            asset_id: Asset database ID

        Returns:
            AssetPrice object or None if not found
        """
        from models.price import AssetPrice

        logger.debug(f"Getting latest asset price for asset_id {asset_id}")
        return self.asset_price_manager.get_entity_from_database(str(asset_id))

    def save_asset_price_data(self, asset_price: "AssetPrice") -> bool:
        """Save asset price data to database.

        Args:
            asset_price: AssetPrice object to save

        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Saving asset price for asset_id {asset_price.asset_id}")
        return self.asset_price_manager.set_entity_to_database(
            str(asset_price.asset_id), asset_price
        )

    def batch_save_asset_prices(
        self, asset_prices: list["AssetPrice"]
    ) -> tuple[int, int, int, int]:
        """Batch save asset price data to database.

        Args:
            asset_prices: List of AssetPrice objects to save

        Returns:
            Tuple of (new_records, duplicate_records, successful_count, failed_count)
        """
        logger.debug(f"Batch saving {len(asset_prices)} asset prices")
        return self.asset_price_manager.batch_set_entities_to_database(asset_prices)

    def transform_ticker_snapshot_to_asset_price(
        self, symbol: str, asset_id: int, ticker_snapshot: TickerSnapshot
    ) -> Optional["AssetPrice"]:
        """Transform TickerSnapshot model to AssetPrice model.

        Args:
            symbol: Stock symbol
            asset_id: Asset database ID
            ticker_snapshot: TickerSnapshot object to transform

        Returns:
            AssetPrice object or None if error
        """
        try:
            from models.price import AssetPrice

            # Get provider ID (default to 1 = Polygon)
            provider_id = 1

            # Use Polygon's updated timestamp or default to 0
            provider_updated_at = ticker_snapshot.updated_ns or 0

            # Determine trade date
            if provider_updated_at and provider_updated_at != 0:
                updated_seconds = provider_updated_at // 1_000_000_000
                trade_date = datetime.fromtimestamp(updated_seconds).date()
            elif ticker_snapshot.min_bar and ticker_snapshot.min_bar.timestamp:
                trade_date = datetime.fromtimestamp(
                    ticker_snapshot.min_bar.timestamp / 1000
                ).date()
            else:
                trade_date = datetime.now().date()

            return AssetPrice(
                id=0,  # Will be set by database auto-increment
                asset_id=asset_id,
                symbol=symbol,
                provider_id=provider_id,
                provider_updated_at=provider_updated_at,
                trade_date=trade_date,
                updated_at=datetime.now(),
                # Previous day data
                prevday_open=ticker_snapshot.prev_open,
                prevday_high=ticker_snapshot.prev_high,
                prevday_low=ticker_snapshot.prev_low,
                prevday_close=ticker_snapshot.prev_close,
                prevday_volume=ticker_snapshot.prev_volume,
                prevday_vwap=ticker_snapshot.prev_vwap,
                # Current day data
                day_open=ticker_snapshot.open_price,
                day_high=ticker_snapshot.high_price,
                day_low=ticker_snapshot.low_price,
                day_close=ticker_snapshot.close_price,
                day_volume=ticker_snapshot.volume,
                day_vwap=ticker_snapshot.vwap,
                # Min data
                min_timestamp=(
                    ticker_snapshot.min_bar.timestamp
                    if ticker_snapshot.min_bar
                    else None
                ),
                min_open=(
                    ticker_snapshot.min_bar.open if ticker_snapshot.min_bar else None
                ),
                min_high=(
                    ticker_snapshot.min_bar.high if ticker_snapshot.min_bar else None
                ),
                min_low=(
                    ticker_snapshot.min_bar.low if ticker_snapshot.min_bar else None
                ),
                min_close=(
                    ticker_snapshot.min_bar.close if ticker_snapshot.min_bar else None
                ),
                min_volume=(
                    ticker_snapshot.min_bar.volume if ticker_snapshot.min_bar else None
                ),
                min_vwap=(
                    ticker_snapshot.min_bar.vwap if ticker_snapshot.min_bar else None
                ),
                min_accumulated_volume=(
                    ticker_snapshot.min_bar.accumulated_volume
                    if ticker_snapshot.min_bar
                    else None
                ),
                min_num_trades=(
                    ticker_snapshot.min_bar.num_trades
                    if ticker_snapshot.min_bar
                    else None
                ),
            )

        except Exception as e:
            logger.error(f"Error transforming TickerSnapshot for {symbol}: {e}")
            return None

    # ============================================================================
    # ASSET OPERATIONS (REFERENCE DATA)
    # ============================================================================

    def get_asset_with_market(
        self, symbol: str, force_refresh: bool = False
    ) -> Optional[Tuple[Asset, "Market"]]:
        """Get asset and its associated market (orchestrates managers).

        Args:
            symbol: Stock symbol
            force_refresh: Force refresh from API

        Returns:
            Tuple of (Asset, Market) or None if not found
        """
        asset = self.get_asset(symbol, force_refresh)
        if not asset:
            return None

        market = (
            self.get_market_by_id(asset.market_id) if asset.market_id else None
        )
        return (asset, market)

    def get_all_assets_dict(self) -> Dict[str, int]:
        """Get all active assets as a dictionary for quick symbol lookups.

        Returns:
            Dictionary mapping symbol -> asset_id
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT symbol, id FROM assets WHERE is_active = 1")
                return {row[0]: row[1] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error getting all assets dict: {e}")
            return {}

    def get_asset(self, symbol: str, force_refresh: bool = False) -> Optional[Asset]:
        """Get asset reference data for a symbol with automatic cache/refresh logic.

        Assets are relatively static reference data (symbol, name, type, etc.)
        fetched from Polygon's /v3/reference/tickers endpoint. They are typically
        bootstrapped in bulk but can be fetched individually on-demand.

        This method:
        1. Checks if force_refresh is requested
        2. Delegates to manager which checks TTL
        3. Manager calls API provider if data is stale or forced
        4. Manager stores fresh data to database
        5. Returns the asset

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            force_refresh: If True, bypass cache and always fetch fresh data

        Returns:
            Asset object or None if not found
        """
        logger.debug(f"Getting asset for {symbol} (force_refresh={force_refresh})")

        # Get market mapping for the provider to use
        markets = self.get_all_markets(active_only=False)
        market_code_to_id = {m.code: m.id for m in markets} if markets else None

        # Use get_or_fetch pattern with PolygonTickersProvider
        return self.asset_manager.get_or_fetch(
            key=symbol,
            fetch_fn=lambda: self.polygon_tickers_provider.fetch_ticker_details(
                symbol, market_code_to_id
            ),
            force_refresh=force_refresh,
        )

    def bootstrap_assets(
        self,
        market: str = "stocks",
        active: bool = True,
        progress: Optional[ProgressReporter] = None,
    ) -> BootstrapResult:
        """Bootstrap all assets from Polygon tickers API.

        Fetches all tickers from Polygon and stores them as assets in database.
        This is a bulk operation that should be run periodically (every 3 days per TTL).

        Args:
            market: Market type (default: "stocks")
            active: Only fetch active tickers (default: True)
            progress: Optional progress reporter for operation tracking

        Returns:
            BootstrapResult with operation statistics and error details

        Raises:
            RuntimeError: If prerequisites (providers, markets) are not met
        """
        import time

        start_time = time.time()
        logger.info(
            f"Bootstrapping assets from Polygon (market={market}, active={active})"
        )

        # Check prerequisites
        providers = self.get_all_providers()
        if not providers:
            raise RuntimeError(
                "Cannot bootstrap assets: No providers in database. Run 'bootstrap-providers' first."
            )

        markets = self.get_all_markets(active_only=False)
        if not markets:
            raise RuntimeError(
                "Cannot bootstrap assets: No markets in database. Run 'bootstrap-markets' first."
            )

        # Get Polygon provider ID (should be the active one)
        polygon_provider = next((p for p in providers if p.name == "polygon"), None)
        if not polygon_provider:
            raise RuntimeError(
                "Cannot bootstrap assets: Polygon provider not found in database."
            )

        # Create market_code to market_id mapping for the provider
        market_code_to_id = {m.code: m.id for m in markets}

        # Fetch all tickers from API with market mapping
        raw_assets = self.polygon_tickers_provider.fetch_all_tickers(
            market=market, active=active, market_code_to_id=market_code_to_id
        )

        # Fix provider_id for all assets (provider uses placeholder provider_id)
        # Asset is frozen dataclass, so we need to use dataclasses.replace()
        from dataclasses import replace

        assets = []
        for asset in raw_assets:
            fixed_asset = replace(asset, provider_id=polygon_provider.id)
            assets.append(fixed_asset)

        if not assets:
            logger.warning("No assets fetched from Polygon")
            return BootstrapResult(
                operation="assets",
                total_items=0,
                successful=0,
                failed=0,
                duration_seconds=time.time() - start_time,
                timestamp=datetime.now(),
            )

        # Bulk insert assets to database in batches
        batch_size = 1000
        stored_count = 0
        failed_count = 0
        total = len(assets)
        insert_errors = []

        if progress:
            progress.start_operation("Storing assets", total)

        for i in range(0, total, batch_size):
            batch = assets[i : i + batch_size]
            batch_stored = self.asset_manager.bulk_insert_assets(batch)
            stored_count += batch_stored
            batch_failed = len(batch) - batch_stored
            failed_count += batch_failed

            # Track errors for failed inserts
            if batch_failed > 0:
                insert_errors.append(
                    f"Batch {i//batch_size + 1}: {batch_failed} assets failed to insert"
                )

            if progress:
                progress.update_progress(i + len(batch), f"Stored {stored_count} assets")

        if progress:
            progress.complete_operation(
                success=True, message=f"Stored {stored_count}/{total} assets"
            )

        # Record the bootstrap operation timestamp
        self.asset_manager._record_update()

        duration = time.time() - start_time

        result = BootstrapResult(
            operation="assets",
            total_items=total,
            successful=stored_count,
            failed=failed_count,
            insert_errors=insert_errors,
            duration_seconds=duration,
            timestamp=datetime.now(),
        )

        logger.info(f"Bootstrapped {stored_count}/{total} assets successfully")
        return result

    # ============================================================================
    # FUNDAMENTALS OPERATIONS
    # ============================================================================

    def _fetch_fundamentals_for_symbol(
        self, symbol: str, asset_id: int
    ) -> Optional[AssetFundamentals]:
        """Internal helper to fetch fundamentals from Polygon API.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            asset_id: Asset ID from assets table

        Returns:
            AssetFundamentals object or None if error
        """
        # Fetch raw ticker data from Polygon
        ticker_data = self.polygon_tickers_provider.fetch_ticker_details_raw(symbol)
        if not ticker_data:
            logger.warning(f"Failed to fetch ticker details for {symbol}")
            return None

        # Convert to AssetFundamentals using model's class method
        # Provider ID 1 = Polygon (hardcoded for now)
        try:
            fundamentals = AssetFundamentals.from_polygon_data(
                asset_id=asset_id,
                provider_id=1,  # Polygon provider
                polygon_data=ticker_data,
            )
            logger.debug(f"Successfully parsed fundamentals for {symbol}")
            return fundamentals
        except Exception as e:
            logger.error(f"Error parsing fundamentals for {symbol}: {e}")
            return None

    def bootstrap_fundamentals(
        self, limit: Optional[int] = None, progress: Optional[ProgressReporter] = None
    ) -> BootstrapResult:
        """Bootstrap fundamentals for all assets in database.

        This is a bulk operation that:
        1. Gets all assets from database
        2. For each asset, fetches ticker details from Polygon
        3. Extracts and stores fundamentals data

        Note: This can be expensive with many assets. Use limit to process in batches.

        Args:
            limit: Optional limit on number of assets to process
            progress: Optional progress reporter for operation tracking

        Returns:
            BootstrapResult with operation statistics and error details

        Raises:
            RuntimeError: If prerequisites (assets) are not met
        """
        import time

        start_time = time.time()
        logger.info(f"Bootstrapping fundamentals (limit={limit})")

        # Get all assets from database via AssetManager
        assets = self.asset_manager.get_all_active_asset_ids(limit=limit)

        if not assets:
            raise RuntimeError(
                "Cannot bootstrap fundamentals: No assets in database. Run 'bootstrap-tickers' first."
            )

        total_assets = len(assets)
        logger.info(f"Fetching fundamentals for {total_assets} assets")

        # Phase 1: Fetch ALL fundamentals from API (network calls only)
        fundamentals_data = {}  # {asset_id: AssetFundamentals object}
        fetch_errors = []

        if progress:
            progress.start_operation("Fetching from API", total_assets)

        for i, (asset_id, symbol) in enumerate(assets, start=1):
            try:
                fundamentals = self._fetch_fundamentals_for_symbol(symbol, asset_id)
                if fundamentals:
                    fundamentals_data[asset_id] = fundamentals
                else:
                    fetch_errors.append(f"{symbol}: No data returned")
            except Exception as e:
                fetch_errors.append(f"{symbol}: {str(e)}")

            if progress:
                progress.update_progress(i, f"Fetched {symbol}")

        if progress:
            progress.complete_operation(
                success=True,
                message=f"Fetched {len(fundamentals_data)}/{total_assets} fundamentals from API",
            )

        # Phase 2: Batch insert to database
        stored_count = 0
        insert_errors = []

        if progress:
            progress.start_operation("Writing to database", len(fundamentals_data))

        for i, (asset_id, fundamentals) in enumerate(fundamentals_data.items(), start=1):
            try:
                if self.fundamentals_manager.set_entity_to_database(
                    str(asset_id), fundamentals
                ):
                    stored_count += 1
                else:
                    insert_errors.append(
                        f"Asset ID {asset_id}: Database insert failed"
                    )
            except Exception as e:
                insert_errors.append(f"Asset ID {asset_id}: {str(e)}")

            if progress:
                progress.update_progress(i, f"Stored asset {asset_id}")

        if progress:
            progress.complete_operation(
                success=True,
                message=f"Stored {stored_count}/{len(fundamentals_data)} fundamentals to database",
            )

        # Record the bootstrap operation timestamp
        self.fundamentals_manager._record_update()

        duration = time.time() - start_time
        failed_count = total_assets - stored_count

        result = BootstrapResult(
            operation="fundamentals",
            total_items=total_assets,
            successful=stored_count,
            failed=failed_count,
            fetch_errors=fetch_errors,
            insert_errors=insert_errors,
            duration_seconds=duration,
            timestamp=datetime.now(),
        )

        logger.info(
            f"Bootstrapped {stored_count}/{total_assets} fundamentals successfully ({result.total_errors} errors total)"
        )

        return result

    # ============================================================================
    # UNIVERSE OPERATIONS (INTERNAL ONLY - NO API)
    # ============================================================================

    def bootstrap_universes(
        self, universe_name: str = "default_universe", force_refresh: bool = False
    ) -> Dict[str, int]:
        """Bootstrap a universe by filtering assets based on configuration criteria.

        Universes are filtered subsets of assets created by applying inclusion/exclusion
        criteria defined in config/universe_config.py. This method:
        1. Fetches all assets + fundamentals data from database
        2. Applies filtering criteria (exchanges, market cap, sectors, etc.)
        3. Creates/updates Universe record
        4. Clears old memberships and adds new ones
        5. Records metadata timestamp

        Args:
            universe_name: Name of universe from UNIVERSE_CONFIG (default: "default_universe")
            force_refresh: If True, bypass TTL and refresh regardless of freshness

        Returns:
            Dictionary with statistics: {
                "total_assets": int,
                "filtered_assets": int,
                "memberships_added": int
            }

        Raises:
            RuntimeError: If prerequisites (assets) are not met
        """
        logger.info(f"Bootstrapping universe: {universe_name}")

        # Get universe configuration
        config_loader = get_config_loader()
        all_universes = config_loader.load_all_universes()
        config = all_universes.get(universe_name)
        if not config:
            raise ValueError(
                f"Unknown universe: {universe_name}. Available: {list(all_universes.keys())}"
            )

        # Check prerequisites - need assets in database to filter
        asset_stats = self.asset_manager.get_stats()
        if asset_stats.get("total_active_assets", 0) == 0:
            raise RuntimeError(
                "Cannot bootstrap universes: No assets in database. Run 'bootstrap-tickers' first."
            )

        # Check if this specific universe exists and is fresh
        if not force_refresh:
            universe_stats = self.universe_manager.get_universe_stats(universe_name)
            if universe_stats and not self.universe_manager._is_data_stale():
                logger.info(
                    f"Universe '{universe_name}' data is fresh, skipping bootstrap. Use force_refresh=True to override."
                )
                return {
                    "total_assets": 0,
                    "filtered_assets": universe_stats.total_members,
                    "memberships_added": 0,
                    "skipped": True,
                }

        # Fetch all assets with fundamentals and market data
        all_assets = self._fetch_assets_with_fundamentals()
        logger.info(f"Found {len(all_assets)} total assets in database")

        # Apply filtering criteria (may result in zero assets - that's fine)
        filtered_assets = self._apply_universe_filters(all_assets, config)
        logger.info(f"Filtered to {len(filtered_assets)} assets for {universe_name}")

        # Create/update Universe record
        universe = Universe(
            id=0,  # Will be assigned by database
            name=config["name"],
            description=config.get("description", ""),
            is_active=False,  # Don't auto-activate, user must activate manually
            min_market_cap=config.get("included", {}).get("min_market_cap"),
            min_volume=config.get("included", {}).get("min_volume"),
            max_assets=config.get("max_assets"),
            last_updated=datetime.now(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        if not self.universe_manager.set_entity_to_database(universe_name, universe):
            raise RuntimeError(f"Failed to create/update universe: {universe_name}")

        # Add/update memberships (UPSERT - no need to clear)
        asset_ids = [asset["id"] for asset in filtered_assets]
        memberships_added = self.universe_manager.add_universe_memberships(
            universe_name, asset_ids
        )

        # Record metadata timestamp
        self.universe_manager._record_update()

        stats = {
            "total_assets": len(all_assets),
            "filtered_assets": len(filtered_assets),
            "memberships_added": memberships_added,
        }

        logger.info(f"Universe '{universe_name}' bootstrapped: {stats}")
        return stats

    def _fetch_assets_with_fundamentals(self) -> List[Dict[str, Any]]:
        """Fetch all assets with their fundamentals and market data.

        Returns:
            List of dicts with keys: id, symbol, name, asset_type, market_code,
                                     is_active, sector, market_cap, volume
        """
        return self.universe_manager.get_assets_with_fundamentals()

    def _apply_universe_filters(
        self, assets: List[Dict[str, Any]], config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply universe filtering criteria to assets.

        Args:
            assets: List of asset dicts
            config: Universe configuration from UNIVERSE_CONFIG

        Returns:
            Filtered list of asset dicts
        """
        included = config.get("included", {})
        excluded = config.get("excluded", {})

        filtered = []
        for asset in assets:
            if self._should_include_asset(asset, included, excluded):
                filtered.append(asset)

        return filtered

    def _should_include_asset(
        self, asset: Dict[str, Any], included: Dict[str, Any], excluded: Dict[str, Any]
    ) -> bool:
        """Check if asset meets inclusion criteria and doesn't meet exclusion criteria.

        Args:
            asset: Asset dict with all fields
            included: Inclusion criteria from config
            excluded: Exclusion criteria from config

        Returns:
            True if asset should be included in universe
        """
        # Check inclusion criteria
        if not self._meets_inclusion_criteria(asset, included):
            return False

        # Check exclusion criteria
        if self._meets_exclusion_criteria(asset, excluded):
            return False

        return True

    def _meets_inclusion_criteria(
        self, asset: Dict[str, Any], criteria: Dict[str, Any]
    ) -> bool:
        """Check if asset meets all inclusion criteria.

        Args:
            asset: Asset dict
            criteria: Inclusion criteria from config

        Returns:
            True if asset meets all criteria
        """
        # Check asset types (ticker_types: CS, ETF, REIT)
        if "ticker_types" in criteria:
            asset_type = asset.get("asset_type", "")
            # Map database asset_type to config ticker_types
            type_mapping = {"stock": "CS", "etf": "ETF", "reit": "REIT"}
            mapped_type = type_mapping.get(asset_type.lower(), asset_type)
            if mapped_type not in criteria["ticker_types"]:
                return False

        # Check exchanges (XNYS, XNAS)
        if "exchanges" in criteria:
            market_code = asset.get("market_code", "")
            if market_code not in criteria["exchanges"]:
                return False

        # Check symbol pattern (regex)
        if "symbol_pattern" in criteria:
            symbol = asset.get("symbol", "")
            if not re.match(criteria["symbol_pattern"], symbol):
                return False

        # Check active status
        if criteria.get("active_only", False):
            if not asset.get("is_active", False):
                return False

        # Check sectors (requires fundamentals data)
        if "sectors" in criteria:
            sector = asset.get("sector")
            # If sector filtering is required but sector data is missing, exclude
            if not sector:
                return False
            if sector not in criteria["sectors"]:
                return False

        # Check minimum market cap
        if "min_market_cap" in criteria:
            market_cap = asset.get("market_cap")
            # If market cap filtering is required but data is missing, exclude
            if market_cap is None:
                return False
            if market_cap < criteria["min_market_cap"]:
                return False

        # Check maximum market cap
        if "max_market_cap" in criteria:
            market_cap = asset.get("market_cap")
            if market_cap is None:
                return False
            if market_cap > criteria["max_market_cap"]:
                return False

        # Check minimum volume
        if "min_volume" in criteria:
            volume = asset.get("volume")
            if volume is None:
                return False
            if volume < criteria["min_volume"]:
                return False

        return True

    def _meets_exclusion_criteria(
        self, asset: Dict[str, Any], criteria: Dict[str, Any]
    ) -> bool:
        """Check if asset meets any exclusion criteria (should be excluded).

        Args:
            asset: Asset dict
            criteria: Exclusion criteria from config

        Returns:
            True if asset should be excluded
        """
        symbol = asset.get("symbol", "")
        market_code = asset.get("market_code", "")

        # Exclude preferred stocks (symbols ending in -P, -PR, -A, etc.)
        if criteria.get("preferred_stocks", False):
            if re.search(r"-[PA-Z]+$", symbol):
                return True

        # Exclude non-major exchanges (minor_exchanges.otc_markets)
        if criteria.get("minor_exchanges", {}).get("otc_markets", False):
            # Only keep XNYS and XNAS
            if market_code not in ["XNYS", "XNAS"]:
                return True

        # Exclude invalid symbols (special characters, not matching [A-Z]{1,5})
        if criteria.get("invalid_symbols", {}).get("special_characters", False):
            if not re.match(r"^[A-Z]{1,5}$", symbol):
                return True

        return False

    # ============================================================================

    def get_all_universes(self):
        """Get all universes from database.

        Returns:
            List of Universe objects
        """
        return self.universe_manager.get_all_universes()

    def get_active_universe(self):
        """Get the currently active universe.

        Returns:
            Active Universe object or None
        """
        return self.universe_manager.get_active_universe()

    def set_active_universe(self, universe_name: str) -> bool:
        """Set the active universe.

        Args:
            universe_name: Name of universe to activate

        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Setting active universe to: {universe_name}")
        return self.universe_manager.set_active_universe(universe_name)

    # ============================================================================
    # PROVIDER OPERATIONS (INTERNAL CONFIG - NO API)
    # ============================================================================

    def get_all_providers(self):
        """Get all configured providers.

        Returns:
            List of Provider objects
        """
        return self.provider_manager.get_all_providers()

    def get_active_provider(self):
        """Get the currently active provider.

        Returns:
            Active Provider object or None
        """
        return self.provider_manager.get_active_provider()

    def bootstrap_providers(self) -> int:
        """Bootstrap providers into database.

        Currently stores the hardcoded Polygon provider to the database.
        In the future, this could be expanded to support multiple providers
        (YFinance, Alpha Vantage, Finnhub, etc.).

        Returns:
            Number of providers stored successfully
        """
        logger.info("Bootstrapping providers")

        # Get hardcoded Polygon provider from manager
        from database.managers.provider_manager import POLYGON_PROVIDER

        # Store to database
        if self.provider_manager.set_entity_to_database("polygon", POLYGON_PROVIDER):
            # Record the bootstrap operation
            self.provider_manager._record_update()
            logger.info("Bootstrapped 1 provider (Polygon)")
            return 1
        else:
            logger.warning("Failed to bootstrap Polygon provider")
            return 0

    # ============================================================================
    # MARKETS OPERATIONS (INTERNAL CONFIG - NO API)
    # ============================================================================

    def get_all_markets(self, active_only: bool = True) -> List[Market]:
        """Get all markets from database.

        Args:
            active_only: If True, return only active markets

        Returns:
            List of Market objects
        """
        return self.markets_manager.get_all_markets(active_only=active_only)

    def get_market_by_id(self, market_id: int) -> Optional[Market]:
        """Get market by database ID.

        Args:
            market_id: Market database ID

        Returns:
            Market object or None if not found
        """
        return self.markets_manager.get_market_by_id(market_id)

    def bootstrap_markets(self, asset_class: str = "stocks", locale: str = "us") -> int:
        """Bootstrap markets/exchanges from Polygon API.

        Fetches all exchanges from Polygon /v3/reference/exchanges endpoint
        and stores them to the markets table.

        Args:
            asset_class: Asset class to filter (default: "stocks")
            locale: Locale to filter (default: "us")

        Returns:
            Number of markets stored successfully

        Raises:
            RuntimeError: If prerequisites (providers) are not met
        """
        logger.info(
            f"Bootstrapping markets from Polygon (asset_class={asset_class}, locale={locale})"
        )

        # Check prerequisites
        providers = self.get_all_providers()
        if not providers:
            raise RuntimeError(
                "Cannot bootstrap markets: No providers in database. Run 'bootstrap-providers' first."
            )

        # Fetch all markets from Polygon API
        markets = self.polygon_markets_provider.fetch_all_exchanges(
            asset_class=asset_class, locale=locale
        )

        if not markets:
            logger.warning("No markets fetched from Polygon")
            return 0

        # Store each market to database
        stored_count = 0
        for market in markets:
            try:
                if self.markets_manager.set_entity_to_database(market.code, market):
                    stored_count += 1
            except Exception as e:
                logger.warning(f"Failed to store market {market.code}: {e}")
                continue

        # Record the bootstrap operation timestamp
        self.markets_manager._record_update()

        logger.info(f"Bootstrapped {stored_count}/{len(markets)} markets successfully")
        return stored_count

    # ============================================================================
    # MARKET HOLIDAYS OPERATIONS
    # ============================================================================

    def get_market_holidays(self, force_refresh: bool = False) -> List[MarketHoliday]:
        """Get market holidays with automatic cache/refresh logic.

        Holidays are fetched from Polygon's /v1/marketstatus/upcoming endpoint.
        Uses 30-day TTL since holiday calendars are published well in advance.

        Args:
            force_refresh: If True, bypass cache and always fetch fresh data

        Returns:
            List of MarketHoliday objects
        """
        logger.debug(f"Getting market holidays (force_refresh={force_refresh})")

        # Check if we need to refresh (TTL expired or force_refresh)
        if force_refresh or self.market_holidays_manager._is_data_stale():
            logger.debug("Fetching fresh holidays from API")

            # Fetch from Polygon API
            holidays = self.polygon_market_status_provider.fetch_upcoming_holidays()

            if holidays:
                # Store to database
                stored_count = self.market_holidays_manager.store_holidays_bulk(
                    holidays
                )
                logger.info(f"Stored {stored_count} holidays")

                # Record metadata timestamp
                self.market_holidays_manager._record_update()

                return holidays
            else:
                logger.warning("Failed to fetch holidays, returning cached data")
                # Fallback to cached data
                return self.market_holidays_manager.get_all_holidays()
        else:
            # Use cached data
            logger.debug("Using cached holidays")
            return self.market_holidays_manager.get_all_holidays()

    def get_upcoming_holidays(
        self, from_date: Optional[Any] = None
    ) -> List[MarketHoliday]:
        """Get upcoming holidays from a specific date.

        Args:
            from_date: Start date (default: today)

        Returns:
            List of upcoming MarketHoliday objects
        """
        return self.market_holidays_manager.get_upcoming_holidays(from_date)

    # ============================================================================
    # MARKET CONTEXT OPERATIONS
    # ============================================================================

    def get_market_status(self) -> Optional[Dict[str, Any]]:
        """Get current market status from Polygon API.

        Returns:
            Dictionary with market status data including:
            - market: 'open', 'closed', or 'extended-hours'
            - serverTime: Current server time
            - exchanges: Status of different exchanges
            - currencies: Status of currency markets
        """
        try:
            return self.polygon_market_status_provider.fetch_market_status()
        except Exception as e:
            logger.error(f"Error fetching market status: {e}")
            return None

    def get_market_context(
        self, market_code: str = "XNYS", force_refresh: bool = False
    ) -> MarketContext:
        """Get current market context (session, trading day info, etc.).

        Args:
            market_code: Market code (default: XNYS)
            force_refresh: If True, bypass cache

        Returns:
            MarketContext object with session and trading day info
        """
        return self.market_context_service.get_context(market_code, force_refresh)

    # ============================================================================
    # MARKET HOLIDAYS/CONTEXT STATISTICS
    # ============================================================================

    def get_market_holidays_stats(self) -> dict:
        """Get statistics from market holidays manager.

        Returns:
            Dictionary with manager statistics
        """
        return self.market_holidays_manager.get_stats()

    def get_sentiment_events(
        self,
        asset_id: Optional[int] = None,
        sentiment_type_id: Optional[int] = None,
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None,
    ) -> List[SentimentEvent]:
        """Query sentiment events with flexible filtering.

        Args:
            asset_id: Filter by asset ID
            sentiment_type_id: Filter by sentiment type ID
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            List of SentimentEvent objects matching filters
        """
        # Route to appropriate manager method based on filters
        if asset_id:
            return self.sentiment_events_manager.get_events_by_asset(
                asset_id, start_date=start_date, end_date=end_date
            )
        elif sentiment_type_id:
            return self.sentiment_events_manager.get_events_by_type(
                sentiment_type_id, start_date=start_date, end_date=end_date
            )
        elif start_date and end_date:
            return self.sentiment_events_manager.get_events_by_date_range(
                start_date, end_date
            )
        else:
            logger.warning("get_sentiment_events called with no filters")
            return []

    def is_news_stale(self, asset_id: int, ttl_minutes: int = 30) -> bool:
        """Check if news data for an asset is stale (older than TTL).

        Args:
            asset_id: Asset database ID
            ttl_minutes: Time-to-live in minutes (default: 30 from config)

        Returns:
            True if news should be refreshed, False if recent news exists
        """
        last_news_time = self.sentiment_events_manager.get_most_recent_news_timestamp(asset_id)

        if not last_news_time:
            # No news events found - definitely stale
            return True

        # Check if last news is older than TTL
        from datetime import timedelta
        age = datetime.now() - last_news_time
        return age > timedelta(minutes=ttl_minutes)


    # ============================================================================
    # UNIVERSE OPERATIONS (ADDITIONAL METHODS)
    # ============================================================================

    def get_active_universe_symbols(self) -> List[str]:
        """Get all symbols in the active universe.

        Returns:
            List of symbols
        """
        return self.universe_manager.get_active_universe_symbols()

    def is_symbol_in_universe(self, symbol: str, universe_name: str) -> bool:
        """Check if a symbol is in a specific universe.

        Args:
            symbol: Asset symbol to check
            universe_name: Name of universe to check

        Returns:
            True if symbol is in the universe, False otherwise
        """
        return self.universe_manager.is_symbol_in_universe(symbol, universe_name)

    def get_universe_stats(self, name: str) -> Optional["UniverseStats"]:
        """Get statistics for a universe.

        Args:
            name: Universe name

        Returns:
            UniverseStats object or None if not found
        """
        return self.universe_manager.get_universe_stats(name)

    def create_universe(
        self,
        name: str,
        description: Optional[str] = None,
        min_market_cap: Optional[int] = None,
        min_volume: Optional[int] = None,
        max_assets: Optional[int] = None,
    ) -> bool:
        """Create a new universe.

        Args:
            name: Universe name
            description: Optional description
            min_market_cap: Optional minimum market cap filter
            min_volume: Optional minimum volume filter
            max_assets: Optional maximum asset count

        Returns:
            True if created successfully, False otherwise
        """
        # Create Universe model
        universe = Universe(
            id=0,
            name=name,
            description=description or "",
            is_active=False,
            min_market_cap=min_market_cap,
            min_volume=min_volume,
            max_assets=max_assets,
            last_updated=datetime.now(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Delegate to manager
        return self.universe_manager.set_entity_to_database(name, universe)

    def delete_universe(self, name: str) -> Tuple[bool, int]:
        """Delete a universe and all its memberships.

        Args:
            name: Universe name to delete

        Returns:
            Tuple of (success, member_count_deleted)
        """
        return self.universe_manager.delete_universe(name)

    def get_universe_market_breakdown(
        self, universe_name: str
    ) -> List[Tuple[str, str, int]]:
        """Get market breakdown for a universe.

        Args:
            universe_name: Universe name to analyze

        Returns:
            List of tuples (market_code, market_name, asset_count)
        """
        return self.universe_manager.get_market_breakdown(universe_name)

    # ============================================================================
    # MARKET OPERATIONS (ADDITIONAL METHODS)
    # ============================================================================

    def get_market_by_code(self, code: str) -> Optional[Market]:
        """Get market by exchange code.

        Args:
            code: Market code (e.g., 'XNYS', 'XNAS')

        Returns:
            Market object or None if not found
        """
        return self.markets_manager.get_entity_from_database(code)

    def get_active_markets_by_codes(self, codes: List[str]) -> List[Tuple[str, str]]:
        """Get multiple markets by codes, return (code, name) tuples.

        Args:
            codes: List of market codes to filter by

        Returns:
            List of tuples (market_code, market_name)
        """
        return self.markets_manager.get_markets_by_codes(codes)

    def get_current_market_session(self) -> str:
        """Get current market session name.

        Returns:
            Session name: 'premarket', 'regular', 'afterhours', or 'closed'
        """
        try:
            # Fetch market status from Polygon API
            status_data = self.polygon_market_status_provider.fetch_market_status()

            # Parse Polygon market status response
            market = status_data.get("market", "").lower()
            early_hours = status_data.get("earlyHours", False)
            after_hours = status_data.get("afterHours", False)

            # Map Polygon market status to our session names
            if market == "open":
                return "regular"
            elif market == "extended-hours":
                if early_hours:
                    return "premarket"
                elif after_hours:
                    return "afterhours"
                else:
                    return "premarket"  # Default to premarket for extended hours
            elif market == "closed":
                return "closed"
            else:
                raise RuntimeError(f"Unknown market status from Polygon API: {market}")

        except Exception as e:
            logger.error(f"Error getting current market session: {e}")
            raise RuntimeError("Failed to get market session from Polygon API")

    # ============================================================================
    # SCREENER OPERATIONS
    # ============================================================================

    def execute_screener_query(self, sql: str) -> List[Dict[str, Any]]:
        """Execute raw SQL query for screeners.

        Args:
            sql: SQL query to execute

        Returns:
            List of dictionaries representing query results
        """
        if not self.db_manager:
            logger.error("No database manager available")
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)

                # Get column names
                columns = [description[0] for description in cursor.description]

                # Fetch results
                rows = cursor.fetchall()

                # Convert to list of dictionaries
                results = []
                for row in rows:
                    result = dict(zip(columns, row))
                    results.append(result)

                return results

        except Exception as e:
            logger.error(f"Error executing screener query: {e}")
            return []

    # ============================================================================
    # VOLUME VALIDATION OPERATIONS
    # ============================================================================

    def fetch_minute_bars(
        self,
        symbol: str,
        from_datetime: datetime,
        to_datetime: datetime,
        adjusted: bool = True
    ) -> Optional[List[Dict[str, Any]]]:
        """Fetch minute-level bars for a symbol within a time range.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            from_datetime: Start datetime (inclusive)
            to_datetime: End datetime (inclusive)
            adjusted: Whether to return adjusted prices (default: True)

        Returns:
            List of bar dictionaries with fields: o, h, l, c, v, vw, t, n
            Or None if error
        """
        return self.polygon_aggregates_provider.fetch_minute_bars(
            symbol=symbol,
            from_datetime=from_datetime,
            to_datetime=to_datetime,
            adjusted=adjusted
        )

    def calculate_extended_hours_volume(
        self,
        symbol: str,
        trading_date: date,
        session: str = "afterhours"
    ) -> Optional[int]:
        """Calculate total volume for an extended hours session using Aggregates API.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            trading_date: Trading date (not datetime - just the date)
            session: Session type - "premarket" or "afterhours"

        Returns:
            Total volume for the session, or None if error

        Session Times (Eastern Time):
            - premarket: 4:00 AM - 9:30 AM
            - afterhours: 4:00 PM - 8:00 PM
        """
        return self.polygon_aggregates_provider.calculate_extended_hours_volume(
            symbol=symbol,
            trading_date=trading_date,
            session=session
        )

    # ============================================================================
    # NEWS AND SENTIMENT OPERATIONS
    # ============================================================================

    def fetch_news_and_sentiment(
        self, symbol: str, limit: int = 10
    ) -> NewsResult:
        """Fetch news articles and create sentiment events for a symbol.

        This operation:
        1. Gets asset from database
        2. Fetches news from Polygon API
        3. Creates SentimentEvent objects (with article details in JSON field)
        4. Stores SentimentEvent records
        5. Returns NewsResult with sentiment events and stats

        Args:
            symbol: Stock ticker symbol
            limit: Maximum number of articles to fetch

        Returns:
            NewsResult object with sentiment events and stats
        """
        symbol = symbol.upper()
        start_time = datetime.now()

        # Initialize result tracking
        sentiment_events: List[SentimentEvent] = []
        sentiment_events_created = 0
        sentiment_events_stored = 0
        sentiment_events_duplicates = 0
        errors = []

        try:
            # 1. Get asset from database
            asset = self.asset_manager.get_entity_from_database(symbol)
            if not asset:
                errors.append(f"Asset {symbol} not found in database")
                return NewsResult(
                    symbol=symbol,
                    source="api",
                    articles_found=0,
                    sentiment_events_created=0,
                    sentiment_events_stored=0,
                    sentiment_events_duplicates=0,
                    sentiment_events=[],
                    errors=errors,
                )

            # 2. Fetch news from Polygon
            logger.info(f"Fetching news for {symbol} (limit={limit})")
            raw_articles = self.polygon_news_provider.fetch_news_for_ticker(
                symbol, limit=limit
            )

            if raw_articles is None:
                errors.append("Failed to fetch news from Polygon API")
                return NewsResult(
                    symbol=symbol,
                    source="api",
                    articles_found=0,
                    sentiment_events_created=0,
                    sentiment_events_stored=0,
                    sentiment_events_duplicates=0,
                    sentiment_events=[],
                    errors=errors,
                )

            # 3. Transform raw articles into NewsArticle objects and create sentiment events
            for raw_article in raw_articles:
                try:
                    # Debug: Log raw insights to see what Polygon returns
                    if raw_article.get("insights"):
                        logger.debug(f"Raw insights for article: {raw_article.get('insights')}")

                    # Extract sentiment data for this ticker
                    sentiment_data = self.polygon_news_provider.extract_sentiment_from_article(
                        raw_article, symbol
                    )

                    if sentiment_data:
                        logger.debug(f"Extracted sentiment data: {sentiment_data}")

                    # Parse published timestamp
                    published_utc = raw_article.get("published_utc", "")
                    try:
                        published_dt = datetime.fromisoformat(
                            published_utc.replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        logger.warning(f"Could not parse published date: {published_utc}")
                        continue

                    # Determine sentiment type based on sentiment value
                    sentiment_value = sentiment_data.get("sentiment", "neutral") if sentiment_data else "neutral"
                    if sentiment_value == "positive":
                        sentiment_type_name = "news_positive"
                    elif sentiment_value == "negative":
                        sentiment_type_name = "news_negative"
                    elif sentiment_value == "mixed":
                        sentiment_type_name = "news_mixed"
                    else:
                        sentiment_type_name = "news_neutral"

                    # Get or create sentiment type
                    sentiment_type = self._get_or_create_sentiment_type(
                        sentiment_type_name, "news"
                    )
                    if not sentiment_type:
                        errors.append(f"Could not get sentiment type: {sentiment_type_name}")
                        continue

                    # Determine magnitude based on sentiment reasoning (since no numeric score)
                    # Default to medium unless we have indicators otherwise
                    magnitude = "medium"

                    # Create SentimentEvent object with article details in JSON
                    sentiment_event = SentimentEvent(
                        id=0,  # Will be assigned by database
                        asset_id=asset.id,
                        sentiment_type_id=sentiment_type.id,
                        event_date=published_dt.date(),
                        event_time=published_dt.time(),
                        session=None,  # News doesn't map to trading session
                        value=Decimal("0.0"),  # No numeric score from Polygon
                        magnitude=magnitude,
                        details={
                            "article_id": raw_article.get("id", ""),
                            "title": raw_article.get("title", "No title"),
                            "author": raw_article.get("author"),
                            "article_url": raw_article.get("article_url", ""),
                            "publisher_name": raw_article.get("publisher", {}).get("name", "Unknown"),
                            "publisher_homepage_url": raw_article.get("publisher", {}).get("homepage_url"),
                            "description": raw_article.get("description"),
                            "ticker": symbol,
                            "sentiment": sentiment_value,
                            "sentiment_reasoning": sentiment_data.get("reasoning", "") if sentiment_data else "",
                        },
                        created_at=datetime.now(),
                    )

                    sentiment_events_created += 1
                    sentiment_events.append(sentiment_event)

                    # Store sentiment event
                    success = self.sentiment_events_manager.set_entity_to_database(
                        str(sentiment_event.id), sentiment_event
                    )
                    if success:
                        sentiment_events_stored += 1
                    else:
                        # Not stored - likely a duplicate (unique constraint)
                        sentiment_events_duplicates += 1
                        logger.debug(f"Sentiment event duplicate skipped: {sentiment_event.get_detail('title', 'unknown')}")

                except Exception as e:
                    logger.error(f"Error processing article sentiment: {e}")
                    errors.append(f"Error processing article: {str(e)}")
                    continue

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"News fetch complete: {len(sentiment_events)} articles, "
                f"{sentiment_events_created} sentiment events created, "
                f"{sentiment_events_stored} stored ({duration:.2f}s)"
            )

            return NewsResult(
                symbol=symbol,
                source="api",
                articles_found=len(sentiment_events),
                sentiment_events_created=sentiment_events_created,
                sentiment_events_stored=sentiment_events_stored,
                sentiment_events_duplicates=sentiment_events_duplicates,
                sentiment_events=sentiment_events,
                errors=errors,
            )

        except Exception as e:
            logger.error(f"Error in fetch_news_and_sentiment: {e}")
            errors.append(f"Unexpected error: {str(e)}")
            return NewsResult(
                symbol=symbol,
                source="api",
                articles_found=len(sentiment_events),
                sentiment_events_created=sentiment_events_created,
                sentiment_events_stored=sentiment_events_stored,
                sentiment_events_duplicates=sentiment_events_duplicates,
                sentiment_events=sentiment_events,
                errors=errors,
            )

    def calculate_asset_sentiment(self, symbol: str, limit: int, time_window_days: int):
        """Calculate overall sentiment score for an asset from recent news events.

        Args:
            symbol: Stock ticker symbol
            limit: Maximum number of recent events to analyze
            time_window_days: Only analyze events within this many days

        Returns:
            SentimentScore object or None if no events found
        """
        from analysis.sentiment_analyzer import SentimentAnalyzer
        from datetime import date, timedelta

        symbol = symbol.upper()

        # Get asset from database
        asset = self.asset_manager.get_entity_from_database(symbol)
        if not asset:
            logger.warning(f"Asset {symbol} not found in database")
            return None

        # Get recent sentiment events from database
        start_date = date.today() - timedelta(days=time_window_days)
        all_events = self.sentiment_events_manager.get_events_by_asset(
            asset.id, start_date=start_date
        )

        # Limit to most recent events
        recent_events = all_events[:limit] if all_events else []

        if not recent_events:
            logger.debug(f"No sentiment events found for {symbol} in last {time_window_days} days")
            return None

        # Calculate sentiment score
        analyzer = SentimentAnalyzer(time_window_days=time_window_days)
        score = analyzer.calculate_sentiment_score(symbol, recent_events)

        return score

    def _get_or_create_sentiment_type(
        self, name: str, category: str
    ) -> Optional[SentimentType]:
        """Get existing sentiment type or create if doesn't exist.

        Args:
            name: Sentiment type name (e.g., "news_positive")
            category: Category (e.g., "news")

        Returns:
            SentimentType object or None
        """
        # Try to get existing type
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, description, category, parameters, created_at, is_active "
                "FROM sentiment_types WHERE name = ?",
                (name,),
            )
            row = cursor.fetchone()

            if row:
                # Parse existing type
                import json

                return SentimentType(
                    id=row[0],
                    name=row[1],
                    description=row[2],
                    category=row[3],
                    parameters=json.loads(row[4]) if row[4] else {},
                    created_at=datetime.fromisoformat(row[5]),
                    is_active=bool(row[6]),
                )

            # Create new type
            description = f"{category.title()} {name.split('_')[-1]} sentiment"
            cursor.execute(
                """INSERT INTO sentiment_types (name, description, category, parameters, is_active)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, description, category, "{}", True),
            )
            conn.commit()

            # Get the created type
            type_id = cursor.lastrowid
            return SentimentType(
                id=type_id,
                name=name,
                description=description,
                category=category,
                parameters={},
                created_at=datetime.now(),
                is_active=True,
            )

    # ============================================================================
    # DATABASE STATISTICS (Cross-cutting concern)
    # ============================================================================

    def get_database_stats(self) -> Optional["DatabaseStats"]:
        """Get database statistics and health information.

        This is a cross-cutting concern that aggregates data from multiple managers.
        """
        if not self.db_manager:
            return None

        try:
            from models.database_stats import DatabaseStats

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get table counts
                table_counts = {}
                tables = [
                    "assets",
                    "markets",
                    "asset_prices",
                    "universes",
                    "universe_memberships",
                    "fundamentals",
                    "data_update_metadata",
                ]

                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    table_counts[table] = cursor.fetchone()[0]

                # Get latest updates
                cursor.execute(
                    """
                    SELECT operation_type, MAX(last_update) as latest
                    FROM data_update_metadata
                    GROUP BY operation_type
                """
                )
                latest_updates = {row[0]: row[1] for row in cursor.fetchall()}

                # Get database file size
                cursor.execute(
                    "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"
                )
                db_size_bytes = cursor.fetchone()[0]

                return DatabaseStats(
                    table_counts=table_counts,
                    latest_updates=latest_updates,
                    database_size_bytes=db_size_bytes,
                    database_path=self.db_manager.db_path,
                )

        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return None

    # ============================================================================
    # PROVIDER HEALTH & INFO
    # ============================================================================

    def check_api_health(self) -> bool:
        """Check if API providers are accessible.

        Returns:
            True if all providers are healthy, False otherwise
        """
        try:
            polygon_healthy = self.polygon_snapshot_provider.health_check()
            logger.debug(f"Polygon API health: {polygon_healthy}")
            return polygon_healthy
        except Exception as e:
            logger.error(f"API health check failed: {e}")
            return False

    def get_provider_info(self) -> dict:
        """Get information about configured providers.

        Returns:
            Dictionary with provider information
        """
        return {"polygon_snapshot": self.polygon_snapshot_provider.get_provider_info()}

    # ============================================================================
    # MANAGER STATISTICS
    # ============================================================================

    def get_ticker_snapshot_stats(self) -> dict:
        """Get statistics from ticker snapshot manager.

        Returns:
            Dictionary with manager statistics
        """
        return self.ticker_snapshot_manager.get_stats()

    def get_market_snapshot_stats(self) -> dict:
        """Get statistics from market snapshot manager.

        Returns:
            Dictionary with manager statistics
        """
        return self.market_snapshot_manager.get_stats()

    def get_asset_stats(self) -> dict:
        """Get statistics from asset manager.

        Returns:
            Dictionary with manager statistics
        """
        return self.asset_manager.get_stats()

    def get_provider_stats(self) -> dict:
        """Get statistics from provider manager.

        Returns:
            Dictionary with manager statistics
        """
        return self.provider_manager.get_stats()

    def get_fundamentals_stats(self) -> dict:
        """Get statistics from fundamentals manager.

        Returns:
            Dictionary with manager statistics
        """
        return self.fundamentals_manager.get_stats()

    def get_markets_stats(self) -> dict:
        """Get statistics from markets manager.

        Returns:
            Dictionary with manager statistics
        """
        return self.markets_manager.get_stats()

    def get_sentiment_types_stats(self) -> dict:
        """Get statistics from sentiment types manager.

        Returns:
            Dictionary with manager statistics
        """
        return self.sentiment_types_manager.get_stats()

    def get_sentiment_events_stats(self) -> dict:
        """Get statistics from sentiment events manager.

        Returns:
            Dictionary with manager statistics
        """
        return self.sentiment_events_manager.get_stats()
