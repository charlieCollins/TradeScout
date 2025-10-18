"""Cache Service - Generic cache-aside pattern implementation.

It implements the cache-aside pattern: check local store → fetch if stale → update → return.
"""

import logging
from datetime import datetime
from typing import Callable, Optional, TypeVar, Generic
from models.dataclass.data_update_metadata import DataUpdateMetadataType
from repositories.data_update_metadata_repository import DataUpdateMetadataRepository

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheService(Generic[T]):
    """Generic cache-aside pattern implementation.

    This is the extracted "get-or-fetch" logic from legacy BaseManager.
    Works with any repository, any provider, any data type.

    Implements the on-demand fetching requirement:
    1. Check local store first (repository)
    2. If data not present or outdated (TTL) → fetch from API (provider)
    3. Update local store (repository)
    4. Return data

    This service is GENERIC and REUSABLE across all entity types.
    """

    def __init__(
        self,
        repository,  # Any repository with get_by_symbol() and save()
        metadata_repository: DataUpdateMetadataRepository,
        metadata_type: DataUpdateMetadataType,
        ttl_seconds: int
    ):
        """Initialize cache service.

        Args:
            repository: Repository for data persistence (must have get_by_symbol, save)
            metadata_repository: Repository for TTL tracking
            metadata_type: Type of metadata for this entity
            ttl_seconds: Time-to-live in seconds
        """
        self.repository = repository
        self.metadata_repository = metadata_repository
        self.metadata_type = metadata_type
        self.ttl_seconds = ttl_seconds

    def get_or_fetch(
        self,
        key: str,
        fetch_fn: Callable[[], Optional[T]],
        force_refresh: bool = False
    ) -> Optional[T]:
        """Cache-aside pattern: on-demand fetching with local persistence.

        This implements YOUR requirement:
        "check the local store first, if the data is not present or outdated
        fetch it, update the data locally, then return it"

        Flow:
        1. Check local store first (via repository.get_by_symbol for assets)
        2. If data present AND fresh (TTL valid) → return cached data
        3. If data missing OR stale (TTL expired) → fetch from API (fetch_fn)
        4. Update local store (via repository.save)
        5. Return data

        Args:
            key: Cache key (e.g., symbol for assets)
            fetch_fn: Function that calls API provider to fetch fresh data
            force_refresh: If True, bypass cache check and always fetch

        Returns:
            Cached or freshly fetched data, None if error
        """
        # Step 1: Check local store (unless force refresh)
        if not force_refresh:
            cached_data = self._get_from_local_store(key)

            # Step 2: Check if data is fresh (TTL not expired)
            if cached_data and not self._is_stale():
                logger.debug(
                    f"Cache HIT for {key} "
                    f"(type={self.metadata_type.value}, ttl={self.ttl_seconds}s)"
                )
                return cached_data

        # Step 3: Data not present or outdated - fetch from API
        logger.debug(
            f"Cache MISS for {key} "
            f"(force_refresh={force_refresh}, type={self.metadata_type.value}) "
            f"- fetching from API"
        )
        fresh_data = fetch_fn()  # Calls provider

        if fresh_data:
            # Step 4: Update local store
            self._save_to_local_store(fresh_data)

            # Record the update for TTL tracking
            self._record_update()

        # Step 5: Return data
        return fresh_data

    def _get_from_local_store(self, key: str) -> Optional[T]:
        """Get data from local store (repository).

        Args:
            key: Cache key

        Returns:
            Cached data if found, None otherwise
        """
        try:
            return self.repository.get_by_symbol(key)
        except Exception as e:
            logger.error(f"Error getting {key} from local store: {e}")
            return None

    def _save_to_local_store(self, data: T) -> bool:
        """Save data to local store (repository).

        Args:
            data: Data to save

        Returns:
            True if successful, False otherwise
        """
        try:
            self.repository.save(data)
            return True
        except Exception as e:
            logger.error(f"Error saving to local store: {e}")
            return False

    def _is_stale(self) -> bool:
        """Check if cached data is outdated (TTL expired).

        Uses operation-level metadata tracking (not per-record).

        Returns:
            True if data is stale and needs refresh, False if fresh
        """
        # Get latest metadata for this operation type
        metadata = self.metadata_repository.get_latest_by_operation(
            operation_type=self.metadata_type.value
        )

        if not metadata or not metadata.completed_at:
            # No record found - data is stale
            logger.debug(f"No metadata found for {self.metadata_type.value}, considering stale")
            return True

        # Calculate staleness
        age = datetime.utcnow() - metadata.completed_at
        is_stale = age.total_seconds() > self.ttl_seconds

        if is_stale:
            logger.debug(
                f"Data for {self.metadata_type.value} is stale "
                f"(age: {age.total_seconds():.0f}s, TTL: {self.ttl_seconds}s)"
            )
        else:
            logger.debug(
                f"Data for {self.metadata_type.value} is fresh "
                f"(age: {age.total_seconds():.0f}s, TTL: {self.ttl_seconds}s)"
            )

        return is_stale

    def _record_update(self) -> None:
        """Record that a data update occurred.

        Updates the metadata timestamp for TTL tracking.
        """
        from models.sqlmodel.data_update_metadata_sqlmodel import DataUpdateMetadataSQLModel

        # Create or update metadata record
        metadata = DataUpdateMetadataSQLModel(
            operation_type=self.metadata_type.value,
            operation_subtype=None,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            status="completed",
            total_items=1,
            processed_items=1
        )

        self.metadata_repository.save(metadata)
        logger.debug(f"Recorded update for {self.metadata_type.value}")


