"""
Tests for Gap Market Scanner - Core Gap Detection Logic

Tests the critical gap detection algorithms, market session awareness,
and filtering logic for trading opportunities.
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict

import pytest

from src.tradescout.analysis.gap_market_scanner import GapMarketScanner
from src.tradescout.data_models.domain_models_core import Asset, AssetType, MarketQuote, PriceData
from src.tradescout.data_models.factories import MarketFactory
from src.tradescout.data_models.market_wide_models import MarketMover


class TestGapMarketScannerInitialization:
    """Test GapMarketScanner initialization and configuration"""

    def test_scanner_initialization(self):
        """Test basic scanner initialization"""
        mock_coordinator = Mock()
        scanner = GapMarketScanner(mock_coordinator)
        
        assert scanner.coordinator == mock_coordinator
        assert scanner.nasdaq_market is not None
        
        # Verify academic research thresholds are set
        assert scanner.min_gap_threshold == Decimal("2.0")
        assert scanner.min_volume_ratio == Decimal("2.0")
        assert scanner.min_market_cap == 1_000_000_000  # $1B
        assert scanner.max_bid_ask_spread == Decimal("1.0")


class TestGapDetectionLogic:
    """Test core gap detection and calculation logic"""

    def setup_method(self):
        """Setup scanner with mocked coordinator"""
        self.mock_coordinator = Mock()
        self.scanner = GapMarketScanner(self.mock_coordinator)

    def test_scan_pre_market_gaps_successful_scan(self):
        """Test successful gap scanning with valid market data"""
        # Setup mock market movers (gainers and losers)
        mock_gainer = MarketMover(
            asset=Asset(symbol="GAINER1", name="Gainer Corp", asset_type=AssetType.COMMON_STOCK,
                       market=MarketFactory().create_nasdaq_market(), currency="USD"),
            current_price=Decimal("105.00"),
            price_change=Decimal("5.00"),
            price_change_percent=Decimal("5.00"),
            volume=1000000,
            rank=1
        )
        
        mock_loser = MarketMover(
            asset=Asset(symbol="LOSER1", name="Loser Corp", asset_type=AssetType.COMMON_STOCK,
                       market=MarketFactory().create_nasdaq_market(), currency="USD"),
            current_price=Decimal("95.00"),
            price_change=Decimal("-5.00"),
            price_change_percent=Decimal("-5.00"),
            volume=800000,
            rank=1
        )
        
        # Setup coordinator mocks
        self.mock_coordinator.get_market_gainers.return_value = [mock_gainer]
        self.mock_coordinator.get_market_losers.return_value = [mock_loser]
        
        # Mock full market snapshot
        snapshot_data = {
            'GAINER1': {
                'ticker': 'GAINER1',
                'day': {'c': 105.0, 'v': 1000000},
                'prevDay': {'c': 100.0},
                'min': {'c': 105.0}
            },
            'LOSER1': {
                'ticker': 'LOSER1', 
                'day': {'c': 95.0, 'v': 800000},
                'prevDay': {'c': 100.0},
                'min': {'c': 95.0}
            }
        }
        self.mock_coordinator.get_full_market_snapshot.return_value = snapshot_data
        
        # Mock gap data calculations
        gainer_gap_data = {
            'current_price': 105.0,
            'reference_close': 100.0,
            'gap_percent': 5.0,
            'gap_amount': 5.0,
            'session_type': 'premarket'
        }
        loser_gap_data = {
            'current_price': 95.0,
            'reference_close': 100.0,
            'gap_percent': 5.0,
            'gap_amount': -5.0,
            'session_type': 'premarket'
        }
        
        self.mock_coordinator.get_gap_data_from_snapshot.side_effect = [gainer_gap_data, loser_gap_data]
        
        # Mock current time as pre-market
        mock_now = Mock()
        mock_now.hour = 7  # 7 AM pre-market
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = mock_now
            
            # Execute scan
            gap_candidates, stats = self.scanner.scan_pre_market_gaps(min_gap_percent=Decimal("3.0"))
        
        # Verify results
        assert len(gap_candidates) == 2  # Both should meet 3% threshold
        assert stats['movers_analyzed'] == 2
        assert stats['movers_processed'] == 2
        assert stats['data_available'] == 2
        assert stats['gap_candidates'] == 2
        
        # Verify gap candidates have correct properties
        assert gap_candidates[0].gap_size >= Decimal("3.0")
        assert gap_candidates[1].gap_size >= Decimal("3.0")
        assert gap_candidates[0].gap_direction in ["up", "down"]
        assert gap_candidates[1].gap_direction in ["up", "down"]

    def test_scan_pre_market_gaps_filters_small_gaps(self):
        """Test that scanner filters out gaps below threshold"""
        mock_mover = MarketMover(
            asset=Asset(symbol="SMALL_GAP", name="Small Gap Corp", asset_type=AssetType.COMMON_STOCK,
                       market=MarketFactory().create_nasdaq_market(), currency="USD"),
            current_price=Decimal("101.00"),
            price_change=Decimal("1.00"),
            price_change_percent=Decimal("1.00"),
            volume=500000,
            rank=1
        )
        
        self.mock_coordinator.get_market_gainers.return_value = [mock_mover]
        self.mock_coordinator.get_market_losers.return_value = []
        
        snapshot_data = {
            'SMALL_GAP': {
                'ticker': 'SMALL_GAP',
                'day': {'c': 101.0, 'v': 500000},
                'prevDay': {'c': 100.0}
            }
        }
        self.mock_coordinator.get_full_market_snapshot.return_value = snapshot_data
        
        # Small gap - only 1%
        gap_data = {
            'current_price': 101.0,
            'reference_close': 100.0,
            'gap_percent': 1.0,  # Below 2% threshold
            'gap_amount': 1.0,
            'session_type': 'premarket'
        }
        self.mock_coordinator.get_gap_data_from_snapshot.return_value = gap_data
        
        # Execute scan with 2% minimum
        gap_candidates, stats = self.scanner.scan_pre_market_gaps(min_gap_percent=Decimal("2.0"))
        
        # Should filter out the small gap
        assert len(gap_candidates) == 0
        assert stats['gap_candidates'] == 0
        assert stats['data_available'] == 1  # Data was available but filtered

    def test_scan_handles_missing_snapshot_data(self):
        """Test graceful handling when snapshot data is unavailable"""
        mock_mover = MarketMover(
            asset=Asset(symbol="TEST", name="Test Corp", asset_type=AssetType.COMMON_STOCK,
                       market=MarketFactory().create_nasdaq_market(), currency="USD"),
            current_price=Decimal("100.00"),
            price_change=Decimal("0.00"),
            price_change_percent=Decimal("0.00"),
            volume=1000000,
            rank=1
        )
        
        self.mock_coordinator.get_market_gainers.return_value = [mock_mover]
        self.mock_coordinator.get_market_losers.return_value = []
        
        # No snapshot data available
        self.mock_coordinator.get_full_market_snapshot.return_value = None
        
        gap_candidates, stats = self.scanner.scan_pre_market_gaps()
        
        # Should return empty results gracefully
        assert len(gap_candidates) == 0
        assert stats['movers_analyzed'] == 1
        assert stats['data_available'] == 0

    def test_scan_handles_missing_gap_data_for_symbol(self):
        """Test handling when specific symbol has no gap data"""
        mock_mover = MarketMover(
            asset=Asset(symbol="NO_DATA", name="No Data Corp", asset_type=AssetType.COMMON_STOCK,
                       market=MarketFactory().create_nasdaq_market(), currency="USD"),
            current_price=Decimal("100.00"),
            price_change=Decimal("0.00"),
            price_change_percent=Decimal("0.00"),
            volume=1000000,
            rank=1
        )
        
        self.mock_coordinator.get_market_gainers.return_value = [mock_mover]
        self.mock_coordinator.get_market_losers.return_value = []
        self.mock_coordinator.get_full_market_snapshot.return_value = {"OTHER_SYMBOL": {}}
        
        # No gap data for this specific symbol
        self.mock_coordinator.get_gap_data_from_snapshot.return_value = None
        
        gap_candidates, stats = self.scanner.scan_pre_market_gaps()
        
        assert len(gap_candidates) == 0
        assert stats['movers_processed'] == 1
        assert stats['data_available'] == 0  # No gap data available

    def test_session_detection_logging(self):
        """Test that scanner correctly identifies different market sessions"""
        self.mock_coordinator.get_market_gainers.return_value = []
        self.mock_coordinator.get_market_losers.return_value = []
        self.mock_coordinator.get_full_market_snapshot.return_value = {}
        
        # Test different time periods
        test_cases = [
            (6, "pre-market gaps"),      # 6 AM - pre-market
            (10, "intraday gaps"),       # 10 AM - regular hours
            (18, "after-hours gaps"),    # 6 PM - after-hours
            (22, "extended hours gaps"), # 10 PM - extended
        ]
        
        for hour, expected_session in test_cases:
            mock_now = Mock()
            mock_now.hour = hour
            with patch('datetime.datetime') as mock_datetime:
                mock_datetime.now.return_value = mock_now
                
                with patch('src.tradescout.analysis.gap_market_scanner.logger') as mock_logger:
                    self.scanner.scan_pre_market_gaps()
                    
                    # Verify session was logged correctly
                    mock_logger.debug.assert_any_call(
                        f"Scanning for {expected_session} >= 2.0%"
                    )


class TestBasicCriteriaFiltering:
    """Test the basic criteria filtering for gap candidates"""

    def setup_method(self):
        """Setup scanner for criteria testing"""
        self.mock_coordinator = Mock()
        self.scanner = GapMarketScanner(self.mock_coordinator)

    def test_meets_basic_criteria_valid_quote(self):
        """Test that valid quotes pass basic criteria"""
        asset = Asset(symbol="VALID", name="Valid Corp", asset_type=AssetType.COMMON_STOCK,
                     market=MarketFactory().create_nasdaq_market(), currency="USD")
        
        price_data = PriceData(
            asset=asset,
            timestamp=datetime.now(),
            price=Decimal("50.00"),
            volume=1000000
        )
        
        quote = MarketQuote(asset=asset, price_data=price_data)
        quote.market_cap = 2_000_000_000  # $2B - above minimum
        
        result = self.scanner._meets_basic_criteria(quote, Decimal("3.0"))
        assert result is True

    def test_meets_basic_criteria_rejects_no_volume(self):
        """Test rejection of quotes with no volume data"""
        asset = Asset(symbol="NO_VOL", name="No Volume Corp", asset_type=AssetType.COMMON_STOCK,
                     market=MarketFactory().create_nasdaq_market(), currency="USD")
        
        price_data = PriceData(
            asset=asset,
            timestamp=datetime.now(),
            price=Decimal("50.00"),
            volume=0  # No volume
        )
        
        quote = MarketQuote(asset=asset, price_data=price_data)
        
        result = self.scanner._meets_basic_criteria(quote, Decimal("3.0"))
        assert result is False

    def test_meets_basic_criteria_rejects_unreasonable_price(self):
        """Test rejection of quotes with unreasonable prices"""
        asset = Asset(symbol="BAD_PRICE", name="Bad Price Corp", asset_type=AssetType.COMMON_STOCK,
                     market=MarketFactory().create_nasdaq_market(), currency="USD")
        
        # Test extremely high price
        price_data_high = PriceData(
            asset=asset,
            timestamp=datetime.now(),
            price=Decimal("15000.00"),  # Unreasonably high
            volume=1000000
        )
        quote_high = MarketQuote(asset=asset, price_data=price_data_high)
        
        assert self.scanner._meets_basic_criteria(quote_high, Decimal("3.0")) is False
        
        # Test negative price
        price_data_negative = PriceData(
            asset=asset,
            timestamp=datetime.now(),
            price=Decimal("-5.00"),  # Negative price
            volume=1000000
        )
        quote_negative = MarketQuote(asset=asset, price_data=price_data_negative)
        
        assert self.scanner._meets_basic_criteria(quote_negative, Decimal("3.0")) is False

    def test_meets_basic_criteria_rejects_small_market_cap(self):
        """Test rejection of quotes with market cap below threshold"""
        asset = Asset(symbol="SMALL_CAP", name="Small Cap Corp", asset_type=AssetType.COMMON_STOCK,
                     market=MarketFactory().create_nasdaq_market(), currency="USD")
        
        price_data = PriceData(
            asset=asset,
            timestamp=datetime.now(),
            price=Decimal("10.00"),
            volume=1000000
        )
        
        quote = MarketQuote(asset=asset, price_data=price_data)
        quote.market_cap = 500_000_000  # $500M - below $1B minimum
        
        result = self.scanner._meets_basic_criteria(quote, Decimal("3.0"))
        assert result is False

    def test_meets_basic_criteria_handles_missing_market_cap(self):
        """Test that missing market cap doesn't cause rejection"""
        asset = Asset(symbol="NO_CAP", name="No Cap Corp", asset_type=AssetType.COMMON_STOCK,
                     market=MarketFactory().create_nasdaq_market(), currency="USD")
        
        price_data = PriceData(
            asset=asset,
            timestamp=datetime.now(),
            price=Decimal("25.00"),
            volume=1000000
        )
        
        quote = MarketQuote(asset=asset, price_data=price_data)
        # No market_cap attribute set
        
        result = self.scanner._meets_basic_criteria(quote, Decimal("3.0"))
        assert result is True  # Should pass when market cap is not available


