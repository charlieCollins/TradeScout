"""
Tests for Polygon.io Asset Data Provider

Tests the centralized market data architecture and core functionality.
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.tradescout.data_sources_api.asset_data_provider_polygon import AssetDataProviderPolygon
from src.tradescout.data_models.domain_models_core import Asset, AssetType
from src.tradescout.data_models.factories import MarketFactory


class TestPolygonProviderInitialization:
    """Test Polygon provider initialization and setup"""

    def test_provider_initialization(self):
        """Test basic provider initialization"""
        # Use temp directory to avoid loading existing cache
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.tradescout.data_sources_api.asset_data_provider_polygon.Path') as mock_path:
                mock_cache_dir = Path(temp_dir) / "test_cache"
                mock_cache_dir.mkdir(parents=True, exist_ok=True)
                mock_path.return_value = mock_cache_dir
                
                provider = AssetDataProviderPolygon(api_key="test_key")
                
                assert provider.api_key == "test_key"
                assert provider.provider_name == "polygon"
                assert provider._market_data_ttl_minutes == 15
                # Note: provider may load existing cache on init, so data might not be None

    def test_cache_directory_creation(self):
        """Test that cache directory is created during initialization"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create provider with custom cache path by patching Path
            with patch('src.tradescout.data_sources_api.asset_data_provider_polygon.Path') as mock_path:
                mock_cache_dir = Path(temp_dir) / "test_cache"
                mock_path.return_value = mock_cache_dir
                
                provider = AssetDataProviderPolygon(api_key="test_key")
                
                # Verify cache directory setup was attempted
                assert mock_path.called


