"""Bootstrapper for market data."""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MarketBootstrapper:
    """Bootstrap market reference data."""

    def __init__(self, db_manager):
        """Initialize the market bootstrapper.

        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager

    def bootstrap_markets(self) -> Dict[str, int]:
        """Ensure all required markets exist in database.

        Returns:
            Dictionary with bootstrap statistics
        """
        if not self.db_manager:
            raise ValueError("Database manager required for markets bootstrap")

        stats = {'inserted': 0, 'updated': 0, 'errors': 0}

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            # Define markets to bootstrap
            markets = [
                ('XNYS', 'New York Stock Exchange', 'America/New_York'),
                ('XNAS', 'NASDAQ', 'America/New_York'),
                ('ARCX', 'NYSE Arca', 'America/New_York'),
                ('XASE', 'NYSE American', 'America/New_York'),
                ('BATS', 'Cboe BZX', 'America/New_York'),
                ('IEXG', 'IEX', 'America/New_York'),
                ('UNKNOWN', 'Unknown Exchange', 'America/New_York'),
            ]

            for code, name, timezone in markets:
                try:
                    # Check if market exists
                    cursor.execute("SELECT id FROM markets WHERE code = ?", (code,))
                    existing = cursor.fetchone()

                    if existing:
                        # Update if needed
                        cursor.execute("""
                            UPDATE markets
                            SET name = ?, timezone = ?
                            WHERE code = ?
                        """, (name, timezone, code))
                        if cursor.rowcount > 0:
                            stats['updated'] += 1
                    else:
                        # Insert new market
                        cursor.execute("""
                            INSERT INTO markets (code, name, timezone)
                            VALUES (?, ?, ?)
                        """, (code, name, timezone))
                        stats['inserted'] += 1

                except Exception as e:
                    logger.error(f"Error bootstrapping market {code}: {e}")
                    stats['errors'] += 1

            conn.commit()
            logger.info(f"Markets bootstrapped: {stats['inserted']} inserted, "
                       f"{stats['updated']} updated, {stats['errors']} errors")

        return stats

    def get_markets(self) -> List[str]:
        """Get list of all markets.

        Returns:
            List of market names
        """
        if not self.db_manager:
            return []

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM markets ORDER BY code")
            return [row[0] for row in cursor.fetchall()]