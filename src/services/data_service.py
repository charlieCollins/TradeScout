"""Data service orchestration layer.

Wires together database managers (storage/TTL) and API providers (external calls).
Provides clean interface for business logic to access data.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from api.providers import (
    PolygonMarketsProvider,
    PolygonMarketStatusProvider,
    PolygonNewsProvider,
    PolygonSnapshotProvider,
    PolygonTickersProvider,
)
from config.universe_config import UNIVERSE_CONFIG
from database.managers import (
    AssetManager,
    AssetPriceManager,
    DataUpdateMetadataManager,
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
from models.sentiment_event import SentimentEvent
from models.sentiment_type import SentimentType
from models.snapshot import MarketSnapshot, TickerSnapshot
from models.universe import Universe

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

        # Initialize API providers
        self.polygon_snapshot_provider = PolygonSnapshotProvider(polygon_api_key)
        self.polygon_tickers_provider = PolygonTickersProvider(polygon_api_key)
        self.polygon_markets_provider = PolygonMarketsProvider(polygon_api_key)
        self.polygon_market_status_provider = PolygonMarketStatusProvider(
            polygon_api_key
        )
        self.polygon_news_provider = PolygonNewsProvider(polygon_api_key)

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
    ) -> tuple[int, int]:
        """Batch save asset price data to database.

        Args:
            asset_prices: List of AssetPrice objects to save

        Returns:
            Tuple of (successful_count, failed_count)
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

        # Use get_or_fetch pattern with PolygonTickersProvider
        return self.asset_manager.get_or_fetch(
            key=symbol,
            fetch_fn=lambda: self.polygon_tickers_provider.fetch_ticker_details(symbol),
            force_refresh=force_refresh,
        )

    def bootstrap_assets(self, market: str = "stocks", active: bool = True) -> int:
        """Bootstrap all assets from Polygon tickers API.

        Fetches all tickers from Polygon and stores them as assets in database.
        This is a bulk operation that should be run periodically (every 3 days per TTL).

        Args:
            market: Market type (default: "stocks")
            active: Only fetch active tickers (default: True)

        Returns:
            Number of assets stored

        Raises:
            RuntimeError: If prerequisites (providers, markets) are not met
        """
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
            return 0

        # Bulk insert assets to database in batches with progress bar
        import logging

        from rich.console import Console
        from rich.progress import (
            BarColumn,
            Progress,
            SpinnerColumn,
            TextColumn,
            TimeElapsedColumn,
        )

        batch_size = 1000
        stored_count = 0
        failed_count = 0
        total = len(assets)

        # Temporarily suppress all logging during progress bar
        original_levels = {}
        for name in logging.root.manager.loggerDict:
            log = logging.getLogger(name)
            if log.level != logging.NOTSET:
                original_levels[name] = log.level
                log.setLevel(logging.CRITICAL)

        root_logger = logging.getLogger()
        original_root_level = root_logger.level
        root_logger.setLevel(logging.CRITICAL)

        console = Console()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TextColumn("{task.completed}/{task.total}"),
            TextColumn("•"),
            TextColumn("[green]✓ {task.fields[stored]}[/green]"),
            TextColumn("•"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"Storing assets", total=total, stored=0)

            for i in range(0, total, batch_size):
                batch = assets[i : i + batch_size]
                batch_stored = self.asset_manager.bulk_insert_assets(batch)
                stored_count += batch_stored
                failed_count += len(batch) - batch_stored

                progress.update(task, advance=len(batch), stored=stored_count)

        # Restore original log levels
        root_logger.setLevel(original_root_level)
        for name, level in original_levels.items():
            logging.getLogger(name).setLevel(level)

        # Display summary
        console.print(f"\n✅ Successfully stored {stored_count}/{total} assets")
        if failed_count > 0:
            console.print(f"⚠️  Failed: {failed_count} assets")

        # Record the bootstrap operation timestamp
        self.asset_manager._record_update()

        logger.info(f"Bootstrapped {stored_count}/{len(assets)} assets successfully")
        return stored_count

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

    def bootstrap_fundamentals(self, limit: Optional[int] = None) -> int:
        """Bootstrap fundamentals for all assets in database.

        This is a bulk operation that:
        1. Gets all assets from database
        2. For each asset, fetches ticker details from Polygon
        3. Extracts and stores fundamentals data

        Note: This can be expensive with many assets. Use limit to process in batches.

        Args:
            limit: Optional limit on number of assets to process

        Returns:
            Number of fundamentals stored successfully

        Raises:
            RuntimeError: If prerequisites (assets) are not met
        """
        logger.info(f"Bootstrapping fundamentals (limit={limit})")

        # Get all assets from database via AssetManager
        assets = self.asset_manager.get_all_active_asset_ids(limit=limit)

        if not assets:
            raise RuntimeError(
                "Cannot bootstrap fundamentals: No assets in database. Run 'bootstrap-tickers' first."
            )

        logger.info(f"Fetching fundamentals for {len(assets)} assets")

        # Setup progress display
        import logging

        from rich.console import Console
        from rich.live import Live
        from rich.progress import (
            BarColumn,
            Progress,
            SpinnerColumn,
            TextColumn,
            TimeElapsedColumn,
        )
        from rich.table import Table

        # Temporarily suppress all logging during progress bar
        original_levels = {}
        for name in logging.root.manager.loggerDict:
            log = logging.getLogger(name)
            if log.level != logging.NOTSET:
                original_levels[name] = log.level
                log.setLevel(logging.CRITICAL)

        root_logger = logging.getLogger()
        original_root_level = root_logger.level
        root_logger.setLevel(logging.CRITICAL)

        console = Console()

        # Phase 1: Fetch ALL fundamentals from API (network calls only)
        fundamentals_data = {}  # {asset_id: AssetFundamentals object}
        fetch_errors = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TextColumn("{task.completed}/{task.total}"),
            TextColumn("•"),
            TextColumn("[red]✗ {task.fields[errors]}[/red]"),
            TextColumn("•"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            fetch_task = progress.add_task(
                "[cyan]Fetching from API", total=len(assets), errors=0
            )

            for asset_id, symbol in assets:
                try:
                    fundamentals = self._fetch_fundamentals_for_symbol(symbol, asset_id)
                    if fundamentals:
                        fundamentals_data[asset_id] = fundamentals
                    else:
                        fetch_errors.append(f"{symbol}: No data returned")
                except Exception as e:
                    fetch_errors.append(f"{symbol}: {str(e)}")

                progress.update(fetch_task, advance=1, errors=len(fetch_errors))

        console.print(
            f"✓ Fetched {len(fundamentals_data)}/{len(assets)} fundamentals from API"
        )

        # Phase 2: Batch insert to database
        stored_count = 0
        insert_errors = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TextColumn("{task.completed}/{task.total}"),
            TextColumn("•"),
            TextColumn("[red]✗ {task.fields[errors]}[/red]"),
            TextColumn("•"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            insert_task = progress.add_task(
                "[green]Writing to database", total=len(fundamentals_data), errors=0
            )

            for asset_id, fundamentals in fundamentals_data.items():
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

                progress.update(insert_task, advance=1, errors=len(insert_errors))

        # Restore original log levels
        root_logger.setLevel(original_root_level)
        for name, level in original_levels.items():
            logging.getLogger(name).setLevel(level)

        # Display final summary
        total_errors = len(fetch_errors) + len(insert_errors)
        console.print(f"\n[bold green]✅ Bootstrap Complete[/]")
        console.print(
            f"  • API Fetches: {len(fundamentals_data)}/{len(assets)} succeeded"
        )
        console.print(
            f"  • Database Inserts: {stored_count}/{len(fundamentals_data)} succeeded"
        )
        console.print(f"  • Total Errors: {total_errors}")

        if fetch_errors:
            console.print(f"\n[yellow]⚠️  API Fetch Errors ({len(fetch_errors)}):[/]")
            for error in fetch_errors[:10]:
                console.print(f"  • {error}")
            if len(fetch_errors) > 10:
                console.print(f"  • ... and {len(fetch_errors) - 10} more")

        if insert_errors:
            console.print(
                f"\n[yellow]⚠️  Database Insert Errors ({len(insert_errors)}):[/]"
            )
            for error in insert_errors[:10]:
                console.print(f"  • {error}")
            if len(insert_errors) > 10:
                console.print(f"  • ... and {len(insert_errors) - 10} more")

        # Record the bootstrap operation timestamp
        self.fundamentals_manager._record_update()

        logger.info(
            f"Bootstrapped {stored_count}/{len(assets)} fundamentals successfully ({total_errors} errors total)"
        )
        return stored_count

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
        config = UNIVERSE_CONFIG.get(universe_name)
        if not config:
            raise ValueError(
                f"Unknown universe: {universe_name}. Available: {list(UNIVERSE_CONFIG.keys())}"
            )

        # Check prerequisites - need assets in database to filter
        asset_stats = self.asset_manager.get_stats()
        if asset_stats.get("total_active_assets", 0) == 0:
            raise RuntimeError(
                "Cannot bootstrap universes: No assets in database. Run 'bootstrap-tickers' first."
            )

        # Check TTL unless forced
        if not force_refresh and not self.universe_manager._is_data_stale():
            logger.info(
                f"Universe data is fresh, skipping bootstrap. Use force_refresh=True to override."
            )
            # Return stats from existing universe
            memberships = self.universe_manager.get_universe_memberships(universe_name)
            return {
                "total_assets": 0,
                "filtered_assets": len(memberships),
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


    # ============================================================================
    # UNIVERSE OPERATIONS (ADDITIONAL METHODS)
    # ============================================================================

    def get_active_universe_symbols(self) -> List[str]:
        """Get all symbols in the active universe.

        Returns:
            List of symbols
        """
        return self.universe_manager.get_active_universe_symbols()

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
