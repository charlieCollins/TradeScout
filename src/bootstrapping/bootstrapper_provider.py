"""Bootstrap all data providers into the database."""

import logging
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class ProviderBootstrapper:
    """Bootstrap all supported data providers."""

    def __init__(self, db_manager=None):
        """Initialize with database manager."""
        self.db_manager = db_manager
        self.last_stats = {}

    def get_all_providers(self) -> List[Dict[str, Any]]:
        """Get all provider definitions for bootstrapping."""
        return [
            {
                'name': 'polygon',
                'display_name': 'Polygon.io',
                'base_url': 'https://api.polygon.io',
                'api_key_required': True,
                'is_active': True
            }
        ]

    def bootstrap_providers(self) -> Dict[str, int]:
        """Bootstrap all providers into database. Returns statistics."""
        if not self.db_manager:
            raise ValueError("Database manager required for provider bootstrap")

        stats = {"inserted": 0, "updated": 0, "errors": 0}
        providers = self.get_all_providers()

        logger.info(f"Starting bootstrap of {len(providers)} providers")

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            for provider in providers:
                try:
                    # Check if provider exists
                    cursor.execute(
                        "SELECT id, is_active FROM providers WHERE name = ?",
                        (provider['name'],)
                    )
                    existing = cursor.fetchone()

                    if existing:
                        # Update existing provider if needed
                        cursor.execute("""
                            UPDATE providers
                            SET display_name = ?, base_url = ?, api_key_required = ?, is_active = ?
                            WHERE name = ?
                        """, (
                            provider['display_name'],
                            provider['base_url'],
                            provider['api_key_required'],
                            provider['is_active'],
                            provider['name']
                        ))
                        stats["updated"] += 1
                        logger.debug(f"Updated provider: {provider['name']}")
                    else:
                        # Insert new provider
                        cursor.execute("""
                            INSERT INTO providers (
                                name, display_name, base_url, api_key_required, is_active
                            ) VALUES (?, ?, ?, ?, ?)
                        """, (
                            provider['name'],
                            provider['display_name'],
                            provider['base_url'],
                            provider['api_key_required'],
                            provider['is_active']
                        ))
                        stats["inserted"] += 1
                        logger.info(f"Inserted provider: {provider['name']}")

                except Exception as e:
                    logger.error(f"Error processing provider {provider['name']}: {e}")
                    stats["errors"] += 1

            conn.commit()

        logger.info(f"Provider bootstrap complete: {stats}")
        self.last_stats = stats
        return stats

    def get_active_providers(self) -> List[str]:
        """Get list of active provider names from database."""
        if not self.db_manager:
            return []

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM providers WHERE is_active = TRUE")
            return [row[0] for row in cursor.fetchall()]

    def activate_provider(self, provider_name: str) -> bool:
        """Activate a specific provider."""
        if not self.db_manager:
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE providers SET is_active = TRUE WHERE name = ?",
                    (provider_name,)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to activate provider {provider_name}: {e}")
            return False

    def deactivate_provider(self, provider_name: str) -> bool:
        """Deactivate a specific provider."""
        if not self.db_manager:
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE providers SET is_active = FALSE WHERE name = ?",
                    (provider_name,)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to deactivate provider {provider_name}: {e}")
            return False

    def get_bootstrap_stats(self) -> Dict[str, Any]:
        """Get statistics from the last bootstrap run."""
        return self.last_stats.copy()