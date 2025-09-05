"""
Tests for Centralized Market Movers Architecture

Tests that market gainers/losers use the centralized Full Market Snapshot approach.
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.tradescout.data_sources_api.asset_data_provider_polygon import AssetDataProviderPolygon


class TestCentralizedMarketMovers:
    """Test centralized market movers functionality"""

    def setup_method(self):
        """Setup test provider with isolated cache"""
        self.temp_dir = tempfile.mkdtemp()
        
        with patch('src.tradescout.data_sources_api.asset_data_provider_polygon.Path') as mock_path:
            mock_cache_dir = Path(self.temp_dir) / "test_cache"
            mock_cache_dir.mkdir(parents=True, exist_ok=True)
            mock_path.return_value = mock_cache_dir
            
            self.provider = AssetDataProviderPolygon(api_key="test_key")
            
        # Clear any loaded cache
        self.provider._market_snapshot_data = None
        self.provider._market_snapshot_timestamp = None

    def teardown_method(self):
        """Cleanup"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_market_gainers_uses_centralized_data(self):
        """Test that market gainers use centralized snapshot data"""
        # Set up mock market data
        mock_market_data = {
            "GAIN1": {
                "ticker": "GAIN1",
                "day": {"c": 110.0, "o": 100.0, "v": 1000000},
                "prevDay": {"c": 100.0},
                "todaysChangePerc": 10.0,
                "todaysChange": 10.0
            },
            "GAIN2": {
                "ticker": "GAIN2", 
                "day": {"c": 55.0, "o": 50.0, "v": 800000},
                "prevDay": {"c": 50.0},
                "todaysChangePerc": 10.0,
                "todaysChange": 5.0
            },
            "LOSS1": {
                "ticker": "LOSS1",
                "day": {"c": 90.0, "o": 100.0, "v": 1200000},
                "prevDay": {"c": 100.0},
                "todaysChangePerc": -10.0,
                "todaysChange": -10.0
            }
        }
        
        # Mock the centralized data fetch
        with patch.object(self.provider, '_get_fresh_market_data') as mock_get_data:
            mock_get_data.return_value = mock_market_data
            
            # Get market gainers
            gainers = self.provider.get_market_gainers(limit=2)
            
            # Verify centralized method was called
            mock_get_data.assert_called_once()
            
            # Verify results
            assert len(gainers) == 2
            assert gainers[0].asset.symbol == "GAIN1"  # Should be first (higher absolute change)
            assert gainers[1].asset.symbol == "GAIN2"  # Should be second
            assert gainers[0].price_change_percent > 0  # Should be positive (gainer)
            assert gainers[1].price_change_percent > 0  # Should be positive (gainer)

    def test_market_losers_uses_centralized_data(self):
        """Test that market losers use centralized snapshot data"""
        # Set up mock market data
        mock_market_data = {
            "LOSS1": {
                "ticker": "LOSS1",
                "day": {"c": 80.0, "o": 100.0, "v": 1200000},
                "prevDay": {"c": 100.0},
                "todaysChangePerc": -20.0,
                "todaysChange": -20.0
            },
            "LOSS2": {
                "ticker": "LOSS2",
                "day": {"c": 90.0, "o": 100.0, "v": 1000000},
                "prevDay": {"c": 100.0},
                "todaysChangePerc": -10.0,
                "todaysChange": -10.0
            },
            "GAIN1": {
                "ticker": "GAIN1",
                "day": {"c": 110.0, "o": 100.0, "v": 800000},
                "prevDay": {"c": 100.0},
                "todaysChangePerc": 10.0,
                "todaysChange": 10.0
            }
        }
        
        # Mock the centralized data fetch
        with patch.object(self.provider, '_get_fresh_market_data') as mock_get_data:
            mock_get_data.return_value = mock_market_data
            
            # Get market losers
            losers = self.provider.get_market_losers(limit=2)
            
            # Verify centralized method was called
            mock_get_data.assert_called_once()
            
            # Verify results
            assert len(losers) == 2
            assert losers[0].asset.symbol == "LOSS1"  # Should be first (bigger loss)
            assert losers[1].asset.symbol == "LOSS2"  # Should be second
            assert losers[0].price_change_percent < 0  # Should be negative (loser)
            assert losers[1].price_change_percent < 0  # Should be negative (loser)

    def test_force_refresh_passed_to_centralized_method(self):
        """Test that force_refresh parameter is properly passed through"""
        mock_market_data = {
            "TEST": {
                "ticker": "TEST",
                "day": {"c": 100.0, "o": 95.0, "v": 1000000},
                "prevDay": {"c": 95.0},
                "todaysChangePerc": 5.26,
                "todaysChange": 5.0
            }
        }
        
        with patch.object(self.provider, '_get_fresh_market_data') as mock_get_data:
            mock_get_data.return_value = mock_market_data
            
            # Call with force_refresh=True
            gainers = self.provider.get_market_gainers(limit=1, force_refresh=True)
            
            # Verify force_refresh was passed through
            mock_get_data.assert_called_once_with(True)
            
            # Call with force_refresh=False
            mock_get_data.reset_mock()
            gainers = self.provider.get_market_gainers(limit=1, force_refresh=False)
            
            # Verify force_refresh was passed through
            mock_get_data.assert_called_once_with(False)

    def test_empty_market_data_returns_empty_list(self):
        """Test handling of empty market data"""
        # Mock empty data
        with patch.object(self.provider, '_get_fresh_market_data') as mock_get_data:
            mock_get_data.return_value = None
            
            # Get market gainers with empty data
            gainers = self.provider.get_market_gainers(limit=5)
            
            # Should return empty list, not crash
            assert gainers == []
            
            # Same for losers
            losers = self.provider.get_market_losers(limit=5)
            assert losers == []

    def test_market_movers_calculation_accuracy(self):
        """Test that percentage calculations are accurate"""
        mock_market_data = {
            "ACCURATE": {
                "ticker": "ACCURATE",
                "day": {"c": 105.0, "o": 100.0, "v": 1000000},
                "prevDay": {"c": 100.0},
                "todaysChangePerc": 5.0,  # Should be calculated, not just used
                "todaysChange": 5.0
            }
        }
        
        with patch.object(self.provider, '_get_fresh_market_data') as mock_get_data:
            mock_get_data.return_value = mock_market_data
            
            gainers = self.provider.get_market_gainers(limit=1)
            
            assert len(gainers) == 1
            gainer = gainers[0]
            
            # Verify the calculation: (105 - 100) / 100 * 100 = 5.0%
            assert abs(float(gainer.price_change_percent) - 5.0) < 0.01
            assert float(gainer.current_price) == 105.0
            assert float(gainer.price_change) == 5.0

    def test_market_movers_sorting(self):
        """Test that market movers are properly sorted by percentage change"""
        mock_market_data = {
            "BIG_GAIN": {
                "ticker": "BIG_GAIN",
                "day": {"c": 150.0, "v": 1000000},
                "prevDay": {"c": 100.0},
                "todaysChangePerc": 50.0,
                "todaysChange": 50.0
            },
            "SMALL_GAIN": {
                "ticker": "SMALL_GAIN", 
                "day": {"c": 102.0, "v": 1000000},
                "prevDay": {"c": 100.0},
                "todaysChangePerc": 2.0,
                "todaysChange": 2.0
            },
            "MED_GAIN": {
                "ticker": "MED_GAIN",
                "day": {"c": 110.0, "v": 1000000},
                "prevDay": {"c": 100.0},
                "todaysChangePerc": 10.0,
                "todaysChange": 10.0
            }
        }
        
        with patch.object(self.provider, '_get_fresh_market_data') as mock_get_data:
            mock_get_data.return_value = mock_market_data
            
            gainers = self.provider.get_market_gainers(limit=3)
            
            # Should be sorted by percentage change (descending for gainers)
            assert len(gainers) == 3
            assert gainers[0].asset.symbol == "BIG_GAIN"   # 50%
            assert gainers[1].asset.symbol == "MED_GAIN"   # 10%
            assert gainers[2].asset.symbol == "SMALL_GAIN" # 2%
            
            # Verify they're actually in descending order
            assert gainers[0].price_change_percent > gainers[1].price_change_percent
            assert gainers[1].price_change_percent > gainers[2].price_change_percent


if __name__ == "__main__":
    pytest.main([__file__, "-v"])