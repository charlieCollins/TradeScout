"""DataService V2 - New architecture with Repository + DAO + Cache-Aside pattern.

This is the new DataService implementation demonstrating the layered architecture.
It coexists with the old data_service.py during the strangler fig migration.

Architecture:
  DataService → CacheService → Repository → DAO (SQLModel) → Database
                      ↓
                API Provider
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlmodel import Session
from repositories.asset_repository import AssetRepository
from repositories.market_repository import MarketRepository
from repositories.fundamentals_repository import FundamentalsRepository
from repositories.provider_repository import ProviderRepository
from repositories.universe_repository import UniverseRepository
from repositories.asset_price_repository import AssetPriceRepository
from repositories.data_update_metadata_repository import DataUpdateMetadataRepository
from services.cache_service import CacheService, CacheConfig
from api.providers.polygon_tickers_provider import PolygonTickersProvider
from models.sqlmodel.asset_sqlmodel import AssetSQLModel
from models.sqlmodel.market_sqlmodel import MarketSQLModel
from models.sqlmodel.fundamentals_sqlmodel import FundamentalsSQLModel
from models.sqlmodel.provider_sqlmodel import ProviderSQLModel
from models.sqlmodel.universe_sqlmodel import UniverseSQLModel, UniverseMembershipSQLModel
from models.sqlmodel.asset_price_sqlmodel import AssetPriceSQLModel
from models.dataclass.data_update_metadata import DataUpdateMetadataType

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

        from repositories.fed_data_repository import FedDataRepository
        self.fed_data_repository = FedDataRepository(session)
        self.metadata_repository = DataUpdateMetadataRepository(session)

        # Initialize gap-related repositories
        from repositories.gap_candidate_repository import GapCandidateRepository
        from repositories.gap_candidate_result_repository import GapCandidateResultRepository
        from repositories.market_holiday_repository import MarketHolidayRepository
        from repositories.gap_result_news_repository import GapResultNewsRepository
        from repositories.sentiment_type_repository import SentimentTypeRepository
        from repositories.sentiment_event_repository import SentimentEventRepository

        self.gap_candidate_repository = GapCandidateRepository(session)
        self.gap_candidate_result_repository = GapCandidateResultRepository(session)
        self.market_holiday_repository = MarketHolidayRepository(session)
        self.gap_result_news_repository = GapResultNewsRepository(session)
        self.sentiment_type_repository = SentimentTypeRepository(session)
        self.sentiment_event_repository = SentimentEventRepository(session)

        # Initialize API providers
        self.polygon_provider = PolygonTickersProvider(polygon_api_key)

        from api.providers.polygon_snapshot_provider import PolygonSnapshotProvider
        from api.providers.polygon_aggregates_provider import PolygonAggregatesProvider
        from api.providers.polygon_news_provider import PolygonNewsProvider
        from api.providers.polygon_markets_provider import PolygonMarketsProvider
        from api.providers.polygon_market_status_provider import PolygonMarketStatusProvider

        self.polygon_snapshot_provider = PolygonSnapshotProvider(polygon_api_key)
        self.polygon_aggregates_provider = PolygonAggregatesProvider(polygon_api_key)
        self.polygon_news_provider = PolygonNewsProvider(polygon_api_key)
        self.polygon_markets_provider = PolygonMarketsProvider(polygon_api_key)
        self.polygon_market_status_provider = PolygonMarketStatusProvider(polygon_api_key)

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
    ) -> Optional[AssetSQLModel]:
        """Get asset with cache-aside pattern.

        This implements the on-demand fetching requirement:
        1. Check local store (via cache → repository)
        2. If missing/outdated → fetch from API (via provider)
        3. Update local store (via cache → repository)
        4. Return asset

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            force_refresh: If True, bypass cache and always fetch fresh

        Returns:
            Asset if found, None otherwise
        """
        return self.asset_cache.get_or_fetch(
            key=symbol.upper(),
            fetch_fn=lambda: self._fetch_asset_from_api(symbol),
            force_refresh=force_refresh
        )

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
            # Fetch from Polygon provider (returns old Asset dataclass)
            # TODO: Update provider to return AssetSQLModel directly
            # For now, we'll need to convert

            # Get market mapping for provider
            # TODO: Implement this properly when we migrate markets
            market_code_to_id = {
                "XNYS": 1,  # Placeholder
                "XNAS": 2,  # Placeholder
            }

            asset_dataclass = self.polygon_provider.fetch_ticker_details(
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
    ) -> Optional[MarketSQLModel]:
        """Get market by code with cache-aside pattern.

        Markets are reference data that rarely changes, so they use a longer TTL (7 days).

        Args:
            code: Market code (e.g., 'XNYS', 'NASDAQ')
            force_refresh: If True, bypass cache and always fetch fresh

        Returns:
            Market if found, None otherwise
        """
        # Markets are simpler - they're already in database from bootstrap
        # So cache just returns from repository (no API fetch for markets)
        return self.market_repository.get_by_code(code)

    def get_all_markets(self, active_only: bool = True) -> List[MarketSQLModel]:
        """Get all active markets.

        Args:
            active_only: If True, return only active markets (default: True)
                        Note: Currently only active markets are supported

        Returns:
            List of all active markets
        """
        return self.market_repository.find_all_active()

    def get_us_markets(self) -> List[MarketSQLModel]:
        """Get all active US markets.

        Returns:
            List of US markets
        """
        return self.market_repository.find_us_markets()

    # ============================================================================
    # FUNDAMENTALS OPERATIONS - Phase 3: Fundamentals entity migrated
    # ============================================================================

    def get_fundamentals(
        self, asset_id: int, force_refresh: bool = False
    ) -> Optional[FundamentalsSQLModel]:
        """Get fundamentals for an asset.

        Args:
            asset_id: Asset database ID
            force_refresh: If True, bypass cache and always fetch fresh

        Returns:
            Fundamentals if found, None otherwise
        """
        # Fundamentals are already in database from bootstrap
        return self.fundamentals_repository.get_by_asset_id(asset_id)

    def find_by_market_cap(
        self, min_cap: int, max_cap: Optional[int] = None
    ) -> List[FundamentalsSQLModel]:
        """Find assets by market cap range.

        Critical for gap trading screeners (min $300M market cap required).

        Args:
            min_cap: Minimum market cap in dollars
            max_cap: Maximum market cap in dollars (optional)

        Returns:
            List of fundamentals meeting criteria
        """
        return self.fundamentals_repository.find_by_market_cap_range(
            min_cap=min_cap,
            max_cap=max_cap
        )

    def find_gap_trading_candidates(self) -> List[FundamentalsSQLModel]:
        """Find assets suitable for gap trading (min $300M market cap).

        Business rule: Gap trading requires sufficient liquidity.

        Returns:
            List of fundamentals meeting gap trading criteria
        """
        return self.fundamentals_repository.find_for_gap_trading()

    def find_by_sector(self, sector: str) -> List[FundamentalsSQLModel]:
        """Find assets by sector.

        Args:
            sector: Sector name (e.g., 'Technology', 'Healthcare')

        Returns:
            List of fundamentals in the sector
        """
        return self.fundamentals_repository.find_by_sector(sector)

    def get_all_sectors(self) -> List[str]:
        """Get list of all sectors.

        Returns:
            List of sector names
        """
        return self.fundamentals_repository.get_all_sectors()

    # ============================================================================
    # PROVIDER OPERATIONS - Phase 4: Providers entity migrated
    # ============================================================================

    def get_provider(self, name: str) -> Optional[ProviderSQLModel]:
        """Get provider by name.

        Args:
            name: Provider name (e.g., 'polygon', 'yfinance')

        Returns:
            Provider if found, None otherwise
        """
        return self.provider_repository.get_by_name(name)

    def get_all_providers(self) -> List[ProviderSQLModel]:
        """Get all active providers.

        Returns:
            List of active providers
        """
        return self.provider_repository.find_all_active()

    # ============================================================================
    # UNIVERSE OPERATIONS - Phase 5: Universes entity migrated
    # ============================================================================

    def get_universe(self, name: str) -> Optional[UniverseSQLModel]:
        """Get universe by name.

        Universes are INTERNAL-ONLY - not fetched from APIs.

        Args:
            name: Universe name (e.g., 'gap_trading_universe')

        Returns:
            Universe if found, None otherwise
        """
        return self.universe_repository.get_by_name(name)

    def get_all_universes(self) -> List[UniverseSQLModel]:
        """Get all universes.

        Returns:
            List of all universes
        """
        return self.universe_repository.find_all()

    def get_active_universe(self) -> Optional[UniverseSQLModel]:
        """Get the currently active universe.

        Returns:
            Active universe or None
        """
        return self.universe_repository.get_active_universe()

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
    ) -> List[UniverseMembershipSQLModel]:
        """Get memberships for a universe.

        Args:
            universe_name: Universe name

        Returns:
            List of memberships
        """
        return self.universe_repository.get_memberships_by_universe_name(universe_name)

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

    def get_latest_price(self, symbol: str) -> Optional[AssetPriceSQLModel]:
        """Get most recent price for a symbol.

        Critical for gap analysis.

        Args:
            symbol: Stock symbol

        Returns:
            Latest price or None
        """
        return self.asset_price_repository.get_latest_by_symbol(symbol)

    def get_latest_prices(
        self, symbols: List[str]
    ) -> List[AssetPriceSQLModel]:
        """Get latest prices for multiple symbols.

        Batch query for gap screeners.

        Args:
            symbols: List of stock symbols

        Returns:
            List of latest prices
        """
        return self.asset_price_repository.get_latest_for_symbols(symbols)

    def find_prices_with_gaps(
        self, min_gap_percent: float = 2.0
    ) -> List[AssetPriceSQLModel]:
        """Find assets with significant gaps.

        Core gap trading screener query.

        Args:
            min_gap_percent: Minimum gap percentage (default: 2%)

        Returns:
            List of assets with gaps
        """
        return self.asset_price_repository.find_with_gaps(min_gap_percent)

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
        from models.dataclass.stats import MarketSnapshotUpdateStats

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

        # market_snapshot.tickers is a dict[symbol -> TickerSnapshot]
        for symbol, ticker_snapshot in market_snapshot.tickers.items():
            symbol = symbol.upper()  # Normalize symbol

            # Look up asset_id
            asset = self.asset_repository.get_by_symbol(symbol)
            if not asset:
                stats_unmatched += 1
                continue

            stats_matched += 1

            # Transform to AssetPrice
            asset_price = self.transform_ticker_snapshot_to_asset_price(
                symbol=symbol,
                asset_id=asset.id,
                ticker_snapshot=ticker_snapshot
            )

            if asset_price:
                asset_prices.append(asset_price)
            else:
                stats_invalid += 1

        # Batch save to database (only saves new tuples)
        saved_count = 0
        if asset_prices:
            saved_count = self.batch_save_asset_prices(asset_prices)
            logger.info(f"Saved {saved_count} new asset prices to database (skipped {len(asset_prices) - saved_count} duplicates, {stats_invalid} invalid)")

            # Record metadata
            self.record_bulk_operation_metadata(
                operation_type=DataUpdateMetadataType.MARKET_SNAPSHOTS,
                operation_subtype="refresh",
                start_time=start_time,
                total_items=len(market_snapshot.tickers),
                processed_items=saved_count,
                failed_items=stats_invalid
            )
        else:
            logger.warning(f"No valid asset prices to save ({stats_invalid} invalid)")

        return MarketSnapshotUpdateStats(
            total_tickers=len(market_snapshot.tickers),
            matched_symbols=stats_matched,
            unmatched_symbols=stats_unmatched,
            transformed=len(asset_prices),
            invalid=stats_invalid,
            saved=saved_count,
            duplicates=len(asset_prices) - saved_count,
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
        from models.dataclass.results import NewsResult
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
        from models.sqlmodel.sentiment_event_sqlmodel import SentimentEventSQLModel
        from models.dataclass.sentiment_event import SentimentEvent
        from sqlmodel import select
        from datetime import date, timedelta, time as dt_time
        import json
        from decimal import Decimal

        symbol = symbol.upper()

        # Get asset from database using repository
        asset = self.asset_repository.get_by_symbol(symbol)
        if not asset:
            logger.warning(f"Asset {symbol} not found in database")
            return None

        # Query sentiment events using SQLModel
        start_date = date.today() - timedelta(days=time_window_days)

        statement = select(SentimentEventSQLModel).where(
            SentimentEventSQLModel.asset_id == asset.id,
            SentimentEventSQLModel.event_date >= start_date
        ).order_by(SentimentEventSQLModel.event_date.desc())  # type: ignore

        events_sql = self.session.exec(statement).all()

        # Limit to most recent events
        events_sql = events_sql[:limit] if events_sql else []

        # Convert SQLModel objects to SentimentEvent dataclass objects
        sentiment_events = []
        for event_sql in events_sql:
            try:
                # Parse details JSON
                details = json.loads(event_sql.details) if event_sql.details else {}

                # Create SentimentEvent dataclass
                sentiment_event = SentimentEvent(
                    id=event_sql.id,
                    asset_id=event_sql.asset_id,
                    sentiment_type_id=event_sql.sentiment_type_id,
                    event_date=event_sql.event_date,
                    event_time=event_sql.event_time,
                    session=event_sql.session,
                    value=Decimal(str(event_sql.value)) if event_sql.value else Decimal("0"),
                    magnitude=event_sql.magnitude or "small",
                    details=details,
                    created_at=event_sql.created_at
                )
                sentiment_events.append(sentiment_event)
            except Exception as e:
                logger.warning(f"Failed to parse sentiment event {event_sql.id}: {e}")
                continue

        if not sentiment_events:
            logger.debug(f"No sentiment events found for {symbol} in the last {time_window_days} days")
            return None

        # Use SentimentAnalyzer to calculate score
        analyzer = SentimentAnalyzer(time_window_days=time_window_days)
        return analyzer.calculate_sentiment_score(symbol, sentiment_events)

    # ============================================================================
    # BOOTSTRAP OPERATIONS (Temporary delegations during migration)
    # ============================================================================
    #
    # Bootstrap operations are complex, large-scale operations that fetch from APIs
    # and populate the database. They delegate to old architecture during migration.

    def bootstrap_providers(self) -> int:
        """Bootstrap data providers into database using new architecture.

        Currently stores the hardcoded Polygon provider to the database.
        In the future, this could be expanded to support multiple providers
        (YFinance, Alpha Vantage, Finnhub, etc.).

        Returns:
            Number of providers stored successfully
        """
        logger.info("Bootstrapping providers")

        # Check if Polygon provider already exists
        existing = self.provider_repository.get_by_name("polygon")
        if existing:
            logger.info("Provider 'polygon' already exists - skipping")
            return 0

        # Create Polygon provider
        from datetime import datetime

        provider_sql = ProviderSQLModel(
            id=1,
            name="polygon",
            display_name="Polygon.io",
            base_url="https://api.polygon.io",
            api_key_required=True,
            is_active=True,
            created_at=datetime.now()
        )

        # Save to database using repository
        self.provider_repository.save(provider_sql)

        logger.info("Bootstrapped 1 provider (Polygon)")
        return 1

    def bootstrap_markets(self, asset_class: str = "stocks", locale: str = "us") -> int:
        """Bootstrap markets/exchanges from Polygon API using new architecture.

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
        provider_count = self.provider_repository.count_all()
        if provider_count == 0:
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

        # Convert Market dataclass → MarketSQLModel
        market_sql_list = []
        for market in markets:
            market_sql = MarketSQLModel(
                id=market.id if market.id != 0 else None,
                code=market.code,
                name=market.name,
                asset_class=market.asset_class,
                locale=market.locale,
                is_active=market.is_active,
                created_at=market.created_at
            )
            market_sql_list.append(market_sql)

        # Bulk save using repository
        stored_count = self.market_repository.bulk_save(market_sql_list)

        logger.info(f"Bootstrapped {stored_count} markets")
        return stored_count

    def bootstrap_assets(
        self,
        market: str = "stocks",
        active: bool = True,
        progress=None
    ):
        """Bootstrap all assets from Polygon tickers API using new architecture.

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
        from dataclasses import replace
        from models.dataclass.results import BootstrapResult

        start_time = time.time()
        logger.info(
            f"Bootstrapping assets from Polygon (market={market}, active={active})"
        )

        # Check prerequisites
        provider_count = self.provider_repository.count_all()
        if provider_count == 0:
            raise RuntimeError(
                "Cannot bootstrap assets: No providers in database. Run 'bootstrap-providers' first."
            )

        market_count = self.market_repository.count_all()
        if market_count == 0:
            raise RuntimeError(
                "Cannot bootstrap assets: No markets in database. Run 'bootstrap-markets' first."
            )

        # Get Polygon provider ID
        polygon_provider = self.provider_repository.get_by_name("polygon")
        if not polygon_provider:
            raise RuntimeError(
                "Cannot bootstrap assets: Polygon provider not found in database."
            )

        # Create market_code to market_id mapping
        all_markets = self.market_repository.get_all(active_only=False)
        market_code_to_id = {m.code: m.id for m in all_markets}

        # Fetch all tickers from API with market mapping
        raw_assets = self.polygon_provider.fetch_all_tickers(
            market=market, active=active, market_code_to_id=market_code_to_id
        )

        # Fix provider_id for all assets (provider uses placeholder provider_id)
        assets = [
            replace(asset, provider_id=polygon_provider.id)
            for asset in raw_assets
        ]

        if not assets:
            duration = time.time() - start_time
            return BootstrapResult(
                operation="assets",
                total_items=0,
                successful=0,
                failed=0,
                duration_seconds=duration
            )

        # Convert Asset dataclass → AssetSQLModel
        asset_sql_list = []
        for asset in assets:
            asset_sql = AssetSQLModel(
                id=asset.id if asset.id != 0 else None,
                symbol=asset.symbol,
                name=asset.name,
                asset_type=asset.asset_type.value if hasattr(asset.asset_type, 'value') else asset.asset_type,
                asset_class=asset.asset_class.value if hasattr(asset.asset_class, 'value') else asset.asset_class,
                is_active=asset.is_active,
                provider_id=asset.provider_id,
                market_id=asset.market_id,
                created_at=asset.created_at,
                updated_at=asset.updated_at
            )
            asset_sql_list.append(asset_sql)

        # Bulk save using repository
        stored_count = self.asset_repository.bulk_save(asset_sql_list)

        duration = time.time() - start_time
        logger.info(f"Bootstrapped {stored_count} assets in {duration:.1f}s")

        # Record metadata for bulk ticker operation
        from datetime import datetime
        self.record_bulk_operation_metadata(
            operation_type=DataUpdateMetadataType.TICKERS,
            operation_subtype="bootstrap",
            start_time=datetime.fromtimestamp(start_time),
            total_items=len(assets),
            processed_items=stored_count,
            failed_items=len(assets) - stored_count,
            api_calls_made=1
        )

        return BootstrapResult(
            operation="assets",
            total_items=len(assets),
            successful=stored_count,
            failed=len(assets) - stored_count,
            duration_seconds=duration
        )

    def bootstrap_fundamentals(self, limit: Optional[int] = None, progress=None):
        """Bootstrap fundamentals for all assets in database using new architecture.

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
        from models.dataclass.results import BootstrapResult
        from models.asset_fundamentals import AssetFundamentals
        from models.sqlmodel.fundamentals_sqlmodel import FundamentalsSQLModel

        start_time = time.time()
        logger.info(f"Bootstrapping fundamentals (limit={limit})")

        # Get all active assets from database
        assets = self.asset_repository.find_all_active(limit=limit)

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

        for i, asset_sql in enumerate(assets, start=1):
            try:
                # Fetch raw ticker data from Polygon
                ticker_data = self.polygon_provider.fetch_ticker_details_raw(asset_sql.symbol)
                if not ticker_data:
                    fetch_errors.append(f"{asset_sql.symbol}: No data from API")
                    continue

                # Convert to AssetFundamentals using model's class method
                fundamentals = AssetFundamentals.from_polygon_data(
                    asset_id=asset_sql.id,
                    provider_id=1,  # Polygon provider
                    polygon_data=ticker_data,
                )
                fundamentals_data[asset_sql.id] = fundamentals
                logger.debug(f"Successfully parsed fundamentals for {asset_sql.symbol}")

            except Exception as e:
                fetch_errors.append(f"{asset_sql.symbol}: {str(e)}")
                logger.error(f"Error fetching fundamentals for {asset_sql.symbol}: {e}")

            if progress and i % 10 == 0:
                progress.update_progress(i, total_assets)

        if progress:
            progress.complete_operation()

        # Phase 2: Bulk save all fundamentals (single database transaction)
        insert_errors = []
        successful_count = 0

        if fundamentals_data:
            logger.info(f"Saving {len(fundamentals_data)} fundamentals to database...")

            if progress:
                progress.start_operation("Saving to database", len(fundamentals_data))

            # Convert to SQLModel
            fundamentals_sql_list = []
            for asset_id, fundamentals in fundamentals_data.items():
                try:
                    fundamentals_sql = FundamentalsSQLModel(
                        id=fundamentals.id if fundamentals.id != 0 else None,
                        asset_id=fundamentals.asset_id,
                        provider_id=fundamentals.provider_id,
                        market_cap=fundamentals.market_cap,
                        shares_outstanding=fundamentals.shares_outstanding,
                        sector=fundamentals.sector,
                        industry=fundamentals.industry,
                        description=fundamentals.description,
                        employees=fundamentals.employees,
                        headquarters=fundamentals.headquarters,
                        homepage_url=fundamentals.homepage_url,
                        created_at=fundamentals.created_at,
                        updated_at=fundamentals.updated_at
                    )
                    fundamentals_sql_list.append(fundamentals_sql)
                except Exception as e:
                    insert_errors.append(f"asset_id {asset_id}: {str(e)}")

            # Bulk save using repository
            if fundamentals_sql_list:
                successful_count = self.fundamentals_repository.bulk_save(fundamentals_sql_list)

            if progress:
                progress.complete_operation()

        duration = time.time() - start_time
        logger.info(
            f"Bootstrapped {successful_count}/{total_assets} fundamentals in {duration:.1f}s"
        )

        # Record metadata for bulk fundamentals operation
        from datetime import datetime
        self.record_bulk_operation_metadata(
            operation_type=DataUpdateMetadataType.FUNDAMENTALS,
            operation_subtype="bootstrap",
            start_time=datetime.fromtimestamp(start_time),
            total_items=total_assets,
            processed_items=successful_count,
            failed_items=total_assets - successful_count,
            api_calls_made=total_assets
        )

        return BootstrapResult(
            operation="fundamentals",
            total_items=total_assets,
            successful=successful_count,
            failed=total_assets - successful_count,
            fetch_errors=fetch_errors,
            insert_errors=insert_errors,
            duration_seconds=duration
        )

    # ============================================================================
    # UNIVERSE FILTERING HELPERS
    # ============================================================================

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
        """Check if asset meets inclusion criteria and doesn't meet exclusion criteria."""
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
        """Check if asset meets all inclusion criteria."""
        import re

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
        """Check if asset meets any exclusion criteria (should be excluded)."""
        import re

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
    # BOOTSTRAP OPERATIONS - UNIVERSES
    # ============================================================================

    def bootstrap_universes(self, universe_name: str = "default_universe", force_refresh: bool = False):
        """Bootstrap a universe by filtering assets based on configuration criteria using new architecture.

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
        from config.universe_loader import get_config_loader

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
        asset_count = self.asset_repository.count_active()
        if asset_count == 0:
            raise RuntimeError(
                "Cannot bootstrap universes: No assets in database. Run 'bootstrap-tickers' first."
            )

        # Check if this specific universe exists
        # Note: Universe freshness checking removed - use force_refresh=True to always rebuild
        if not force_refresh:
            universe_record = self.universe_repository.get_by_name(universe_name)
            if universe_record:
                # Universe exists - optionally skip if you want to avoid rebuilding
                # For now, we'll always rebuild to ensure data is current
                pass

        # Fetch all assets with fundamentals and market data
        all_assets = self.universe_repository.get_assets_with_fundamentals()

        if not all_assets:
            raise RuntimeError(
                "Cannot bootstrap universes: No assets with fundamentals found."
            )

        # Apply filtering criteria
        filtered_assets = self._apply_universe_filters(all_assets, config)

        logger.info(
            f"Filtered {len(all_assets)} assets down to {len(filtered_assets)} for universe '{universe_name}'"
        )

        # Create or update Universe record
        universe_record = self.universe_repository.upsert_universe(
            name=universe_name,
            description=config.get("description", ""),
            is_active=True
        )

        # Clear old memberships
        self.universe_repository.clear_memberships(universe_record.id)

        # Add new memberships (asset_ids only)
        asset_ids = [asset["id"] for asset in filtered_assets]
        memberships_added = self.universe_repository.bulk_add_memberships(
            universe_id=universe_record.id,
            asset_ids=asset_ids
        )

        logger.info(
            f"Bootstrapped universe '{universe_name}': {memberships_added} memberships added"
        )

        return {
            "total_assets": len(all_assets),
            "filtered_assets": len(filtered_assets),
            "memberships_added": memberships_added
        }

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
        from models.database_stats import DatabaseStats
        from models.sqlmodel.asset_sqlmodel import AssetSQLModel
        from models.sqlmodel.market_sqlmodel import MarketSQLModel
        from models.sqlmodel.asset_price_sqlmodel import AssetPriceSQLModel
        from models.sqlmodel.universe_sqlmodel import UniverseSQLModel, UniverseMembershipSQLModel
        from models.sqlmodel.fundamentals_sqlmodel import FundamentalsSQLModel
        from sqlmodel import func, select

        # Get table counts using SQLModel
        table_counts = {}

        # Count assets
        stmt = select(func.count(AssetSQLModel.id))
        table_counts["assets"] = self.session.exec(stmt).first() or 0

        # Count markets
        stmt = select(func.count(MarketSQLModel.id))
        table_counts["markets"] = self.session.exec(stmt).first() or 0

        # Count asset_prices
        stmt = select(func.count(AssetPriceSQLModel.id))
        table_counts["asset_prices"] = self.session.exec(stmt).first() or 0

        # Count universes
        stmt = select(func.count(UniverseSQLModel.id))
        table_counts["universes"] = self.session.exec(stmt).first() or 0

        # Count universe_memberships
        stmt = select(func.count(UniverseMembershipSQLModel.id))
        table_counts["universe_memberships"] = self.session.exec(stmt).first() or 0

        # Count fundamentals
        stmt = select(func.count(FundamentalsSQLModel.id))
        table_counts["fundamentals"] = self.session.exec(stmt).first() or 0

        # Get total records
        total_records = sum(table_counts.values())

        # Get latest update time across all entities
        latest_updates = []

        stmt = select(func.max(AssetSQLModel.updated_at))
        asset_update = self.session.exec(stmt).first()
        if asset_update:
            latest_updates.append(asset_update)

        stmt = select(func.max(FundamentalsSQLModel.last_updated))
        fund_update = self.session.exec(stmt).first()
        if fund_update:
            latest_updates.append(fund_update)

        last_updated = max(latest_updates) if latest_updates else None

        return DatabaseStats(
            database_path="data/tradescout.db",
            schema_version="2.0",  # New architecture
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
                return None

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
        from models.sqlmodel.sentiment_event_sqlmodel import SentimentEventSQLModel
        from models.dataclass.sentiment_event import SentimentEvent
        from sqlmodel import select
        import json
        from decimal import Decimal

        symbol = symbol.upper()

        # Get asset from database
        asset = self.asset_repository.get_by_symbol(symbol)
        if not asset:
            logger.warning(f"Asset {symbol} not found in database")
            return []

        # Query sentiment events using SQLModel
        statement = select(SentimentEventSQLModel).where(
            SentimentEventSQLModel.asset_id == asset.id
        ).order_by(
            SentimentEventSQLModel.event_date.desc(),  # type: ignore
            SentimentEventSQLModel.event_time.desc()  # type: ignore
        ).limit(limit)

        events_sql = self.session.exec(statement).all()

        # Convert SQLModel objects to SentimentEvent dataclass objects
        sentiment_events = []
        for event_sql in events_sql:
            try:
                # Parse details JSON
                details = json.loads(event_sql.details) if event_sql.details else {}

                # Create SentimentEvent dataclass
                sentiment_event = SentimentEvent(
                    id=event_sql.id,
                    asset_id=event_sql.asset_id,
                    sentiment_type_id=event_sql.sentiment_type_id,
                    event_date=event_sql.event_date,
                    event_time=event_sql.event_time,
                    session=event_sql.session,
                    value=Decimal(str(event_sql.value)) if event_sql.value else Decimal("0"),
                    magnitude=event_sql.magnitude or "small",
                    details=details,
                    created_at=event_sql.created_at
                )
                sentiment_events.append(sentiment_event)
            except Exception as e:
                logger.warning(f"Failed to parse sentiment event {event_sql.id}: {e}")
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
        from models.sqlmodel.sentiment_event_sqlmodel import SentimentEventSQLModel
        from models.sqlmodel.sentiment_type_sqlmodel import SentimentTypeSQLModel
        from sqlmodel import select, func
        from datetime import datetime, timedelta

        symbol = symbol.upper()

        # Get asset from database
        asset = self.asset_repository.get_by_symbol(symbol)
        if not asset:
            logger.warning(f"Asset {symbol} not found in database")
            return True  # No asset = definitely stale

        # Get news sentiment type IDs (any type with name LIKE 'news_%')
        news_type_stmt = select(SentimentTypeSQLModel.id).where(
            SentimentTypeSQLModel.name.like('news_%')  # type: ignore
        )
        news_type_ids = list(self.session.exec(news_type_stmt).all())

        if not news_type_ids:
            logger.debug("No news sentiment types found in database")
            return True  # No news types = definitely stale

        # Get most recent created_at timestamp for this asset's news events
        stmt = select(func.max(SentimentEventSQLModel.created_at)).where(
            SentimentEventSQLModel.asset_id == asset.id,
            SentimentEventSQLModel.sentiment_type_id.in_(news_type_ids)  # type: ignore
        )

        last_news_time = self.session.exec(stmt).first()

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

    # ============================================================================
    # FED DATA OPERATIONS
    # ============================================================================

    def fed_bulk_upsert(self, fed_data_list):
        """Bulk insert or update Federal Reserve data using FedDataRepository.

        Args:
            fed_data_list: List of FedData dataclass objects to store

        Returns:
            Number of records successfully stored
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

        # Use repository for upsert
        return self.fed_data_repository.bulk_upsert(sql_models)

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
        from models.sqlmodel.fed_data_sqlmodel import FedDataSQLModel
        from models.dataclass.fed_data import FedData
        from sqlmodel import select
        from decimal import Decimal
        import json

        statement = select(FedDataSQLModel).where(
            FedDataSQLModel.data_type == data_type
        ).order_by(FedDataSQLModel.observation_date.desc()).limit(limit)  # type: ignore

        feds_sql = self.session.exec(statement).all()

        # Convert SQLModel objects to FedData dataclass objects
        fed_data_list = []
        for fed_sql in feds_sql:
            try:
                fed_data = FedData(
                    id=fed_sql.id,
                    data_type=fed_sql.data_type,
                    observation_date=fed_sql.observation_date,
                    value=Decimal(str(fed_sql.value)),
                    details=json.loads(fed_sql.details) if fed_sql.details else {},
                    created_at=fed_sql.created_at,
                    updated_at=fed_sql.updated_at
                )
                fed_data_list.append(fed_data)
            except Exception as e:
                logger.warning(f"Failed to parse FED data row: {e}")
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

                # Record metadata timestamp
                from models.sqlmodel.data_update_metadata_sqlmodel import DataUpdateMetadataSQLModel
                from models.dataclass.data_update_metadata import OperationStatus

                metadata = DataUpdateMetadataSQLModel(
                    operation_type=DataUpdateMetadataType.MARKET_HOLIDAYS.value,
                    operation_subtype="fetch",
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    status=OperationStatus.COMPLETED.value,
                    total_items=len(holidays_data),
                    processed_items=len(holidays_data),
                    api_calls_made=1
                )
                self.metadata_repository.save(metadata)

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
        """Record metadata for bulk operations - ONLY for market_snapshots, tickers, fundamentals.

        IMPORTANT: This method should ONLY be called by three bulk operations:
        1. Market snapshots (market update command)
        2. Tickers (bootstrap_assets)
        3. Fundamentals (bootstrap_fundamentals)

        All other operations (providers, markets, holidays, universes) should NOT use this.

        This utility standardizes metadata tracking across the three bulk operations.
        Automatically handles timing, status determination, and metadata persistence.

        Args:
            operation_type: MUST be MARKET_SNAPSHOTS, TICKERS, or FUNDAMENTALS
            operation_subtype: Subtype (e.g., "bootstrap", "bulk_update", "fetch")
            start_time: When the operation started
            total_items: Total number of items processed
            processed_items: Number of items successfully processed
            failed_items: Number of items that failed (default: 0)
            api_calls_made: Number of API calls made (default: 1)
        """
        from models.sqlmodel.data_update_metadata_sqlmodel import DataUpdateMetadataSQLModel
        from models.dataclass.data_update_metadata import OperationStatus

        # Determine status based on failures
        if failed_items == 0:
            status = OperationStatus.COMPLETED
        elif processed_items > 0:
            status = OperationStatus.PARTIAL
        else:
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
