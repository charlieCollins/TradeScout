"""
Universe Manager

Manages asset universes in SQLite database with proper relational design.
Focuses on universe creation/management and asset-universe memberships.
Assets are managed separately by the storage layer.
"""

import logging
import sqlite3
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class UniverseManager:
    """Manages asset universes and their memberships in SQLite database"""

    def __init__(self, db_manager):
        """Initialize universe manager with database manager instance"""
        from .sqlite_repository import SQLiteDatabaseManager

        if isinstance(db_manager, SQLiteDatabaseManager):
            self.db_manager = db_manager
        elif isinstance(db_manager, str):
            # Fallback: if string path provided, create db manager
            self.db_manager = SQLiteDatabaseManager(db_manager)
        else:
            raise TypeError(
                f"Expected SQLiteDatabaseManager or str, got {type(db_manager)}"
            )

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory"""
        conn = self.db_manager.get_connection()
        conn.row_factory = sqlite3.Row
        return conn

    # Universe Management Methods

    def create_universe(self, name: str, description: str = None) -> int:
        """
        Create a new universe

        Args:
            name: Universe name
            description: Optional description

        Returns:
            Universe ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO universes (name, description)
                VALUES (?, ?)
            """,
                (name, description),
            )

            universe_id = cursor.lastrowid
            conn.commit()

            logger.debug(f"Created universe {name} with ID {universe_id}")
            return universe_id

        except Exception as e:
            logger.error(f"Error creating universe {name}: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_universe(self, name: str) -> Optional[Dict]:
        """Get universe details by name"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM universes WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def add_to_universe(
        self, symbol: str, universe_name: str, reason: str = None
    ) -> bool:
        """Add an asset to a universe by symbol and universe name"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get asset ID
            cursor.execute("SELECT id FROM assets WHERE symbol = ?", (symbol,))
            asset = cursor.fetchone()
            if not asset:
                logger.warning(f"Asset {symbol} not found - cannot add to universe")
                return False

            # Get universe ID
            cursor.execute("SELECT id FROM universes WHERE name = ?", (universe_name,))
            universe = cursor.fetchone()
            if not universe:
                logger.warning(f"Universe {universe_name} not found - cannot add asset")
                return False

            # Add membership
            cursor.execute(
                """
                INSERT OR REPLACE INTO universe_memberships 
                (asset_id, universe_id, reason, is_active)
                VALUES (?, ?, ?, 1)
            """,
                (asset["id"], universe["id"], reason),
            )

            conn.commit()
            logger.debug(f"Added {symbol} to {universe_name} universe")
            return True

        except Exception as e:
            logger.error(f"Error adding {symbol} to universe: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_universe_assets(
        self, universe_name: str, active_only: bool = True
    ) -> List[str]:
        """Get all asset symbols in a universe"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            query = """
                SELECT a.symbol 
                FROM assets a
                JOIN universe_memberships um ON a.id = um.asset_id
                JOIN universes u ON um.universe_id = u.id
                WHERE u.name = ?
            """

            params = [universe_name]

            if active_only:
                query += " AND um.is_active = 1 AND a.is_active = 1"

            query += " ORDER BY a.symbol"

            cursor.execute(query, params)
            return [row["symbol"] for row in cursor.fetchall()]

        finally:
            conn.close()

    def get_universe_statistics(self, universe_name: str) -> Dict:
        """Get statistics for a universe"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT 
                    COUNT(*) as total_assets,
                    SUM(CASE WHEN um.is_active = 1 THEN 1 ELSE 0 END) as active_assets,
                    MIN(um.added_date) as first_asset_added,
                    MAX(um.added_date) as last_asset_added
                FROM universe_memberships um
                JOIN universes u ON um.universe_id = u.id
                WHERE u.name = ?
            """,
                (universe_name,),
            )

            row = cursor.fetchone()
            return dict(row) if row else {}

        finally:
            conn.close()

    def get_all_active_assets(self) -> List[str]:
        """Get all active asset symbols across all universes"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT DISTINCT a.symbol
                FROM assets a
                JOIN universe_memberships um ON a.id = um.asset_id
                WHERE a.is_active = 1 AND um.is_active = 1
                ORDER BY a.symbol
            """
            )

            return [row["symbol"] for row in cursor.fetchall()]

        finally:
            conn.close()

    # Legacy methods for backward compatibility
    def add_asset(self, symbol: str, name: str = None, **kwargs) -> int:
        """
        Add a new asset to the database

        Args:
            symbol: Stock symbol
            name: Company name
            **kwargs: Additional fields (exchange, sector, market_cap_millions, etc.)

        Returns:
            Asset ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Build insert query dynamically
            fields = ["symbol", "name"]
            values = [symbol, name]
            placeholders = ["?", "?"]

            for key, value in kwargs.items():
                if key in [
                    "asset_type",
                    "exchange",
                    "sector",
                    "industry",
                    "market_cap_millions",
                    "avg_daily_volume",
                    "is_active",
                    "is_tradeable",
                ]:
                    fields.append(key)
                    values.append(value)
                    placeholders.append("?")

            query = f"""
                INSERT OR REPLACE INTO assets ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
            """

            cursor.execute(query, values)
            asset_id = cursor.lastrowid
            conn.commit()

            logger.debug(f"Added asset {symbol} with ID {asset_id}")
            return asset_id

        except Exception as e:
            logger.error(f"Error adding asset {symbol}: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_asset(self, symbol: str) -> Optional[Dict]:
        """Get asset details by symbol"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM assets WHERE symbol = ?", (symbol,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_asset(self, symbol: str, **kwargs) -> bool:
        """Update asset information"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Build update query dynamically
            set_clauses = []
            values = []

            for key, value in kwargs.items():
                if key in [
                    "name",
                    "asset_type",
                    "exchange",
                    "sector",
                    "industry",
                    "market_cap_millions",
                    "avg_daily_volume",
                    "is_active",
                    "is_tradeable",
                ]:
                    set_clauses.append(f"{key} = ?")
                    values.append(value)

            if not set_clauses:
                return False

            # Add updated_at
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            values.append(symbol)

            query = f"""
                UPDATE assets 
                SET {', '.join(set_clauses)}
                WHERE symbol = ?
            """

            cursor.execute(query, values)
            conn.commit()

            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error updating asset {symbol}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    # Legacy Methods - End of Class
