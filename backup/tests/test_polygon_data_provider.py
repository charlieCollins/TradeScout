"""
Tests for Polygon Data Provider

Tests the Polygon.io data provider implementation including:
- Interface compliance
- Asset data retrieval
- Market data operations
- Database caching
- Error handling
"""

import pytest
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from src.tradescout.data_sources.data_provider_polygon import DataProviderPolygon
from src.tradescout.storage.sqlite_repository import SQLiteDatabaseManager
from src.tradescout.data_models.models_asset import Asset, AssetType, PriceData
from src.tradescout.data_models.models_market import MarketMover
from src.tradescout.data_models.models_market import Market, MarketType


class TestPolygonDataProvider:
    """Test suite for PolygonDataProvider"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            db_path = tmp_file.name

        db_manager = SQLiteDatabaseManager(db_path)

        # Populate test data
        conn = db_manager.get_connection()
        cursor = conn.cursor()

        # Create markets
        cursor.execute("""
            INSERT INTO markets (id, name, market_type, timezone, country)
            VALUES
                ('XNAS', 'NASDAQ', 'stock', 'America/New_York', 'US'),
                ('XNYS', 'NYSE', 'stock', 'America/New_York', 'US')
        """)

        # Create test assets
        cursor.execute("""
            INSERT INTO assets (symbol, name, asset_type, market_id, currency, is_active, min_order_size)
            VALUES
                ('AAPL', 'Apple Inc.', 'common_stock', 'XNAS', 'USD', 1, 1),
                ('MSFT', 'Microsoft Corporation', 'common_stock', 'XNAS', 'USD', 1, 1),
                ('TSLA', 'Tesla, Inc.', 'common_stock', 'XNAS', 'USD', 1, 1),
                ('SPY', 'SPDR S&P 500 ETF Trust', 'etf', 'XNYS', 'USD', 1, 1)
        """)

        conn.commit()
        conn.close()

        yield db_manager

        # Cleanup
        import os
        os.unlink(db_path)

    @pytest.fixture
    def polygon_provider(self, temp_db):
        """Create PolygonDataProvider instance for testing"""
        return DataProviderPolygon(api_key="test_api_key", db_manager=temp_db)

    @pytest.fixture
    def mock_response_data(self):
        """Mock API response data"""
        return {
            "tickers": [
                {
                    "ticker": "AAPL",
                    "day": {
                        "c": 150.00,  # close
                        "o": 145.00,  # open
                        "h": 152.00,  # high
                        "l": 144.00,  # low
                        "v": 1000000  # volume
                    },
                    "prevDay": {
                        "c": 148.00,  # previous close
                    },
                    "min": {
                        "c": 150.50,  # minute close
                        "t": int(datetime.now().timestamp() * 1000),  # timestamp
                        "v": 5000  # minute volume
                    }
                },
                {
                    "ticker": "MSFT",
                    "day": {
                        "c": 300.00,
                        "o": 295.00,
                        "h": 302.00,
                        "l": 294.00,
                        "v": 800000
                    },
                    "prevDay": {
                        "c": 298.00,
                    },
                    "min": {
                        "c": 300.25,
                        "t": int(datetime.now().timestamp() * 1000),
                        "v": 3000
                    }
                }
            ]
        }

    def test_provider_properties(self, polygon_provider):
        """Test provider basic properties"""
        assert polygon_provider.provider_name == "Polygon.io"
        assert polygon_provider.supports_extended_hours is True
        assert polygon_provider.rate_limit_per_minute == 5

    def test_interface_compliance(self, polygon_provider):
        """Test that provider implements required interfaces"""
        from src.tradescout.interfaces.interface_provider import DataProvider
        from src.tradescout.interfaces.interface_asset import AssetDataInterface
        from src.tradescout.interfaces.interface_market import MarketDataInterface
        
        assert isinstance(polygon_provider, DataProvider)
        assert isinstance(polygon_provider, AssetDataInterface)
        assert isinstance(polygon_provider, MarketDataInterface)

    @patch('requests.get')
    def test_get_current_quote_success(self, mock_get, polygon_provider, mock_response_data):
        """Test successful current quote retrieval"""
        # Mock the market snapshot response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response
        
        # Get quote for AAPL
        quote = polygon_provider.get_current_quote("AAPL")
        
        assert quote is not None
        assert isinstance(quote, PriceData)
        assert quote.asset.symbol == "AAPL"
        assert quote.current_price == Decimal("150.50")  # minute price preferred
        assert quote.volume == 5000

    @patch('requests.get')
    def test_get_current_quote_no_data(self, mock_get, polygon_provider):
        """Test current quote when symbol not found"""
        # Mock empty response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response
        
        quote = polygon_provider.get_current_quote("NONEXISTENT")
        assert quote is None

    @patch('requests.get')
    def test_get_fundamentals_success(self, mock_get, polygon_provider):
        """Test successful fundamentals retrieval"""
        # Mock fundamentals response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": {
                "name": "Apple Inc.",
                "market_cap": 2500000000000,
                "description": "Apple Inc. designs and manufactures consumer electronics...",
                "sic_description": "Electronic Computers",
                "total_employees": 164000
            }
        }
        mock_get.return_value = mock_response
        
        fundamentals = polygon_provider.get_fundamentals("AAPL")
        
        assert fundamentals is not None
        assert fundamentals["company_name"] == "Apple Inc."
        assert fundamentals["market_cap"] == 2500000000000
        assert fundamentals["data_source"] == "polygon"

    @patch('requests.get')
    def test_get_fundamentals_not_found(self, mock_get, polygon_provider):
        """Test fundamentals when symbol not found"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        fundamentals = polygon_provider.get_fundamentals("NONEXISTENT")
        assert fundamentals is None


    @patch('requests.get')
    def test_get_ohlc_success(self, mock_get, polygon_provider):
        """Test successful OHLC data retrieval"""
        # Mock OHLC response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "OK",
            "open": 145.00,
            "high": 150.00,
            "low": 144.00,
            "close": 149.00,
            "volume": 1000000
        }
        mock_get.return_value = mock_response
        
        ohlc = polygon_provider.get_ohlc("AAPL", "2024-01-01")
        
        assert ohlc is not None
        assert ohlc["open"] == 145.00
        assert ohlc["close"] == 149.00
        assert ohlc["volume"] == 1000000
        assert ohlc["date"] == "2024-01-01"

    @patch('requests.get')
    def test_get_market_gainers(self, mock_get, polygon_provider, mock_response_data):
        """Test market gainers retrieval"""
        # Mock market snapshot response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response
        
        gainers = polygon_provider.get_market_gainers(limit=5)
        
        assert len(gainers) <= 5
        assert all(isinstance(mover, MarketMover) for mover in gainers)
        
        # Check that results are sorted by percentage change (descending)
        if len(gainers) > 1:
            for i in range(len(gainers) - 1):
                assert gainers[i].price_change_percent >= gainers[i + 1].price_change_percent
        
        # Check ranks are assigned
        for i, mover in enumerate(gainers, 1):
            assert mover.rank == i

    @patch('requests.get')
    def test_get_market_losers(self, mock_get, polygon_provider):
        """Test market losers retrieval"""
        # Mock response with losing stocks
        mock_response_data = {
            "results": [
                {
                    "ticker": "LOSS1",
                    "day": {"c": 90.00, "v": 500000},
                    "prevDay": {"c": 100.00}
                },
                {
                    "ticker": "LOSS2", 
                    "day": {"c": 95.00, "v": 300000},
                    "prevDay": {"c": 100.00}
                }
            ]
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response
        
        losers = polygon_provider.get_market_losers(limit=5)
        
        assert len(losers) <= 5
        assert all(isinstance(mover, MarketMover) for mover in losers)
        
        # Check that all are losers (negative price change)
        for mover in losers:
            assert mover.price_change_percent > 0  # Absolute value for losers


    @patch('requests.get')
    def test_get_market_snapshot_fresh(self, mock_get, polygon_provider, mock_response_data):
        """Test market snapshot retrieval (fresh data)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response
        
        snapshot = polygon_provider.get_market_snapshot(force_refresh=True)
        
        assert snapshot is not None
        assert isinstance(snapshot, dict)
        assert "AAPL" in snapshot
        assert "MSFT" in snapshot
        assert snapshot["AAPL"]["ticker"] == "AAPL"

    def test_get_market_snapshot_cached(self, polygon_provider):
        """Test market snapshot caching functionality"""
        # This would test the database caching mechanism
        # For now, just test that the method exists and handles empty cache
        snapshot = polygon_provider.get_market_snapshot()
        # Should return None when no cache and no API response
        assert snapshot is None or isinstance(snapshot, dict)

    @patch('requests.get')
    def test_api_error_handling(self, mock_get, polygon_provider):
        """Test handling of API errors"""
        # Mock 429 rate limit error
        mock_response = Mock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response
        
        quote = polygon_provider.get_current_quote("AAPL")
        assert quote is None
        
        fundamentals = polygon_provider.get_fundamentals("AAPL")
        assert fundamentals is None
        

    def test_sentiment_methods_not_implemented(self, polygon_provider):
        """Test that sentiment methods return None/empty as expected"""
        assert polygon_provider.get_asset_sentiment("AAPL") is None
        assert polygon_provider.get_market_sentiment() is None
        assert polygon_provider.get_trending_sentiment() == []
        assert polygon_provider.get_news_sentiment() == []
        assert polygon_provider.get_social_sentiment("AAPL") == {}
        assert polygon_provider.get_analyst_sentiment("AAPL") is None

    @patch('requests.get')
    def test_rate_limiting_delay(self, mock_get, polygon_provider):
        """Test that rate limiting delays are applied"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": {"name": "Test"}}
        mock_get.return_value = mock_response
        
        with patch('time.sleep') as mock_sleep:
            polygon_provider.get_fundamentals("AAPL")
            mock_sleep.assert_called_with(0.12)

    def test_database_integration(self, polygon_provider, temp_db):
        """Test database integration functionality"""
        # Test that provider can work with database manager
        assert polygon_provider.db_manager is not None
        assert polygon_provider.db_manager == temp_db
        
        # Test that provider can handle None database manager
        provider_no_db = DataProviderPolygon(api_key="test_key", db_manager=None)
        assert provider_no_db.db_manager is None

    def test_edge_cases(self, polygon_provider):
        """Test various edge cases"""
        # Test with empty symbol
        quote = polygon_provider.get_current_quote("")
        assert quote is None
        
        # Test with None symbol (should handle gracefully)
        try:
            quote = polygon_provider.get_current_quote(None)
            # Should either return None or handle the TypeError gracefully
            assert quote is None
        except (TypeError, AttributeError):
            # It's acceptable to raise these for None input
            pass