"""
Tests for SQLite Repository Implementation
"""

import os
import tempfile

import pytest

from src.tradescout.storage.sqlite_repository import (
    SQLiteDatabaseManager,
    create_sqlite_database_manager,
)


@pytest.fixture
def temp_db_path():
    """Create a temporary database file path"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_file:
        temp_path = temp_file.name
    yield temp_path
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def db_manager(temp_db_path):
    """Create a SQLite database manager with temporary database"""
    manager = SQLiteDatabaseManager(temp_db_path)
    manager.initialize_database()
    return manager


class TestSQLiteDatabaseManager:
    """Test cases for SQLite Database Manager"""

    def test_database_creation(self, temp_db_path):
        """Test database file creation"""
        manager = SQLiteDatabaseManager(temp_db_path)
        assert manager.db_path == temp_db_path

    def test_initialize_database(self, db_manager):
        """Test database initialization"""
        success = db_manager.initialize_database()
        assert success is True

    def test_get_database_stats(self, db_manager):
        """Test getting database statistics"""
        stats = db_manager.get_database_stats()
        assert isinstance(stats, dict)
        assert "database_size_bytes" in stats
        assert "database_path" in stats

    def test_cleanup_old_data(self, db_manager):
        """Test cleanup old data (should return 0 since no data)"""
        deleted_count = db_manager.cleanup_old_data(30)
        assert deleted_count == 0

    def test_execute_raw_query(self, db_manager):
        """Test executing raw SQL queries"""
        result = db_manager.execute_raw_query("SELECT 1 as test")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["test"] == 1

    def test_backup_database(self, db_manager, temp_db_path):
        """Test database backup functionality"""
        backup_path = temp_db_path + ".backup"
        try:
            success = db_manager.backup_database(backup_path)
            assert success is True
            assert os.path.exists(backup_path)
        finally:
            if os.path.exists(backup_path):
                os.unlink(backup_path)

    def test_restore_database(self, temp_db_path):
        """Test database restore functionality"""
        # Create source database
        source_manager = SQLiteDatabaseManager(temp_db_path)
        source_manager.initialize_database()
        
        # Create backup
        backup_path = temp_db_path + ".backup"
        source_manager.backup_database(backup_path)
        
        # Create new database and restore
        new_db_path = temp_db_path + ".new"
        try:
            new_manager = SQLiteDatabaseManager(new_db_path)
            success = new_manager.restore_database(backup_path)
            assert success is True
            assert os.path.exists(new_db_path)
        finally:
            if os.path.exists(backup_path):
                os.unlink(backup_path)
            if os.path.exists(new_db_path):
                os.unlink(new_db_path)

    def test_create_database_manager_function(self):
        """Test the create_sqlite_database_manager function"""
        manager = create_sqlite_database_manager()
        assert isinstance(manager, SQLiteDatabaseManager)

    def test_unimplemented_repositories(self, db_manager):
        """Test that unimplemented repositories raise NotImplementedError"""
        with pytest.raises(NotImplementedError):
            _ = db_manager.extended_hours
        
        with pytest.raises(NotImplementedError):
            _ = db_manager.news
        
        with pytest.raises(NotImplementedError):
            _ = db_manager.sentiment


if __name__ == "__main__":
    pytest.main([__file__, "-v"])