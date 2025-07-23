"""
Pytest configuration and fixtures for TradeScout tests
"""

import pytest
from decimal import Decimal
from datetime import datetime, time
from unittest.mock import Mock, patch

from tradescout.data_models.domain_models_core import (
    Asset,
    Market,
    MarketSegment,
    AssetType,
    MarketType,
    MarketStatus,
)
from tradescout.caches.api_cache import APICache


@pytest.fixture
def sample_market():
    """Create a sample market for testing"""
    return Market(
        id="NASDAQ",
        name="NASDAQ Stock Market",
        market_type=MarketType.STOCK,
        timezone="America/New_York",
        currency="USD",
        regular_open=time(9, 30),
        regular_close=time(16, 0),
        pre_market_start=time(4, 0),
        after_hours_end=time(20, 0),
    )


@pytest.fixture
def sample_market_segment():
    """Create a sample market segment for testing"""
    return MarketSegment(
        id="TECH",
        name="Technology",
        description="Technology sector stocks",
        segment_type="sector",
    )


@pytest.fixture
def sample_asset(sample_market, sample_market_segment):
    """Create a sample asset for testing"""
    return Asset(
        symbol="AAPL",
        name="Apple Inc.",
        asset_type=AssetType.COMMON_STOCK,
        market=sample_market,
        currency="USD",
        segments={sample_market_segment},
    )


@pytest.fixture
def mock_yfinance_ticker():
    """Mock yfinance Ticker for testing"""
    with patch("tradescout.data_sources.yfinance_adapter.yf.Ticker") as mock_ticker:
        # Configure mock ticker with realistic data
        mock_instance = Mock()
        mock_instance.info = {
            "previousClose": 150.0,
            "averageVolume": 50000000,
            "marketCap": 2500000000000,
            "longName": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
        }

        # Mock history data
        import pandas as pd

        mock_hist = pd.DataFrame(
            {
                "Open": [149.0, 150.5],
                "High": [152.0, 153.0],
                "Low": [148.0, 149.5],
                "Close": [151.0, 152.5],
                "Volume": [45000000, 52000000],
            }
        )
        mock_instance.history.return_value = mock_hist

        mock_ticker.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def test_cache():
    """Create a test cache instance"""
    return APICache()


@pytest.fixture
def mock_cache():
    """Create a mock cache for testing"""
    cache = Mock(spec=APICache)
    cache.get.return_value = None  # Default to cache miss
    cache.set.return_value = True
    return cache


# Test data fixtures
@pytest.fixture
def sample_quote_data():
    """Sample quote data for testing"""
    return {
        "symbol": "AAPL",
        "current_price": Decimal("151.50"),
        "previous_close": Decimal("150.00"),
        "price_change": Decimal("1.50"),
        "price_change_percent": Decimal("1.00"),
        "volume": 50000000,
        "avg_volume": 45000000,
        "market_cap": 2500000000000,
        "day_high": Decimal("152.00"),
        "day_low": Decimal("149.00"),
        "open_price": Decimal("150.25"),
        "timestamp": datetime.now(),
        "is_extended_hours": False,
    }


# Pytest markers for different test types
pytest_plugins = []


def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line(
        "markers", "unit: Unit tests that don't require external dependencies"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests that may use real APIs"
    )
    config.addinivalue_line("markers", "slow: Tests that take a long time to run")
    config.addinivalue_line(
        "markers", "api: Tests that make real API calls (use with caution)"
    )


# Environment setup for tests
@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch, tmp_path):
    """Set up test environment variables"""
    # Disable cache by default in tests
    monkeypatch.setenv("TRADESCOUT_CACHE_ENABLED", "false")
    # Set test mode
    monkeypatch.setenv("TRADESCOUT_TEST_MODE", "true")
    # Use test-specific database path
    test_db_path = tmp_path / "test_tradescout.db"
    monkeypatch.setenv("TRADESCOUT_TEST_DB_PATH", str(test_db_path))