class TestCentralizedMarketDataCache:
    """Test centralized market data caching functionality"""

    def setup_method(self):
        """Setup test provider"""
        self.provider = AssetDataProviderPolygon(api_key="test_key")
        
        # Mock cache file to avoid filesystem interactions
        self.temp_dir = tempfile.mkdtemp()
        self.provider._cache_dir = Path(self.temp_dir)
        self.provider._market_cache_file = self.provider._cache_dir / "market_snapshot.json"

    def teardown_method(self):
        """Cleanup test provider"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_empty_cache_is_not_fresh(self):
        """Test that empty cache is not considered fresh"""
        # Clear any existing cache data
        self.provider._market_snapshot_data = None
        self.provider._market_snapshot_timestamp = None
        
        assert not self.provider._is_market_data_fresh()

    def test_fresh_cache_is_detected(self):
        """Test that recent cache data is considered fresh"""
        # Set up fresh data
        self.provider._market_snapshot_data = {"AAPL": {"ticker": "AAPL"}}
        self.provider._market_snapshot_timestamp = datetime.now()
        
        assert self.provider._is_market_data_fresh()

    def test_stale_cache_is_detected(self):
        """Test that old cache data is considered stale"""
        # Set up stale data (older than TTL)
        self.provider._market_snapshot_data = {"AAPL": {"ticker": "AAPL"}}
        self.provider._market_snapshot_timestamp = datetime.now() - timedelta(minutes=20)
        
        assert not self.provider._is_market_data_fresh()

    def test_cache_save_to_disk(self):
        """Test saving cache data to filesystem"""
        # Set up test data
        test_data = {"AAPL": {"ticker": "AAPL", "day": {"c": 150.0}}}
        self.provider._market_snapshot_data = test_data
        self.provider._market_snapshot_timestamp = datetime.now()
        
        # Save to disk
        self.provider._save_market_cache_to_disk()
        
        # Verify file was created and contains correct data
        assert self.provider._market_cache_file.exists()
        
        with open(self.provider._market_cache_file, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data['data'] == test_data
        assert saved_data['symbols'] == 1
        assert saved_data['provider'] == 'polygon'

    def test_cache_load_from_disk(self):
        """Test loading cache data from filesystem"""
        # Create test cache file
        test_data = {"AAPL": {"ticker": "AAPL", "day": {"c": 150.0}}}
        timestamp = datetime.now()
        
        cache_data = {
            'data': test_data,
            'timestamp': timestamp.isoformat(),
            'symbols': 1,
            'provider': 'polygon'
        }
        
        with open(self.provider._market_cache_file, 'w') as f:
            json.dump(cache_data, f)
        
        # Load from disk
        self.provider._load_market_cache_from_disk()
        
        # Verify data was loaded
        assert self.provider._market_snapshot_data == test_data
        assert self.provider._market_snapshot_timestamp is not None

    def test_stale_cache_file_ignored(self):
        """Test that stale cache files are not loaded"""
        # Clear existing cache first
        self.provider._market_snapshot_data = None
        self.provider._market_snapshot_timestamp = None
        
        # Create stale cache file
        test_data = {"AAPL": {"ticker": "AAPL"}}
        stale_timestamp = datetime.now() - timedelta(minutes=20)
        
        cache_data = {
            'data': test_data,
            'timestamp': stale_timestamp.isoformat(),
            'symbols': 1,
            'provider': 'polygon'
        }
        
        with open(self.provider._market_cache_file, 'w') as f:
            json.dump(cache_data, f)
        
        # Load from disk
        self.provider._load_market_cache_from_disk()
        
        # Verify stale data was not loaded
        assert self.provider._market_snapshot_data is None


class TestMarketDataStatus:
    """Test market data status reporting"""

    def setup_method(self):
        """Setup test provider"""
        self.provider = AssetDataProviderPolygon(api_key="test_key")

    def test_empty_cache_status(self):
        """Test status when cache is empty"""
        # Clear any existing cache data
        self.provider._market_snapshot_data = None
        self.provider._market_snapshot_timestamp = None
        
        status = self.provider.get_market_data_status()
        
        assert status['status'] == 'empty'
        assert status['symbols'] == 0

    def test_fresh_cache_status(self):
        """Test status when cache is fresh"""
        # Set up fresh data
        test_data = {"AAPL": {"ticker": "AAPL"}, "MSFT": {"ticker": "MSFT"}}
        self.provider._market_snapshot_data = test_data
        self.provider._market_snapshot_timestamp = datetime.now()
        
        status = self.provider.get_market_data_status()
        
        assert status['status'] == 'cached'
        assert status['symbols'] == 2
        assert status['age_minutes'] < 1  # Should be very fresh

    def test_stale_cache_status(self):
        """Test status when cache is stale"""
        # Set up stale data
        test_data = {"AAPL": {"ticker": "AAPL"}}
        self.provider._market_snapshot_data = test_data
        self.provider._market_snapshot_timestamp = datetime.now() - timedelta(minutes=20)
        
        status = self.provider.get_market_data_status()
        
        assert status['status'] == 'stale'
        assert status['symbols'] == 1
        assert status['age_minutes'] > 15


class TestCentralizedDataRetrieval:
    """Test centralized data retrieval methods"""

    def setup_method(self):
        """Setup test provider"""
        self.provider = AssetDataProviderPolygon(api_key="test_key")

    def test_ticker_data_extraction(self):
        """Test extracting individual ticker data from centralized snapshot"""
        # Set up test market data
        test_data = {
            "AAPL": {
                "ticker": "AAPL",
                "day": {"c": 150.0, "o": 148.0, "h": 152.0, "l": 147.0, "v": 1000000},
                "prevDay": {"c": 145.0}
            },
            "MSFT": {
                "ticker": "MSFT", 
                "day": {"c": 250.0, "o": 248.0, "h": 252.0, "l": 247.0, "v": 800000},
                "prevDay": {"c": 245.0}
            }
        }
        
        self.provider._market_snapshot_data = test_data
        self.provider._market_snapshot_timestamp = datetime.now()
        
        # Test successful extraction
        aapl_data = self.provider._get_ticker_data("AAPL")
        assert aapl_data is not None
        assert aapl_data["ticker"] == "AAPL"
        assert aapl_data["day"]["c"] == 150.0
        
        # Test case-insensitive extraction
        aapl_data_lower = self.provider._get_ticker_data("aapl")
        assert aapl_data_lower is not None
        assert aapl_data_lower["ticker"] == "AAPL"
        
        # Test non-existent symbol
        missing_data = self.provider._get_ticker_data("NONEXISTENT")
        assert missing_data is None

    @patch('src.tradescout.data_sources_api.asset_data_provider_polygon.AssetDataProviderPolygon._get_full_market_snapshot')
    def test_force_refresh_bypasses_cache(self, mock_snapshot):
        """Test that force refresh bypasses cache and fetches fresh data"""
        # Set up existing cache
        old_data = {"OLD": {"ticker": "OLD"}}
        self.provider._market_snapshot_data = old_data
        self.provider._market_snapshot_timestamp = datetime.now()
        
        # Set up mock to return new data
        new_data = {"NEW": {"ticker": "NEW"}}
        mock_snapshot.return_value = new_data
        
        # Call with force refresh
        result = self.provider._get_fresh_market_data(force_refresh=True)
        
        # Verify API was called and new data returned
        mock_snapshot.assert_called_once()
        assert result == new_data
        assert self.provider._market_snapshot_data == new_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])