class TestHighQualitySetupDetection:
    """Test detection of high-quality gap setups"""

    def setup_method(self):
        """Setup scanner for quality testing"""
        self.mock_coordinator = Mock()
        self.scanner = GapMarketScanner(self.mock_coordinator)

    def test_is_high_quality_setup_large_gap_high_volume(self):
        """Test high quality detection with large gap and high volume"""
        asset = Asset(symbol="HIGH_QUAL", name="High Quality Corp", asset_type=AssetType.COMMON_STOCK,
                     market=MarketFactory().create_nasdaq_market(), currency="USD")
        
        price_data = PriceData(
            asset=asset,
            timestamp=datetime.now(),
            price=Decimal("50.00"),
            volume=1000000
        )
        
        quote = MarketQuote(asset=asset, price_data=price_data)
        quote.gap_size = Decimal("4.5")     # > 3% gap
        quote.volume_ratio = Decimal("3.5") # > 3x volume
        
        result = self.scanner._is_high_quality_setup(quote)
        assert result is True

    def test_is_high_quality_setup_rejects_small_gap(self):
        """Test rejection when gap is too small"""
        asset = Asset(symbol="SMALL_GAP", name="Small Gap Corp", asset_type=AssetType.COMMON_STOCK,
                     market=MarketFactory().create_nasdaq_market(), currency="USD")
        
        price_data = PriceData(
            asset=asset,
            timestamp=datetime.now(),
            price=Decimal("50.00"),
            volume=1000000
        )
        
        quote = MarketQuote(asset=asset, price_data=price_data)
        quote.gap_size = Decimal("2.5")     # < 3% gap
        quote.volume_ratio = Decimal("3.5") # > 3x volume (but gap too small)
        
        result = self.scanner._is_high_quality_setup(quote)
        assert result is False

    def test_is_high_quality_setup_rejects_low_volume(self):
        """Test rejection when volume ratio is too low"""
        asset = Asset(symbol="LOW_VOL", name="Low Volume Corp", asset_type=AssetType.COMMON_STOCK,
                     market=MarketFactory().create_nasdaq_market(), currency="USD")
        
        price_data = PriceData(
            asset=asset,
            timestamp=datetime.now(),
            price=Decimal("50.00"),
            volume=1000000
        )
        
        quote = MarketQuote(asset=asset, price_data=price_data)
        quote.gap_size = Decimal("4.5")     # > 3% gap
        quote.volume_ratio = Decimal("2.0") # < 3x volume
        
        result = self.scanner._is_high_quality_setup(quote)
        assert result is False

    def test_is_high_quality_setup_handles_missing_attributes(self):
        """Test graceful handling when gap_size or volume_ratio are missing"""
        asset = Asset(symbol="MISSING", name="Missing Attrs Corp", asset_type=AssetType.COMMON_STOCK,
                     market=MarketFactory().create_nasdaq_market(), currency="USD")
        
        price_data = PriceData(
            asset=asset,
            timestamp=datetime.now(),
            price=Decimal("50.00"),
            volume=1000000
        )
        
        quote = MarketQuote(asset=asset, price_data=price_data)
        # No gap_size or volume_ratio attributes
        
        result = self.scanner._is_high_quality_setup(quote)
        assert result is False  # Should default to False when attributes missing


