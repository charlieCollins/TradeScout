"""Bootstrap Service - Handles all database initialization and seeding operations.

This service is responsible for bootstrapping/seeding the database with initial data:
- Providers (NASDAQ Trader, etc.)
- Markets/Exchanges
- Assets/Tickers
- Fundamentals
- Universes
- Sentiment Types

Separates bootstrap logic from runtime data operations in DataService.
"""

import logging
from typing import Optional, List, Dict, Any
from models.sqlmodel.provider_sqlmodel import ProviderSQLModel
from models.sqlmodel.market_sqlmodel import MarketSQLModel
from models.sqlmodel.asset_sqlmodel import AssetSQLModel
from models.dataclass.data_update_metadata import DataUpdateMetadataType

logger = logging.getLogger(__name__)


class BootstrapService:
    """Service for bootstrapping and seeding database with initial data.

    This service handles all bootstrap operations that populate the database
    with initial data from APIs or hardcoded seeds. It's separate from
    DataService which handles runtime data operations.

    Bootstrap operations are typically run once during setup or when
    refreshing data.
    """

    def __init__(self, data_service):
        """Initialize BootstrapService.

        Args:
            data_service: DataServiceV2 instance (provides access to repositories and providers)
        """
        self.data_service = data_service

        # Quick access to commonly used components
        self.session = data_service.session
        self.asset_repository = data_service.asset_repository
        self.market_repository = data_service.market_repository
        self.fundamentals_repository = data_service.fundamentals_repository
        self.provider_repository = data_service.provider_repository
        self.universe_repository = data_service.universe_repository
        self.sentiment_type_repository = data_service.sentiment_type_repository

        # API providers (now provider-agnostic via factory)
        self.reference_provider = data_service.reference_provider
        self.economic_provider = data_service.economic_provider

    def bootstrap_sentiment_types(self) -> int:
        """Bootstrap sentiment types into database.

        Seeds the database with the standard news sentiment types:
        - news_positive: Positive news sentiment
        - news_negative: Negative news sentiment
        - news_neutral: Neutral news sentiment
        - news_mixed: Mixed news sentiment

        Returns:
            Number of sentiment types created (0 if already exist)
        """
        from datetime import datetime
        from models.sqlmodel.sentiment_type_sqlmodel import SentimentTypeSQLModel

        logger.info("Bootstrapping sentiment types")

        # Define standard sentiment types
        sentiment_types = [
            {
                "name": "news_positive",
                "description": "Positive news sentiment from market articles",
                "category": "news",
                "parameters": '{"weight": 1.0}',
                "is_active": True
            },
            {
                "name": "news_negative",
                "description": "Negative news sentiment from market articles",
                "category": "news",
                "parameters": '{"weight": -1.0}',
                "is_active": True
            },
            {
                "name": "news_neutral",
                "description": "Neutral news sentiment from market articles",
                "category": "news",
                "parameters": '{"weight": 0.0}',
                "is_active": True
            },
            {
                "name": "news_mixed",
                "description": "Mixed news sentiment from market articles",
                "category": "news",
                "parameters": '{"weight": 0.0}',
                "is_active": True
            }
        ]

        created_count = 0
        for sent_type in sentiment_types:
            # Check if already exists
            existing = self.sentiment_type_repository.get_by_name(sent_type["name"])
            if existing:
                logger.debug(f"Sentiment type '{sent_type['name']}' already exists - skipping")
                continue

            # Create new sentiment type
            sentiment_type_sql = SentimentTypeSQLModel(
                name=sent_type["name"],
                description=sent_type["description"],
                category=sent_type["category"],
                parameters=sent_type["parameters"],
                is_active=sent_type["is_active"],
                created_at=datetime.now()
            )

            # Save to database
            self.sentiment_type_repository.save(sentiment_type_sql)
            created_count += 1
            logger.debug(f"Created sentiment type: {sent_type['name']}")

        logger.info(f"Bootstrapped {created_count} sentiment types")
        return created_count

    def bootstrap_providers(self) -> int:
        """Bootstrap all active data providers into database.

        Registers each provider used by the system so the providers table
        reflects the actual runtime configuration.

        Returns:
            Number of providers stored successfully
        """
        from datetime import datetime

        logger.info("Bootstrapping providers")

        providers = [
            ProviderSQLModel(
                name="nasdaq_trader",
                display_name="NASDAQ Trader",
                base_url="https://www.nasdaqtrader.com",
                api_key_required=False,
                is_active=True,
                created_at=datetime.now(),
            ),
            ProviderSQLModel(
                name="yfinance",
                display_name="Yahoo Finance",
                base_url="https://finance.yahoo.com",
                api_key_required=False,
                is_active=True,
                created_at=datetime.now(),
            ),
            ProviderSQLModel(
                name="finnhub",
                display_name="Finnhub",
                base_url="https://finnhub.io",
                api_key_required=True,
                is_active=True,
                created_at=datetime.now(),
            ),
            ProviderSQLModel(
                name="fred",
                display_name="Federal Reserve (FRED)",
                base_url="https://api.stlouisfed.org",
                api_key_required=True,
                is_active=True,
                created_at=datetime.now(),
            ),
            ProviderSQLModel(
                name="pandas_market_calendars",
                display_name="Pandas Market Calendars",
                base_url=None,
                api_key_required=False,
                is_active=True,
                created_at=datetime.now(),
            ),
            ProviderSQLModel(
                name="edgar",
                display_name="SEC EDGAR",
                base_url="https://data.sec.gov",
                api_key_required=False,
                is_active=True,
                created_at=datetime.now(),
            ),
        ]

        created_count = 0
        for provider in providers:
            existing = self.provider_repository.get_by_name(provider.name)
            if existing:
                logger.debug(f"Provider '{provider.name}' already exists - skipping")
                continue
            self.provider_repository.save(provider)
            created_count += 1
            logger.debug(f"Created provider: {provider.name}")

        logger.info(f"Bootstrapped {created_count} providers")
        return created_count

    def bootstrap_markets(self, asset_class: str = "stocks", locale: str = "us") -> int:
        """Bootstrap markets/exchanges into database.

        Fetches exchange data from the reference provider and stores to the markets table.

        Args:
            asset_class: Asset class to filter (default: "stocks")
            locale: Locale to filter (default: "us")

        Returns:
            Number of markets stored successfully

        Raises:
            RuntimeError: If prerequisites (providers) are not met
        """
        logger.info(
            f"Bootstrapping markets (asset_class={asset_class}, locale={locale})"
        )

        # Check prerequisites
        provider_count = self.provider_repository.count_all()
        if provider_count == 0:
            raise RuntimeError(
                "Cannot bootstrap markets: No providers in database. Run 'bootstrap-providers' first."
            )

        # Fetch all markets from reference provider
        markets = self.reference_provider.fetch_all_exchanges(
            asset_class=asset_class, locale=locale
        )

        if not markets:
            logger.warning("No markets fetched from reference provider")
            return 0

        # Convert Market dataclass → MarketSQLModel with extended hours
        from datetime import time
        market_sql_list = []
        for market in markets:
            # Set extended hours for US stock markets
            premarket_start = None
            premarket_end = None
            afterhours_start = None
            afterhours_end = None
            timezone = market.timezone or "America/New_York"
            currency = market.currency or "USD"

            # US stock markets have standard extended hours
            if locale == "us" and asset_class == "stocks":
                premarket_start = time(4, 0)   # 4:00 AM
                premarket_end = time(9, 30)    # 9:30 AM
                afterhours_start = time(16, 0) # 4:00 PM
                afterhours_end = time(20, 0)   # 8:00 PM

            market_sql = MarketSQLModel(
                id=market.id if market.id != 0 else None,
                code=market.code,
                name=market.name,
                country=market.country or "US",
                timezone=timezone,
                currency=currency,
                premarket_start_time=premarket_start,
                premarket_end_time=premarket_end,
                regular_open_time=market.regular_open_time,
                regular_close_time=market.regular_close_time,
                afterhours_start_time=afterhours_start,
                afterhours_end_time=afterhours_end,
                is_active=market.is_active,
                created_at=market.created_at
            )
            market_sql_list.append(market_sql)

        # Upsert markets (insert new or update existing)
        stored_count = 0
        for market_sql in market_sql_list:
            existing = self.market_repository.get_by_code(market_sql.code)
            if existing:
                # Update existing market
                existing.name = market_sql.name
                existing.country = market_sql.country
                existing.timezone = market_sql.timezone
                existing.currency = market_sql.currency
                existing.premarket_start_time = market_sql.premarket_start_time
                existing.premarket_end_time = market_sql.premarket_end_time
                existing.regular_open_time = market_sql.regular_open_time
                existing.regular_close_time = market_sql.regular_close_time
                existing.afterhours_start_time = market_sql.afterhours_start_time
                existing.afterhours_end_time = market_sql.afterhours_end_time
                existing.is_active = market_sql.is_active
                self.market_repository.save(existing)
                stored_count += 1
            else:
                # Insert new market
                self.market_repository.save(market_sql)
                stored_count += 1

        logger.info(f"Bootstrapped {stored_count} markets")
        return stored_count

    def bootstrap_assets(
        self,
        market: str = "stocks",
        active: bool = True,
        progress=None
    ):
        """Bootstrap all tickers from reference provider.

        Fetches all tickers and stores them as assets in database.
        This is a bulk operation that should be run periodically.

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
        from models.result.bootstrap_result import BootstrapResult

        start_time = time.time()
        logger.info(
            f"Bootstrapping tickers (market={market}, active={active})"
        )

        # Check prerequisites
        provider_count = self.provider_repository.count_all()
        if provider_count == 0:
            raise RuntimeError(
                "Cannot bootstrap tickers: No providers in database. Run 'bootstrap-providers' first."
            )

        market_count = self.market_repository.count_all()
        if market_count == 0:
            raise RuntimeError(
                "Cannot bootstrap tickers: No markets in database. Run 'bootstrap-markets' first."
            )

        # Get provider ID for asset FK
        provider = self.provider_repository.get_by_name("nasdaq_trader")
        if not provider:
            raise RuntimeError(
                "Cannot bootstrap tickers: nasdaq_trader provider not found in database. "
                "Run 'bootstrap-providers' first."
            )

        # Get all existing symbols before bulk save to calculate deprecations
        existing_symbols_before = set(self.asset_repository.get_all_symbols())

        # Create market_code to market_id mapping, including provider_id
        all_markets = self.market_repository.get_all(active_only=False)
        market_code_to_id = {m.code: m.id for m in all_markets}
        market_code_to_id["__provider_id__"] = provider.id

        # Fetch all tickers from API with market mapping (includes provider_id)
        assets = self.reference_provider.fetch_all_tickers(
            market=market, active=active, market_code_to_id=market_code_to_id
        )

        if not assets:
            duration = time.time() - start_time
            return BootstrapResult(
                operation="tickers",
                total_items=0,
                successful=0,
                failed=0,
                duration_seconds=duration
            )

        # Convert Asset dataclass → AssetSQLModel
        asset_sql_list = []
        incoming_symbols = set()
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
            incoming_symbols.add(asset.symbol)

        # Bulk save using repository (returns inserted, updated, total)
        inserted_count, updated_count, total_processed = self.asset_repository.bulk_save(asset_sql_list)

        # Calculate deprecated tickers (in DB but not in latest response)
        deprecated_symbols = existing_symbols_before - incoming_symbols
        deprecated_count = len(deprecated_symbols)

        duration = time.time() - start_time
        logger.info(
            f"Bootstrapped {total_processed} tickers in {duration:.1f}s "
            f"({inserted_count} new, {updated_count} updated, {deprecated_count} deprecated)"
        )

        # Record metadata for bulk ticker operation
        from datetime import datetime
        self.data_service.record_bulk_operation_metadata(
            operation_type=DataUpdateMetadataType.TICKERS,
            operation_subtype="bootstrap",
            start_time=datetime.fromtimestamp(start_time),
            total_items=len(assets),
            processed_items=total_processed,
            failed_items=len(assets) - total_processed,
            api_calls_made=1
        )

        return BootstrapResult(
            operation="tickers",
            total_items=len(assets),
            successful=total_processed,
            failed=len(assets) - total_processed,
            duration_seconds=duration,
            new_items=inserted_count,
            updated_items=updated_count,
            deprecated_items=deprecated_count
        )

    def bootstrap_fundamentals(self, limit: Optional[int] = None, force: bool = False, progress=None):
        """Bootstrap fundamentals for all assets in active universe via SEC EDGAR bulk data.

        Uses SEC EDGAR for bulk fundamentals:
        1. company_tickers_exchange.json for ticker→CIK mapping (1 call)
        2. XBRL Frames for shares outstanding (1 call)
        3. submissions/CIK{cik}.json for SIC codes (~10K calls at 10/sec)
        4. yfinance bulk download for last prices → market cap calculation

        Falls back to per-ticker yfinance if EDGAR fails.

        Args:
            limit: Optional limit on number of assets to process
            force: If True, bypass DB freshness checks
            progress: Optional progress reporter for operation tracking

        Returns:
            BootstrapResult with operation statistics and error details

        Raises:
            RuntimeError: If prerequisites (assets, active universe) are not met
        """
        import time
        from datetime import datetime
        from models.result.bootstrap_result import BootstrapResult
        from models.dataclass.fundamentals import AssetFundamentals
        from models.sqlmodel.fundamentals_sqlmodel import FundamentalsSQLModel
        from utils.config_loader import ConfigLoader

        start_time = time.time()
        logger.info(f"Bootstrapping fundamentals (limit={limit})")

        config_loader = ConfigLoader()
        config = config_loader.load_database_ttl_config()
        max_age_days = config["max_fundamentals_age_days"]  # 30 days

        # Get assets from active universe
        assets = self.universe_repository.get_active_universe_assets(limit=limit)

        if not assets:
            raise RuntimeError(
                "Cannot bootstrap fundamentals: No assets in active universe. "
                "Run 'bootstrap-tickers' and 'bootstrap-universes' first."
            )

        total_assets = len(assets)
        logger.info(f"Processing fundamentals for {total_assets} assets in active universe")

        # Build symbol→asset_id mapping
        symbol_to_asset = {asset.symbol: asset for asset in assets}

        # Phase 1: Check DB for fresh data (skip already-fresh records)
        symbols_needing_data = []
        from_database = 0

        if not force:
            for asset in assets:
                existing = self.fundamentals_repository.get_by_asset_id(asset.id)
                if existing and existing.last_updated:
                    age_days = (datetime.now() - existing.last_updated).days
                    if age_days < max_age_days:
                        from_database += 1
                        continue
                symbols_needing_data.append(asset.symbol)

            if from_database:
                logger.info(f"Skipping {from_database} assets with fresh DB data (<{max_age_days} days)")
        else:
            symbols_needing_data = [asset.symbol for asset in assets]

        if not symbols_needing_data:
            logger.info("All fundamentals are fresh — nothing to fetch")
            duration = time.time() - start_time
            return BootstrapResult(
                operation="fundamentals",
                total_items=total_assets,
                successful=from_database,
                failed=0,
                duration_seconds=duration,
                from_database=from_database,
                from_cache=0,
                from_api=0,
            )

        # Phase 2: Fetch bulk data from SEC EDGAR
        logger.info(f"Fetching fundamentals for {len(symbols_needing_data)} symbols via SEC EDGAR...")

        # Look up edgar provider_id
        edgar_provider = self.provider_repository.get_by_name("edgar")
        provider_id = edgar_provider.id if edgar_provider else 1

        from api.providers.adapters.edgar_fundamentals_adapter import EdgarFundamentalsAdapter
        edgar_adapter = EdgarFundamentalsAdapter()
        edgar_data = edgar_adapter.fetch_bulk_fundamentals(symbols_needing_data, progress=progress)

        # Phase 3: Build AssetFundamentals objects
        fundamentals_data = {}
        fetch_errors = []
        from_api = 0

        for symbol in symbols_needing_data:
            asset = symbol_to_asset[symbol]
            data = edgar_data.get(symbol)

            if not data:
                fetch_errors.append(f"{symbol}: No EDGAR data (no CIK match)")
                continue

            try:
                fundamentals = AssetFundamentals.from_edgar_data(
                    asset_id=asset.id,
                    provider_id=provider_id,
                    edgar_data=data,
                )
                fundamentals_data[asset.id] = fundamentals
                from_api += 1
            except Exception as e:
                fetch_errors.append(f"{symbol}: {str(e)}")
                logger.error(f"Error building fundamentals for {symbol}: {e}")

        logger.info(
            f"Data sources: {from_database} from DB (fresh), "
            f"{from_api} from EDGAR, "
            f"{len(fetch_errors)} errors"
        )

        # Phase 4: Bulk save all fundamentals (single database transaction)
        insert_errors = []
        successful_count = 0

        if fundamentals_data:
            logger.info(f"Saving {len(fundamentals_data)} fundamentals to database...")

            if progress:
                progress.start_operation("Saving to database", len(fundamentals_data))

            fundamentals_sql_list = []
            for asset_id, fundamentals in fundamentals_data.items():
                try:
                    fundamentals_sql = FundamentalsSQLModel(
                        asset_id=fundamentals.asset_id,
                        company_name=fundamentals.company_name,
                        sector=fundamentals.sector,
                        industry=fundamentals.industry,
                        sic_code=fundamentals.sic_code,
                        market_cap=fundamentals.market_cap,
                        shares_outstanding=fundamentals.shares_outstanding,
                        avg_volume_30d=fundamentals.avg_volume_30d,
                        beta=fundamentals.beta,
                        pe_ratio=fundamentals.pe_ratio,
                        dividend_yield=fundamentals.dividend_yield,
                        provider_id=fundamentals.provider_id,
                        last_updated=fundamentals.last_updated
                    )
                    fundamentals_sql_list.append(fundamentals_sql)
                except Exception as e:
                    insert_errors.append(f"asset_id {asset_id}: {str(e)}")

            if fundamentals_sql_list:
                successful_count = self.fundamentals_repository.bulk_save(fundamentals_sql_list)

            if progress:
                progress.complete_operation(success=True)

        duration = time.time() - start_time
        total_successful = successful_count + from_database
        total_failed = len(fetch_errors)

        logger.info(
            f"Bootstrapped {total_successful}/{total_assets} fundamentals in {duration:.1f}s "
            f"({successful_count} updated, {from_database} already fresh)"
        )

        self.data_service.record_bulk_operation_metadata(
            operation_type=DataUpdateMetadataType.FUNDAMENTALS,
            operation_subtype="bootstrap",
            start_time=datetime.fromtimestamp(start_time),
            total_items=total_assets,
            processed_items=total_successful,
            failed_items=total_failed,
            api_calls_made=from_api
        )

        return BootstrapResult(
            operation="fundamentals",
            total_items=total_assets,
            successful=total_successful,
            failed=total_failed,
            fetch_errors=fetch_errors,
            insert_errors=insert_errors,
            duration_seconds=duration,
            from_database=from_database,
            from_cache=0,
            from_api=from_api
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

    def bootstrap_universes(self, universe_name: str = "default", force_refresh: bool = False):
        """Bootstrap a universe by filtering assets based on configuration criteria using new architecture.

        Universes are filtered subsets of assets created by applying inclusion/exclusion
        criteria defined in config/universe_config.py. This method:
        1. Fetches all assets + fundamentals data from database
        2. Applies filtering criteria (exchanges, market cap, sectors, etc.)
        3. Creates/updates Universe record
        4. Clears old memberships and adds new ones
        5. Records metadata timestamp

        Args:
            universe_name: Name of universe from UNIVERSE_CONFIG (default: "default")
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
        from utils.config_loader import get_config_loader

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

        # Note: Universe freshness checking removed - use force_refresh=True to always rebuild
        # We always rebuild to ensure data is current

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
