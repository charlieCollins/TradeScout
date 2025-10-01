"""Unit tests for SentimentEventsManager database manager."""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, date, time
from decimal import Decimal

from database.managers.sentiment_events_manager import SentimentEventsManager
from models.sentiment_event import SentimentEvent


class TestSentimentEventsManager:
    """Test SentimentEventsManager database operations."""

    @pytest.fixture
    def mock_db_manager(self):
        """Create mock database manager."""
        db_manager = Mock()
        db_manager.get_connection = MagicMock()
        return db_manager

    @pytest.fixture
    def manager(self, mock_db_manager):
        """Create SentimentEventsManager instance."""
        # Sentiment managers don't need update_tracker or metadata_manager
        return SentimentEventsManager(
            mock_db_manager,
            None,  # update_tracker not needed
            None   # metadata_manager not needed
        )

    @pytest.fixture
    def sample_sentiment_event(self):
        """Create sample SentimentEvent for testing."""
        return SentimentEvent(
            id=1,
            asset_id=42,
            sentiment_type_id=1,
            event_date=date(2025, 9, 30),
            event_time=time(14, 30, 0),
            session="regular",
            value=Decimal("0.75"),
            magnitude="medium",
            details={"title": "Apple Announces New Product", "source": "polygon"},
            created_at=datetime(2025, 9, 30, 14, 30, 0)
        )

    # ============================================================================
    # GET ENTITY FROM DATABASE TESTS
    # ============================================================================

    def test_get_entity_from_database_success(self, manager, mock_db_manager):
        """Test successful retrieval of sentiment event from database."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate database row data
        mock_cursor.fetchone.return_value = (
            1,  # id
            42,  # asset_id
            1,  # sentiment_type_id
            "2025-09-30",  # event_date
            "14:30:00",  # event_time
            "regular",  # session
            0.75,  # value
            "medium",  # magnitude
            '{"title": "Apple Announces New Product", "source": "polygon"}',  # details (JSON)
            "2025-09-30T14:30:00"  # created_at
        )

        result = manager.get_entity_from_database("1")

        assert result is not None
        assert isinstance(result, SentimentEvent)
        assert result.id == 1
        assert result.asset_id == 42
        assert result.sentiment_type_id == 1
        assert result.event_date == date(2025, 9, 30)
        assert result.event_time == time(14, 30, 0)
        assert result.session == "regular"
        assert result.value == Decimal("0.75")
        assert result.magnitude == "medium"
        assert result.details["title"] == "Apple Announces New Product"

    def test_get_entity_from_database_not_found(self, manager, mock_db_manager):
        """Test get_entity_from_database when event not found."""
        # Mock database response - no results
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = manager.get_entity_from_database("999")

        assert result is None

    def test_get_entity_from_database_no_dependencies(self):
        """Test get_entity_from_database with no dependencies."""
        manager = SentimentEventsManager(None, None, None)

        result = manager.get_entity_from_database("1")

        assert result is None

    # ============================================================================
    # SET ENTITY TO DATABASE TESTS
    # ============================================================================

    def test_set_entity_to_database_success(self, manager, mock_db_manager, sample_sentiment_event):
        """Test successful storage of sentiment event to database."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        result = manager.set_entity_to_database("1", sample_sentiment_event)

        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

        # Verify the SQL values passed
        call_args = mock_cursor.execute.call_args[0]
        values = call_args[1]
        assert values[0] == 42  # asset_id
        assert values[1] == 1  # sentiment_type_id
        assert values[2] == "2025-09-30"  # event_date
        assert values[3] == "14:30:00"  # event_time
        assert values[4] == "regular"  # session
        assert values[5] == 0.75  # value (converted to float)
        assert values[6] == "medium"  # magnitude

    def test_set_entity_to_database_none_entity(self, manager, mock_db_manager):
        """Test set_entity_to_database with None entity."""
        result = manager.set_entity_to_database("1", None)

        assert result is False

    def test_set_entity_to_database_no_dependencies(self, sample_sentiment_event):
        """Test set_entity_to_database with no dependencies."""
        manager = SentimentEventsManager(None, None, None)

        result = manager.set_entity_to_database("1", sample_sentiment_event)

        assert result is False

    # ============================================================================
    # GET EVENTS BY ASSET TESTS
    # ============================================================================

    def test_get_events_by_asset_success(self, manager, mock_db_manager):
        """Test successful retrieval of events by asset."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate two event rows
        mock_cursor.fetchall.return_value = [
            (1, 42, 1, "2025-09-30", "14:30:00", "regular", 0.75, "medium", '{}', "2025-09-30T14:30:00"),
            (2, 42, 2, "2025-09-29", "09:00:00", "premarket", 0.60, "small", '{}', "2025-09-29T09:00:00")
        ]

        result = manager.get_events_by_asset(42)

        assert len(result) == 2
        assert result[0].asset_id == 42
        assert result[1].asset_id == 42

    def test_get_events_by_asset_with_date_range(self, manager, mock_db_manager):
        """Test get_events_by_asset with date range filter."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        manager.get_events_by_asset(42, start_date=date(2025, 9, 1), end_date=date(2025, 9, 30))

        # Verify date filters in query
        call_args = mock_cursor.execute.call_args[0]
        query = call_args[0]
        assert "event_date >= ?" in query
        assert "event_date <= ?" in query

    def test_get_events_by_asset_no_dependencies(self):
        """Test get_events_by_asset with no dependencies."""
        manager = SentimentEventsManager(None, None, None)

        result = manager.get_events_by_asset(42)

        assert result == []

    # ============================================================================
    # GET EVENTS BY TYPE TESTS
    # ============================================================================

    def test_get_events_by_type_success(self, manager, mock_db_manager):
        """Test successful retrieval of events by type."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate event rows
        mock_cursor.fetchall.return_value = [
            (1, 42, 1, "2025-09-30", "14:30:00", "regular", 0.75, "medium", '{}', "2025-09-30T14:30:00"),
            (2, 43, 1, "2025-09-29", "09:00:00", "premarket", 0.60, "small", '{}', "2025-09-29T09:00:00")
        ]

        result = manager.get_events_by_type(1)

        assert len(result) == 2
        assert result[0].sentiment_type_id == 1
        assert result[1].sentiment_type_id == 1

    def test_get_events_by_type_with_date_range(self, manager, mock_db_manager):
        """Test get_events_by_type with date range filter."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        manager.get_events_by_type(1, start_date=date(2025, 9, 1), end_date=date(2025, 9, 30))

        # Verify date filters in query
        call_args = mock_cursor.execute.call_args[0]
        query = call_args[0]
        assert "event_date >= ?" in query
        assert "event_date <= ?" in query

    def test_get_events_by_type_no_dependencies(self):
        """Test get_events_by_type with no dependencies."""
        manager = SentimentEventsManager(None, None, None)

        result = manager.get_events_by_type(1)

        assert result == []

    # ============================================================================
    # GET EVENTS BY DATE RANGE TESTS
    # ============================================================================

    def test_get_events_by_date_range_success(self, manager, mock_db_manager):
        """Test successful retrieval of events by date range."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate event rows
        mock_cursor.fetchall.return_value = [
            (1, 42, 1, "2025-09-30", "14:30:00", "regular", 0.75, "medium", '{}', "2025-09-30T14:30:00"),
            (2, 43, 1, "2025-09-29", "09:00:00", "premarket", 0.60, "small", '{}', "2025-09-29T09:00:00")
        ]

        result = manager.get_events_by_date_range(date(2025, 9, 1), date(2025, 9, 30))

        assert len(result) == 2

    def test_get_events_by_date_range_no_dependencies(self):
        """Test get_events_by_date_range with no dependencies."""
        manager = SentimentEventsManager(None, None, None)

        result = manager.get_events_by_date_range(date(2025, 9, 1), date(2025, 9, 30))

        assert result == []

    # ============================================================================
    # STATISTICS TESTS
    # ============================================================================

    def test_get_stats(self, manager, mock_db_manager):
        """Test get_stats returns manager statistics."""
        # Mock database responses
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock stats queries
        mock_cursor.fetchone.side_effect = [
            (150,),  # Total events
            ("2025-09-30T14:30:00",)  # Last created
        ]
        mock_cursor.fetchall.side_effect = [
            [("news_positive", 100), ("news_negative", 50)],  # by_type
            [("medium", 80), ("small", 70)]  # by_magnitude
        ]

        stats = manager.get_stats()

        assert stats is not None
        assert "total_events" in stats
        assert stats["total_events"] == 150
        assert "by_type" in stats
        assert stats["by_type"]["news_positive"] == 100
        assert "by_magnitude" in stats
        assert stats["by_magnitude"]["medium"] == 80

    def test_get_stats_no_dependencies(self):
        """Test get_stats with no dependencies."""
        manager = SentimentEventsManager(None, None, None)

        stats = manager.get_stats()

        assert stats is not None
        assert "error" in stats
        assert stats["error"] == "Dependencies not available"