class TestVolumeLeaderScanning:
    """Test volume spike detection functionality"""

    def setup_method(self):
        """Setup scanner for volume testing"""
        self.mock_coordinator = Mock()
        self.scanner = GapMarketScanner(self.mock_coordinator)

    def test_scan_volume_spikes_delegates_to_coordinator(self):
        """Test that volume spike scanning delegates to coordinator"""
        expected_volume_leaders = [
            MarketQuote(
                asset=Asset(symbol="HIGH_VOL", name="High Volume Corp", 
                           asset_type=AssetType.COMMON_STOCK,
                           market=MarketFactory().create_nasdaq_market(), currency="USD"),
                price_data=PriceData(
                    asset=Asset(symbol="HIGH_VOL", name="High Volume Corp", 
                               asset_type=AssetType.COMMON_STOCK,
                               market=MarketFactory().create_nasdaq_market(), currency="USD"),
                    timestamp=datetime.now(),
                    price=Decimal("100.00"),
                    volume=5000000  # High volume
                )
            )
        ]
        
        self.mock_coordinator.get_volume_leaders.return_value = expected_volume_leaders
        
        result = self.scanner.scan_volume_spikes(min_volume_ratio=Decimal("2.5"))
        
        assert result == expected_volume_leaders
        # Verify coordinator was called with correct parameters
        self.mock_coordinator.get_volume_leaders.assert_called_once()
        call_args = self.mock_coordinator.get_volume_leaders.call_args
        assert call_args[1]['min_volume_ratio'] == Decimal("2.5")
        
        # Verify that major symbols list was passed
        symbols_list = call_args[0][0]
        assert "AAPL" in symbols_list
        assert "MSFT" in symbols_list
        assert "GOOGL" in symbols_list


