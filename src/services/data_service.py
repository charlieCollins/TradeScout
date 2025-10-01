"""Data service orchestration layer.

Wires together database managers (storage/TTL) and API providers (external calls).
Provides clean interface for business logic to access data.
"""

import logging
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from models.snapshot import TickerSnapshot, MarketSnapshot
from models.asset import Asset
from models.fundamentals import AssetFundamentals
from models.market import Market
from models.universe import Universe
from models.sentiment_type import SentimentType
from models.sentiment_event import SentimentEvent
from config.universe_config import UNIVERSE_CONFIG
from database.managers import (
    TickerSnapshotManager,
    MarketSnapshotManager,
    AssetManager,
    UniverseManager,
    ProviderManager,
    FundamentalsManager,
    MarketsManager,
    DataUpdateMetadataManager,
    SentimentTypesManager,
    SentimentEventsManager
)
from api.provider import PolygonSnapshotProvider, PolygonTickersProvider, PolygonMarketsProvider

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

    def __init__(self, db_manager, update_tracker, polygon_api_key: str):
        """Initialize data service with dependencies.

        Args:
            db_manager: Database manager for SQLite operations
            update_tracker: Data update tracker for TTL validation
            polygon_api_key: Polygon API key for API provider
        """
        self.db_manager = db_manager
        self.update_tracker = update_tracker

        # Initialize metadata manager for TTL tracking
        self.metadata_manager = DataUpdateMetadataManager(db_manager)

        # Initialize database managers (with metadata manager for recording updates)
        self.ticker_snapshot_manager = TickerSnapshotManager(
            db_manager,
            update_tracker,
            self.metadata_manager
        )
        self.market_snapshot_manager = MarketSnapshotManager(
            db_manager,
            update_tracker,
            self.metadata_manager
        )
        self.asset_manager = AssetManager(
            db_manager,
            update_tracker,
            self.metadata_manager
        )
        self.universe_manager = UniverseManager(
            db_manager,
            update_tracker,
            self.metadata_manager
        )
        self.provider_manager = ProviderManager(
            db_manager,
            update_tracker,
            self.metadata_manager
        )
        self.fundamentals_manager = FundamentalsManager(
            db_manager,
            update_tracker,
            self.metadata_manager
        )
        self.markets_manager = MarketsManager(
            db_manager,
            update_tracker,
            self.metadata_manager
        )

        # Initialize sentiment managers (no metadata tracking - see docs/DATA_UPDATE_METADATA.md)
        self.sentiment_types_manager = SentimentTypesManager(
            db_manager,
            None,  # No update_tracker needed
            None   # No metadata_manager needed
        )
        self.sentiment_events_manager = SentimentEventsManager(
            db_manager,
            None,  # No update_tracker needed
            None   # No metadata_manager needed
        )

        # Initialize API providers
        self.polygon_snapshot_provider = PolygonSnapshotProvider(polygon_api_key)
        self.polygon_tickers_provider = PolygonTickersProvider(polygon_api_key)
        self.polygon_markets_provider = PolygonMarketsProvider(polygon_api_key)

        logger.debug("DataService initialized with managers and providers")

    # ============================================================================
    # TICKER SNAPSHOT OPERATIONS
    # ============================================================================

    def get_ticker_snapshot(
        self,
        symbol: str,
        force_refresh: bool = False
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
        logger.debug(f"Getting ticker snapshot for {symbol} (force_refresh={force_refresh})")

        # The manager handles all the logic:
        # - Check TTL (unless force_refresh)
        # - Decide whether to fetch or use cached
        # - Store fresh data if fetched
        # We just provide the API fetch function
        return self.ticker_snapshot_manager.get_or_fetch(
            key=symbol,
            fetch_fn=lambda: self.polygon_snapshot_provider.fetch_single_ticker_snapshot(symbol),
            force_refresh=force_refresh
        )

    # ============================================================================
    # MARKET SNAPSHOT OPERATIONS (BULK REFRESH)
    # ============================================================================

    def refresh_market_data(
        self,
        symbols: Optional[List[str]] = None,
        force_refresh: bool = False
    ) -> Optional[MarketSnapshot]:
        """Refresh market data via bulk snapshot API call.

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
            f"Refreshing market data for {len(symbols) if symbols else 'all'} symbols "
            f"(force_refresh={force_refresh})"
        )

        # The manager handles TTL logic and decides whether to fetch
        market_snapshot = self.market_snapshot_manager.get_or_fetch(
            key=cache_key,
            fetch_fn=lambda: self.polygon_snapshot_provider.fetch_bulk_market_snapshot(symbols),
            force_refresh=force_refresh
        )

        # Store individual tickers from the bulk fetch to asset_prices table
        if market_snapshot and self.market_snapshot_manager.should_store_individual_tickers(market_snapshot):
            self._store_individual_tickers_from_market_snapshot(market_snapshot)

        return market_snapshot

    def _store_individual_tickers_from_market_snapshot(self, market_snapshot: MarketSnapshot) -> None:
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
                success = self.ticker_snapshot_manager.set_entity_to_database(symbol, ticker_snapshot)
                if success:
                    stored_count += 1
            except Exception as e:
                logger.warning(f"Failed to store ticker {symbol} from market snapshot: {e}")

        logger.debug(f"Stored {stored_count}/{len(market_snapshot.tickers)} individual tickers from market snapshot")

    # ============================================================================
    # ASSET OPERATIONS (REFERENCE DATA)
    # ============================================================================

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
            force_refresh=force_refresh
        )

    def bootstrap_assets(
        self,
        market: str = "stocks",
        active: bool = True
    ) -> int:
        """Bootstrap all assets from Polygon tickers API.

        Fetches all tickers from Polygon and stores them as assets in database.
        This is a bulk operation that should be run periodically (every 3 days per TTL).

        Args:
            market: Market type (default: "stocks")
            active: Only fetch active tickers (default: True)

        Returns:
            Number of assets stored
        """
        logger.info(f"Bootstrapping assets from Polygon (market={market}, active={active})")

        # Fetch all tickers from API
        assets = self.polygon_tickers_provider.fetch_all_tickers(market=market, active=active)

        if not assets:
            logger.warning("No assets fetched from Polygon")
            return 0

        # Store each asset to database
        stored_count = 0
        for asset in assets:
            try:
                if self.asset_manager.set_entity_to_database(asset.symbol, asset):
                    stored_count += 1
            except Exception as e:
                logger.warning(f"Failed to store asset {asset.symbol}: {e}")
                continue

        # Record the bootstrap operation timestamp
        self.asset_manager._record_update()

        logger.info(f"Bootstrapped {stored_count}/{len(assets)} assets successfully")
        return stored_count

    # ============================================================================
    # FUNDAMENTALS OPERATIONS
    # ============================================================================

    def get_fundamentals(
        self,
        symbol: str,
        force_refresh: bool = False
    ) -> Optional[AssetFundamentals]:
        """Get asset fundamentals with automatic cache/refresh logic.

        Fundamentals are company data (market cap, sector, industry, etc.) that
        change infrequently. Uses 1-week TTL for refresh checks.

        This method:
        1. Looks up asset_id from symbol (via assets table)
        2. Checks if fundamentals are cached and fresh (TTL check)
        3. Fetches from Polygon tickers API if stale or forced
        4. Stores to database and returns AssetFundamentals

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            force_refresh: If True, bypass cache and always fetch fresh data

        Returns:
            AssetFundamentals object or None if not found
        """
        logger.debug(f"Getting fundamentals for {symbol} (force_refresh={force_refresh})")

        # First, get the asset to get its asset_id
        # We need asset_id to store fundamentals (foreign key constraint)
        asset = self.asset_manager.get_entity_from_database(symbol)
        if not asset:
            # Asset not in database - fetch it first
            logger.debug(f"Asset {symbol} not found, fetching asset first")
            asset = self.get_asset(symbol)
            if not asset:
                logger.warning(f"Cannot get fundamentals for {symbol}: asset not found")
                return None

        asset_id = asset.id

        # Use get_or_fetch pattern with asset_id as key
        return self.fundamentals_manager.get_or_fetch(
            key=str(asset_id),
            fetch_fn=lambda: self._fetch_fundamentals_for_symbol(symbol, asset_id),
            force_refresh=force_refresh
        )

    def _fetch_fundamentals_for_symbol(
        self,
        symbol: str,
        asset_id: int
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
                polygon_data=ticker_data
            )
            logger.debug(f"Successfully parsed fundamentals for {symbol}")
            return fundamentals
        except Exception as e:
            logger.error(f"Error parsing fundamentals for {symbol}: {e}")
            return None

    def bootstrap_fundamentals(
        self,
        limit: Optional[int] = None
    ) -> int:
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
        """
        logger.info(f"Bootstrapping fundamentals (limit={limit})")

        # Get all assets from database
        # We'll query directly rather than using AssetManager to get all symbols
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT id, symbol FROM assets WHERE is_active = 1"
                if limit:
                    query += f" LIMIT {limit}"

                cursor.execute(query)
                assets = cursor.fetchall()

        except Exception as e:
            logger.error(f"Error fetching assets from database: {e}")
            return 0

        if not assets:
            logger.warning("No assets found in database")
            return 0

        logger.info(f"Fetching fundamentals for {len(assets)} assets")

        # Fetch and store fundamentals for each asset
        stored_count = 0
        for asset_id, symbol in assets:
            try:
                # Fetch fundamentals (bypasses cache to force fresh fetch during bootstrap)
                fundamentals = self._fetch_fundamentals_for_symbol(symbol, asset_id)
                if fundamentals:
                    # Store to database
                    if self.fundamentals_manager.set_entity_to_database(str(asset_id), fundamentals):
                        stored_count += 1
                        if stored_count % 100 == 0:
                            logger.info(f"Bootstrapped {stored_count}/{len(assets)} fundamentals...")
            except Exception as e:
                logger.warning(f"Failed to fetch fundamentals for {symbol}: {e}")
                continue

        # Record the bootstrap operation timestamp
        self.fundamentals_manager._record_update()

        logger.info(f"Bootstrapped {stored_count}/{len(assets)} fundamentals successfully")
        return stored_count

    # ============================================================================
    # UNIVERSE OPERATIONS (INTERNAL ONLY - NO API)
    # ============================================================================

    def bootstrap_universes(
        self,
        universe_name: str = "default_universe",
        force_refresh: bool = False
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
        """
        logger.info(f"Bootstrapping universe: {universe_name}")

        # Get universe configuration
        config = UNIVERSE_CONFIG.get(universe_name)
        if not config:
            raise ValueError(f"Unknown universe: {universe_name}. Available: {list(UNIVERSE_CONFIG.keys())}")

        # Check TTL unless forced
        if not force_refresh and not self.universe_manager._is_data_stale():
            logger.info(f"Universe data is fresh, skipping bootstrap. Use force_refresh=True to override.")
            # Return stats from existing universe
            memberships = self.universe_manager.get_universe_memberships(universe_name)
            return {
                "total_assets": 0,
                "filtered_assets": len(memberships),
                "memberships_added": 0,
                "skipped": True
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
            updated_at=datetime.now()
        )

        if not self.universe_manager.set_entity_to_database(universe_name, universe):
            raise RuntimeError(f"Failed to create/update universe: {universe_name}")

        # Clear old memberships
        self.universe_manager.clear_universe_memberships(universe_name)

        # Add new memberships (extract asset_ids from filtered assets)
        asset_ids = [asset["id"] for asset in filtered_assets]
        memberships_added = self.universe_manager.add_universe_memberships(universe_name, asset_ids)

        # Record metadata timestamp
        self.universe_manager._record_update()

        stats = {
            "total_assets": len(all_assets),
            "filtered_assets": len(filtered_assets),
            "memberships_added": memberships_added
        }

        logger.info(f"Universe '{universe_name}' bootstrapped: {stats}")
        return stats

    def _fetch_assets_with_fundamentals(self) -> List[Dict[str, Any]]:
        """Fetch all assets with their fundamentals and market data.

        Returns:
            List of dicts with keys: id, symbol, name, asset_type, market_code,
                                     is_active, sector, market_cap, volume
        """
        if not self.db_manager:
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Join assets + fundamentals + markets to get complete data for filtering
                query = """
                    SELECT
                        a.id,
                        a.symbol,
                        a.name,
                        a.asset_type,
                        m.code as market_code,
                        a.is_active,
                        f.sector,
                        f.market_cap,
                        f.avg_volume_30d as volume
                    FROM assets a
                    LEFT JOIN markets m ON a.market_id = m.id
                    LEFT JOIN asset_fundamentals f ON a.id = f.asset_id
                    WHERE a.is_active = 1
                    ORDER BY a.symbol
                """

                cursor.execute(query)
                rows = cursor.fetchall()

                # Convert to list of dicts
                assets = []
                for row in rows:
                    assets.append({
                        "id": row[0],
                        "symbol": row[1],
                        "name": row[2],
                        "asset_type": row[3],
                        "market_code": row[4],
                        "is_active": bool(row[5]),
                        "sector": row[6],
                        "market_cap": row[7],
                        "volume": row[8]
                    })

                return assets

        except Exception as e:
            logger.error(f"Error fetching assets with fundamentals: {e}")
            return []

    def _apply_universe_filters(
        self,
        assets: List[Dict[str, Any]],
        config: Dict[str, Any]
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
        self,
        asset: Dict[str, Any],
        included: Dict[str, Any],
        excluded: Dict[str, Any]
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
        self,
        asset: Dict[str, Any],
        criteria: Dict[str, Any]
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
            type_mapping = {
                "stock": "CS",
                "etf": "ETF",
                "reit": "REIT"
            }
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
        self,
        asset: Dict[str, Any],
        criteria: Dict[str, Any]
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

    def get_universe(self, universe_name: str):
        """Get universe by name.

        Note: Universes are internal-only entities with no external API.

        Args:
            universe_name: Name of universe (e.g., 'default_universe')

        Returns:
            Universe object or None if not found
        """
        logger.debug(f"Getting universe: {universe_name}")
        return self.universe_manager.get_entity_from_database(universe_name)

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

    def get_provider(self, provider_name: str):
        """Get provider by name.

        Note: Providers are internal configuration with no external API.

        Args:
            provider_name: Name of provider (e.g., 'polygon')

        Returns:
            Provider object or None if not found
        """
        logger.debug(f"Getting provider: {provider_name}")
        return self.provider_manager.get_entity_from_database(provider_name)

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

    def get_market(self, market_code: str) -> Optional[Market]:
        """Get market by code.

        Note: Markets are internal configuration with no external API.

        Args:
            market_code: Market code (e.g., 'XNYS', 'XNAS')

        Returns:
            Market object or None if not found
        """
        logger.debug(f"Getting market: {market_code}")
        return self.markets_manager.get_entity_from_database(market_code)

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

    def bootstrap_markets(
        self,
        asset_class: str = "stocks",
        locale: str = "us"
    ) -> int:
        """Bootstrap markets/exchanges from Polygon API.

        Fetches all exchanges from Polygon /v3/reference/exchanges endpoint
        and stores them to the markets table.

        Args:
            asset_class: Asset class to filter (default: "stocks")
            locale: Locale to filter (default: "us")

        Returns:
            Number of markets stored successfully
        """
        logger.info(f"Bootstrapping markets from Polygon (asset_class={asset_class}, locale={locale})")

        # Fetch all markets from Polygon API
        markets = self.polygon_markets_provider.fetch_all_exchanges(
            asset_class=asset_class,
            locale=locale
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

    def bootstrap_sentiment_types(self) -> int:
        """Bootstrap predefined sentiment types to database.

        Creates hardcoded sentiment type definitions (news_positive, news_negative, etc.)
        No API fetch needed - this is static configuration data.

        Returns:
            Number of sentiment types created
        """
        from datetime import datetime

        logger.info("Bootstrapping predefined sentiment types")

        # Define predefined sentiment types
        # Phase 1: News sentiment only
        predefined_types = [
            SentimentType(
                id=0,  # Will be auto-assigned by database
                name="news_positive",
                description="Positive news sentiment from articles",
                category="news",
                parameters={"min_confidence": 0.7, "sources": ["polygon"]},
                is_active=True,
                created_at=datetime.now()
            ),
            SentimentType(
                id=0,
                name="news_negative",
                description="Negative news sentiment from articles",
                category="news",
                parameters={"min_confidence": 0.7, "sources": ["polygon"]},
                is_active=True,
                created_at=datetime.now()
            ),
            SentimentType(
                id=0,
                name="news_neutral",
                description="Neutral/informational news",
                category="news",
                parameters={"min_confidence": 0.5, "sources": ["polygon"]},
                is_active=True,
                created_at=datetime.now()
            )
            # Phase 2 - Earnings (future):
            # earnings_beat, earnings_miss, guidance_raised, guidance_lowered
            # Phase 3 - Analyst ratings (future):
            # analyst_upgrade, analyst_downgrade, price_target_increase
        ]

        # Store each type to database
        stored_count = 0
        for sentiment_type in predefined_types:
            try:
                if self.sentiment_types_manager.set_entity_to_database(sentiment_type.name, sentiment_type):
                    stored_count += 1
            except Exception as e:
                logger.warning(f"Failed to store sentiment type {sentiment_type.name}: {e}")
                continue

        logger.info(f"Bootstrapped {stored_count}/{len(predefined_types)} sentiment types successfully")
        return stored_count

    def get_sentiment_events(
        self,
        asset_id: Optional[int] = None,
        sentiment_type_id: Optional[int] = None,
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None
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
                asset_id,
                start_date=start_date,
                end_date=end_date
            )
        elif sentiment_type_id:
            return self.sentiment_events_manager.get_events_by_type(
                sentiment_type_id,
                start_date=start_date,
                end_date=end_date
            )
        elif start_date and end_date:
            return self.sentiment_events_manager.get_events_by_date_range(
                start_date,
                end_date
            )
        else:
            logger.warning("get_sentiment_events called with no filters")
            return []

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
        return {
            "polygon_snapshot": self.polygon_snapshot_provider.get_provider_info()
        }

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

    def get_universe_stats(self) -> dict:
        """Get statistics from universe manager.

        Returns:
            Dictionary with manager statistics
        """
        return self.universe_manager.get_stats()

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

    def get_universe_stats(self) -> dict:
        """Get statistics from universe manager.

        Returns:
            Dictionary with manager statistics
        """
        return self.universe_manager.get_stats()
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
