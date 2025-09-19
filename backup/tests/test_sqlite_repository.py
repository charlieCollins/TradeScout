"""
Tests for SQLiteDatabaseManager

Tests the core database functionality including:
- Database initialization
- Connection management
- Migration execution
- Table creation
- Basic CRUD operations
"""

import pytest
import sqlite3
import tempfile
import os
from pathlib import Path

from src.tradescout.storage.sqlite_repository import SQLiteDatabaseManager


class TestSQLiteDatabaseManager:
    """Test suite for SQLiteDatabaseManager"""

    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database path for testing"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            db_path = tmp_file.name
        
        yield db_path
        
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def db_manager(self, temp_db_path):
        """Create SQLiteDatabaseManager instance for testing"""
        return SQLiteDatabaseManager(temp_db_path)

    def test_initialization(self, temp_db_path):
        """Test database manager initialization"""
        db_manager = SQLiteDatabaseManager(temp_db_path)
        
        assert db_manager.db_path == temp_db_path
        assert os.path.exists(temp_db_path)

    def test_directory_creation(self):
        """Test that database directory is created if it doesn't exist"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "nested", "directory", "test.db")
            
            # Directory doesn't exist initially
            assert not os.path.exists(os.path.dirname(db_path))
            
            # Create database manager
            db_manager = SQLiteDatabaseManager(db_path)
            
            # Directory should now exist
            assert os.path.exists(os.path.dirname(db_path))
            assert os.path.exists(db_path)

    def test_get_connection(self, db_manager):
        """Test getting database connection"""
        conn = db_manager.get_connection()
        
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)
        
        # Test connection works
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1
        
        conn.close()

    def test_connection_isolation(self, db_manager):
        """Test that each get_connection call returns a new connection"""
        conn1 = db_manager.get_connection()
        conn2 = db_manager.get_connection()
        
        assert conn1 is not conn2
        
        conn1.close()
        conn2.close()

    def test_execute_migration(self, db_manager):
        """Test executing a database migration"""
        migration_sql = """
        CREATE TABLE test_table (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        INSERT INTO test_table (name) VALUES ('test_record');
        """
        
        # Execute migration
        db_manager.execute_migration("test_migration", migration_sql)
        
        # Verify table was created and data inserted
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")
        table_exists = cursor.fetchone()
        assert table_exists is not None
        
        cursor.execute("SELECT COUNT(*) FROM test_table")
        count = cursor.fetchone()[0]
        assert count == 1
        
        cursor.execute("SELECT name FROM test_table")
        name = cursor.fetchone()[0]
        assert name == "test_record"
        
        conn.close()

    def test_migration_file_execution(self, db_manager):
        """Test executing migration from file"""
        # Create a temporary migration file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as tmp_file:
            tmp_file.write("""
            CREATE TABLE migration_test (
                id INTEGER PRIMARY KEY,
                value TEXT
            );
            INSERT INTO migration_test (value) VALUES ('from_file');
            """)
            migration_file = tmp_file.name
        
        try:
            # Execute migration from file
            db_manager.execute_migration_file(migration_file)
            
            # Verify results
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT value FROM migration_test")
            value = cursor.fetchone()[0]
            assert value == "from_file"
            
            conn.close()
        finally:
            os.unlink(migration_file)

    def test_transaction_commit(self, db_manager):
        """Test transaction commit"""
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        # Create test table
        cursor.execute("CREATE TABLE transaction_test (id INTEGER, data TEXT)")
        
        # Start transaction
        cursor.execute("BEGIN TRANSACTION")
        cursor.execute("INSERT INTO transaction_test (id, data) VALUES (1, 'test1')")
        cursor.execute("INSERT INTO transaction_test (id, data) VALUES (2, 'test2')")
        conn.commit()
        
        # Verify data persisted
        cursor.execute("SELECT COUNT(*) FROM transaction_test")
        count = cursor.fetchone()[0]
        assert count == 2
        
        conn.close()

    def test_transaction_rollback(self, db_manager):
        """Test transaction rollback"""
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        # Create test table and insert initial data
        cursor.execute("CREATE TABLE rollback_test (id INTEGER PRIMARY KEY, data TEXT)")
        cursor.execute("INSERT INTO rollback_test (data) VALUES ('initial')")
        conn.commit()
        
        # Start transaction and make changes
        cursor.execute("BEGIN TRANSACTION")
        cursor.execute("INSERT INTO rollback_test (data) VALUES ('should_rollback')")
        cursor.execute("UPDATE rollback_test SET data = 'modified' WHERE data = 'initial'")
        
        # Rollback
        conn.rollback()
        
        # Verify changes were rolled back
        cursor.execute("SELECT COUNT(*) FROM rollback_test")
        count = cursor.fetchone()[0]
        assert count == 1  # Only initial record
        
        cursor.execute("SELECT data FROM rollback_test")
        data = cursor.fetchone()[0]
        assert data == "initial"  # Original value preserved
        
        conn.close()

    def test_datetime_adapter(self, db_manager):
        """Test datetime adapter/converter functionality"""
        from datetime import datetime
        
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        # Create test table
        cursor.execute("CREATE TABLE datetime_test (id INTEGER, timestamp DATETIME)")
        
        # Insert datetime
        test_time = datetime(2023, 9, 14, 15, 30, 45)
        cursor.execute("INSERT INTO datetime_test (id, timestamp) VALUES (?, ?)", (1, test_time))
        conn.commit()
        
        # Retrieve datetime
        cursor.execute("SELECT timestamp FROM datetime_test WHERE id = 1")
        retrieved_time = cursor.fetchone()[0]
        
        # Should be able to work with datetime (either as string or datetime object)
        assert retrieved_time is not None
        
        conn.close()

    def test_concurrent_connections(self, db_manager):
        """Test multiple concurrent connections"""
        # Create table with first connection
        conn1 = db_manager.get_connection()
        cursor1 = conn1.cursor()
        cursor1.execute("CREATE TABLE concurrent_test (id INTEGER, data TEXT)")
        cursor1.execute("INSERT INTO concurrent_test (id, data) VALUES (1, 'conn1')")
        conn1.commit()
        
        # Read with second connection
        conn2 = db_manager.get_connection()
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT data FROM concurrent_test WHERE id = 1")
        data = cursor2.fetchone()[0]
        assert data == "conn1"
        
        # Write with second connection
        cursor2.execute("INSERT INTO concurrent_test (id, data) VALUES (2, 'conn2')")
        conn2.commit()
        
        # Verify with first connection
        cursor1.execute("SELECT COUNT(*) FROM concurrent_test")
        count = cursor1.fetchone()[0]
        assert count == 2
        
        conn1.close()
        conn2.close()

    def test_error_handling(self, db_manager):
        """Test error handling in database operations"""
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        # Test SQL syntax error
        with pytest.raises(sqlite3.OperationalError):
            cursor.execute("INVALID SQL STATEMENT")
        
        # Test constraint violation
        cursor.execute("CREATE TABLE constraint_test (id INTEGER PRIMARY KEY, unique_val TEXT UNIQUE)")
        cursor.execute("INSERT INTO constraint_test (unique_val) VALUES ('unique')")
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("INSERT INTO constraint_test (unique_val) VALUES ('unique')")
        
        conn.close()

    def test_database_file_permissions(self, temp_db_path):
        """Test database file is created with appropriate permissions"""
        db_manager = SQLiteDatabaseManager(temp_db_path)
        
        # Check file exists and is readable/writable
        assert os.path.exists(temp_db_path)
        assert os.access(temp_db_path, os.R_OK)
        assert os.access(temp_db_path, os.W_OK)
        
        # File should not be executable
        assert not os.access(temp_db_path, os.X_OK)

    def test_connection_close_cleanup(self, db_manager):
        """Test that connections are properly cleaned up"""
        connections = []
        
        # Create multiple connections
        for i in range(5):
            conn = db_manager.get_connection()
            connections.append(conn)
        
        # Close all connections
        for conn in connections:
            conn.close()
        
        # Should be able to create new connections
        new_conn = db_manager.get_connection()
        cursor = new_conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1
        
        new_conn.close()