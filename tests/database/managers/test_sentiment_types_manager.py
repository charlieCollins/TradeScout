"""Unit tests for SentimentTypesManager database manager."""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from database.managers.sentiment_types_manager import SentimentTypesManager
from models.sentiment_type import SentimentType


class TestSentimentTypesManager:
    """Test SentimentTypesManager database operations."""

    @pytest.fixture
    def mock_db_manager(self):
        """Create mock database manager."""
        db_manager = Mock()
        db_manager.get_connection = MagicMock()
        return db_manager

    @pytest.fixture
    def manager(self, mock_db_manager):
        """Create SentimentTypesManager instance."""
        # Sentiment managers don't need update_tracker or metadata_manager
        return SentimentTypesManager(
            mock_db_manager,
            None,  # update_tracker not needed
            None   # metadata_manager not needed
        )

    @pytest.fixture
    def sample_sentiment_type(self):
        """Create sample SentimentType for testing."""
        return SentimentType(
            id=1,
            name="news_positive",
            description="Positive news sentiment",
            category="news",
            parameters={"min_confidence": 0.7, "sources": ["polygon"]},
            is_active=True,
            created_at=datetime(2025, 9, 30, 12, 0, 0)
        )

    # ============================================================================
    # GET ENTITY FROM DATABASE TESTS
    # ============================================================================

    def test_get_entity_from_database_success(self, manager, mock_db_manager):
        """Test successful retrieval of sentiment type from database."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate database row data
        mock_cursor.fetchone.return_value = (
            1,  # id
            "news_positive",  # name
            "Positive news sentiment",  # description
            "news",  # category
            '{"min_confidence": 0.7, "sources": ["polygon"]}',  # parameters (JSON)
            True,  # is_active
            "2025-09-30T12:00:00"  # created_at
        )

        result = manager.get_entity_from_database("news_positive")

        assert result is not None
        assert isinstance(result, SentimentType)
        assert result.name == "news_positive"
        assert result.description == "Positive news sentiment"
        assert result.category == "news"
        assert result.parameters == {"min_confidence": 0.7, "sources": ["polygon"]}
        assert result.is_active is True

    def test_get_entity_from_database_not_found(self, manager, mock_db_manager):
        """Test get_entity_from_database when sentiment type not found."""
        # Mock database response - no results
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = manager.get_entity_from_database("invalid_type")

        assert result is None

    def test_get_entity_from_database_no_dependencies(self):
        """Test get_entity_from_database with no dependencies."""
        manager = SentimentTypesManager(None, None, None)

        result = manager.get_entity_from_database("news_positive")

        assert result is None

    # ============================================================================
    # SET ENTITY TO DATABASE TESTS
    # ============================================================================

    def test_set_entity_to_database_success(self, manager, mock_db_manager, sample_sentiment_type):
        """Test successful storage of sentiment type to database."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        result = manager.set_entity_to_database("news_positive", sample_sentiment_type)

        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

        # Verify the SQL values passed
        call_args = mock_cursor.execute.call_args[0]
        values = call_args[1]
        assert values[0] == "news_positive"  # name
        assert values[1] == "Positive news sentiment"  # description
        assert values[2] == "news"  # category
        assert '{"min_confidence": 0.7' in values[3]  # parameters (JSON string)

    def test_set_entity_to_database_none_entity(self, manager, mock_db_manager):
        """Test set_entity_to_database with None entity."""
        result = manager.set_entity_to_database("news_positive", None)

        assert result is False

    def test_set_entity_to_database_no_dependencies(self, sample_sentiment_type):
        """Test set_entity_to_database with no dependencies."""
        manager = SentimentTypesManager(None, None, None)

        result = manager.set_entity_to_database("news_positive", sample_sentiment_type)

        assert result is False

    # ============================================================================
    # GET ALL TYPES TESTS
    # ============================================================================

    def test_get_all_types_success(self, manager, mock_db_manager):
        """Test successful retrieval of all sentiment types."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate two sentiment type rows
        mock_cursor.fetchall.return_value = [
            (1, "news_positive", "Positive news", "news", '{}', True, "2025-09-30T12:00:00"),
            (2, "news_negative", "Negative news", "news", '{}', True, "2025-09-30T12:00:00")
        ]

        result = manager.get_all_types()

        assert len(result) == 2
        assert result[0].name == "news_positive"
        assert result[1].name == "news_negative"

    def test_get_all_types_active_only(self, manager, mock_db_manager):
        """Test that active_only parameter filters correctly."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        manager.get_all_types(active_only=True)

        # Verify WHERE clause added for active types
        call_args = mock_cursor.execute.call_args[0]
        query = call_args[0]
        assert "WHERE is_active = 1" in query

    def test_get_all_types_no_dependencies(self):
        """Test get_all_types with no dependencies."""
        manager = SentimentTypesManager(None, None, None)

        result = manager.get_all_types()

        assert result == []

    # ============================================================================
    # GET TYPES BY CATEGORY TESTS
    # ============================================================================

    def test_get_types_by_category_success(self, manager, mock_db_manager):
        """Test successful retrieval of sentiment types by category."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            (1, "news_positive", "Positive news", "news", '{}', True, "2025-09-30T12:00:00"),
            (2, "news_negative", "Negative news", "news", '{}', True, "2025-09-30T12:00:00")
        ]

        result = manager.get_types_by_category("news")

        assert len(result) == 2
        assert all(t.category == "news" for t in result)

    def test_get_types_by_category_not_found(self, manager, mock_db_manager):
        """Test get_types_by_category when no types found."""
        # Mock database response - no results
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        result = manager.get_types_by_category("nonexistent")

        assert result == []

    # ============================================================================
    # GET TYPE ID BY NAME TESTS
    # ============================================================================

    def test_get_type_id_by_name_success(self, manager, mock_db_manager):
        """Test successful retrieval of sentiment type ID by name."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)

        result = manager.get_type_id_by_name("news_positive")

        assert result == 1

    def test_get_type_id_by_name_not_found(self, manager, mock_db_manager):
        """Test get_type_id_by_name when type not found."""
        # Mock database response - no results
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = manager.get_type_id_by_name("invalid")

        assert result is None

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
            (3,),  # Total types
            (3,),  # Active types
            ("2025-09-30T12:00:00",)  # Last created
        ]
        mock_cursor.fetchall.return_value = [("news", 3)]

        stats = manager.get_stats()

        assert stats is not None
        assert "total_types" in stats
        assert stats["total_types"] == 3
        assert "active_types" in stats
        assert stats["active_types"] == 3
        assert "by_category" in stats
        assert stats["by_category"]["news"] == 3

    def test_get_stats_no_dependencies(self):
        """Test get_stats with no dependencies."""
        manager = SentimentTypesManager(None, None, None)

        stats = manager.get_stats()

        assert stats is not None
        assert "error" in stats
        assert stats["error"] == "Dependencies not available"
