"""Fed data database manager for Federal Reserve economic data storage and retrieval."""

import logging
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal

from models.fed_data import FedData
from .base_manager import BaseManager

logger = logging.getLogger(__name__)


class FedDataManager(BaseManager):
    """Database manager for Federal Reserve economic data CRUD operations."""

    def get_data_update_metadata_type(self):
        """Get the metadata type for fed data updates.

        Returns:
            String identifier for metadata tracking
        """
        return "fed_data"

    def get_ttl_seconds(self) -> int:
        """Get time-to-live for fed data cache.

        Fed data is updated periodically (typically monthly/quarterly), so we
        use a configurable TTL (default 12 hours) to avoid excessive API calls.

        Returns:
            TTL in seconds (from config or 12 hours default)
        """
        try:
            from utils.config_loader import get_config_loader
            config_loader = get_config_loader()
            ttl_config = config_loader.load_database_ttl_config()
            hours = ttl_config.get("fed_data_ttl_hours", 12)
            return hours * 3600  # Convert hours to seconds
        except Exception:
            return 43200  # 12 hours default if config fails

    def get_entity_from_database(self, key: str) -> Optional[FedData]:
        """Get FedData from database by ID.

        Args:
            key: Fed data ID as string

        Returns:
            FedData object or None if not found
        """
        if not self._check_dependencies():
            return None

        try:
            fed_data_id = int(key)
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT id, data_type, observation_date, value, details,
                           created_at, updated_at
                    FROM fed_data
                    WHERE id = ?
                """

                cursor.execute(query, (fed_data_id,))
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"No fed data found for id {fed_data_id}")
                    return None

                return self._parse_fed_data_row(row)

        except (ValueError, Exception) as e:
            logger.error(f"Error getting fed data from database for id {key}: {e}")
            return None

    def set_entity_to_database(self, key: str, entity: FedData) -> bool:
        """Store FedData to database.

        Args:
            key: Fed data ID as string (ignored - uses entity properties)
            entity: FedData object to store

        Returns:
            True if successful, False otherwise
        """
        if not self._check_dependencies() or not entity:
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Use INSERT OR REPLACE for upsert behavior
                query = """
                    INSERT OR REPLACE INTO fed_data
                    (data_type, observation_date, value, details, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """

                cursor.execute(
                    query,
                    (
                        entity.data_type,
                        entity.observation_date.isoformat(),
                        float(entity.value),
                        json.dumps(entity.details),
                        entity.created_at.isoformat(),
                        datetime.now().isoformat(),  # Update timestamp
                    ),
                )

                conn.commit()
                logger.debug(f"Stored fed data: {entity.data_type} for {entity.observation_date}")
                return True

        except Exception as e:
            logger.error(f"Error storing fed data to database: {e}")
            return False

    # ============================================================================
    # QUERY METHODS
    # ============================================================================

    def get_latest_by_type(self, data_type: str) -> Optional[FedData]:
        """Get the most recent observation for a specific data type.

        Args:
            data_type: Type of fed data ('inflation', 'inflation_expectations', 'treasury_yields')

        Returns:
            FedData object or None if not found
        """
        if not self._check_dependencies():
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT id, data_type, observation_date, value, details,
                           created_at, updated_at
                    FROM fed_data
                    WHERE data_type = ?
                    ORDER BY observation_date DESC
                    LIMIT 1
                """

                cursor.execute(query, (data_type,))
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"No fed data found for type {data_type}")
                    return None

                return self._parse_fed_data_row(row)

        except Exception as e:
            logger.error(f"Error getting latest fed data for type {data_type}: {e}")
            return None

    def get_recent_by_type(self, data_type: str, limit: int = 10) -> List[FedData]:
        """Get recent observations for a specific data type.

        Args:
            data_type: Type of fed data
            limit: Maximum number of observations to return

        Returns:
            List of FedData objects ordered by observation_date DESC
        """
        if not self._check_dependencies():
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT id, data_type, observation_date, value, details,
                           created_at, updated_at
                    FROM fed_data
                    WHERE data_type = ?
                    ORDER BY observation_date DESC
                    LIMIT ?
                """

                cursor.execute(query, (data_type, limit))
                rows = cursor.fetchall()

                fed_data_list = []
                for row in rows:
                    try:
                        fed_data = self._parse_fed_data_row(row)
                        if fed_data:
                            fed_data_list.append(fed_data)
                    except Exception as e:
                        logger.warning(f"Failed to parse fed data row: {e}")
                        continue

                logger.debug(f"Retrieved {len(fed_data_list)} fed data points for {data_type}")
                return fed_data_list

        except Exception as e:
            logger.error(f"Error getting recent fed data for type {data_type}: {e}")
            return []

    def get_all_latest(self) -> Dict[str, Optional[FedData]]:
        """Get the latest observation for each data type.

        Returns:
            Dictionary mapping data_type to latest FedData object
        """
        return {
            "inflation": self.get_latest_by_type("inflation"),
            "inflation_expectations": self.get_latest_by_type("inflation_expectations"),
            "treasury_yields": self.get_latest_by_type("treasury_yields"),
        }

    def bulk_upsert(self, fed_data_list: List[FedData]) -> int:
        """Bulk insert or update multiple fed data points.

        Args:
            fed_data_list: List of FedData objects to store

        Returns:
            Number of records successfully stored
        """
        if not fed_data_list:
            return 0

        stored_count = 0
        for fed_data in fed_data_list:
            if self.set_entity_to_database(str(fed_data.id), fed_data):
                stored_count += 1

        logger.info(f"Bulk upserted {stored_count}/{len(fed_data_list)} fed data points")
        return stored_count

    # ============================================================================
    # UTILITY METHODS
    # ============================================================================

    def _parse_fed_data_row(self, row: tuple) -> Optional[FedData]:
        """Parse database row into FedData object.

        Args:
            row: Database row tuple

        Returns:
            FedData object or None if parsing fails
        """
        try:
            return FedData(
                id=row[0],
                data_type=row[1],
                observation_date=datetime.fromisoformat(row[2]).date(),
                value=Decimal(str(row[3])),
                details=json.loads(row[4]) if row[4] else {},
                created_at=datetime.fromisoformat(row[5]),
                updated_at=datetime.fromisoformat(row[6]),
            )
        except Exception as e:
            logger.error(f"Error parsing fed data row: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Get fed data manager statistics.

        Returns:
            Dictionary with statistics
        """
        if not self._check_dependencies():
            return {"error": "Dependencies not available"}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Count by data type
                cursor.execute("""
                    SELECT data_type, COUNT(*), MAX(observation_date)
                    FROM fed_data
                    GROUP BY data_type
                """)
                by_type = {}
                for row in cursor.fetchall():
                    by_type[row[0]] = {
                        "count": row[1],
                        "latest_observation": row[2],
                    }

                # Total count
                cursor.execute("SELECT COUNT(*) FROM fed_data")
                total_count = cursor.fetchone()[0]

                return {
                    "total_records": total_count,
                    "by_type": by_type,
                    "storage": "fed_data table",
                }

        except Exception as e:
            logger.error(f"Error getting fed data manager stats: {e}")
            return {"error": str(e)}