class TestComprehensiveGapScan:
    """Test comprehensive gap scanning with categorization"""

    def setup_method(self):
        """Setup scanner for comprehensive scan testing"""
        self.mock_coordinator = Mock()
        self.scanner = GapMarketScanner(self.mock_coordinator)

    def test_comprehensive_gap_scan_categorizes_results(self):
        """Test that comprehensive scan properly categorizes gap opportunities"""
        # Create test quotes with different characteristics
        high_quality_quote = Mock()
        high_quality_quote.asset.symbol = "HIGH_QUAL"
        high_quality_quote.volume_ratio = Decimal("3.5")  # High volume, > 2.0 threshold
        
        low_volume_quote = Mock()
        low_volume_quote.asset.symbol = "LOW_VOL"
        low_volume_quote.volume_ratio = Decimal("1.5")   # Low volume, < 2.0 threshold
        
        # Mock the scan_pre_market_gaps to return test quotes
        mock_gap_candidates = [high_quality_quote, low_volume_quote]
        with patch.object(self.scanner, 'scan_pre_market_gaps') as mock_scan:
            mock_scan.return_value = (mock_gap_candidates, {})
            
            # Mock high quality detection - only high volume qualifies
            with patch.object(self.scanner, '_is_high_quality_setup') as mock_quality:
                mock_quality.side_effect = lambda q: getattr(q, 'volume_ratio', Decimal("0")) > Decimal("3.0")
                
                result = self.scanner.get_comprehensive_gap_scan(min_gap_percent=Decimal("2.5"))
        
        # Verify categorization
        assert len(result['gap_candidates']) == 2
        
        # Only high_quality_quote should pass volume confirmation (3.5 > 2.0)
        assert len(result['volume_confirmed']) == 1
        assert result['volume_confirmed'][0] == high_quality_quote
        
        # Only high_quality_quote should be high quality (3.5 > 3.0)  
        assert len(result['high_quality']) == 1
        assert result['high_quality'][0] == high_quality_quote
        
        # low_volume_quote should be rejected (1.5 < 2.0)
        assert len(result['rejected']) == 1
        assert result['rejected'][0] == low_volume_quote

    def test_comprehensive_gap_scan_handles_errors_gracefully(self):
        """Test graceful error handling during comprehensive scan"""
        # Create a quote that will cause an exception during analysis
        problematic_quote = Mock()
        problematic_quote.asset.symbol = "ERROR_QUOTE"
        problematic_quote.volume_ratio = None  # This might cause AttributeError
        
        with patch.object(self.scanner, 'scan_pre_market_gaps') as mock_scan:
            mock_scan.return_value = ([problematic_quote], {})
            
            # Mock volume ratio check to raise exception
            def volume_check(quote):
                if quote.volume_ratio is None:
                    raise AttributeError("volume_ratio is None")
                return quote.volume_ratio >= self.scanner.min_volume_ratio
            
            with patch.object(problematic_quote, '__getattribute__') as mock_attr:
                mock_attr.side_effect = lambda name: volume_check(problematic_quote) if name == 'volume_ratio' else Mock()
                
                result = self.scanner.get_comprehensive_gap_scan()
        
        # Should handle error gracefully and put quote in rejected list
        assert len(result['rejected']) >= 1
        assert result['volume_confirmed'] == []
        assert result['high_quality'] == []