class CacheConfig:
    """Configuration for cache TTLs loaded from configs/database_ttl.yaml."""

    _config = None

    @classmethod
    def _load_config(cls):
        """Load TTL config from YAML file."""
        if cls._config is None:
            from utils.config_loader import ConfigLoader
            loader = ConfigLoader()
            cls._config = loader.load_database_ttl_config()
        return cls._config

    @classmethod
    def get_ttl(cls, metadata_type: DataUpdateMetadataType) -> int:
        """Get TTL for a specific metadata type from YAML config.

        Args:
            metadata_type: Type of metadata

        Returns:
            TTL in seconds
        """
        config = cls._load_config()

        # Map metadata types to config keys and convert to seconds
        if metadata_type == DataUpdateMetadataType.TICKERS:
            return config["tickers_ttl_hours"] * 3600
        elif metadata_type == DataUpdateMetadataType.FUNDAMENTALS:
            return config["fundamentals_ttl_hours"] * 3600
        elif metadata_type == DataUpdateMetadataType.ASSET_PRICES:
            return config["asset_price_ttl_minutes"] * 60
        elif metadata_type == DataUpdateMetadataType.TICKER_SNAPSHOTS:
            return config["ticker_snapshot_ttl_minutes"] * 60
        elif metadata_type == DataUpdateMetadataType.MARKET_SNAPSHOTS:
            return config["market_snapshot_ttl_minutes"] * 60
        elif metadata_type == DataUpdateMetadataType.MARKETS:
            return config["markets_ttl_hours"] * 3600
        elif metadata_type == DataUpdateMetadataType.UNIVERSES:
            return config["universes_ttl_hours"] * 3600
        elif metadata_type == DataUpdateMetadataType.MARKET_CONTEXT:
            return config["market_context_ttl_minutes"] * 60
        elif metadata_type == DataUpdateMetadataType.MARKET_HOLIDAYS:
            return config["market_holidays_ttl_days"] * 86400
        elif metadata_type == DataUpdateMetadataType.PROVIDERS:
            return config["markets_ttl_hours"] * 3600  # Providers change rarely like markets
        else:
            return config["default_ttl_seconds"]
