"""DataService V2 - New architecture with Repository + DAO + Cache-Aside pattern.

This is the new DataService implementation demonstrating the layered architecture.
It coexists with the old data_service.py during the strangler fig migration.

Architecture:
  DataService → CacheService → Repository → DAO (SQLModel) → Database
                      ↓
                API Provider
"""

import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from sqlmodel import Session
from repositories.asset_repository import AssetRepository
from repositories.market_repository import MarketRepository
from repositories.fundamentals_repository import FundamentalsRepository
from repositories.provider_repository import ProviderRepository
from repositories.universe_repository import UniverseRepository
from repositories.asset_price_repository import AssetPriceRepository
from repositories.data_update_metadata_repository import DataUpdateMetadataRepository
from repositories.screener_repository import ScreenerRepository
from repositories.fed_data_repository import FedDataRepository
from repositories.gap_candidate_repository import GapCandidateRepository
from repositories.gap_candidate_result_repository import GapCandidateResultRepository
from repositories.market_holiday_repository import MarketHolidayRepository
from repositories.gap_result_news_repository import GapResultNewsRepository
from repositories.sentiment_type_repository import SentimentTypeRepository
from repositories.sentiment_event_repository import SentimentEventRepository
from services.cache_service import CacheService, CacheConfig
from api.providers.provider_factory import ProviderFactory
from models.sqlmodel.asset_sqlmodel import AssetSQLModel
from models.sqlmodel.market_sqlmodel import MarketSQLModel
from models.sqlmodel.fundamentals_sqlmodel import FundamentalsSQLModel
from models.sqlmodel.provider_sqlmodel import ProviderSQLModel
from models.sqlmodel.universe_sqlmodel import UniverseSQLModel, UniverseMembershipSQLModel
from models.sqlmodel.asset_price_sqlmodel import AssetPriceSQLModel
from models.dataclass.data_update_metadata import DataUpdateMetadataType
from services.converters import (
    convert_asset_sqlmodel_to_dataclass,
    convert_market_sqlmodel_to_dataclass,
    convert_asset_price_sqlmodel_to_dataclass,
    convert_universe_membership_sqlmodel_to_dataclass,
    convert_sentiment_event_sqlmodel_to_dataclass,
    convert_fed_data_sqlmodel_to_dataclass
)

logger = logging.getLogger(__name__)