class TestScannerConfiguration:
    """Test scanner configuration and parameter handling"""

    def setup_method(self):
        """Setup for configuration tests"""
        self.mock_coordinator = Mock()
        self.scanner = GapMarketScanner(self.mock_coordinator)

    def test_scan_respects_custom_gap_threshold(self):
        """Test that scanner respects custom gap thresholds"""
        mock_mover = Mock()
        mock_mover.asset.symbol = "TEST"
        
        self.mock_coordinator.get_market_gainers.return_value = [mock_mover]
        self.mock_coordinator.get_market_losers.return_value = []
        self.mock_coordinator.get_full_market_snapshot.return_value = {"TEST": {}}
        
        # Mock gap data with 4.5% gap
        gap_data = {
            'current_price': 104.5,
            'reference_close': 100.0,
            'gap_percent': 4.5,
            'gap_amount': 4.5,
            'session_type': 'premarket'
        }
        self.mock_coordinator.get_gap_data_from_snapshot.return_value = gap_data
        
        # Test with different thresholds
        with patch.object(self.scanner, '_meets_basic_criteria', return_value=True):
            # Should find gap with 3% threshold
            candidates_3pct, _ = self.scanner.scan_pre_market_gaps(min_gap_percent=Decimal("3.0"))
            assert len(candidates_3pct) == 1
            
            # Should NOT find gap with 5% threshold
            candidates_5pct, _ = self.scanner.scan_pre_market_gaps(min_gap_percent=Decimal("5.0"))
            assert len(candidates_5pct) == 0

    def test_scan_respects_movers_limit_override(self):
        """Test that scanner respects custom movers limit"""
        # Mock multiple movers
        movers = [Mock() for _ in range(10)]
        for i, mover in enumerate(movers):
            mover.asset.symbol = f"MOVER_{i}"
        
        self.mock_coordinator.get_market_gainers.return_value = movers[:5]
        self.mock_coordinator.get_market_losers.return_value = movers[5:]
        
        # Mock config to return default limit
        with patch('src.tradescout.analysis.gap_market_scanner.get_market_movers_limit') as mock_config:
            mock_config.return_value = 50  # Default config limit
            
            self.mock_coordinator.get_full_market_snapshot.return_value = {}
            
            # Test with custom limit override
            self.scanner.scan_pre_market_gaps(movers_limit=20)
            
            # Verify coordinator was called with custom limit, not config default
            self.mock_coordinator.get_market_gainers.assert_called_with(limit=20, force_refresh=False)
            self.mock_coordinator.get_market_losers.assert_called_with(limit=20, force_refresh=False)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])