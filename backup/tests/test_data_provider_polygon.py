"""
Tests for DataProviderPolygon

Tests the Polygon.io data provider implementation including:
- Market snapshot retrieval and caching
- Quote data extraction
- Market movers (gainers, losers, most active)
- Database caching with TTL
- Error handling
"""

import pytest
import sqlite3
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from src.tradescout.data_sources.data_provider_polygon import DataProviderPolygon
from src.tradescout.storage.sqlite_repository import SQLiteDatabaseManager
from src.tradescout.data_models.models_asset import Asset, AssetType, PriceData
from src.tradescout.data_models.models_market import MarketMover
from src.tradescout.data_models.models_market import Market


class TestDataProviderPolygon:
    """Test suite for DataProviderPolygon"""

    @pytest.fixture
    def mock_api_key(self):
        """Mock API key for testing"""
        return "test_polygon_api_key"

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            db_path = tmp_file.name
        
        # Initialize database with tables
        db_manager = SQLiteDatabaseManager(db_path)
        
        # Create tables manually for testing
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        # Assets table
        cursor.execute("""
            CREATE TABLE assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol VARCHAR(10) NOT NULL UNIQUE,
                name VARCHAR(255),
                asset_type VARCHAR(50) DEFAULT 'COMMON_STOCK',
                is_active BOOLEAN DEFAULT 1,
                is_tradeable BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Market snapshots table
        cursor.execute("""
            CREATE TABLE market_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_time TIMESTAMP NOT NULL,
                asset_id INTEGER NOT NULL,
                price REAL,
                change_percent REAL,
                change_dollars REAL,
                volume BIGINT,
                day_open REAL,
                day_high REAL,
                day_low REAL,
                previous_close REAL,
                minute_bar_price REAL,
                minute_bar_timestamp BIGINT,
                minute_bar_volume BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (asset_id) REFERENCES assets(id),
                UNIQUE(snapshot_time, asset_id)
            )
        """)
        
        # Market snapshot metadata table
        cursor.execute("""
            CREATE TABLE market_snapshot_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_type VARCHAR(50) NOT NULL,
                last_retrieved_at TIMESTAMP NOT NULL,
                symbols_count INTEGER DEFAULT 0,
                status VARCHAR(20) DEFAULT 'success',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(snapshot_type)
            )
        """)
        
        conn.commit()
        conn.close()
        
        yield db_manager
        
        # Cleanup
        import os
        os.unlink(db_path)

    @pytest.fixture
    def provider(self, mock_api_key, temp_db):
        """Create DataProviderPolygon instance for testing"""
        return DataProviderPolygon(mock_api_key, temp_db)

    @pytest.fixture
    def mock_polygon_response(self):
        """Mock Polygon API snapshot response"""
        return {
            "status": "OK",
            "results": [
                {
                    "ticker": "AAPL",
                    "day": {
                        "c": 150.25,
                        "o": 148.50,
                        "h": 151.00,
                        "l": 147.75,
                        "v": 45678900
                    },
                    "prevDay": {
                        "c": 148.00
                    },
                    "min": {
                        "c": 150.25,
                        "t": 1694707200000,
                        "v": 12345
                    }
                },
                {
                    "ticker": "TSLA",
                    "day": {
                        "c": 245.80,
                        "o": 250.00,
                        "h": 252.50,
                        "l": 244.20,
                        "v": 23456789
                    },
                    "prevDay": {
                        "c": 250.50
                    },
                    "min": {
                        "c": 245.80,
                        "t": 1694707200000,
                        "v": 8765
                    }
                }
            ]
        }

    def test_provider_initialization(self, mock_api_key, temp_db):
        """Test provider initialization"""
        provider = DataProviderPolygon(mock_api_key, temp_db)
        
        assert provider.api_key == mock_api_key
        assert provider.db_manager == temp_db
        assert provider.base_url == "https://api.polygon.io"
        assert provider.provider_name == "Polygon.io"
        assert provider.supports_extended_hours is True
        assert provider.rate_limit_per_minute == 5

    @patch('requests.get')
    def test_get_market_snapshot_fresh(self, mock_get, provider, mock_polygon_response):
        """Test getting fresh market snapshot from API"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_polygon_response
        mock_get.return_value = mock_response
        
        # Get snapshot
        result = provider.get_market_snapshot(force_refresh=True)
        
        # Verify API was called
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "api.polygon.io" in call_args[0][0]
        assert call_args[1]["params"]["apikey"] == provider.api_key
        
        # Verify result structure
        assert result is not None
        assert "AAPL" in result
        assert "TSLA" in result
        
        # Verify AAPL data
        aapl_data = result["AAPL"]
        assert aapl_data["ticker"] == "AAPL"
        assert aapl_data["day"]["c"] == 150.25
        assert aapl_data["prevDay"]["c"] == 148.00
        
        # Verify TSLA data
        tsla_data = result["TSLA"]
        assert tsla_data["ticker"] == "TSLA"
        assert tsla_data["day"]["c"] == 245.80
        assert tsla_data["prevDay"]["c"] == 250.50

    @patch('requests.get')
    def test_get_market_snapshot_api_error(self, mock_get, provider):
        """Test handling of API errors"""
        # Mock API error
        mock_response = Mock()
        mock_response.status_code = 429  # Rate limit error
        mock_get.return_value = mock_response
        
        result = provider.get_market_snapshot()
        
        assert result is None
        mock_get.assert_called_once()

    @patch('requests.get')
    def test_get_market_snapshot_stores_in_cache(self, mock_get, provider, mock_polygon_response):
        """Test that fresh snapshot data is stored in database cache"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_polygon_response
        mock_get.return_value = mock_response
        
        # Get snapshot - should store in cache
        result = provider.get_market_snapshot(force_refresh=True)
        
        assert result is not None
        
        # Verify data was stored in database
        conn = provider.db_manager.get_connection()
        cursor = conn.cursor()
        
        # Check metadata was stored
        cursor.execute("SELECT * FROM market_snapshot_metadata WHERE snapshot_type = 'full_market'")
        metadata = cursor.fetchone()
        assert metadata is not None
        assert metadata[2] == 2  # symbols_count should be 2 (AAPL, TSLA)
        assert metadata[3] == "success"
        
        # Check snapshot data was stored
        cursor.execute("SELECT COUNT(*) FROM market_snapshots")
        snapshot_count = cursor.fetchone()[0]
        assert snapshot_count == 2
        
        # Check specific symbol data
        cursor.execute("""
            SELECT a.symbol, ms.price, ms.previous_close
            FROM market_snapshots ms
            JOIN assets a ON ms.asset_id = a.id
            WHERE a.symbol = 'AAPL'
        """)
        aapl_row = cursor.fetchone()
        assert aapl_row is not None
        assert aapl_row[0] == "AAPL"
        assert aapl_row[1] == 150.25  # current price
        assert aapl_row[2] == 148.00  # previous close
        
        conn.close()

    def test_get_cached_snapshot(self, provider, mock_polygon_response):
        """Test retrieving snapshot from database cache"""
        # First, manually store some data in cache
        conn = provider.db_manager.get_connection()
        cursor = conn.cursor()
        
        # Create test assets
        cursor.execute("INSERT INTO assets (symbol, asset_type) VALUES ('AAPL', 'COMMON_STOCK')")
        aapl_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO assets (symbol, asset_type) VALUES ('TSLA', 'COMMON_STOCK')")
        tsla_id = cursor.lastrowid
        
        # Store recent snapshot metadata (within TTL)
        recent_time = datetime.now() - timedelta(minutes=5)
        cursor.execute("""
            INSERT INTO market_snapshot_metadata 
            (snapshot_type, last_retrieved_at, symbols_count, status)
            VALUES ('full_market', ?, 2, 'success')
        """, (recent_time.isoformat(),))
        
        # Store snapshot data
        cursor.execute("""
            INSERT INTO market_snapshots 
            (snapshot_time, asset_id, price, previous_close, day_open, day_high, day_low, volume)
            VALUES (?, ?, 150.25, 148.00, 148.50, 151.00, 147.75, 45678900)
        """, (recent_time.isoformat(), aapl_id))
        
        cursor.execute("""
            INSERT INTO market_snapshots 
            (snapshot_time, asset_id, price, previous_close, day_open, day_high, day_low, volume)
            VALUES (?, ?, 245.80, 250.50, 250.00, 252.50, 244.20, 23456789)
        """, (recent_time.isoformat(), tsla_id))
        
        conn.commit()
        conn.close()
        
        # Now test retrieving cached data
        cached_result = provider._get_cached_snapshot()
        
        assert cached_result is not None
        assert "AAPL" in cached_result
        assert "TSLA" in cached_result
        
        # Verify AAPL data structure matches Polygon format
        aapl_data = cached_result["AAPL"]
        assert aapl_data["ticker"] == "AAPL"
        assert aapl_data["day"]["c"] == 150.25
        assert aapl_data["prevDay"]["c"] == 148.00

    def test_cached_snapshot_expired(self, provider):
        """Test that expired cache returns None"""
        # Store old snapshot metadata (beyond TTL)
        conn = provider.db_manager.get_connection()
        cursor = conn.cursor()
        
        old_time = datetime.now() - timedelta(minutes=15)  # Older than 10-minute TTL
        cursor.execute("""
            INSERT INTO market_snapshot_metadata 
            (snapshot_type, last_retrieved_at, symbols_count, status)
            VALUES ('full_market', ?, 1, 'success')
        """, (old_time.isoformat(),))
        
        conn.commit()
        conn.close()
        
        # Should return None due to expired cache
        cached_result = provider._get_cached_snapshot()
        assert cached_result is None

    def test_get_current_quote(self, provider, mock_polygon_response):
        """Test getting current quote for a symbol"""
        # Mock the get_market_snapshot method to return our test data
        with patch.object(provider, 'get_market_snapshot') as mock_snapshot:
            mock_snapshot.return_value = {
                "AAPL": mock_polygon_response["results"][0]
            }
            
            quote = provider.get_current_quote("AAPL")
            
            assert quote is not None
            assert isinstance(quote, PriceData)
            assert quote.asset.symbol == "AAPL"
            assert quote.current_price == Decimal("150.25")
            assert quote.volume == 12345  # From min data

    def test_get_current_quote_symbol_not_found(self, provider):
        """Test getting quote for symbol not in snapshot"""
        with patch.object(provider, 'get_market_snapshot') as mock_snapshot:
            mock_snapshot.return_value = {}
            
            quote = provider.get_current_quote("NONEXISTENT")
            assert quote is None

    def test_get_market_gainers(self, provider, mock_polygon_response):
        """Test getting market gainers"""
        with patch.object(provider, 'get_market_snapshot') as mock_snapshot:
            mock_snapshot.return_value = {
                "AAPL": mock_polygon_response["results"][0],  # Gainer: 148->150.25
                "TSLA": mock_polygon_response["results"][1],  # Loser: 250.5->245.80
            }
            
            gainers = provider.get_market_gainers(limit=10)
            
            assert len(gainers) == 1  # Only AAPL is a gainer
            assert isinstance(gainers[0], MarketMover)
            assert gainers[0].asset.symbol == "AAPL"
            assert gainers[0].current_price == Decimal("150.25")
            assert gainers[0].rank == 1

    def test_get_market_losers(self, provider, mock_polygon_response):
        """Test getting market losers"""
        with patch.object(provider, 'get_market_snapshot') as mock_snapshot:
            mock_snapshot.return_value = {
                "AAPL": mock_polygon_response["results"][0],  # Gainer: 148->150.25
                "TSLA": mock_polygon_response["results"][1],  # Loser: 250.5->245.80
            }
            
            losers = provider.get_market_losers(limit=10)
            
            assert len(losers) == 1  # Only TSLA is a loser
            assert isinstance(losers[0], MarketMover)
            assert losers[0].asset.symbol == "TSLA"
            assert losers[0].current_price == Decimal("245.80")
            assert losers[0].rank == 1


    @patch('requests.get')
    def test_get_fundamentals(self, mock_get, provider):
        """Test getting fundamental data"""
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": {
                "name": "Apple Inc.",
                "market_cap": 2800000000000,
                "description": "Technology company",
                "sic_description": "Technology",
                "total_employees": 164000
            }
        }
        mock_get.return_value = mock_response
        
        fundamentals = provider.get_fundamentals("AAPL")
        
        assert fundamentals is not None
        assert fundamentals["company_name"] == "Apple Inc."
        assert fundamentals["market_cap"] == 2800000000000
        assert fundamentals["data_source"] == "polygon"


    def test_sentiment_methods_not_implemented(self, provider):
        """Test that sentiment methods return None/empty as expected"""
        assert provider.get_social_sentiment("AAPL") is None
        assert provider.get_news_sentiment("AAPL") is None
        assert provider.search_news("AAPL") == []

    @patch('time.sleep')  # Mock sleep to speed up tests
    def test_rate_limiting_applied(self, mock_sleep, provider):
        """Test that rate limiting is applied to API calls"""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"results": []}
            mock_get.return_value = mock_response
            
            provider.get_market_snapshot(force_refresh=True)
            
            # Verify sleep was called for rate limiting
            mock_sleep.assert_called_with(0.2)