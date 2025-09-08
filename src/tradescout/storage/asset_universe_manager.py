"""
Asset Universe Manager

Manages dynamic asset universe in SQLite database, replacing static YAML files.
Provides methods to add/remove assets, manage universes, and track performance.
"""

import logging
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal

logger = logging.getLogger(__name__)


class AssetUniverseManager:
    """Manages asset universe in SQLite database"""
    
    def __init__(self, db_path: str = "data/tradescout.db"):
        """Initialize asset universe manager with database connection"""
        self.db_path = db_path
        self._ensure_database_exists()
        
    def _ensure_database_exists(self):
        """Ensure database file exists"""
        db_file = Path(self.db_path)
        if not db_file.exists():
            raise FileNotFoundError(f"Database not found at {self.db_path}")
            
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # Asset Management Methods
    
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
            fields = ['symbol', 'name']
            values = [symbol, name]
            placeholders = ['?', '?']
            
            for key, value in kwargs.items():
                if key in ['asset_type', 'exchange', 'sector', 'industry', 
                          'market_cap_millions', 'avg_daily_volume', 'is_active', 'is_tradeable']:
                    fields.append(key)
                    values.append(value)
                    placeholders.append('?')
            
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
                if key in ['name', 'asset_type', 'exchange', 'sector', 'industry',
                          'market_cap_millions', 'avg_daily_volume', 'is_active', 'is_tradeable']:
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
    
    # Universe Management Methods
    
    def add_to_universe(self, symbol: str, universe_name: str, reason: str = None) -> bool:
        """Add an asset to a specific universe"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Get asset ID
            cursor.execute("SELECT id FROM assets WHERE symbol = ?", (symbol,))
            asset = cursor.fetchone()
            
            if not asset:
                # Auto-create asset if it doesn't exist
                asset_id = self.add_asset(symbol)
            else:
                asset_id = asset['id']
            
            # Add to universe
            cursor.execute("""
                INSERT OR REPLACE INTO universe_membership 
                (asset_id, universe_name, reason, is_active)
                VALUES (?, ?, ?, 1)
            """, (asset_id, universe_name, reason))
            
            conn.commit()
            logger.debug(f"Added {symbol} to {universe_name} universe")
            return True
            
        except Exception as e:
            logger.error(f"Error adding {symbol} to universe: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def remove_from_universe(self, symbol: str, universe_name: str, reason: str = None) -> bool:
        """Remove an asset from a universe"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Get asset ID
            cursor.execute("SELECT id FROM assets WHERE symbol = ?", (symbol,))
            asset = cursor.fetchone()
            
            if not asset:
                return False
            
            # Mark as inactive in universe
            cursor.execute("""
                UPDATE universe_membership 
                SET is_active = 0, removed_date = CURRENT_DATE, reason = ?
                WHERE asset_id = ? AND universe_name = ?
            """, (reason, asset['id'], universe_name))
            
            conn.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            logger.error(f"Error removing {symbol} from universe: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def get_universe_symbols(self, universe_name: str, active_only: bool = True) -> List[str]:
        """Get all symbols in a universe"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            query = """
                SELECT a.symbol 
                FROM assets a
                JOIN universe_membership um ON a.id = um.asset_id
                WHERE um.universe_name = ?
            """
            
            params = [universe_name]
            
            if active_only:
                query += " AND um.is_active = 1 AND a.is_active = 1"
            
            query += " ORDER BY a.symbol"
            
            cursor.execute(query, params)
            return [row['symbol'] for row in cursor.fetchall()]
            
        finally:
            conn.close()
    
    def import_from_yaml(self, yaml_path: str) -> Tuple[int, int]:
        """
        Import assets from existing YAML file
        
        Returns:
            Tuple of (assets_imported, universe_memberships_added)
        """
        import yaml
        
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        
        assets_imported = 0
        memberships_added = 0
        
        # Assuming structure like screening_universe.yaml
        for universe_name, universe_data in data.items():
            if not isinstance(universe_data, dict):
                continue
                
            symbols = universe_data.get('symbols', [])
            min_volume = universe_data.get('min_avg_volume')
            min_market_cap = universe_data.get('min_market_cap')
            
            # Create or update universe
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO universes 
                    (name, description, min_avg_volume, min_market_cap_millions)
                    VALUES (?, ?, ?, ?)
                """, (universe_name, 
                     universe_data.get('description', ''),
                     min_volume,
                     min_market_cap / 1000000 if min_market_cap else None))
                conn.commit()
            except Exception as e:
                logger.error(f"Error creating universe {universe_name}: {e}")
            finally:
                conn.close()
            
            # Add symbols to universe
            for symbol in symbols:
                asset_id = self.add_asset(symbol)
                if asset_id:
                    assets_imported += 1
                
                if self.add_to_universe(symbol, universe_name):
                    memberships_added += 1
        
        logger.info(f"Imported {assets_imported} assets, added {memberships_added} universe memberships")
        return assets_imported, memberships_added
    
    # Historical Data Methods
    
    def save_price_history(self, symbol: str, date: date, **price_data) -> bool:
        """Save historical price data for an asset"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Get asset ID
            asset = self.get_asset(symbol)
            if not asset:
                asset_id = self.add_asset(symbol)
            else:
                asset_id = asset['id']
            
            # Build insert query
            fields = ['asset_id', 'date']
            values = [asset_id, date]
            
            for key in ['open', 'high', 'low', 'close', 'volume', 'vwap',
                       'premarket_open', 'premarket_close', 'premarket_volume',
                       'afterhours_open', 'afterhours_close', 'afterhours_volume']:
                if key in price_data:
                    fields.append(key)
                    values.append(price_data[key])
            
            placeholders = ['?' for _ in values]
            
            query = f"""
                INSERT OR REPLACE INTO price_history ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
            """
            
            cursor.execute(query, values)
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error saving price history for {symbol}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def save_gap_event(self, symbol: str, gap_date: date, gap_percent: float, 
                       gap_type: str, **kwargs) -> bool:
        """Record a gap event"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            asset = self.get_asset(symbol)
            if not asset:
                asset_id = self.add_asset(symbol)
            else:
                asset_id = asset['id']
            
            cursor.execute("""
                INSERT INTO gap_history 
                (asset_id, gap_date, gap_type, gap_size_percent, gap_size_dollars,
                 previous_close, open_price, session_type, volume_at_open)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (asset_id, gap_date, gap_type, gap_percent,
                 kwargs.get('gap_dollars'), kwargs.get('previous_close'),
                 kwargs.get('open_price'), kwargs.get('session_type', 'regular'),
                 kwargs.get('volume_at_open')))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error saving gap event for {symbol}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def save_market_snapshot(self, snapshot_data: List[Dict], snapshot_time: datetime = None) -> int:
        """
        Save a full market snapshot
        
        Args:
            snapshot_data: List of dicts with symbol, price, volume, etc.
            snapshot_time: Time of snapshot (defaults to now)
            
        Returns:
            Number of records saved
        """
        if snapshot_time is None:
            snapshot_time = datetime.now()
            
        conn = self._get_connection()
        cursor = conn.cursor()
        records_saved = 0
        
        try:
            for item in snapshot_data:
                symbol = item.get('symbol')
                if not symbol:
                    continue
                
                # Get or create asset
                asset = self.get_asset(symbol)
                if not asset:
                    asset_id = self.add_asset(symbol, item.get('name'))
                else:
                    asset_id = asset['id']
                
                # Save snapshot
                cursor.execute("""
                    INSERT OR REPLACE INTO market_snapshots
                    (snapshot_time, asset_id, price, change_percent, change_dollars,
                     volume, day_open, day_high, day_low, previous_close)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (snapshot_time, asset_id,
                     item.get('price'), item.get('change_percent'),
                     item.get('change_dollars'), item.get('volume'),
                     item.get('day_open'), item.get('day_high'),
                     item.get('day_low'), item.get('previous_close')))
                
                records_saved += 1
            
            conn.commit()
            logger.info(f"Saved market snapshot with {records_saved} records")
            return records_saved
            
        except Exception as e:
            logger.error(f"Error saving market snapshot: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()
    
    # Query Methods
    
    def get_gap_history(self, symbol: str = None, days_back: int = 30) -> List[Dict]:
        """Get gap history for a symbol or all symbols"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            query = """
                SELECT a.symbol, g.*
                FROM gap_history g
                JOIN assets a ON g.asset_id = a.id
                WHERE g.gap_date >= date('now', '-{} days')
            """.format(days_back)
            
            params = []
            if symbol:
                query += " AND a.symbol = ?"
                params.append(symbol)
            
            query += " ORDER BY g.gap_date DESC"
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
            
        finally:
            conn.close()
    
    def get_asset_performance(self, symbol: str) -> Optional[Dict]:
        """Get performance metrics for an asset"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            asset = self.get_asset(symbol)
            if not asset:
                return None
            
            # Get gap statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_gaps,
                    SUM(CASE WHEN filled = 1 THEN 1 ELSE 0 END) as gaps_filled,
                    AVG(gap_size_percent) as avg_gap_size,
                    MAX(gap_date) as last_gap_date
                FROM gap_history
                WHERE asset_id = ?
            """, (asset['id'],))
            
            gap_stats = dict(cursor.fetchone())
            
            # Get price history stats
            cursor.execute("""
                SELECT 
                    AVG(volume) as avg_volume,
                    AVG((high - low) / low * 100) as avg_daily_range
                FROM price_history
                WHERE asset_id = ? AND date >= date('now', '-30 days')
            """, (asset['id'],))
            
            price_stats = dict(cursor.fetchone())
            
            return {
                'symbol': symbol,
                **gap_stats,
                **price_stats
            }
            
        finally:
            conn.close()