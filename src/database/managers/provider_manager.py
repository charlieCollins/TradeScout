"""Provider database manager for internal provider configuration.

SPECIAL NOTE: Providers are INTERNAL-ONLY configuration entities that do NOT come
from external APIs. Similar to UniverseManager, ProviderManager has NO associated
API provider. Providers define which external data sources (Polygon, YFinance, etc.)
are configured and active in the system.

Currently hardcoded to Polygon, but designed for future expansion to support multiple
data providers (Alpha Vantage, Finnhub, YFinance, etc.).

This manager handles:
- Provider CRUD operations (though currently read-only with Polygon hardcoded)
- Active provider tracking (which provider is currently in use)
- Provider configuration storage (base URLs, API key requirements)
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from models.provider import Provider
from models.data_update_metadata import DataUpdateMetadataType
from .base_manager import BaseManager

logger = logging.getLogger(__name__)

# Hardcoded Polygon provider configuration (for now)
POLYGON_PROVIDER_ID = 1
POLYGON_PROVIDER = Provider(
    id=POLYGON_PROVIDER_ID,
    name="polygon",
    display_name="Polygon.io",
    base_url="https://api.polygon.io",
    api_key_required=True,
    is_active=True,
    created_at=datetime.now()
)


class ProviderManager(BaseManager):
    """Database manager for provider configuration.

    Providers define external data sources and their configuration. Currently
    hardcoded to Polygon.io, but designed to support multiple providers in the
    future (YFinance, Alpha Vantage, Finnhub, etc.).

    Note: Providers are internal configuration, not fetched from external APIs.
    """

    def get_data_update_metadata_type(self) -> DataUpdateMetadataType:
        """Get the data update metadata type for TTL validation."""
        return DataUpdateMetadataType.PROVIDERS

    def get_ttl_seconds(self) -> int:
        """Get TTL in seconds for this data type.

        Providers are static configuration that rarely changes. Use a very long
        TTL (essentially no automatic refresh needed).
        """
        return 365 * 24 * 3600  # 1 year - essentially static config

    def get_entity_from_database(self, key: str) -> Optional[Provider]:
        """Get Provider from database by name.

        Args:
            key: Provider name (e.g., 'polygon', 'yfinance')

        Returns:
            Provider object or None if not found
        """
        provider_name = key.lower()

        # For now, hardcode Polygon provider
        if provider_name == "polygon":
            return POLYGON_PROVIDER

        if not self._check_dependencies():
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT id, name, display_name, base_url, api_key_required,
                           is_active, created_at
                    FROM providers
                    WHERE name = ?
                """

                cursor.execute(query, (provider_name,))
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"No provider found with name: {provider_name}")
                    return None

                return Provider.from_db_row(row)

        except Exception as e:
            logger.error(f"Error getting provider from database for {provider_name}: {e}")
            return None

    def set_entity_to_database(self, key: str, entity: Provider) -> bool:
        """Store Provider to database.

        Args:
            key: Provider name (should match entity.name)
            entity: Provider object to store

        Returns:
            True if successful, False otherwise
        """
        if not self._check_dependencies() or not entity:
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Upsert provider - preserve ID if exists, update other fields
                query = """
                    INSERT INTO providers (
                        name, display_name, base_url, api_key_required,
                        is_active, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        display_name = excluded.display_name,
                        base_url = excluded.base_url,
                        api_key_required = excluded.api_key_required,
                        is_active = excluded.is_active
                """

                values = (
                    entity.name,
                    entity.display_name,
                    entity.base_url,
                    entity.api_key_required,
                    entity.is_active,
                    entity.created_at.isoformat() if entity.created_at else datetime.now().isoformat()
                )

                cursor.execute(query, values)
                conn.commit()

                logger.debug(f"Successfully stored provider: {entity.name}")
                return True

        except Exception as e:
            logger.error(f"Error storing provider to database for {entity.name}: {e}")
            return False

    # ============================================================================
    # PROVIDER-SPECIFIC OPERATIONS
    # ============================================================================

    def get_all_providers(self) -> List[Provider]:
        """Get all providers from database.

        Returns:
            List of Provider objects
        """
        if not self._check_dependencies():
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, name, display_name, base_url, api_key_required,
                           is_active, created_at
                    FROM providers
                    ORDER BY name
                """)
                rows = cursor.fetchall()

                providers = []
                for row in rows:
                    provider = Provider(
                        id=row[0],
                        name=row[1],
                        display_name=row[2],
                        base_url=row[3],
                        api_key_required=bool(row[4]),
                        is_active=bool(row[5]),
                        created_at=datetime.fromisoformat(row[6])
                    )
                    providers.append(provider)

                return providers

        except Exception as e:
            logger.error(f"Error getting all providers: {e}")
            return []

    def get_active_provider(self) -> Optional[Provider]:
        """Get the currently active provider.

        Returns:
            Active Provider object or None if no active provider
        """
        if not self._check_dependencies():
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, name, display_name, base_url, api_key_required,
                           is_active, created_at
                    FROM providers
                    WHERE is_active = 1
                    LIMIT 1
                """)
                row = cursor.fetchone()

                if not row:
                    return None

                return Provider(
                    id=row[0],
                    name=row[1],
                    display_name=row[2],
                    base_url=row[3],
                    api_key_required=bool(row[4]),
                    is_active=bool(row[5]),
                    created_at=datetime.fromisoformat(row[6])
                )

        except Exception as e:
            logger.error(f"Error getting active provider: {e}")
            return None

    def get_provider_by_id(self, provider_id: int) -> Optional[Provider]:
        """Get provider by ID.

        Args:
            provider_id: Provider ID (e.g., 1 for Polygon)

        Returns:
            Provider object or None if not found
        """
        # For now, hardcode Polygon
        if provider_id == POLYGON_PROVIDER_ID:
            return POLYGON_PROVIDER

        if not self._check_dependencies():
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT id, name, display_name, base_url, api_key_required,
                           is_active, created_at
                    FROM providers
                    WHERE id = ?
                """

                cursor.execute(query, (provider_id,))
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"No provider found with ID: {provider_id}")
                    return None

                return Provider.from_db_row(row)

        except Exception as e:
            logger.error(f"Error getting provider by ID {provider_id}: {e}")
            return None

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get provider manager statistics."""
        # For now, return hardcoded stats for Polygon
        return {
            "metadata_type": self.get_data_update_metadata_type().value,
            "ttl_hours": self.get_ttl_seconds() / 3600,
            "total_providers": 1,
            "active_provider": "polygon",
            "providers": ["polygon"],
            "storage": "hardcoded (Polygon only)",
            "note": "Currently hardcoded to Polygon.io - will support multiple providers in future"
        }

        # Future implementation when database is populated:
        # if not self._check_dependencies():
        #     return {"error": "Dependencies not available"}
        #
        # try:
        #     with self.db_manager.get_connection() as conn:
        #         cursor = conn.cursor()
        #
        #         # Count total providers
        #         cursor.execute("SELECT COUNT(*) FROM providers")
        #         total_providers = cursor.fetchone()[0]
        #
        #         # Get active provider
        #         cursor.execute("SELECT name FROM providers WHERE is_active = 1 LIMIT 1")
        #         row = cursor.fetchone()
        #         active_provider = row[0] if row else None
        #
        #         # Get all provider names
        #         cursor.execute("SELECT name FROM providers ORDER BY name")
        #         provider_names = [row[0] for row in cursor.fetchall()]
        #
        #         return {
        #             "metadata_type": self.get_data_update_metadata_type().value,
        #             "ttl_hours": self.get_ttl_seconds() / 3600,
        #             "total_providers": total_providers,
        #             "active_provider": active_provider,
        #             "providers": provider_names,
        #             "storage": "providers table"
        #         }
        #
        # except Exception as e:
        #     logger.error(f"Error getting provider manager stats: {e}")
        #     return {"error": str(e)}
