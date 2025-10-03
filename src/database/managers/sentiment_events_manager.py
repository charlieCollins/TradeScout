"""Sentiment events database manager for sentiment event storage and retrieval.

Sentiment events are continuously detected and stored events (not bootstrap operations).
Each event represents a detected sentiment signal (news, analyst action, etc.) for a specific asset.

No TTL/metadata tracking needed - events are created on-demand and kept for 90 days (cleanup, not TTL).
"""

import logging
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, date, time
from decimal import Decimal
from models.sentiment_event import SentimentEvent
from .base_manager import BaseManager

logger = logging.getLogger(__name__)


class SentimentEventsManager(BaseManager):
    """Database manager for sentiment event CRUD operations.

    Sentiment events are continuously created (not batch operations), so no TTL tracking needed.
    90-day retention is for cleanup, not staleness checking.
    """

    def get_data_update_metadata_type(self):
        """Sentiment events don't use metadata tracking.

        This method is required by BaseManager but not used for sentiment events.
        """
        return None

    def get_ttl_seconds(self) -> int:
        """Sentiment events don't have TTL.

        This method is required by BaseManager but not used for sentiment events.
        Returns 0 to indicate no expiration (90-day retention is cleanup, not TTL).
        """
        return 0

    def _check_dependencies(self) -> bool:
        """Check if required dependencies are available.

        Sentiment managers only need db_manager, not metadata_manager (no TTL tracking needed).
        """
        if not self.db_manager:
            logger.warning("Database manager not available")
            return False
        return True

    def get_entity_from_database(self, key: str) -> Optional[SentimentEvent]:
        """Get SentimentEvent from database by ID.

        Args:
            key: Event ID as string

        Returns:
            SentimentEvent object or None if not found
        """
        if not self._check_dependencies():
            return None

        try:
            event_id = int(key)
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT id, asset_id, sentiment_type_id, event_date, event_time,
                           session, value, magnitude, details, created_at
                    FROM sentiment_events
                    WHERE id = ?
                """

                cursor.execute(query, (event_id,))
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"No sentiment event found for id {event_id}")
                    return None

                return self._parse_sentiment_event_row(row)

        except (ValueError, Exception) as e:
            logger.error(f"Error getting sentiment event from database for id {key}: {e}")
            return None

    def set_entity_to_database(self, key: str, entity: SentimentEvent) -> bool:
        """Store SentimentEvent to database.

        Args:
            key: Event ID as string (ignored - uses entity.id or auto-increments)
            entity: SentimentEvent object to store

        Returns:
            True if successful, False otherwise
        """
        if not self._check_dependencies() or not entity:
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Use INSERT OR REPLACE to handle both new and existing events
                query = """
                    INSERT OR REPLACE INTO sentiment_events (
                        asset_id, sentiment_type_id, event_date, event_time,
                        session, value, magnitude, details, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

                values = (
                    entity.asset_id,
                    entity.sentiment_type_id,
                    entity.event_date.isoformat(),
                    entity.event_time.isoformat() if entity.event_time else None,
                    entity.session,
                    float(entity.value),  # Convert Decimal to float for SQLite
                    entity.magnitude,
                    json.dumps(entity.details),  # Serialize dict to JSON
                    entity.created_at.isoformat()
                )

                cursor.execute(query, values)
                conn.commit()

                logger.debug(f"Successfully stored sentiment event {entity.id}")
                return True

        except Exception as e:
            logger.error(f"Error storing sentiment event to database: {e}")
            return False

    # ============================================================================
    # SENTIMENT EVENT-SPECIFIC METHODS
    # ============================================================================

    def get_events_by_asset(
        self,
        asset_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[SentimentEvent]:
        """Get sentiment events for a specific asset.

        Args:
            asset_id: Asset database ID
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of SentimentEvent objects
        """
        if not self._check_dependencies():
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT id, asset_id, sentiment_type_id, event_date, event_time,
                           session, value, magnitude, details, created_at
                    FROM sentiment_events
                    WHERE asset_id = ?
                """

                params = [asset_id]

                if start_date:
                    query += " AND event_date >= ?"
                    params.append(start_date.isoformat())

                if end_date:
                    query += " AND event_date <= ?"
                    params.append(end_date.isoformat())

                query += " ORDER BY event_date DESC, event_time DESC"

                cursor.execute(query, params)
                rows = cursor.fetchall()

                events = []
                for row in rows:
                    try:
                        event = self._parse_sentiment_event_row(row)
                        if event:
                            events.append(event)
                    except Exception as e:
                        logger.warning(f"Failed to parse sentiment event row: {e}")
                        continue

                logger.debug(f"Retrieved {len(events)} sentiment events for asset {asset_id}")
                return events

        except Exception as e:
            logger.error(f"Error getting sentiment events for asset {asset_id}: {e}")
            return []

    def get_events_by_type(
        self,
        sentiment_type_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[SentimentEvent]:
        """Get sentiment events by type.

        Args:
            sentiment_type_id: Sentiment type ID
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of SentimentEvent objects
        """
        if not self._check_dependencies():
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT id, asset_id, sentiment_type_id, event_date, event_time,
                           session, value, magnitude, details, created_at
                    FROM sentiment_events
                    WHERE sentiment_type_id = ?
                """

                params = [sentiment_type_id]

                if start_date:
                    query += " AND event_date >= ?"
                    params.append(start_date.isoformat())

                if end_date:
                    query += " AND event_date <= ?"
                    params.append(end_date.isoformat())

                query += " ORDER BY event_date DESC, event_time DESC"

                cursor.execute(query, params)
                rows = cursor.fetchall()

                events = []
                for row in rows:
                    try:
                        event = self._parse_sentiment_event_row(row)
                        if event:
                            events.append(event)
                    except Exception as e:
                        logger.warning(f"Failed to parse sentiment event row: {e}")
                        continue

                logger.debug(f"Retrieved {len(events)} sentiment events for type {sentiment_type_id}")
                return events

        except Exception as e:
            logger.error(f"Error getting sentiment events for type {sentiment_type_id}: {e}")
            return []

    def get_events_by_date_range(
        self,
        start_date: date,
        end_date: date
    ) -> List[SentimentEvent]:
        """Get all sentiment events in a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of SentimentEvent objects
        """
        if not self._check_dependencies():
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT id, asset_id, sentiment_type_id, event_date, event_time,
                           session, value, magnitude, details, created_at
                    FROM sentiment_events
                    WHERE event_date >= ? AND event_date <= ?
                    ORDER BY event_date DESC, event_time DESC
                """

                cursor.execute(query, (start_date.isoformat(), end_date.isoformat()))
                rows = cursor.fetchall()

                events = []
                for row in rows:
                    try:
                        event = self._parse_sentiment_event_row(row)
                        if event:
                            events.append(event)
                    except Exception as e:
                        logger.warning(f"Failed to parse sentiment event row: {e}")
                        continue

                logger.debug(f"Retrieved {len(events)} sentiment events in date range")
                return events

        except Exception as e:
            logger.error(f"Error getting sentiment events for date range: {e}")
            return []

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _parse_sentiment_event_row(self, row: tuple) -> Optional[SentimentEvent]:
        """Parse database row into SentimentEvent object.

        Args:
            row: Database row tuple

        Returns:
            SentimentEvent object or None if parsing fails
        """
        try:
            def parse_time(time_str: Optional[str]) -> Optional[time]:
                """Parse time string to time object."""
                if not time_str:
                    return None
                try:
                    # Parse ISO format time (HH:MM:SS)
                    parts = time_str.split(':')
                    return time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
                except (ValueError, IndexError):
                    return None

            return SentimentEvent(
                id=row[0],
                asset_id=row[1],
                sentiment_type_id=row[2],
                event_date=date.fromisoformat(row[3]),
                event_time=parse_time(row[4]),
                session=row[5],
                value=Decimal(str(row[6])),  # Convert float to Decimal
                magnitude=row[7],
                details=json.loads(row[8]) if row[8] else {},  # Parse JSON to dict
                created_at=datetime.fromisoformat(row[9])
            )

        except Exception as e:
            logger.error(f"Error parsing sentiment event row: {e}")
            return None

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get sentiment events manager statistics."""
        if not self._check_dependencies():
            return {"error": "Dependencies not available"}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Count total events
                cursor.execute("SELECT COUNT(*) FROM sentiment_events")
                total_events = cursor.fetchone()[0]

                # Count by sentiment type
                cursor.execute("""
                    SELECT st.name, COUNT(*)
                    FROM sentiment_events se
                    JOIN sentiment_types st ON se.sentiment_type_id = st.id
                    GROUP BY st.name
                    ORDER BY COUNT(*) DESC
                """)
                by_type = dict(cursor.fetchall())

                # Count by magnitude
                cursor.execute("""
                    SELECT magnitude, COUNT(*)
                    FROM sentiment_events
                    GROUP BY magnitude
                    ORDER BY COUNT(*) DESC
                """)
                by_magnitude = dict(cursor.fetchall())

                # Get most recent event
                cursor.execute("SELECT MAX(created_at) FROM sentiment_events")
                last_created = cursor.fetchone()[0]

                return {
                    "total_events": total_events,
                    "by_type": by_type,
                    "by_magnitude": by_magnitude,
                    "last_created": last_created,
                    "storage": "sentiment_events table"
                }

        except Exception as e:
            logger.error(f"Error getting sentiment events manager stats: {e}")
            return {"error": str(e)}
