"""
TradeScout Domain Factories

Factory classes for creating domain entities with common configurations.
Separates object creation logic from domain models.
"""

from datetime import time
from decimal import Decimal
from typing import Dict, Set

from .domain_models_core import (
    Asset, Market, MarketSegment, AssetType, MarketType
)


class MarketFactory:
    """Factory for creating Market entities with standard configurations"""
    
    @staticmethod
    def create_us_stock_market() -> Market:
        """Create standard US stock market configuration"""
        return Market(
            id="US_STOCKS",
            name="US Stock Markets",
            market_type=MarketType.STOCK,
            timezone="America/New_York",
            currency="USD",
            regular_open=time(9, 30),
            regular_close=time(16, 0),
            pre_market_start=time(4, 0),
            after_hours_end=time(20, 0),
            min_tick_size=Decimal('0.01'),
            trading_days={0, 1, 2, 3, 4}  # Monday to Friday
        )
    
    @staticmethod
    def create_nyse_market() -> Market:
        """Create New York Stock Exchange market"""
        return Market(
            id="NYSE",
            name="New York Stock Exchange",
            market_type=MarketType.STOCK,
            timezone="America/New_York",
            currency="USD",
            regular_open=time(9, 30),
            regular_close=time(16, 0),
            pre_market_start=time(4, 0),
            after_hours_end=time(20, 0),
            min_tick_size=Decimal('0.01'),
            trading_days={0, 1, 2, 3, 4}
        )
    
    @staticmethod
    def create_nasdaq_market() -> Market:
        """Create NASDAQ market"""
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
            min_tick_size=Decimal('0.01'),
            trading_days={0, 1, 2, 3, 4}
        )
    
    @staticmethod
    def create_crypto_market() -> Market:
        """Create 24/7 cryptocurrency market"""
        return Market(
            id="CRYPTO",
            name="Cryptocurrency Markets",
            market_type=MarketType.CRYPTO,
            timezone="UTC",
            currency="USD",
            regular_open=time(0, 0),
            regular_close=time(23, 59),
            min_tick_size=Decimal('0.00000001'),
            trading_days={0, 1, 2, 3, 4, 5, 6}  # All days
        )


class MarketSegmentFactory:
    """Factory for creating MarketSegment entities with standard hierarchies"""
    
    @staticmethod
    def create_technology_segment() -> MarketSegment:
        """Create technology sector segment"""
        return MarketSegment(
            id="technology",
            name="Technology",
            description="Technology companies and software",
            segment_type="sector"
        )
    
    @staticmethod
    def create_healthcare_segment() -> MarketSegment:
        """Create healthcare sector segment"""
        return MarketSegment(
            id="healthcare",
            name="Healthcare",
            description="Healthcare and pharmaceutical companies",
            segment_type="sector"
        )
    
    @staticmethod
    def create_financial_segment() -> MarketSegment:
        """Create financial sector segment"""
        return MarketSegment(
            id="financial",
            name="Financial Services",
            description="Banks, insurance, and financial services",
            segment_type="sector"
        )
    
    @staticmethod
    def create_sp500_segment() -> MarketSegment:
        """Create S&P 500 index segment"""
        return MarketSegment(
            id="sp500",
            name="S&P 500",
            description="Standard & Poor's 500 large-cap US stocks",
            segment_type="index"
        )
    
    @staticmethod
    def create_nasdaq100_segment() -> MarketSegment:
        """Create NASDAQ-100 index segment"""
        return MarketSegment(
            id="nasdaq100",
            name="NASDAQ-100",
            description="100 largest non-financial companies on NASDAQ",
            segment_type="index"
        )
    
    @staticmethod
    def create_large_cap_segment() -> MarketSegment:
        """Create large-cap size segment"""
        return MarketSegment(
            id="large_cap",
            name="Large Cap",
            description="Large capitalization stocks (>$10B market cap)",
            segment_type="size"
        )
    
    @staticmethod
    def create_hierarchical_tech_segments() -> Dict[str, MarketSegment]:
        """Create hierarchical technology segments"""
        # Parent sector
        technology = MarketSegmentFactory.create_technology_segment()
        
        # Sub-industries
        software = MarketSegment(
            id="software",
            name="Software",
            description="Software development and services",
            segment_type="industry",
            parent_segment=technology
        )
        
        hardware = MarketSegment(
            id="hardware",
            name="Hardware",
            description="Computer and electronic hardware",
            segment_type="industry",
            parent_segment=technology
        )
        
        semiconductors = MarketSegment(
            id="semiconductors",
            name="Semiconductors",
            description="Semiconductor and chip manufacturers",
            segment_type="industry",
            parent_segment=technology
        )
        
        # Sub-sub-industries
        cloud_software = MarketSegment(
            id="cloud_software",
            name="Cloud Software",
            description="Cloud-based software services (SaaS)",
            segment_type="sub_industry",
            parent_segment=software
        )
        
        return {
            "technology": technology,
            "software": software,
            "hardware": hardware,
            "semiconductors": semiconductors,
            "cloud_software": cloud_software
        }


