"""Unit tests for snapshot models."""

import pytest
from datetime import datetime
from decimal import Decimal

from models.snapshot import TickerSnapshot, MarketSnapshot


class TestTickerSnapshot:
    """Test TickerSnapshot model."""

    def test_create_ticker_snapshot(self):
        """Test basic TickerSnapshot creation."""
        snapshot = TickerSnapshot(
            symbol="AAPL",
            prev_close=Decimal("150.00"),
            prev_volume=1000000,
            open_price=Decimal("151.00"),
            high_price=Decimal("152.00"),
            low_price=Decimal("149.50"),
            close_price=Decimal("151.50"),
            volume=800000,
            vwap=Decimal("151.25"),
            last_price=Decimal("151.50"),
            last_timestamp=datetime(2025, 9, 28, 16, 0, 0),
            market_status="closed"
        )

        assert snapshot.symbol == "AAPL"
        assert snapshot.prev_close == Decimal("150.00")
        assert snapshot.last_price == Decimal("151.50")

    def test_ticker_snapshot_change_calculation(self):
        """Test change property calculation."""
        snapshot = TickerSnapshot(
            symbol="AAPL",
            prev_close=Decimal("150.00"),
            prev_volume=None,
            open_price=None,
            high_price=None,
            low_price=None,
            close_price=None,
            volume=None,
            vwap=None,
            last_price=Decimal("151.50"),
            last_timestamp=None,
            market_status=None
        )

        # Test change calculation
        assert snapshot.change == Decimal("1.50")

    def test_ticker_snapshot_change_percent_calculation(self):
        """Test change_percent property calculation."""
        snapshot = TickerSnapshot(
            symbol="AAPL",
            prev_close=Decimal("150.00"),
            prev_volume=None,
            open_price=None,
            high_price=None,
            low_price=None,
            close_price=None,
            volume=None,
            vwap=None,
            last_price=Decimal("151.50"),
            last_timestamp=None,
            market_status=None
        )

        # Test change percent calculation
        assert snapshot.change_percent == Decimal("1.00")  # 1.5/150 * 100 = 1%

    def test_ticker_snapshot_no_change_when_missing_data(self):
        """Test change returns None when required data is missing."""
        snapshot = TickerSnapshot(
            symbol="AAPL",
            prev_close=None,  # Missing prev_close
            prev_volume=None,
            open_price=None,
            high_price=None,
            low_price=None,
            close_price=None,
            volume=None,
            vwap=None,
            last_price=Decimal("151.50"),
            last_timestamp=None,
            market_status=None
        )

        assert snapshot.change is None
        assert snapshot.change_percent is None


class TestMarketSnapshot:
    """Test MarketSnapshot model."""

    def test_create_market_snapshot(self):
        """Test basic MarketSnapshot creation."""
        ticker = TickerSnapshot(
            symbol="AAPL",
            prev_close=Decimal("150.00"),
            prev_volume=1000000,
            open_price=None,
            high_price=None,
            low_price=None,
            close_price=None,
            volume=None,
            vwap=None,
            last_price=Decimal("151.50"),
            last_timestamp=None,
            market_status="closed"
        )

        snapshot = MarketSnapshot(
            tickers={"AAPL": ticker},
            timestamp=datetime(2025, 9, 28, 16, 0, 0),
            market_status="closed",
            total_symbols=1
        )

        assert len(snapshot.tickers) == 1
        assert "AAPL" in snapshot.tickers
        assert snapshot.total_symbols == 1
        assert snapshot.market_status == "closed"

    def test_market_snapshot_from_polygon_data(self):
        """Test creating MarketSnapshot from Polygon API response."""
        polygon_data = {
            "results": [
                {
                    "ticker": "AAPL",
                    "prevDay": {
                        "c": 150.00,
                        "v": 1000000
                    },
                    "lastQuote": {
                        "c": 151.50,
                        "t": 1727546400000000000  # 2025-09-28 16:00:00 in nanoseconds
                    },
                    "lastTrade": {
                        "p": 151.50,
                        "t": 1727546400000
                    }
                }
            ]
        }

        market_snapshot = MarketSnapshot.from_polygon_data(polygon_data)

        assert len(market_snapshot.tickers) == 1
        assert "AAPL" in market_snapshot.tickers

        aapl = market_snapshot.tickers["AAPL"]
        assert aapl.symbol == "AAPL"
        assert aapl.prev_close == Decimal("150.00")
        assert aapl.prev_volume == 1000000

    def test_market_snapshot_handles_empty_data(self):
        """Test MarketSnapshot handles empty/missing data gracefully."""
        polygon_data = {"results": []}

        market_snapshot = MarketSnapshot.from_polygon_data(polygon_data)

        assert len(market_snapshot.tickers) == 0
        assert market_snapshot.total_symbols == 0

    def test_market_snapshot_skips_invalid_tickers(self):
        """Test MarketSnapshot skips tickers without symbol."""
        polygon_data = {
            "results": [
                {
                    # Missing "ticker" field
                    "prevDay": {"c": 150.00}
                },
                {
                    "ticker": "",  # Empty ticker
                    "prevDay": {"c": 150.00}
                },
                {
                    "ticker": "AAPL",  # Valid ticker
                    "prevDay": {"c": 150.00}
                }
            ]
        }

        market_snapshot = MarketSnapshot.from_polygon_data(polygon_data)

        # Should only have the valid AAPL ticker
        assert len(market_snapshot.tickers) == 1
        assert "AAPL" in market_snapshot.tickers