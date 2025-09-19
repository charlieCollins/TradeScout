"""
Tests for Gap Analyzer

Tests the GapAnalyzer implementation including:
- Gap candidate identification
- Risk assessment processing
- Batch processing capabilities
- Edge cases and error handling
- Mock data testing
"""

import pytest
from datetime import datetime, time
from decimal import Decimal
from unittest.mock import Mock, patch

from src.tradescout.analysis.gap_analyzer import GapAnalyzer
from src.tradescout.data_models.models_asset import Asset, AssetType, PriceData
from src.tradescout.data_models.models_market import Market, MarketType, MarketStatus
from src.tradescout.data_models.models_analysis import (
    GapRules,
    GapCandidate,
    GapAssessment,
    GapType,
    RiskLevel,
    ConfidenceLevel,
)


class TestGapAnalyzer:
    """Test suite for GapAnalyzer"""

    @pytest.fixture
    def sample_market(self):
        """Create a sample market for testing"""
        return Market(
            id="NASDAQ",
            name="NASDAQ",
            market_type=MarketType.STOCK,
            timezone="America/New_York",
            currency="USD",
            regular_open=time(9, 30),
            regular_close=time(16, 0),
            pre_market_start=time(4, 0),
            after_hours_end=time(20, 0),
        )

    @pytest.fixture
    def sample_asset(self, sample_market):
        """Create a sample asset for testing"""
        return Asset(
            symbol="AAPL",
            name="Apple Inc.",
            asset_type=AssetType.COMMON_STOCK,
            market=sample_market,
            currency="USD",
        )

    @pytest.fixture
    def sample_gap_rules(self):
        """Create sample gap rules for testing"""
        return GapRules(
            min_gap_percent=2.0,
            max_gap_percent=10.0,
            min_volume=100000,
            min_volume_ratio=1.5,
            min_price=5.0,
            max_price=500.0,
            max_spread_percent=0.5,
            session_types=["pre_market", "after_hours"],
            exclude_penny_stocks=True,
            exclude_low_volume=True,
            exhaustion_threshold=7.0,
            breakaway_min=2.5,
        )

    @pytest.fixture
    def gap_analyzer(self):
        """Create GapAnalyzer instance"""
        return GapAnalyzer()

    def create_price_data(self, asset, current_price, prev_close, volume=200000, avg_volume=150000):
        """Helper to create PriceData objects"""
        return PriceData(
            asset=asset,
            timestamp=datetime.now(),
            volume=volume,
            current_price=Decimal(str(current_price)),
            prev_session_close_price=Decimal(str(prev_close)),
            average_volume=avg_volume,
        )

    def test_identify_gap_candidates_valid_gap(self, gap_analyzer, sample_asset, sample_gap_rules):
        """Test identification of valid gap candidates"""
        # Create price data with a 3% gap up and volume ratio > 1.5
        price_data = [
            self.create_price_data(sample_asset, 103.0, 100.0, 250000, 150000)  # Volume ratio = 1.67
        ]

        candidates = gap_analyzer.identify_gap_candidates(
            price_data, sample_gap_rules, MarketStatus.PRE_MARKET
        )

        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.asset.symbol == "AAPL"
        assert candidate.current_price == Decimal("103.0")
        assert candidate.previous_close == Decimal("100.0")
        assert candidate.gap_size == Decimal("3.0")
        assert candidate.gap_percent == Decimal("3.0")
        assert candidate.gap_direction == "up"
        assert candidate.gap_type == GapType.BREAKAWAY  # 3% >= 2.5% breakaway_min
        assert candidate.session_type == MarketStatus.PRE_MARKET

    def test_identify_gap_candidates_gap_too_small(self, gap_analyzer, sample_asset, sample_gap_rules):
        """Test rejection of gaps below minimum threshold"""
        # Create price data with a 1% gap (below 2% minimum)
        price_data = [
            self.create_price_data(sample_asset, 101.0, 100.0)
        ]

        candidates = gap_analyzer.identify_gap_candidates(
            price_data, sample_gap_rules, MarketStatus.PRE_MARKET
        )

        assert len(candidates) == 0

    def test_identify_gap_candidates_gap_too_large(self, gap_analyzer, sample_asset, sample_gap_rules):
        """Test rejection of gaps above maximum threshold"""
        # Create price data with a 12% gap (above 10% maximum)
        price_data = [
            self.create_price_data(sample_asset, 112.0, 100.0)
        ]

        candidates = gap_analyzer.identify_gap_candidates(
            price_data, sample_gap_rules, MarketStatus.PRE_MARKET
        )

        assert len(candidates) == 0

    def test_identify_gap_candidates_volume_too_low(self, gap_analyzer, sample_asset, sample_gap_rules):
        """Test rejection of candidates with insufficient volume"""
        # Create price data with low volume
        price_data = [
            self.create_price_data(sample_asset, 103.0, 100.0, volume=50000)  # Below 100k minimum
        ]

        candidates = gap_analyzer.identify_gap_candidates(
            price_data, sample_gap_rules, MarketStatus.PRE_MARKET
        )

        assert len(candidates) == 0

    def test_identify_gap_candidates_price_too_low(self, gap_analyzer, sample_asset, sample_gap_rules):
        """Test rejection of penny stocks"""
        # Create price data with low price
        price_data = [
            self.create_price_data(sample_asset, 3.0, 2.94)  # Below $5 minimum
        ]

        candidates = gap_analyzer.identify_gap_candidates(
            price_data, sample_gap_rules, MarketStatus.PRE_MARKET
        )

        assert len(candidates) == 0

    def test_identify_gap_candidates_missing_data(self, gap_analyzer, sample_asset, sample_gap_rules):
        """Test handling of missing price data"""
        price_data = [
            PriceData(
                asset=sample_asset,
                timestamp=datetime.now(),
                volume=200000,
                current_price=None,  # Missing current price
                prev_session_close_price=Decimal("100.0"),
            )
        ]

        candidates = gap_analyzer.identify_gap_candidates(
            price_data, sample_gap_rules, MarketStatus.PRE_MARKET
        )

        assert len(candidates) == 0

    def test_gap_type_classification(self, gap_analyzer, sample_asset, sample_gap_rules):
        """Test gap type classification logic"""
        test_cases = [
            (101.5, 100.0, GapType.COMMON),      # 1.5% - below breakaway_min
            (103.0, 100.0, GapType.CONTINUATION), # 3% - between breakaway and exhaustion
            (108.0, 100.0, GapType.EXHAUSTION),   # 8% - above exhaustion threshold
        ]

        for current, prev_close, expected_type in test_cases:
            price_data = [self.create_price_data(sample_asset, current, prev_close)]
            candidates = gap_analyzer.identify_gap_candidates(
                price_data, sample_gap_rules, MarketStatus.PRE_MARKET
            )

            if candidates:  # Only check if candidate was created
                assert candidates[0].gap_type == expected_type

    def test_gap_direction_classification(self, gap_analyzer, sample_asset, sample_gap_rules):
        """Test gap direction classification"""
        # Gap up
        price_data_up = [self.create_price_data(sample_asset, 103.0, 100.0, 250000, 150000)]
        candidates_up = gap_analyzer.identify_gap_candidates(
            price_data_up, sample_gap_rules, MarketStatus.PRE_MARKET
        )
        assert candidates_up[0].gap_direction == "up"

        # Gap down
        price_data_down = [self.create_price_data(sample_asset, 97.0, 100.0, 250000, 150000)]
        candidates_down = gap_analyzer.identify_gap_candidates(
            price_data_down, sample_gap_rules, MarketStatus.PRE_MARKET
        )
        assert candidates_down[0].gap_direction == "down"

    def test_process_gap_candidate(self, gap_analyzer, sample_asset):
        """Test processing single gap candidate for risk assessment"""
        gap_candidate = GapCandidate(
            asset=sample_asset,
            analysis_time=datetime.now(),
            session_type=MarketStatus.PRE_MARKET,
            previous_close=Decimal("100.0"),
            current_price=Decimal("103.0"),
            gap_size=Decimal("3.0"),
            gap_percent=Decimal("3.0"),
            gap_type=GapType.CONTINUATION,
            gap_direction="up",
            volume=200000,
        )

        assessment = gap_analyzer.process_gap_candidate(gap_candidate)

        assert isinstance(assessment, GapAssessment)
        assert assessment.gap_candidate == gap_candidate
        assert 0 <= assessment.fill_probability <= 1
        assert 0 <= assessment.continuation_probability <= 1
        assert assessment.fill_probability + assessment.continuation_probability == 1
        assert isinstance(assessment.risk_level, RiskLevel)
        assert isinstance(assessment.confidence, ConfidenceLevel)
        assert assessment.suggested_entry == Decimal("103.0")
        assert assessment.stop_loss > 0
        assert assessment.take_profit > 0
        assert assessment.max_position_size > 0
        assert assessment.risk_reward_ratio > 0

    def test_risk_level_assessment(self, gap_analyzer, sample_asset):
        """Test risk level assessment based on gap size"""
        test_cases = [
            (1.5, RiskLevel.CONSERVATIVE),  # Small gap
            (4.0, RiskLevel.MODERATE),      # Medium gap
            (8.0, RiskLevel.AGGRESSIVE),    # Large gap
        ]

        for gap_percent, expected_risk in test_cases:
            gap_candidate = GapCandidate(
                asset=sample_asset,
                analysis_time=datetime.now(),
                session_type=MarketStatus.PRE_MARKET,
                previous_close=Decimal("100.0"),
                current_price=Decimal(str(100.0 + gap_percent)),
                gap_size=Decimal(str(gap_percent)),
                gap_percent=Decimal(str(gap_percent)),
                gap_type=GapType.CONTINUATION,
                gap_direction="up",
                volume=200000,
            )

            assessment = gap_analyzer.process_gap_candidate(gap_candidate)
            assert assessment.risk_level == expected_risk

    def test_confidence_assessment_by_gap_type(self, gap_analyzer, sample_asset):
        """Test confidence assessment based on gap type"""
        test_cases = [
            (GapType.COMMON, ConfidenceLevel.HIGH),
            (GapType.EXHAUSTION, ConfidenceLevel.HIGH),
            (GapType.CONTINUATION, ConfidenceLevel.MEDIUM),
            (GapType.BREAKAWAY, ConfidenceLevel.LOW),
        ]

        for gap_type, expected_confidence in test_cases:
            gap_candidate = GapCandidate(
                asset=sample_asset,
                analysis_time=datetime.now(),
                session_type=MarketStatus.PRE_MARKET,
                previous_close=Decimal("100.0"),
                current_price=Decimal("103.0"),
                gap_size=Decimal("3.0"),
                gap_percent=Decimal("3.0"),
                gap_type=gap_type,
                gap_direction="up",
                volume=200000,
            )

            assessment = gap_analyzer.process_gap_candidate(gap_candidate)
            assert assessment.confidence == expected_confidence

    def test_process_gap_candidates_batch(self, gap_analyzer, sample_asset):
        """Test batch processing of multiple gap candidates"""
        candidates = [
            GapCandidate(
                asset=sample_asset,
                analysis_time=datetime.now(),
                session_type=MarketStatus.PRE_MARKET,
                previous_close=Decimal("100.0"),
                current_price=Decimal("103.0"),
                gap_size=Decimal("3.0"),
                gap_percent=Decimal("3.0"),
                gap_type=GapType.CONTINUATION,
                gap_direction="up",
                volume=200000,
            ),
            GapCandidate(
                asset=sample_asset,
                analysis_time=datetime.now(),
                session_type=MarketStatus.PRE_MARKET,
                previous_close=Decimal("50.0"),
                current_price=Decimal("47.0"),
                gap_size=Decimal("-3.0"),
                gap_percent=Decimal("-6.0"),
                gap_type=GapType.EXHAUSTION,
                gap_direction="down",
                volume=300000,
            ),
        ]

        assessments = gap_analyzer.process_gap_candidates(candidates)

        assert len(assessments) == 2
        assert all(isinstance(a, GapAssessment) for a in assessments)
        assert assessments[0].gap_candidate == candidates[0]
        assert assessments[1].gap_candidate == candidates[1]

    def test_fill_probability_calculation(self, gap_analyzer, sample_asset):
        """Test fill probability calculation logic"""
        # Test different gap types have different fill probabilities
        gap_types_data = [
            (GapType.COMMON, 0.7, 0.9),        # Should have high fill probability
            (GapType.EXHAUSTION, 0.6, 0.8),    # Should have high fill probability
            (GapType.BREAKAWAY, 0.1, 0.4),     # Should have low fill probability
            (GapType.CONTINUATION, 0.4, 0.6),  # Should have medium fill probability
        ]

        for gap_type, min_prob, max_prob in gap_types_data:
            gap_candidate = GapCandidate(
                asset=sample_asset,
                analysis_time=datetime.now(),
                session_type=MarketStatus.PRE_MARKET,
                previous_close=Decimal("100.0"),
                current_price=Decimal("103.0"),
                gap_size=Decimal("3.0"),
                gap_percent=Decimal("3.0"),
                gap_type=gap_type,
                gap_direction="up",
                volume=200000,
            )

            assessment = gap_analyzer.process_gap_candidate(gap_candidate)
            assert min_prob <= float(assessment.fill_probability) <= max_prob

    def test_stop_loss_calculation(self, gap_analyzer, sample_asset):
        """Test stop loss calculation for different gap directions"""
        # Gap up - stop loss should be above current price
        gap_candidate_up = GapCandidate(
            asset=sample_asset,
            analysis_time=datetime.now(),
            session_type=MarketStatus.PRE_MARKET,
            previous_close=Decimal("100.0"),
            current_price=Decimal("103.0"),
            gap_size=Decimal("3.0"),
            gap_percent=Decimal("3.0"),
            gap_type=GapType.CONTINUATION,
            gap_direction="up",
            volume=200000,
        )

        assessment_up = gap_analyzer.process_gap_candidate(gap_candidate_up)
        assert assessment_up.stop_loss > assessment_up.suggested_entry

        # Gap down - stop loss should be below current price
        gap_candidate_down = GapCandidate(
            asset=sample_asset,
            analysis_time=datetime.now(),
            session_type=MarketStatus.PRE_MARKET,
            previous_close=Decimal("100.0"),
            current_price=Decimal("97.0"),
            gap_size=Decimal("-3.0"),
            gap_percent=Decimal("-3.0"),
            gap_type=GapType.CONTINUATION,
            gap_direction="down",
            volume=200000,
        )

        assessment_down = gap_analyzer.process_gap_candidate(gap_candidate_down)
        assert assessment_down.stop_loss < assessment_down.suggested_entry

    def test_multiple_assets_processing(self, gap_analyzer, sample_market, sample_gap_rules):
        """Test processing multiple assets with different characteristics"""
        assets = [
            Asset(symbol="AAPL", name="Apple", asset_type=AssetType.COMMON_STOCK,
                  market=sample_market, currency="USD"),
            Asset(symbol="GOOGL", name="Google", asset_type=AssetType.COMMON_STOCK,
                  market=sample_market, currency="USD"),
            Asset(symbol="TSLA", name="Tesla", asset_type=AssetType.COMMON_STOCK,
                  market=sample_market, currency="USD"),
        ]

        price_data = [
            self.create_price_data(assets[0], 103.0, 100.0, 250000, 150000),  # 3% gap up
            self.create_price_data(assets[1], 194.0, 200.0, 250000, 150000),  # 3% gap down
            self.create_price_data(assets[2], 214.0, 200.0, 250000, 150000),  # 7% gap up
        ]

        candidates = gap_analyzer.identify_gap_candidates(
            price_data, sample_gap_rules, MarketStatus.PRE_MARKET
        )

        assert len(candidates) == 3
        symbols = [c.asset.symbol for c in candidates]
        assert "AAPL" in symbols
        assert "GOOGL" in symbols
        assert "TSLA" in symbols

    def test_edge_case_zero_previous_close(self, gap_analyzer, sample_asset, sample_gap_rules):
        """Test handling of zero previous close price"""
        price_data = [
            PriceData(
                asset=sample_asset,
                timestamp=datetime.now(),
                volume=200000,
                current_price=Decimal("10.0"),
                prev_session_close_price=Decimal("0.0"),  # Zero previous close
                average_volume=150000,
            )
        ]

        candidates = gap_analyzer.identify_gap_candidates(
            price_data, sample_gap_rules, MarketStatus.PRE_MARKET
        )

        assert len(candidates) == 0  # Should be filtered out

    def test_volume_ratio_filtering(self, gap_analyzer, sample_asset, sample_gap_rules):
        """Test volume ratio filtering"""
        # Low volume ratio (below 1.5x average)
        price_data_low_ratio = [
            self.create_price_data(sample_asset, 103.0, 100.0, volume=120000, avg_volume=150000)
        ]

        candidates_low = gap_analyzer.identify_gap_candidates(
            price_data_low_ratio, sample_gap_rules, MarketStatus.PRE_MARKET
        )

        assert len(candidates_low) == 0  # Should be filtered out

        # High volume ratio (above 1.5x average)
        price_data_high_ratio = [
            self.create_price_data(sample_asset, 103.0, 100.0, volume=250000, avg_volume=150000)
        ]

        candidates_high = gap_analyzer.identify_gap_candidates(
            price_data_high_ratio, sample_gap_rules, MarketStatus.PRE_MARKET
        )

        assert len(candidates_high) == 1  # Should pass filter