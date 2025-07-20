#!/usr/bin/env python3
"""
Demo: NVIDIA Asset Representation using TradeScout Domain Models

Shows how real-world market data maps to our clean domain model architecture.
"""

from datetime import datetime, time
from decimal import Decimal

# Import our domain models
from data_models.domain_models_core import (
    Asset, Market, MarketSegment, PriceData, MarketQuote, 
    AssetType, MarketType, MarketStatus
)
from data_models.factories import MarketFactory, MarketSegmentFactory
from data_models.domain_models_analysis import TechnicalIndicators


def create_nvidia_with_current_data():
    """Create NVIDIA asset with current market data (July 18-20, 2025)"""
    
    # 1. Create Market and Segments
    nasdaq = Market(
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
    
    # Create market segments for NVIDIA
    technology = MarketSegment(
        id="technology",
        name="Technology",
        description="Technology companies and software",
        segment_type="sector"
    )
    
    semiconductors = MarketSegment(
        id="semiconductors", 
        name="Semiconductors",
        description="Semiconductor and chip manufacturers",
        segment_type="industry",
        parent_segment=technology
    )
    
    ai_chips = MarketSegment(
        id="ai_chips",
        name="AI/GPU Chips", 
        description="Artificial Intelligence and Graphics Processing Units",
        segment_type="sub_industry",
        parent_segment=semiconductors
    )
    
    sp500 = MarketSegment(
        id="sp500",
        name="S&P 500",
        description="S&P 500 Index Component", 
        segment_type="index"
    )
    
    nasdaq100 = MarketSegment(
        id="nasdaq100",
        name="NASDAQ-100",
        description="NASDAQ-100 Index Component",
        segment_type="index"
    )
    
    large_cap = MarketSegment(
        id="large_cap",
        name="Large Cap",
        description="Large capitalization stocks (>$10B market cap)",
        segment_type="size"
    )
    
    # 2. Create NVIDIA Asset with Real Data
    nvidia = Asset(
        symbol="NVDA",
        name="NVIDIA Corporation",
        asset_type=AssetType.COMMON_STOCK,
        market=nasdaq,
        currency="USD",
        
        # Market segments - NVIDIA belongs to multiple classifications
        segments={
            technology,      # Sector
            semiconductors,  # Industry  
            ai_chips,       # Sub-industry
            sp500,          # Index membership
            nasdaq100,      # Index membership
            large_cap       # Size classification
        },
        
        # Corporate data (estimated based on current market data)
        shares_outstanding=2_440_000_000,  # ~2.44B shares
        market_cap=Decimal("4210000000000"),  # $4.21 Trillion
        
        # Trading characteristics
        is_active=True,
        min_order_size=Decimal('1'),
        tick_size=Decimal('0.01'),
        
        # Metadata
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    # 3. Create Current Price Data (July 18, 2025 close)
    current_price_data = PriceData(
        asset=nvidia,
        timestamp=datetime(2025, 7, 18, 16, 0, 0),  # Market close
        price=Decimal("172.41"),          # Close price
        volume=146_456_416,               # Daily volume
        
        # OHLC data for the day
        open_price=Decimal("173.50"),     # Estimated open
        high_price=Decimal("174.24"),     # Day high
        low_price=Decimal("171.26"),      # Day low
        
        # Market context
        session_type=MarketStatus.OPEN,
        data_source="live_market_data",
        data_quality="good"
    )
    
    # 4. Create Market Quote with Analysis
    nvidia_quote = MarketQuote(
        asset=nvidia,
        price_data=current_price_data,
        
        # Reference data for calculations
        previous_close=Decimal("173.00"),  # Previous close
        average_volume=203_628_106,        # Average daily volume
    )
    
    # 5. Create Technical Indicators (sample data)
    nvidia_technicals = TechnicalIndicators(
        asset=nvidia,
        timestamp=datetime(2025, 7, 18, 16, 0, 0),
        timeframe="1d",
        
        # Moving averages (estimated)
        sma_20=Decimal("165.50"),
        sma_50=Decimal("158.75"),
        ema_12=Decimal("170.25"),
        ema_26=Decimal("162.80"),
        
        # Momentum indicators (estimated)
        rsi=Decimal("72.5"),              # Slightly overbought
        macd=Decimal("2.45"),
        macd_signal=Decimal("1.85"),
        
        # Volume indicators
        volume_sma=Decimal("180000000"),  # 20-day volume average
        volume_ratio=Decimal("0.72"),     # Below average volume
        
        # Volatility (estimated)
        atr=Decimal("8.50")               # Average True Range
    )
    
    return nvidia, nvidia_quote, nvidia_technicals


def print_nvidia_asset_visualization():
    """Create a visual representation of NVIDIA in our domain model"""
    
    nvidia, quote, technicals = create_nvidia_with_current_data()
    
    print("🎯 TRADESCOUT ASSET MODEL DEMONSTRATION")
    print("=" * 60)
    print(f"📊 NVIDIA Corporation Analysis - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()
    
    # Asset Core Information
    print("🏢 CORE ASSET INFORMATION")
    print("-" * 30)
    print(f"Symbol: {nvidia.symbol}")
    print(f"Name: {nvidia.name}")
    print(f"Asset Type: {nvidia.asset_type.value}")
    print(f"Market: {nvidia.market.name} ({nvidia.market.id})")
    print(f"Currency: {nvidia.currency}")
    print(f"ISIN: {nvidia.isin or 'N/A'}")
    print()
    
    # Market Classification
    print("📂 MARKET CLASSIFICATION")
    print("-" * 30)
    for segment in sorted(nvidia.segments, key=lambda s: s.segment_type):
        hierarchy = " → ".join(segment.full_hierarchy) if hasattr(segment, 'full_hierarchy') else segment.name
        print(f"{segment.segment_type.title()}: {hierarchy}")
    print()
    
    # Corporate Financials
    print("💰 CORPORATE FINANCIALS")
    print("-" * 30)
    print(f"Shares Outstanding: {nvidia.shares_outstanding:,}")
    print(f"Market Cap: ${nvidia.market_cap:,.0f}")
    print(f"Market Cap (Trillions): ${float(nvidia.market_cap)/1_000_000_000_000:.2f}T")
    print()
    
    # Current Market Data
    print("📈 CURRENT MARKET DATA")
    print("-" * 30)
    print(f"Current Price: ${quote.price_data.price}")
    print(f"Previous Close: ${quote.previous_close}")
    print(f"Price Change: ${quote.price_change} ({quote.price_change_percent:+.2f}%)")
    print(f"Day Range: ${quote.price_data.low_price} - ${quote.price_data.high_price}")
    print(f"Volume: {quote.price_data.volume:,}")
    print(f"Avg Volume: {quote.average_volume:,}")
    print(f"Volume Ratio: {quote.volume_ratio:.2f}x")
    print()
    
    # Market Status Analysis
    print("🔍 MOMENTUM ANALYSIS")
    print("-" * 30)
    print(f"Gap Status: {'📈 Gap Up' if quote.is_gap_up else '📉 Gap Down' if quote.is_gap_down else '➡️ Normal'}")
    print(f"Volume Surge: {'🔥 YES' if quote.has_volume_surge else '❌ No'}")
    print(f"Session: {quote.price_data.session_type.value}")
    print(f"Near ATH: {'✅ YES' if quote.price_data.price >= Decimal('174.00') else '❌ No'}")
    print()
    
    # Technical Indicators
    print("📊 TECHNICAL INDICATORS")
    print("-" * 30)
    print(f"RSI (14): {technicals.rsi} {'🔴 Overbought' if technicals.is_overbought else '🟢 Normal' if not technicals.is_oversold else '🔵 Oversold'}")
    print(f"MACD: {technicals.macd} (Signal: {technicals.macd_signal}) {'🔥 Bullish' if technicals.is_macd_bullish else '❄️ Bearish'}")
    print(f"SMA 20: ${technicals.sma_20}")
    print(f"SMA 50: ${technicals.sma_50}")
    print(f"Price vs SMA20: {((quote.price_data.price / technicals.sma_20 - 1) * 100):+.1f}%")
    print(f"Price vs SMA50: {((quote.price_data.price / technicals.sma_50 - 1) * 100):+.1f}%")
    print()
    
    # Asset Properties & Methods
    print("🔧 ASSET MODEL FEATURES")
    print("-" * 30)
    print(f"Qualified Symbol: {nvidia.qualified_symbol}")
    print(f"Primary Segment: {nvidia.primary_segment.name if nvidia.primary_segment else 'N/A'}")
    print(f"In Tech Sector: {nvidia.is_in_segment('technology')}")
    print(f"In AI Chips: {nvidia.is_in_segment('ai_chips')}")
    print(f"In S&P 500: {nvidia.is_in_segment('sp500')}")
    print(f"Market Open: {nvidia.market.is_trading_day(datetime.now())}")
    print()
    
    # Data Quality & Sources
    print("📡 DATA METADATA")
    print("-" * 30)
    print(f"Data Source: {quote.price_data.data_source}")
    print(f"Data Quality: {quote.price_data.data_quality}")
    print(f"Last Updated: {quote.price_data.timestamp}")
    print(f"Complete OHLC: {quote.price_data.is_complete_bar}")
    print()
    
    print("✅ DOMAIN MODEL DEMONSTRATION COMPLETE")
    print("=" * 60)
    print("This shows how real NVIDIA data maps perfectly to our")
    print("clean Asset, Market, and PriceData domain model architecture!")


if __name__ == "__main__":
    print_nvidia_asset_visualization()