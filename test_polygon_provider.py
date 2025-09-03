#!/usr/bin/env python3
"""
Test the new Polygon data provider implementation
"""

import sys
import os
import json
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from tradescout.data_sources_api.asset_data_provider_polygon import AssetDataProviderPolygon
from tradescout.data_models.domain_models_core import Asset, AssetType, MarketStatus, MarketType, Market
from datetime import time

def test_polygon_provider():
    """Test the Polygon provider implementation"""
    
    # Initialize provider
    api_key = "HcbSpRgH0pXVMMY7A6nv_prpkeR0wG19"
    provider = AssetDataProviderPolygon(api_key=api_key)
    
    print("🔬 Testing Polygon Data Provider")
    print("=" * 50)
    
    # Create test asset
    market = Market(
        id="US_STOCKS",
        name="US Stock Market",
        market_type=MarketType.STOCK,
        timezone="America/New_York",
        currency="USD",
        regular_open=time(9, 30),
        regular_close=time(16, 0),
        pre_market_start=time(4, 0),
        after_hours_end=time(20, 0)
    )
    
    asset = Asset(
        symbol="GEG",
        name="Great Elm Group Inc",
        asset_type=AssetType.COMMON_STOCK,
        market=market,
        currency="USD"
    )
    
    # Test 1: Health Check
    print("1. Testing health check...")
    is_healthy = provider.health_check()
    print(f"   Health status: {'✅ Healthy' if is_healthy else '❌ Unhealthy'}")
    
    # Test 2: Current Quote
    print("\n2. Testing current quote...")
    quote = provider.get_current_quote(asset)
    if quote:
        print(f"   Symbol: {quote.asset.symbol}")
        print(f"   Price: ${quote.price_data.price}")
        print(f"   Volume: {quote.price_data.volume:,}")
        print(f"   Timestamp: {quote.price_data.timestamp}")
    else:
        print("   ❌ No quote data returned")
    
    # Test 3: Extended Hours Data (Main Test)
    print("\n3. Testing extended hours data...")
    extended_data = provider.get_extended_hours_data(asset, MarketStatus.AFTER_HOURS)
    if extended_data:
        print(f"   Symbol: {extended_data.asset.symbol}")
        print(f"   Current Price: ${extended_data.price_data.price}")
        print(f"   Previous Close: ${extended_data.regular_session_close}")
        print(f"   Gap Amount: ${extended_data.gap_amount}")
        print(f"   Gap Percent: {extended_data.gap_percent:.2f}%")
        print(f"   Volume: {extended_data.price_data.volume:,}")
        print(f"   Session: {extended_data.session_type}")
    else:
        print("   ❌ No extended hours data returned")
    
    # Test 4: Company Info
    print("\n4. Testing company info...")
    company_info = provider.get_company_info(asset)
    if company_info:
        print(f"   Company data available: {len(company_info)} fields")
        # Print a few key fields if available
        for key in ['name', 'description', 'market_cap', 'primary_exchange']:
            if key in company_info:
                print(f"   {key}: {company_info[key]}")
    else:
        print("   ❌ No company info returned")
    
    # Test 5: Market Movers (limited test)
    print("\n5. Testing market gainers (limited)...")
    try:
        gainers = provider.get_market_gainers(limit=3)  # Small limit for testing
        print(f"   Found {len(gainers)} gainers")
        for gainer in gainers[:2]:  # Show first 2
            print(f"   - {gainer.asset.symbol}: {gainer.price_change_percent:.2f}% (${gainer.current_price})")
    except Exception as e:
        print(f"   ❌ Error getting gainers: {e}")
    
    # Save results
    results = {
        "timestamp": datetime.now().isoformat(),
        "provider": "Polygon",
        "tests": {
            "health_check": is_healthy,
            "quote_available": quote is not None,
            "extended_hours_available": extended_data is not None,
            "company_info_available": company_info is not None
        }
    }
    
    if extended_data:
        results["gap_analysis"] = {
            "symbol": asset.symbol,
            "current_price": float(extended_data.price_data.price),
            "previous_close": float(extended_data.regular_session_close),
            "gap_percent": float(extended_data.gap_percent),
            "volume": extended_data.price_data.volume
        }
    
    # Save results
    os.makedirs("data/examples", exist_ok=True)
    with open("data/examples/polygon_provider_test.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to data/examples/polygon_provider_test.json")
    print("\n✅ Polygon provider test completed!")
    
    return results

if __name__ == "__main__":
    test_polygon_provider()