class DataServiceV2:
    """DataService V2 - New layered architecture.

    This service demonstrates the Repository + DAO + Cache-Aside pattern.
    It orchestrates:
    - Repository (business queries)
    - CacheService (cache-aside pattern)
    - APIProvider (Polygon API calls)

    During migration, this coexists with the old DataService.
    Callers can choose which version to use (strangler fig pattern).
    """

    def __init__(self, session: Session, polygon_api_key: str, db_path: str = "data/tradescout.db"):
        """Initialize DataService V2 with all layers.

        Args:
            session: SQLModel session for database operations
            polygon_api_key: Polygon API key for data fetching
            db_path: Path to SQLite database (for metadata manager)
        """
        # Store session for direct queries
        self.session = session

        # Initialize repositories (business queries)
        self.asset_repository = AssetRepository(session)
        self.market_repository = MarketRepository(session)
        self.fundamentals_repository = FundamentalsRepository(session)
        self.provider_repository = ProviderRepository(session)
        self.universe_repository = UniverseRepository(session)
        self.asset_price_repository = AssetPriceRepository(session)
        self.screener_repository = ScreenerRepository(session)
        self.fed_data_repository = FedDataRepository(session)
        self.metadata_repository = DataUpdateMetadataRepository(session)

        # Initialize gap-related repositories
        self.gap_candidate_repository = GapCandidateRepository(session)
        self.gap_candidate_result_repository = GapCandidateResultRepository(session)
        self.market_holiday_repository = MarketHolidayRepository(session)
        self.gap_result_news_repository = GapResultNewsRepository(session)
        self.sentiment_type_repository = SentimentTypeRepository(session)
        self.sentiment_event_repository = SentimentEventRepository(session)

        # Initialize API providers via factory (provider-agnostic)
        # All providers now use abstraction layer - easy to swap via config
        self.snapshot_provider = ProviderFactory.create_snapshot_provider(api_key=polygon_api_key)
        self.aggregates_provider = ProviderFactory.create_aggregates_provider(api_key=polygon_api_key)
        self.news_provider = ProviderFactory.create_news_provider(api_key=polygon_api_key)
        self.market_status_provider = ProviderFactory.create_market_status_provider(api_key=polygon_api_key)
        self.reference_provider = ProviderFactory.create_reference_provider(api_key=polygon_api_key)
        self.economic_provider = ProviderFactory.create_economic_provider(api_key=polygon_api_key)

        # Legacy names for backward compatibility (deprecated - use new names above)
        self.polygon_snapshot_provider = self.snapshot_provider
        self.polygon_aggregates_provider = self.aggregates_provider
        self.polygon_news_provider = self.news_provider
        self.polygon_market_status_provider = self.market_status_provider

        # Initialize cache services (cache-aside pattern)
        self.asset_cache = CacheService[AssetSQLModel](
            repository=self.asset_repository,
            metadata_repository=self.metadata_repository,
            metadata_type=DataUpdateMetadataType.TICKERS,
            ttl_seconds=CacheConfig.get_ttl(DataUpdateMetadataType.TICKERS)
        )

        self.market_cache = CacheService[MarketSQLModel](
            repository=self.market_repository,
            metadata_repository=self.metadata_repository,
            metadata_type=DataUpdateMetadataType.MARKETS,
            ttl_seconds=CacheConfig.get_ttl(DataUpdateMetadataType.MARKETS)
        )

        self.fundamentals_cache = CacheService[FundamentalsSQLModel](
            repository=self.fundamentals_repository,
            metadata_repository=self.metadata_repository,
            metadata_type=DataUpdateMetadataType.FUNDAMENTALS,
            ttl_seconds=CacheConfig.get_ttl(DataUpdateMetadataType.FUNDAMENTALS)
        )

        logger.debug("DataServiceV2 initialized with new architecture")

    # ============================================================================
    # ASSET OPERATIONS - Demonstrating cache-aside pattern
    # ============================================================================

    def get_asset(
        self, symbol: str, force_refresh: bool = False
    ) -> Optional["Asset"]:
        """Get asset by symbol.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            force_refresh: If True, bypass cache and always fetch fresh (not implemented)

        Returns:
            Asset dataclass if found, None otherwise
        """
        # Get from repository (returns SQLModel)
        asset_sqlmodel = self.asset_repository.get_by_symbol(symbol.upper())

        if not asset_sqlmodel:
            return None

        # Convert SQLModel to dataclass at service boundary
        return convert_asset_sqlmodel_to_dataclass(asset_sqlmodel)

    def _fetch_asset_from_api(self, symbol: str) -> Optional[AssetSQLModel]:
        """Fetch asset from Polygon API and convert to SQLModel.

        This is the fetch_fn callback used by cache service.
        It handles the conversion from provider response to SQLModel.

        Args:
            symbol: Stock symbol to fetch

        Returns:
            AssetSQLModel if successful, None otherwise
        """
        try:
            # Fetch from reference provider (returns Asset dataclass)
            # Provider still uses dataclass models - we convert to SQLModel after fetching

            # Build market code-to-ID mapping from database, including provider_id
            markets = self.market_repository.get_all(active_only=False)
            market_code_to_id = {market.code: market.id for market in markets}

            # Get Polygon provider ID for the mapping
            polygon_provider = self.provider_repository.get_by_name("polygon")
            if polygon_provider:
                market_code_to_id["__provider_id__"] = polygon_provider.id

            asset_dataclass = self.reference_provider.fetch_ticker_details(
                symbol,
                market_code_to_id
            )

            if not asset_dataclass:
                return None

            # Convert dataclass to SQLModel
            # This is temporary during migration
            asset_sqlmodel = AssetSQLModel(
                id=asset_dataclass.id if hasattr(asset_dataclass, 'id') else None,
                symbol=asset_dataclass.symbol,
                name=asset_dataclass.name,
                asset_type=asset_dataclass.asset_type.value,
                asset_class=asset_dataclass.asset_class.value,
                market_id=asset_dataclass.market_id,
                currency=asset_dataclass.currency,
                lot_size=asset_dataclass.lot_size,
                tick_size=asset_dataclass.tick_size,
                is_active=asset_dataclass.is_active,
                is_delisted=asset_dataclass.is_delisted,
                listing_date=asset_dataclass.listing_date,
                delisting_date=asset_dataclass.delisting_date,
                provider_id=asset_dataclass.provider_id,
                created_at=asset_dataclass.created_at,
                updated_at=asset_dataclass.updated_at
            )

            return asset_sqlmodel

        except Exception as e:
            logger.error(f"Error fetching asset {symbol} from API: {e}")
            return None

    # ============================================================================
    # MARKET OPERATIONS - Phase 2: Markets entity migrated
    # ============================================================================

    def get_market(
        self, code: str, force_refresh: bool = False
    ) -> Optional["Market"]:
        """Get market by code.

        Args:
            code: Market code (e.g., 'XNYS', 'NASDAQ')
            force_refresh: If True, bypass cache and always fetch fresh (not implemented)

        Returns:
            Market dataclass if found, None otherwise
        """
        # Get from repository (returns SQLModel)
        market_sqlmodel = self.market_repository.get_by_code(code)

        if not market_sqlmodel:
            return None

        # Convert SQLModel to dataclass at service boundary
        return convert_market_sqlmodel_to_dataclass(market_sqlmodel)

    def get_all_markets(self, active_only: bool = True) -> List["Market"]:
        """Get all active markets.

        Args:
            active_only: If True, return only active markets (default: True)
                        Note: Currently only active markets are supported

        Returns:
            List of all active markets as dataclasses
        """
        from models.dataclass.market import Market

        markets_sqlmodel = self.market_repository.find_all_active()

        # Convert SQLModel to dataclass at service boundary
        return [
            Market(
                id=m.id,
                code=m.code,
                name=m.name,
                country=m.country,
                timezone=m.timezone,
                currency=m.currency,
                premarket_start_time=m.premarket_start_time,
                premarket_end_time=m.premarket_end_time,
                regular_open_time=m.regular_open_time,
                regular_close_time=m.regular_close_time,
                afterhours_start_time=m.afterhours_start_time,
                afterhours_end_time=m.afterhours_end_time,
                is_active=m.is_active,
                created_at=m.created_at,
                updated_at=m.updated_at
            )
            for m in markets_sqlmodel
        ]

    def get_us_markets(self) -> List["Market"]:
        """Get all active US markets.

        Returns:
            List of US markets as dataclasses
        """
        from models.dataclass.market import Market

        markets_sqlmodel = self.market_repository.find_us_markets()

        # Convert SQLModel to dataclass at service boundary
        return [
            Market(
                id=m.id,
                code=m.code,
                name=m.name,
                country=m.country,
                timezone=m.timezone,
                currency=m.currency,
                premarket_start_time=m.premarket_start_time,
                premarket_end_time=m.premarket_end_time,
                regular_open_time=m.regular_open_time,
                regular_close_time=m.regular_close_time,
                afterhours_start_time=m.afterhours_start_time,
                afterhours_end_time=m.afterhours_end_time,
                is_active=m.is_active,
                created_at=m.created_at,
                updated_at=m.updated_at
            )
            for m in markets_sqlmodel
        ]

    # ============================================================================
    # FUNDAMENTALS OPERATIONS - Phase 3: Fundamentals entity migrated
    # ============================================================================

    def get_fundamentals(
        self, asset_id: int, force_refresh: bool = False
    ) -> Optional["AssetFundamentals"]:
        """Get fundamentals for an asset.

        Args:
            asset_id: Asset database ID
            force_refresh: If True, bypass cache and always fetch fresh

        Returns:
            AssetFundamentals dataclass if found, None otherwise
        """
        from models.dataclass.fundamentals import AssetFundamentals

        # Fundamentals are already in database from bootstrap
        fundamentals_sqlmodel = self.fundamentals_repository.get_by_asset_id(asset_id)

        if not fundamentals_sqlmodel:
            return None

        # Convert SQLModel to dataclass for domain layer
        return AssetFundamentals(
            asset_id=fundamentals_sqlmodel.asset_id,
            company_name=fundamentals_sqlmodel.company_name,
            sector=fundamentals_sqlmodel.sector,
            industry=fundamentals_sqlmodel.industry,
            sic_code=fundamentals_sqlmodel.sic_code,
            market_cap=fundamentals_sqlmodel.market_cap,
            shares_outstanding=fundamentals_sqlmodel.shares_outstanding,
            avg_volume_30d=fundamentals_sqlmodel.avg_volume_30d,
            beta=fundamentals_sqlmodel.beta,
            pe_ratio=fundamentals_sqlmodel.pe_ratio,
            dividend_yield=fundamentals_sqlmodel.dividend_yield,
            provider_id=fundamentals_sqlmodel.provider_id,
            last_updated=fundamentals_sqlmodel.last_updated
        )

    def find_by_market_cap(
        self, min_cap: int, max_cap: Optional[int] = None
    ) -> List["AssetFundamentals"]:
        """Find assets by market cap range.

        Critical for gap trading screeners (min $300M market cap required).

        Args:
            min_cap: Minimum market cap in dollars
            max_cap: Maximum market cap in dollars (optional)

        Returns:
            List of fundamentals meeting criteria as dataclasses
        """
        from models.dataclass.fundamentals import AssetFundamentals

        fundamentals_sqlmodel = self.fundamentals_repository.find_by_market_cap_range(
            min_cap=min_cap,
            max_cap=max_cap
        )

        # Convert SQLModel to dataclass at service boundary
        return [
            AssetFundamentals(
                asset_id=f.asset_id,
                company_name=f.company_name,
                sector=f.sector,
                industry=f.industry,
                sic_code=f.sic_code,
                market_cap=f.market_cap,
                shares_outstanding=f.shares_outstanding,
                avg_volume_30d=f.avg_volume_30d,
                beta=f.beta,
                pe_ratio=f.pe_ratio,
                dividend_yield=f.dividend_yield,
                provider_id=f.provider_id,
                last_updated=f.last_updated
            )
            for f in fundamentals_sqlmodel
        ]

    def find_gap_trading_candidates(self) -> List["AssetFundamentals"]:
        """Find assets suitable for gap trading (min $300M market cap).

        Business rule: Gap trading requires sufficient liquidity.

        Returns:
            List of fundamentals meeting gap trading criteria as dataclasses
        """
        from models.dataclass.fundamentals import AssetFundamentals

        fundamentals_sqlmodel = self.fundamentals_repository.find_for_gap_trading()

        # Convert SQLModel to dataclass at service boundary
        return [
            AssetFundamentals(
                asset_id=f.asset_id,
                company_name=f.company_name,
                sector=f.sector,
                industry=f.industry,
                sic_code=f.sic_code,
                market_cap=f.market_cap,
                shares_outstanding=f.shares_outstanding,
                avg_volume_30d=f.avg_volume_30d,
                beta=f.beta,
                pe_ratio=f.pe_ratio,
                dividend_yield=f.dividend_yield,
                provider_id=f.provider_id,
                last_updated=f.last_updated
            )
            for f in fundamentals_sqlmodel
        ]

    def find_by_sector(self, sector: str) -> List["AssetFundamentals"]:
        """Find assets by sector.

        Args:
            sector: Sector name (e.g., 'Technology', 'Healthcare')

        Returns:
            List of fundamentals in the sector as dataclasses
        """
        from models.dataclass.fundamentals import AssetFundamentals

        fundamentals_sqlmodel = self.fundamentals_repository.find_by_sector(sector)

        # Convert SQLModel to dataclass at service boundary
        return [
            AssetFundamentals(
                asset_id=f.asset_id,
                company_name=f.company_name,
                sector=f.sector,
                industry=f.industry,
                sic_code=f.sic_code,
                market_cap=f.market_cap,
                shares_outstanding=f.shares_outstanding,
                avg_volume_30d=f.avg_volume_30d,
                beta=f.beta,
                pe_ratio=f.pe_ratio,
                dividend_yield=f.dividend_yield,
                provider_id=f.provider_id,
                last_updated=f.last_updated
            )
            for f in fundamentals_sqlmodel
        ]

    def get_all_sectors(self) -> List[str]:
        """Get list of all sectors.

        Returns:
            List of sector names
        """
        return self.fundamentals_repository.get_all_sectors()

    # ============================================================================
    # PROVIDER OPERATIONS - Phase 4: Providers entity migrated
    # ============================================================================

    def get_provider(self, name: str) -> Optional["Provider"]:
        """Get provider by name.

        Args:
            name: Provider name (e.g., 'polygon', 'yfinance')

        Returns:
            Provider dataclass if found, None otherwise
        """
        from models.dataclass.provider import Provider

        provider_sqlmodel = self.provider_repository.get_by_name(name)

        if not provider_sqlmodel:
            return None

        # Convert SQLModel to dataclass at service boundary
        return Provider(
            id=provider_sqlmodel.id,
            name=provider_sqlmodel.name,
            display_name=provider_sqlmodel.display_name,
            base_url=provider_sqlmodel.base_url,
            api_key_required=provider_sqlmodel.api_key_required,
            is_active=provider_sqlmodel.is_active,
            created_at=provider_sqlmodel.created_at
        )

    def get_all_providers(self) -> List["Provider"]:
        """Get all active providers.

        Returns:
            List of active providers as dataclasses
        """
        from models.dataclass.provider import Provider

        providers_sqlmodel = self.provider_repository.find_all_active()

        # Convert SQLModel to dataclass at service boundary
        return [
            Provider(
                id=p.id,
                name=p.name,
                display_name=p.display_name,
                base_url=p.base_url,
                api_key_required=p.api_key_required,
                is_active=p.is_active,
                created_at=p.created_at
            )
            for p in providers_sqlmodel
        ]

    # ============================================================================
    # UNIVERSE OPERATIONS - Phase 5: Universes entity migrated
    # ============================================================================

    def get_universe(self, name: str) -> Optional["Universe"]:
        """Get universe by name.

        Universes are INTERNAL-ONLY - not fetched from APIs.

        Args:
            name: Universe name (e.g., 'gap_trading_universe')

        Returns:
            Universe dataclass if found, None otherwise
        """
        from models.dataclass.universe import Universe

        universe_sqlmodel = self.universe_repository.get_by_name(name)

        if not universe_sqlmodel:
            return None

        # Convert SQLModel to dataclass at service boundary
        return Universe(
            id=universe_sqlmodel.id,
            name=universe_sqlmodel.name,
            description=universe_sqlmodel.description,
            is_active=universe_sqlmodel.is_active,
            min_market_cap=universe_sqlmodel.min_market_cap,
            min_volume=universe_sqlmodel.min_volume,
            max_assets=universe_sqlmodel.max_assets,
            last_updated=universe_sqlmodel.last_updated,
            created_at=universe_sqlmodel.created_at,
            updated_at=universe_sqlmodel.updated_at
        )

    def get_all_universes(self) -> List["Universe"]:
        """Get all universes.

        Returns:
            List of all universes as dataclasses
        """
        from models.dataclass.universe import Universe

        universes_sqlmodel = self.universe_repository.find_all()

        # Convert SQLModel to dataclass at service boundary
        return [
            Universe(
                id=u.id,
                name=u.name,
                description=u.description,
                is_active=u.is_active,
                min_market_cap=u.min_market_cap,
                min_volume=u.min_volume,
                max_assets=u.max_assets,
                last_updated=u.last_updated,
                created_at=u.created_at,
                updated_at=u.updated_at
            )
            for u in universes_sqlmodel
        ]

    def get_active_universe(self) -> Optional["Universe"]:
        """Get the currently active universe.

        Returns:
            Active universe dataclass or None
        """
        from models.dataclass.universe import Universe

        universe_sqlmodel = self.universe_repository.get_active_universe()

        if not universe_sqlmodel:
            return None

        # Convert SQLModel to dataclass at service boundary
        return Universe(
            id=universe_sqlmodel.id,
            name=universe_sqlmodel.name,
            description=universe_sqlmodel.description,
            is_active=universe_sqlmodel.is_active,
            min_market_cap=universe_sqlmodel.min_market_cap,
            min_volume=universe_sqlmodel.min_volume,
            max_assets=universe_sqlmodel.max_assets,
            last_updated=universe_sqlmodel.last_updated,
            created_at=universe_sqlmodel.created_at,
            updated_at=universe_sqlmodel.updated_at
        )

    def set_active_universe(self, universe_name: str) -> bool:
        """Set the active universe.

        Business rule: Only one universe can be active at a time.

        Args:
            universe_name: Name of universe to activate

        Returns:
            True if successful
        """
        return self.universe_repository.set_active_universe(universe_name)

    def get_universe_memberships(
        self, universe_name: str
    ) -> List["UniverseMembership"]:
        """Get memberships for a universe.

        Args:
            universe_name: Universe name

        Returns:
            List of UniverseMembership dataclasses
        """
        # Get from repository (returns SQLModel list)
        memberships_sqlmodel = self.universe_repository.get_memberships_by_universe_name(universe_name)

        # Convert SQLModel to dataclass at service boundary
        return [
            convert_universe_membership_sqlmodel_to_dataclass(m)
            for m in memberships_sqlmodel
        ]

    def get_active_universe_symbols(self) -> List[str]:
        """Get list of symbols in the active universe.

        Business query: Used by gap trading screeners.

        Returns:
            List of symbol strings
        """
        return self.universe_repository.get_active_universe_symbols()

    def add_universe_memberships(
        self, universe_name: str, asset_ids: List[int]
    ) -> int:
        """Add assets to a universe.

        Args:
            universe_name: Universe name
            asset_ids: List of asset IDs to add

        Returns:
            Number of memberships added
        """
        universe = self.get_universe(universe_name)
        if not universe:
            return 0

        return self.universe_repository.add_memberships(universe.id, asset_ids)

    def clear_universe_memberships(self, universe_name: str) -> int:
        """Clear all memberships from a universe.

        Args:
            universe_name: Universe name

        Returns:
            Number of memberships cleared
        """
        universe = self.get_universe(universe_name)
        if not universe:
            return 0

        return self.universe_repository.clear_memberships(universe.id)

    # ============================================================================
    # ASSET PRICE OPERATIONS - Phase 6: AssetPrice entity migrated
    # ============================================================================

    def get_latest_price(self, symbol: str) -> Optional["AssetPrice"]:
        """Get most recent price for a symbol.

        Critical for gap analysis.

        Args:
            symbol: Stock symbol

        Returns:
            AssetPrice dataclass or None
        """
        # Get from repository (returns SQLModel)
        price_sqlmodel = self.asset_price_repository.get_latest_by_symbol(symbol)

        if not price_sqlmodel:
            return None

        # Convert SQLModel to dataclass at service boundary
        return convert_asset_price_sqlmodel_to_dataclass(price_sqlmodel)

    def get_latest_prices(
        self, symbols: List[str]
    ) -> List["AssetPrice"]:
        """Get latest prices for multiple symbols.

        Batch query for gap screeners.

        Args:
            symbols: List of stock symbols

        Returns:
            List of AssetPrice dataclasses
        """
        # Get from repository (returns SQLModel list)
        prices_sqlmodel = self.asset_price_repository.get_latest_for_symbols(symbols)

        # Convert SQLModel to dataclass at service boundary
        return [
            convert_asset_price_sqlmodel_to_dataclass(p)
            for p in prices_sqlmodel
        ]

    def find_prices_with_gaps(
        self, min_gap_percent: float = 2.0
    ) -> List["AssetPrice"]:
        """Find assets with significant gaps.

        Core gap trading screener query.

        Args:
            min_gap_percent: Minimum gap percentage (default: 2%)

        Returns:
            List of AssetPrice dataclasses with gaps
        """
        # Get from repository (returns SQLModel list)
        prices_sqlmodel = self.asset_price_repository.find_with_gaps(min_gap_percent)

        # Convert SQLModel to dataclass at service boundary
        return [
            convert_asset_price_sqlmodel_to_dataclass(p)
            for p in prices_sqlmodel
        ]

    def get_last_price_update_time(self) -> Optional["datetime"]:
        """Get timestamp of most recent price update across all symbols.

        Business query: Used to check data freshness for gap analysis.

        Returns:
            Most recent updated_at timestamp or None
        """
        from datetime import datetime
        return self.asset_price_repository.get_last_update_time()

    # ============================================================================
    # BULK UPDATE METHODS
    # ============================================================================

    def update_market_snapshot(self, force_refresh: bool = False):
        """Update asset prices from bulk market snapshot with TTL caching.

        Checks if data is fresh based on TTL. If fresh and not forced, returns stats
        showing data was fresh. If stale or forced, fetches from Polygon API and saves
        new records to database.

        Only saves new tuples of (asset_id, provider_id, provider_updated_at) that
        don't already exist in the database.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            MarketSnapshotUpdateStats with operation statistics
        """
        from datetime import datetime, timedelta
        from models.result.market_result import MarketSnapshotUpdateStats

        # Check metadata to see if data is fresh (using configured TTL)
        if not force_refresh:
            ttl_seconds = CacheConfig.get_ttl(DataUpdateMetadataType.MARKET_SNAPSHOTS)
            metadata = self.metadata_repository.get_latest_by_operation(
                operation_type=DataUpdateMetadataType.MARKET_SNAPSHOTS.value
            )

            if metadata and metadata.completed_at:
                age = datetime.now() - metadata.completed_at

                if age < timedelta(seconds=ttl_seconds):
                    logger.debug(f"Market snapshot data is fresh ({age.total_seconds():.1f}s old, TTL: {ttl_seconds}s), skipping API call")
                    return MarketSnapshotUpdateStats(
                        total_tickers=0,
                        matched_symbols=0,
                        unmatched_symbols=0,
                        transformed=0,
                        invalid=0,
                        saved=0,
                        duplicates=0,
                        data_was_fresh=True
                    )

        # Data is stale or force_refresh=True, fetch from API
        start_time = datetime.now()
        market_snapshot = self.polygon_snapshot_provider.fetch_bulk_market_snapshot()

        if not market_snapshot or not market_snapshot.tickers:
            logger.warning("No market snapshot data received from API")
            return MarketSnapshotUpdateStats(
                total_tickers=0,
                matched_symbols=0,
                unmatched_symbols=0,
                transformed=0,
                invalid=0,
                saved=0,
                duplicates=0,
                data_was_fresh=False
            )

        # Transform to AssetPrice objects
        asset_prices = []
        stats_matched = 0
        stats_unmatched = 0
        stats_invalid = 0
        stats_skipped_stale = 0
        stats_invalid_no_timestamp = 0
        stats_invalid_exception = 0

        # market_snapshot.tickers is a dict[symbol -> TickerSnapshot]
        for symbol, ticker_snapshot in market_snapshot.tickers.items():
            symbol = symbol.upper()  # Normalize symbol

            # Look up asset_id
            asset = self.asset_repository.get_by_symbol(symbol)
            if not asset:
                stats_unmatched += 1
                continue

            stats_matched += 1

            # Check if API has newer data than what we already have
            existing_price = self.asset_price_repository.get_latest_by_asset_id(asset.id)
            api_timestamp = ticker_snapshot.updated_ns

            # Only process if API has newer data (or we have no data yet)
            if existing_price and api_timestamp:
                if api_timestamp <= existing_price.provider_updated_at:
                    # API data is same or older, skip (we already have this data or newer)
                    stats_skipped_stale += 1
                    logger.debug(f"Skipping {symbol} - API timestamp {api_timestamp} <= existing {existing_price.provider_updated_at}")
                    continue

            # Transform to AssetPrice
            asset_price = self.transform_ticker_snapshot_to_asset_price(
                symbol=symbol,
                asset_id=asset.id,
                ticker_snapshot=ticker_snapshot
            )

            if asset_price and isinstance(asset_price, object) and not isinstance(asset_price, str):
                asset_prices.append(asset_price)
            else:
                # Transform failed - track the reason
                stats_invalid += 1
                if asset_price == "NO_TIMESTAMP":
                    stats_invalid_no_timestamp += 1
                elif asset_price == "EXCEPTION":
                    stats_invalid_exception += 1

        # Log invalid breakdown (debug level - not critical information)
        if stats_invalid > 0:
            logger.debug(f"Invalid records: {stats_invalid} total ({stats_invalid_no_timestamp} missing timestamp, {stats_invalid_exception} transform exceptions)")

        # Batch save to database (only saves new tuples)
        saved_count = 0
        if asset_prices:
            saved_count = self.batch_save_asset_prices(asset_prices)
            logger.info(f"Saved {saved_count} new asset prices to database (skipped {len(asset_prices) - saved_count} duplicates, {stats_skipped_stale} stale, {stats_invalid} invalid)")

            # Record metadata - processed_items is valid data we handled, not just new saves
            # Invalid/rejected data is quality enforcement, not failure
            # Duplicates mean data is fresh, not a failure
            self.record_bulk_operation_metadata(
                operation_type=DataUpdateMetadataType.MARKET_SNAPSHOTS,
                operation_subtype="refresh",
                start_time=start_time,
                total_items=len(market_snapshot.tickers),
                processed_items=len(asset_prices),  # Valid data successfully processed
                failed_items=0  # Quality rejections aren't failures
            )
        else:
            # All data was skipped - either stale or invalid
            if stats_skipped_stale > 0:
                logger.info(f"No new data to save - all {stats_skipped_stale} records already in database (same or fresher)")
            elif stats_invalid > 0:
                logger.warning(f"No valid asset prices to save ({stats_invalid} invalid: {stats_invalid_no_timestamp} missing timestamp, {stats_invalid_exception} transform exceptions)")

        return MarketSnapshotUpdateStats(
            total_tickers=len(market_snapshot.tickers),
            matched_symbols=stats_matched,
            unmatched_symbols=stats_unmatched,
            transformed=len(asset_prices),
            invalid=stats_invalid,
            invalid_no_timestamp=stats_invalid_no_timestamp,
            invalid_exception=stats_invalid_exception,
            saved=saved_count,
            duplicates=len(asset_prices) - saved_count + stats_skipped_stale,  # Include stale data in duplicates count
            data_was_fresh=False
        )

    def backfill_market_data(self, target_date: date, force_refresh: bool = False):
        """Backfill market data for a specific date using grouped daily bars.

        Fetches all US stock daily bars for the target date and saves data for
        symbols in the active universe. Only inserts/updates if provider_updated_at
        is newer than existing data for that date.

        Args:
            target_date: Date to backfill (e.g., date(2025, 10, 14))
            force_refresh: If True, update even if provider_updated_at is same or older

        Returns:
            MarketSnapshotUpdateStats with operation statistics
        """
        from datetime import datetime
        from models.result.market_result import MarketSnapshotUpdateStats

        start_time = datetime.now()

        logger.info(f"Backfilling market data for {target_date}")

        # Fetch grouped daily bars for the target date
        bars_dict = self.polygon_aggregates_provider.fetch_grouped_daily_bars(target_date)

        if not bars_dict:
            logger.warning(f"No grouped bars data received from API for {target_date}")
            return MarketSnapshotUpdateStats(
                total_tickers=0,
                matched_symbols=0,
                unmatched_symbols=0,
                transformed=0,
                invalid=0,
                saved=0,
                duplicates=0,
                data_was_fresh=False
            )

        # Process all bars, matching against assets in database
        asset_prices = []
        stats_matched = 0
        stats_unmatched = 0
        stats_invalid = 0

        for symbol, bar in bars_dict.items():
            symbol = symbol.upper()  # Normalize symbol

            # Look up asset_id
            asset = self.asset_repository.get_by_symbol(symbol)
            if not asset:
                stats_unmatched += 1
                continue

            stats_matched += 1

            # Polygon grouped bars timestamp is market close (4PM ET)
            # For backfill, use afterhours close (8PM ET) as the "latest" data for that day
            # Add 4 hours (14400000 ms) to the timestamp to represent afterhours close
            bar_timestamp_ms = bar.timestamp_ms
            afterhours_close_ms = bar_timestamp_ms + 14_400_000  # Add 4 hours
            provider_updated_at_ns = afterhours_close_ms * 1_000_000  # Convert to nanoseconds

            # Transform bar to AssetPrice
            from models.sqlmodel.asset_price_sqlmodel import AssetPriceSQLModel

            asset_price = AssetPriceSQLModel(
                asset_id=asset.id,
                provider_id=1,  # Polygon provider
                symbol=symbol,
                trade_date=target_date,
                provider_updated_at=provider_updated_at_ns,
                # Set all price fields from the daily bar
                day_open=bar.open,
                day_high=bar.high,
                day_low=bar.low,
                day_close=bar.close,
                day_volume=int(bar.volume) if bar.volume else 0,
                day_vwap=bar.volume_weighted_price,
                # Leave other fields as None (no prevday/min data from grouped bars)
                prevday_open=None,
                prevday_high=None,
                prevday_low=None,
                prevday_close=None,
                prevday_volume=None,
                prevday_vwap=None,
                min_open=None,
                min_high=None,
                min_low=None,
                min_close=None,
                min_accumulated_volume=None,
                min_vwap=None
            )

            asset_prices.append(asset_price)

        # Upsert to database (insert new or update existing)
        upsert_stats = {'inserted': 0, 'updated': 0, 'skipped': 0, 'deleted': 0}
        if asset_prices:
            # Use bulk_upsert to handle both inserts and updates
            upsert_stats = self.asset_price_repository.bulk_upsert(asset_prices, force_refresh=force_refresh)
            saved_count = upsert_stats['inserted'] + upsert_stats['updated']
            logger.info(f"Backfilled {upsert_stats} prices for {target_date}")

            # Record metadata
            self.record_bulk_operation_metadata(
                operation_type=DataUpdateMetadataType.MARKET_SNAPSHOTS,
                operation_subtype=f"backfill_{target_date.isoformat()}",
                start_time=start_time,
                total_items=len(bars_dict),
                processed_items=len(asset_prices),
                failed_items=0
            )
        else:
            logger.warning(f"No prices to backfill for {target_date}")
            saved_count = 0

        return MarketSnapshotUpdateStats(
            total_tickers=len(bars_dict),
            matched_symbols=stats_matched,
            unmatched_symbols=stats_unmatched,
            transformed=len(asset_prices),
            invalid=stats_invalid,
            saved=saved_count,
            duplicates=upsert_stats['skipped'],
            data_was_fresh=False
        )

    def fetch_news_and_sentiment(self, symbol: str, limit: int = 10):
        """Fetch news and sentiment using new architecture.

        Args:
            symbol: Stock symbol
            limit: Max number of articles

        Returns:
            NewsResult object with processing details
        """
        from models.result.news_result import NewsResult
        from models.sqlmodel.sentiment_event_sqlmodel import SentimentEventSQLModel
        from datetime import datetime, date, time as dt_time
        from decimal import Decimal
        import json

        symbol = symbol.upper()
        errors = []

        # Get asset from database
        asset = self.asset_repository.get_by_symbol(symbol)
        if not asset:
            errors.append(f"Asset {symbol} not found in database")
            return NewsResult(
                symbol=symbol,
                source="api",
                articles_found=0,
                sentiment_events_created=0,
                sentiment_events_stored=0,
                sentiment_events_duplicates=0,
                errors=errors
            )

        # Fetch articles from API
        articles = self.polygon_news_provider.fetch_news_for_ticker(
            ticker=symbol,
            limit=limit
        )

        if not articles:
            return NewsResult(
                symbol=symbol,
                source="api",
                articles_found=0,
                sentiment_events_created=0,
                sentiment_events_stored=0,
                sentiment_events_duplicates=0,
                errors=errors if errors else ["No articles returned from API"]
            )

        articles_found = len(articles)
        sentiment_events_created = 0
        sentiment_events_stored = 0
        sentiment_events_duplicates = 0

        # Get sentiment type IDs
        sentiment_types = {}
        for sentiment_name in ['news_positive', 'news_negative', 'news_neutral', 'news_mixed']:
            sent_type = self.sentiment_type_repository.get_by_name(sentiment_name)
            if sent_type:
                sentiment_types[sentiment_name] = sent_type.id

        if not sentiment_types:
            errors.append("No sentiment types found in database - run bootstrap first")
            return NewsResult(
                symbol=symbol,
                source="api",
                articles_found=articles_found,
                sentiment_events_created=0,
                sentiment_events_stored=0,
                sentiment_events_duplicates=0,
                errors=errors
            )

        # Process each article
        for article in articles:
            try:
                # Check if already processed
                existing = self.sentiment_event_repository.find_by_external_id(article.id)
                if existing:
                    sentiment_events_duplicates += 1
                    continue

                # Get sentiment insight for this ticker
                ticker_insight = article.get_insight_for_ticker(symbol)
                if not ticker_insight:
                    # No sentiment data for this ticker in this article
                    continue

                # Extract date/time from published timestamp
                event_date = article.published_utc.date()
                event_time = article.published_utc.time()

                # Map sentiment to type
                sentiment = ticker_insight.sentiment.lower()
                sentiment_type_map = {
                    'positive': 'news_positive',
                    'negative': 'news_negative',
                    'neutral': 'news_neutral',
                    'mixed': 'news_mixed'
                }
                sentiment_type_name = sentiment_type_map.get(sentiment, 'news_neutral')
                sentiment_type_id = sentiment_types.get(sentiment_type_name)

                if not sentiment_type_id:
                    logger.warning(f"Unknown sentiment type: {sentiment_type_name}")
                    continue

                # Create details JSON
                details = {
                    'title': article.title,
                    'publisher': article.publisher_name,
                    'article_url': article.article_url,
                    'sentiment': sentiment,
                    'sentiment_reasoning': ticker_insight.sentiment_reasoning or ''
                }

                # Create sentiment event
                event = SentimentEventSQLModel(
                    asset_id=asset.id,
                    sentiment_type_id=sentiment_type_id,
                    event_date=event_date,
                    event_time=event_time,
                    session=None,  # Could determine based on time
                    value=Decimal(str(ticker_insight.sentiment_score)),
                    magnitude=None,  # Could categorize based on score
                    details=json.dumps(details),
                    external_id=article.id
                )

                # Save event
                self.sentiment_event_repository.save(event)
                sentiment_events_created += 1
                sentiment_events_stored += 1

            except Exception as e:
                error_msg = f"Error processing article {article.id}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        return NewsResult(
            symbol=symbol,
            source="api",
            articles_found=articles_found,
            sentiment_events_created=sentiment_events_created,
            sentiment_events_stored=sentiment_events_stored,
            sentiment_events_duplicates=sentiment_events_duplicates,
            errors=errors
        )

    def calculate_asset_sentiment(self, symbol: str, limit: int, time_window_days: int):
        """Calculate asset sentiment using new architecture.

        Args:
            symbol: Stock symbol
            limit: Max events to analyze
            time_window_days: Time window in days

        Returns:
            SentimentScore object or None
        """
        from analysis.sentiment_analyzer import SentimentAnalyzer

        symbol = symbol.upper()

        # Get asset from database using repository
        asset = self.asset_repository.get_by_symbol(symbol)
        if not asset:
            logger.warning(f"Asset {symbol} not found in database")
            return None

        # Get sentiment events using repository
        events_sql = self.sentiment_event_repository.find_recent_by_asset(
            asset.id,
            days=time_window_days,
            limit=limit
        )

        # Convert SQLModel objects to SentimentEvent dataclass objects
        sentiment_events = []
        for event_sql in events_sql:
            try:
                sentiment_event = convert_sentiment_event_sqlmodel_to_dataclass(event_sql)
                sentiment_events.append(sentiment_event)
            except Exception as e:
                logger.warning(f"Failed to convert sentiment event {event_sql.id}: {e}")
                continue

        if not sentiment_events:
            logger.debug(f"No sentiment events found for {symbol} in the last {time_window_days} days")
            return None

        # Use SentimentAnalyzer to calculate score
        analyzer = SentimentAnalyzer(time_window_days=time_window_days)
        return analyzer.calculate_sentiment_score(symbol, sentiment_events)

    def get_active_provider(self):
        """Get active provider using repository pattern.

        Returns:
            Active provider (typically 'polygon'), or None if no active provider exists
        """
        return self.provider_repository.get_active_provider()

    def get_asset_stats(self):
        """Get asset statistics using new architecture.

        Returns:
            Dictionary with asset statistics
        """
        return self.asset_repository.get_stats()

    def get_fundamentals_stats(self):
        """Get fundamentals statistics using new architecture.

        Returns:
            Dictionary with fundamentals statistics
        """
        return self.fundamentals_repository.get_stats()

    def get_database_stats(self):
        """Get database statistics using new architecture.

        Aggregates counts from all repositories.

        Returns:
            DatabaseStats object
        """
        from models.result.database_result import DatabaseStats

        # Get table counts using repositories
        table_counts = {
            "assets": self.asset_repository.count(),
            "markets": self.market_repository.count_all(),
            "asset_prices": self.asset_price_repository.count_all(),
            "universes": self.universe_repository.count_all(),
            "universe_memberships": self.universe_repository.count_all_memberships(),
            "fundamentals": self.fundamentals_repository.count_all()
        }

        # Get total records
        total_records = sum(table_counts.values())

        # Get latest update time across all entities using repositories
        latest_updates = []

        asset_update = self.asset_repository.get_last_updated()
        if asset_update:
            latest_updates.append(asset_update)

        fund_update = self.fundamentals_repository.get_last_updated()
        if fund_update:
            latest_updates.append(fund_update)

        last_updated = max(latest_updates) if latest_updates else None

        return DatabaseStats(
            database_path="data/tradescout.db",
            status="healthy",
            table_counts=table_counts,
            total_records=total_records,
            last_updated=last_updated
        )

    # ============================================================================
    # ASSET & PRICE OPERATIONS (Additional temporary delegations)
    # ============================================================================

    def get_asset_with_market(self, symbol: str):
        """Get asset with market info using new architecture.

        Args:
            symbol: Stock symbol

        Returns:
            Tuple[AssetSQLModel, MarketSQLModel] or None
        """
        return self.asset_repository.get_by_symbol_with_market(symbol)

    def get_latest_asset_price(self, symbol: str):
        """Get latest asset price using new architecture.

        Returns:
            AssetPriceSQLModel or None
        """
        return self.asset_price_repository.get_latest_by_symbol(symbol)

    def get_ticker_snapshot(self, symbol: str):
        """Get single ticker snapshot using new architecture.

        Args:
            symbol: Stock symbol

        Returns:
            TickerSnapshot from PolygonSnapshotProvider
        """
        return self.polygon_snapshot_provider.fetch_single_ticker_snapshot(symbol)

    def batch_save_asset_prices(self, prices):
        """Batch save asset prices using new architecture.

        Args:
            prices: List of AssetPrice dataclass objects

        Returns:
            Number of prices saved
        """
        from models.sqlmodel.asset_price_sqlmodel import AssetPriceSQLModel

        # Convert AssetPrice dataclass objects to AssetPriceSQLModel
        sql_models = []
        for price in prices:
            sql_model = AssetPriceSQLModel(
                id=None,  # Will be auto-assigned
                asset_id=price.asset_id,
                symbol=price.symbol,
                provider_id=price.provider_id,
                provider_updated_at=price.provider_updated_at,
                trade_date=price.trade_date,
                updated_at=price.updated_at,
                prevday_open=price.prevday_open,
                prevday_high=price.prevday_high,
                prevday_low=price.prevday_low,
                prevday_close=price.prevday_close,
                prevday_volume=price.prevday_volume,
                prevday_vwap=price.prevday_vwap,
                day_open=price.day_open,
                day_high=price.day_high,
                day_low=price.day_low,
                day_close=price.day_close,
                day_volume=price.day_volume,
                day_vwap=price.day_vwap,
                min_timestamp=price.min_timestamp,
                min_open=price.min_open,
                min_high=price.min_high,
                min_low=price.min_low,
                min_close=price.min_close,
                min_volume=price.min_volume,
                min_vwap=price.min_vwap,
                min_accumulated_volume=price.min_accumulated_volume,
                min_num_trades=price.min_num_trades,
            )
            sql_models.append(sql_model)

        return self.asset_price_repository.bulk_save(sql_models)

    def transform_ticker_snapshot_to_asset_price(self, symbol: str, asset_id: int, ticker_snapshot):
        """Transform TickerSnapshot to AssetPrice using new architecture.

        Args:
            symbol: Stock symbol
            asset_id: Asset database ID
            ticker_snapshot: TickerSnapshot object to transform

        Returns:
            AssetPrice object or None if error
        """
        try:
            from models.dataclass.price import AssetPrice

            # Get provider ID (default to 1 = Polygon)
            provider_id = 1

            # Use Polygon's updated timestamp - REQUIRED, reject if missing
            provider_updated_at = ticker_snapshot.updated_ns
            if not provider_updated_at or provider_updated_at == 0:
                logger.debug(f"Rejecting {symbol} - provider_updated_at is 0 or None")
                return "NO_TIMESTAMP"  # Special marker to track this specific failure

            # Determine trade date
            updated_seconds = provider_updated_at // 1_000_000_000
            trade_date = datetime.fromtimestamp(updated_seconds).date()

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
            logger.warning(f"Error transforming TickerSnapshot for {symbol}: {e}")
            return "EXCEPTION"  # Special marker to track this specific failure

    def get_all_assets_dict(self):
        """Get all active assets as dict for quick symbol lookups.

        Returns:
            Dict[str, int]: Dictionary mapping symbol -> asset_id
        """
        assets = self.asset_repository.find_all_active()
        return {asset.symbol: asset.id for asset in assets}

    # ============================================================================
    # UNIVERSE OPERATIONS (Additional temporary delegations)
    # ============================================================================

    def get_universe_stats(self, universe_name: str):
        """Get universe statistics using new architecture.

        Args:
            universe_name: Universe name

        Returns:
            UniverseStats object or None
        """
        return self.universe_repository.get_universe_stats(universe_name)

    def get_universe_market_breakdown(self, universe_name: str):
        """Get market breakdown for a universe.

        Args:
            universe_name: Universe name

        Returns:
            List[Tuple[str, str, int]]: (market_code, market_name, asset_count)
        """
        return self.universe_repository.get_market_breakdown(universe_name)

    def is_symbol_in_universe(self, symbol: str, universe_name: str) -> bool:
        """Check if symbol is in universe.

        Args:
            symbol: Stock symbol
            universe_name: Universe name

        Returns:
            True if symbol is in the universe
        """
        return self.universe_repository.is_symbol_in_universe(symbol, universe_name)

    # ============================================================================
    # MARKET OPERATIONS (Additional temporary delegations)
    # ============================================================================

    def get_active_markets_by_codes(self, codes: List[str]):
        """Get multiple markets by codes.

        Args:
            codes: List of market codes to filter by

        Returns:
            List[Tuple[str, str]]: List of (market_code, market_name) tuples
        """
        from typing import Tuple
        results = []
        for code in codes:
            market = self.market_repository.get_by_code(code)
            if market:
                results.append((market.code, market.name))
        return results

    # ============================================================================
    # NEWS & SENTIMENT OPERATIONS (Additional temporary delegations)
    # ============================================================================

    def get_sentiment_events(self, symbol: str, limit: int = 10):
        """Get sentiment events using new architecture.

        Args:
            symbol: Stock symbol
            limit: Maximum number of events to return

        Returns:
            List of SentimentEvent dataclass objects
        """
        symbol = symbol.upper()

        # Get asset from database
        asset = self.asset_repository.get_by_symbol(symbol)
        if not asset:
            logger.warning(f"Asset {symbol} not found in database")
            return []

        # Get sentiment events using repository
        events_sql = self.sentiment_event_repository.find_by_asset(asset.id, limit=limit)

        # Convert SQLModel objects to SentimentEvent dataclass objects
        sentiment_events = []
        for event_sql in events_sql:
            try:
                sentiment_event = convert_sentiment_event_sqlmodel_to_dataclass(event_sql)
                sentiment_events.append(sentiment_event)
            except Exception as e:
                logger.warning(f"Failed to convert sentiment event {event_sql.id}: {e}")
                continue

        return sentiment_events

    def is_news_stale(self, symbol: str, hours: int = 24) -> bool:
        """Check if news is stale using new architecture.

        Args:
            symbol: Stock symbol
            hours: TTL in hours (default: 24)

        Returns:
            True if news should be refreshed, False if recent news exists
        """
        from datetime import datetime, timedelta

        symbol = symbol.upper()

        # Get asset from database
        asset = self.asset_repository.get_by_symbol(symbol)
        if not asset:
            logger.warning(f"Asset {symbol} not found in database")
            return True  # No asset = definitely stale

        # Get news sentiment type IDs using repository
        news_type_ids = self.sentiment_type_repository.find_news_types()

        if not news_type_ids:
            logger.debug("No news sentiment types found in database")
            return True  # No news types = definitely stale

        # Get most recent created_at timestamp for this asset's news events using repository
        last_news_time = self.sentiment_event_repository.get_latest_news_time(
            asset.id,
            news_type_ids
        )

        if not last_news_time:
            # No news events found - definitely stale
            return True

        # Check if last news is older than TTL
        age = datetime.utcnow() - last_news_time
        is_stale = age > timedelta(hours=hours)

        logger.debug(
            f"News for {symbol}: last_news={last_news_time}, age={age}, "
            f"ttl={hours}h, stale={is_stale}"
        )

        return is_stale

    # ============================================================================
    # AGGREGATES OPERATIONS (Additional temporary delegations)
    # ============================================================================

    def fetch_minute_bars(self, symbol: str, from_datetime, to_datetime):
        """Fetch minute bars from Polygon using new architecture.

        Args:
            symbol: Stock symbol
            from_datetime: Start datetime
            to_datetime: End datetime

        Returns:
            List of minute bar data from PolygonAggregatesProvider
        """
        return self.polygon_aggregates_provider.fetch_minute_bars(
            symbol=symbol,
            from_datetime=from_datetime,
            to_datetime=to_datetime
        )

    def calculate_extended_hours_volume(self, symbol: str, trading_date, session: str = "afterhours"):
        """Calculate total volume for an extended hours session.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            trading_date: Trading date (not datetime - just the date)
            session: Session type - "premarket" or "afterhours"

        Returns:
            Total volume for the session, or None if error
        """
        return self.polygon_aggregates_provider.calculate_extended_hours_volume(
            symbol=symbol,
            trading_date=trading_date,
            session=session
        )

    def get_daily_aggregates(self, symbol: str, from_date, to_date):
        """Get daily aggregate bars for a symbol.

        Args:
            symbol: Stock symbol
            from_date: Start date
            to_date: End date

        Returns:
            List of daily bar data from PolygonAggregatesProvider
        """
        return self.polygon_aggregates_provider.get_daily_aggregates(
            symbol=symbol,
            from_date=from_date,
            to_date=to_date
        )

    def get_intraday_aggregates(self, symbol: str, date: str, timespan: str = 'minute', multiplier: int = 1):
        """Get intraday aggregate bars for a symbol.

        Args:
            symbol: Stock symbol
            date: Date string (YYYY-MM-DD)
            timespan: Timespan ('minute', 'hour', etc.)
            multiplier: Multiplier for timespan

        Returns:
            List of intraday bar data from PolygonAggregatesProvider
        """
        return self.polygon_aggregates_provider.get_intraday_aggregates(
            symbol=symbol,
            date=date,
            timespan=timespan,
            multiplier=multiplier
        )

    # ============================================================================
    # FED DATA OPERATIONS
    # ============================================================================

    def fed_bulk_upsert(self, fed_data_list):
        """Bulk insert or update Federal Reserve data using FedDataRepository.

        Args:
            fed_data_list: List of FedData dataclass objects to store

        Returns:
            Number of records successfully stored (inserted + updated)
        """
        from models.sqlmodel.fed_data_sqlmodel import FedDataSQLModel
        import json

        if not fed_data_list:
            return 0

        # Convert FedData dataclass objects to FedDataSQLModel
        sql_models = []
        for fed_data in fed_data_list:
            sql_model = FedDataSQLModel(
                id=fed_data.id if fed_data.id != 0 else None,
                data_type=fed_data.data_type,
                observation_date=fed_data.observation_date,
                value=float(fed_data.value),
                details=json.dumps(fed_data.details),
                created_at=fed_data.created_at,
                updated_at=fed_data.updated_at
            )
            sql_models.append(sql_model)

        # Use repository for upsert (returns dict with stats)
        upsert_stats = self.fed_data_repository.bulk_upsert(sql_models)
        return upsert_stats['inserted'] + upsert_stats['updated']

    def fed_get_latest_by_type(self, data_type: str):
        """Get the most recent observation for a specific FED data type.

        Args:
            data_type: Type of fed data ('inflation', 'inflation_expectations', 'treasury_yields')

        Returns:
            FedData dataclass object or None if not found
        """
        from models.dataclass.fed_data import FedData
        from decimal import Decimal
        import json

        # Use repository
        fed_sql = self.fed_data_repository.get_latest_by_type(data_type)

        if not fed_sql:
            return None

        # Convert SQLModel to FedData dataclass
        return FedData(
            id=fed_sql.id,
            data_type=fed_sql.data_type,
            observation_date=fed_sql.observation_date,
            value=Decimal(str(fed_sql.value)),
            details=json.loads(fed_sql.details) if fed_sql.details else {},
            created_at=fed_sql.created_at,
            updated_at=fed_sql.updated_at
        )

    def fed_get_recent_by_type(self, data_type: str, limit: int = 10):
        """Get recent observations for a specific FED data type.

        Args:
            data_type: Type of fed data
            limit: Maximum number of observations to return

        Returns:
            List of FedData objects ordered by observation_date DESC
        """
        # Get FED data using repository
        feds_sql = self.fed_data_repository.get_recent_by_type(data_type, limit=limit)

        # Convert SQLModel objects to FedData dataclass objects
        fed_data_list = []
        for fed_sql in feds_sql:
            try:
                fed_data = convert_fed_data_sqlmodel_to_dataclass(fed_sql)
                fed_data_list.append(fed_data)
            except Exception as e:
                logger.warning(f"Failed to convert FED data row: {e}")
                continue

        return fed_data_list

    def fed_get_all_latest(self):
        """Get the latest observation for each FED data type.

        Returns:
            Dictionary mapping data_type to latest FedData object
        """
        return {
            "inflation": self.fed_get_latest_by_type("inflation"),
            "inflation_expectations": self.fed_get_latest_by_type("inflation_expectations"),
            "treasury_yields": self.fed_get_latest_by_type("treasury_yields"),
        }

    # ============================================================================
    # SENTIMENT TYPE OPERATIONS (New architecture)
    # ============================================================================

    def get_all_sentiment_types(self, active_only: bool = False):
        """Get all sentiment types using new architecture.

        Args:
            active_only: If True, return only active types

        Returns:
            List of SentimentType objects
        """
        from models.dataclass.sentiment_type import SentimentType
        import json

        # Use repository instead of direct SQL
        if active_only:
            types_sql = self.sentiment_type_repository.find_all_active()
        else:
            types_sql = self.sentiment_type_repository.find_all()

        # Convert SQLModel objects to SentimentType dataclass objects
        sentiment_types = []
        for type_sql in types_sql:
            try:
                # Parse parameters JSON
                parameters = json.loads(type_sql.parameters) if type_sql.parameters else {}

                # Create SentimentType dataclass
                sentiment_type = SentimentType(
                    id=type_sql.id,
                    name=type_sql.name,
                    description=type_sql.description or "",
                    category=type_sql.category or "",
                    parameters=parameters,
                    created_at=type_sql.created_at,
                    is_active=type_sql.is_active
                )
                sentiment_types.append(sentiment_type)
            except Exception as e:
                logger.warning(f"Failed to parse sentiment type {type_sql.id}: {e}")
                continue

        return sentiment_types

    # ============================================================================
    # MARKET CONTEXT SUPPORT - Convenience methods for MarketContextService
    # ============================================================================

    def get_market_status(self) -> Optional[dict]:
        """Get current market status from Polygon API.

        Returns:
            Dictionary with market status data including:
            - market: 'open', 'closed', or 'extended-hours'
            - serverTime: Current server time
            - exchanges: Status of different exchanges
        """
        try:
            return self.polygon_market_status_provider.fetch_market_status()
        except Exception as e:
            logger.error(f"Error fetching market status: {e}")
            return None

    def get_market_by_code(self, code: str) -> Optional['Market']:
        """Get market by exchange code, returning domain model.

        Args:
            code: Market code (e.g., 'XNYS', 'XNAS')

        Returns:
            Market domain model or None if not found
        """
        from models.dataclass.market import Market

        market_sql = self.market_repository.get_by_code(code)
        if not market_sql:
            return None

        # Convert MarketSQLModel to Market domain model
        return Market(
            id=market_sql.id,
            code=market_sql.code,
            name=market_sql.name,
            country=market_sql.country,
            timezone=market_sql.timezone,
            currency=market_sql.currency,
            created_at=market_sql.created_at,
            updated_at=market_sql.updated_at,
            premarket_start_time=market_sql.premarket_start_time,
            premarket_end_time=market_sql.premarket_end_time,
            regular_open_time=market_sql.regular_open_time,
            regular_close_time=market_sql.regular_close_time,
            afterhours_start_time=market_sql.afterhours_start_time,
            afterhours_end_time=market_sql.afterhours_end_time,
            is_active=market_sql.is_active
        )

    def get_market_holidays(self, force_refresh: bool = False) -> List['MarketHoliday']:
        """Get market holidays with cache/refresh logic.

        Holidays are fetched from Polygon's /v1/marketstatus/upcoming endpoint.
        Uses repository for persistence.

        Args:
            force_refresh: If True, fetch fresh data from API

        Returns:
            List of MarketHoliday domain models
        """
        from models.dataclass.market_holiday import MarketHoliday
        from datetime import datetime

        # Check if we need to refresh
        if force_refresh or self._is_holidays_data_stale():
            logger.debug("Fetching fresh holidays from API")
            start_time = datetime.now()

            # Fetch from Polygon API
            holidays_data = self.polygon_market_status_provider.fetch_upcoming_holidays()

            if holidays_data:
                # Convert to SQLModel and store
                from models.sqlmodel.market_holiday_sqlmodel import MarketHolidaySQLModel

                # Clear old holidays
                self.market_holiday_repository.clear_all()

                # Bulk save new holidays
                holidays_sql = [
                    MarketHolidaySQLModel(
                        date=h.date,
                        name=h.name,
                        status=h.status.value  # Convert enum to string
                    )
                    for h in holidays_data
                ]
                self.market_holiday_repository.bulk_save(holidays_sql)

                # Record metadata
                self.record_bulk_operation_metadata(
                    operation_type=DataUpdateMetadataType.MARKET_HOLIDAYS,
                    operation_subtype="fetch",
                    start_time=start_time,
                    total_items=len(holidays_data),
                    processed_items=len(holidays_data),
                    failed_items=0,
                    api_calls_made=1
                )

                logger.info(f"Stored {len(holidays_data)} holidays")
                return holidays_data
            else:
                logger.warning("Failed to fetch holidays, returning cached data")

        # Use cached data from repository
        logger.debug("Using cached holidays")
        holidays_sql = self.market_holiday_repository.get_all_holidays()

        # Convert to domain models
        return [
            MarketHoliday(
                date=h.date,
                name=h.name,
                status=h.status
            )
            for h in holidays_sql
        ]

    def _is_holidays_data_stale(self) -> bool:
        """Check if market holidays data is stale (30-day TTL)."""
        from datetime import datetime, timedelta

        # Get latest metadata for market holidays
        metadata = self.metadata_repository.get_latest_by_operation(
            operation_type=DataUpdateMetadataType.MARKET_HOLIDAYS.value
        )

        if not metadata or not metadata.completed_at:
            return True

        # 30-day TTL for holidays (published well in advance)
        ttl_seconds = 30 * 24 * 60 * 60
        age_seconds = (datetime.utcnow() - metadata.completed_at).total_seconds()

        return age_seconds > ttl_seconds

    # ============================================================================
    # METADATA TRACKING UTILITIES
    # ============================================================================

    def record_bulk_operation_metadata(
        self,
        operation_type: DataUpdateMetadataType,
        operation_subtype: str,
        start_time: datetime,
        total_items: int,
        processed_items: int,
        failed_items: int = 0,
        api_calls_made: int = 1
    ) -> None:
        """Record metadata for bulk operations - ONLY for market_snapshots, tickers, fundamentals, and market_holidays.

        IMPORTANT: This method should ONLY be called by four bulk operations:
        1. Market snapshots (market update command)
        2. Tickers (bootstrap_assets)
        3. Fundamentals (bootstrap_fundamentals)
        4. Market holidays (get_market_holidays with refresh)

        All other operations (providers, markets, universes) should NOT use this.

        This utility standardizes metadata tracking across the four bulk operations.
        Automatically handles timing, status determination, and metadata persistence.

        Args:
            operation_type: MUST be MARKET_SNAPSHOTS, TICKERS, FUNDAMENTALS, or MARKET_HOLIDAYS
            operation_subtype: Subtype (e.g., "bootstrap", "bulk_update", "fetch")
            start_time: When the operation started
            total_items: Total number of items processed
            processed_items: Number of items successfully processed
            failed_items: Number of items that failed (default: 0)
            api_calls_made: Number of API calls made (default: 1)
        """
        from models.sqlmodel.data_update_metadata_sqlmodel import DataUpdateMetadataSQLModel
        from models.dataclass.data_update_metadata import OperationStatus

        # Determine status based on success/failure
        # COMPLETED: Got data from API and processed it successfully (even if nothing new)
        # PARTIAL: Got data but some items had real errors/failures
        # FAILED: Couldn't process any data due to errors
        if processed_items > 0 and failed_items == 0:
            status = OperationStatus.COMPLETED
        elif processed_items > 0 and failed_items > 0:
            status = OperationStatus.PARTIAL
        else:
            # No items processed - could be API failure or no data
            status = OperationStatus.FAILED

        metadata = DataUpdateMetadataSQLModel(
            operation_type=operation_type.value,
            operation_subtype=operation_subtype,
            started_at=start_time,
            completed_at=datetime.now(),
            status=status.value,
            total_items=total_items,
            processed_items=processed_items,
            failed_items=failed_items,
            api_calls_made=api_calls_made
        )
        self.metadata_repository.save(metadata)
        logger.debug(
            f"Recorded metadata: {operation_type.value}.{operation_subtype} "
            f"({processed_items}/{total_items} items, {api_calls_made} API calls)"
        )

    # ============================================================================
    # SCREENER SUPPORT
    # ============================================================================

    def execute_screener_query(self, query: str) -> List[Dict]:
        """Execute a raw SQL screener query and return results as list of dicts.

        Args:
            query: SQL query string to execute

        Returns:
            List of dictionaries, one per row
        """
        from sqlalchemy import text

        result = self.session.execute(text(query))

        # Convert rows to dicts
        rows = []
        for row in result:
            rows.append(dict(row._mapping))

        return rows

    def execute_query(self, query: str, params: tuple = None) -> List[tuple]:
        """Execute parameterized SQL query and return raw rows as tuples.

        Args:
            query: SQL query with ? placeholders
            params: Tuple of parameter values

        Returns:
            List of row tuples
        """
        from sqlalchemy import text

        # SQLAlchemy uses :param1, :param2 not ? placeholders
        # Convert ? to named parameters
        converted_query = query
        param_count = query.count('?')
        for i in range(param_count):
            param_name = f'param{i}'
            converted_query = converted_query.replace('?', f':{param_name}', 1)

        # Build params dict
        params_dict = {}
        if params:
            for i, value in enumerate(params):
                params_dict[f'param{i}'] = value

        result = self.session.execute(text(converted_query), params_dict)
        return [tuple(row) for row in result]
