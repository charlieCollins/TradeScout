"""Sentiment types database manager for sentiment type reference data operations.

Sentiment types define the categories of sentiment events that can be detected
(e.g., 'news_positive', 'news_negative', 'analyst_upgrade', 'earnings_beat').

This is static configuration data (not bootstrapped from API), so no TTL/metadata tracking needed.
"""

import logging
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from models.sentiment_type import SentimentType
from .base_manager import BaseManager

logger = logging.getLogger(__name__)


class SentimentTypesManager(BaseManager):
    """Database manager for sentiment type CRUD operations.

    Sentiment types are static configuration (hardcoded definitions), not fetched from APIs.
    No TTL/metadata tracking needed - types are created via bootstrap and don't expire.
    """

    def get_data_update_metadata_type(self):
        """Sentiment types don't use metadata tracking.

        This method is required by BaseManager but not used for sentiment types.
        """
        return None

    def get_ttl_seconds(self) -> int:
        """Sentiment types don't have TTL.

        This method is required by BaseManager but not used for sentiment types.
        Returns 0 to indicate no expiration.
        """
        return 0

    def _check_dependencies(self) -> bool:
        """Check if required dependencies are available.

        Sentiment managers only need db_manager, not update_tracker or metadata_manager.
        """
        if not self.db_manager:
            logger.warning("Database manager not available")
            return False
        return True

    def get_entity_from_database(self, key: str) -> Optional[SentimentType]:
        """Get SentimentType from database by name.

        Args:
            key: Sentiment type name as string (e.g., 'news_positive', 'analyst_upgrade')

        Returns:
            SentimentType object or None if not found
        """
        if not self._check_dependencies():
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT id, name, description, category, parameters, is_active, created_at
                    FROM sentiment_types
                    WHERE name = ?
                """

                cursor.execute(query, (key,))
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"No sentiment type found for name {key}")
                    return None

                return self._parse_sentiment_type_row(row)

        except Exception as e:
            logger.error(f"Error getting sentiment type from database for name {key}: {e}")
            return None

    def set_entity_to_database(self, key: str, entity: SentimentType) -> bool:
        """Store SentimentType to database.

        Args:
            key: Sentiment type name as string (should match entity.name)
            entity: SentimentType object to store

        Returns:
            True if successful, False otherwise
        """
        if not self._check_dependencies() or not entity:
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Use INSERT OR REPLACE to handle both new and existing types
                query = """
                    INSERT OR REPLACE INTO sentiment_types (
                        name, description, category, parameters, is_active, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """

                values = (
                    entity.name,
                    entity.description,
                    entity.category,
                    json.dumps(entity.parameters),  # Serialize dict to JSON
                    entity.is_active,
                    entity.created_at.isoformat()
                )

                cursor.execute(query, values)
                conn.commit()

                logger.debug(f"Successfully stored sentiment type {entity.name}")
                return True

        except Exception as e:
            logger.error(f"Error storing sentiment type to database for {entity.name}: {e}")
            return False

    # ============================================================================
    # SENTIMENT TYPE-SPECIFIC METHODS
    # ============================================================================

    def get_all_types(self, active_only: bool = True) -> List[SentimentType]:
        """Get all sentiment types from database.

        Args:
            active_only: If True, return only active sentiment types

        Returns:
            List of SentimentType objects
        """
        if not self._check_dependencies():
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT id, name, description, category, parameters, is_active, created_at
                    FROM sentiment_types
                """

                if active_only:
                    query += " WHERE is_active = 1"

                query += " ORDER BY category, name"

                cursor.execute(query)
                rows = cursor.fetchall()

                types = []
                for row in rows:
                    try:
                        sentiment_type = self._parse_sentiment_type_row(row)
                        if sentiment_type:
                            types.append(sentiment_type)
                    except Exception as e:
                        logger.warning(f"Failed to parse sentiment type row: {e}")
                        continue

                logger.debug(f"Retrieved {len(types)} sentiment types from database")
                return types

        except Exception as e:
            logger.error(f"Error getting all sentiment types: {e}")
            return []

    def get_types_by_category(self, category: str) -> List[SentimentType]:
        """Get sentiment types by category.

        Args:
            category: Category name (e.g., 'news', 'analyst', 'earnings')

        Returns:
            List of SentimentType objects in that category
        """
        if not self._check_dependencies():
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT id, name, description, category, parameters, is_active, created_at
                    FROM sentiment_types
                    WHERE category = ? AND is_active = 1
                    ORDER BY name
                """

                cursor.execute(query, (category,))
                rows = cursor.fetchall()

                types = []
                for row in rows:
                    try:
                        sentiment_type = self._parse_sentiment_type_row(row)
                        if sentiment_type:
                            types.append(sentiment_type)
                    except Exception as e:
                        logger.warning(f"Failed to parse sentiment type row: {e}")
                        continue

                logger.debug(f"Retrieved {len(types)} sentiment types for category {category}")
                return types

        except Exception as e:
            logger.error(f"Error getting sentiment types for category {category}: {e}")
            return []

    def get_type_id_by_name(self, name: str) -> Optional[int]:
        """Get sentiment type ID by name.

        Args:
            name: Sentiment type name (e.g., 'news_positive')

        Returns:
            Sentiment type ID or None if not found
        """
        if not self._check_dependencies():
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT id FROM sentiment_types WHERE name = ?", (name,))
                row = cursor.fetchone()

                if row:
                    return row[0]

                logger.debug(f"No sentiment type found for name {name}")
                return None

        except Exception as e:
            logger.error(f"Error getting sentiment type ID for name {name}: {e}")
            return None

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _parse_sentiment_type_row(self, row: tuple) -> Optional[SentimentType]:
        """Parse database row into SentimentType object.

        Args:
            row: Database row tuple

        Returns:
            SentimentType object or None if parsing fails
        """
        try:
            return SentimentType(
                id=row[0],
                name=row[1],
                description=row[2],
                category=row[3],
                parameters=json.loads(row[4]) if row[4] else {},  # Parse JSON to dict
                is_active=bool(row[5]),
                created_at=datetime.fromisoformat(row[6])
            )

        except Exception as e:
            logger.error(f"Error parsing sentiment type row: {e}")
            return None

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get sentiment types manager statistics."""
        if not self._check_dependencies():
            return {"error": "Dependencies not available"}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Count total types
                cursor.execute("SELECT COUNT(*) FROM sentiment_types")
                total_types = cursor.fetchone()[0]

                # Count active types
                cursor.execute("SELECT COUNT(*) FROM sentiment_types WHERE is_active = 1")
                active_types = cursor.fetchone()[0]

                # Count by category
                cursor.execute("""
                    SELECT category, COUNT(*)
                    FROM sentiment_types
                    WHERE is_active = 1
                    GROUP BY category
                    ORDER BY COUNT(*) DESC
                """)
                by_category = dict(cursor.fetchall())

                # Get most recent creation
                cursor.execute("SELECT MAX(created_at) FROM sentiment_types")
                last_created = cursor.fetchone()[0]

                return {
                    "total_types": total_types,
                    "active_types": active_types,
                    "by_category": by_category,
                    "last_created": last_created,
                    "storage": "sentiment_types table"
                }

        except Exception as e:
            logger.error(f"Error getting sentiment types manager stats: {e}")
            return {"error": str(e)}
