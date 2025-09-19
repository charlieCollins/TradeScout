"""
TradeScout Storage Interfaces

Abstract interface for database connection management.
"""

from abc import ABC, abstractmethod


class DatabaseManager(ABC):
    """Abstract interface for database connection management"""

    @abstractmethod
    def get_connection(self):
        """Get database connection"""
        pass

    @abstractmethod
    def execute_migration(self, name: str, sql: str) -> None:
        """Execute a database migration"""
        pass

    @abstractmethod
    def execute_migration_file(self, file_path: str) -> None:
        """Execute migration from SQL file"""
        pass