class AssetFactory:
    """Factory for creating Asset entities with real-world examples"""
    
    def __init__(self):
        self.us_market = MarketFactory.create_us_stock_market()
        self.nyse = MarketFactory.create_nyse_market()
        self.nasdaq = MarketFactory.create_nasdaq_market()
        self.segments = self._create_common_segments()
    
    def _create_common_segments(self) -> Dict[str, MarketSegment]:
        """Create commonly used market segments"""
        return {
            "technology": MarketSegmentFactory.create_technology_segment(),
            "healthcare": MarketSegmentFactory.create_healthcare_segment(),
            "financial": MarketSegmentFactory.create_financial_segment(),
            "sp500": MarketSegmentFactory.create_sp500_segment(),
            "nasdaq100": MarketSegmentFactory.create_nasdaq100_segment(),
            "large_cap": MarketSegmentFactory.create_large_cap_segment()
        }
    
    def create_apple(self) -> Asset:
        """Create Apple Inc. (AAPL) asset"""
        return Asset(
            symbol="AAPL",
            name="Apple Inc.",
            asset_type=AssetType.COMMON_STOCK,
            market=self.nasdaq,
            currency="USD",
            segments={
                self.segments["technology"], 
                self.segments["sp500"], 
                self.segments["nasdaq100"],
                self.segments["large_cap"]
            },
            shares_outstanding=15500000000,
            market_cap=Decimal("3000000000000"),  # ~$3T
            is_active=True
        )
    
    def create_microsoft(self) -> Asset:
        """Create Microsoft Corporation (MSFT) asset"""
        return Asset(
            symbol="MSFT",
            name="Microsoft Corporation",
            asset_type=AssetType.COMMON_STOCK,
            market=self.nasdaq,
            currency="USD",
            segments={
                self.segments["technology"], 
                self.segments["sp500"], 
                self.segments["nasdaq100"],
                self.segments["large_cap"]
            },
            shares_outstanding=7400000000,
            market_cap=Decimal("2800000000000"),  # ~$2.8T
            is_active=True
        )
    
    def create_tesla(self) -> Asset:
        """Create Tesla Inc. (TSLA) asset"""
        return Asset(
            symbol="TSLA",
            name="Tesla, Inc.",
            asset_type=AssetType.COMMON_STOCK,
            market=self.nasdaq,
            currency="USD",
            segments={
                self.segments["technology"], 
                self.segments["sp500"],
                self.segments["large_cap"]
            },
            shares_outstanding=3170000000,
            market_cap=Decimal("800000000000"),  # ~$800B
            is_active=True
        )
    
    def create_spy_etf(self) -> Asset:
        """Create SPDR S&P 500 ETF Trust (SPY)"""
        return Asset(
            symbol="SPY",
            name="SPDR S&P 500 ETF Trust",
            asset_type=AssetType.ETF,
            market=self.nyse,
            currency="USD",
            segments={self.segments["sp500"]},
            shares_outstanding=920000000,
            is_active=True
        )
    
    def create_voo_etf(self) -> Asset:
        """Create Vanguard S&P 500 ETF (VOO)"""
        return Asset(
            symbol="VOO",
            name="Vanguard S&P 500 ETF",
            asset_type=AssetType.ETF,
            market=self.nyse,
            currency="USD",
            segments={self.segments["sp500"]},
            shares_outstanding=340000000,
            is_active=True
        )
    
    def create_asset_universe(self) -> Dict[str, Asset]:
        """Create a universe of common assets for testing/development"""
        return {
            "AAPL": self.create_apple(),
            "MSFT": self.create_microsoft(),
            "TSLA": self.create_tesla(),
            "SPY": self.create_spy_etf(),
            "VOO": self.create_voo_etf()
        }


# Convenience functions for easy access
def get_us_stock_market() -> Market:
    """Get standard US stock market configuration"""
    return MarketFactory.create_us_stock_market()


def get_common_assets() -> Dict[str, Asset]:
    """Get common assets for development and testing"""
    factory = AssetFactory()
    return factory.create_asset_universe()


def get_tech_segments() -> Dict[str, MarketSegment]:
    """Get hierarchical technology market segments"""
    return MarketSegmentFactory.create_hierarchical_tech_segments()


# Example usage and testing
if __name__ == "__main__":
    # Create some assets
    factory = AssetFactory()
    
    apple = factory.create_apple()
    print(f"Created: {apple.name} ({apple.symbol})")
    print(f"Market: {apple.market.name}")
    print(f"Segments: {[s.name for s in apple.segments]}")
    
    # Create asset universe
    universe = factory.create_asset_universe()
    print(f"\nAsset Universe: {list(universe.keys())}")
    
    # Create hierarchical segments
    tech_segments = get_tech_segments()
    cloud_software = tech_segments["cloud_software"]
    print(f"\nCloud Software Hierarchy: {cloud_software.full_hierarchy}")