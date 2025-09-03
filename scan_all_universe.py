#!/usr/bin/env python3
"""
Scan all symbols in our screening universe for current after-hours prices
"""

import sys
import os
import json
from datetime import datetime
from decimal import Decimal

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from tradescout.data_sources_api.asset_data_provider_polygon import AssetDataProviderPolygon
from tradescout.data_models.domain_models_core import Asset, AssetType, MarketStatus, MarketType, Market
from tradescout.config.screening_universe_config import get_default_screening_universe
from datetime import time

def scan_universe():
    """Scan all symbols in our universe for current prices"""
    
    # Initialize provider
    api_key = "HcbSpRgH0pXVMMY7A6nv_prpkeR0wG19"
    provider = AssetDataProviderPolygon(api_key=api_key)
    
    # Get screening universe
    symbols = get_default_screening_universe()
    
    print(f"🔍 Scanning {len(symbols)} symbols for current after-hours prices")
    print("=" * 80)
    print(f"{'Symbol':<8} {'Current':<10} {'Prev Close':<10} {'Gap %':<8} {'Gap $':<8} {'Volume':<12}")
    print("-" * 80)
    
    results = []
    successful = 0
    failed = 0
    
    # Create test market
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
    
    for symbol in symbols:
        try:
            # Create asset
            asset = Asset(
                symbol=symbol,
                name=symbol,
                asset_type=AssetType.COMMON_STOCK,
                market=market,
                currency="USD"
            )
            
            # Get extended hours data
            extended_data = provider.get_extended_hours_data(asset, MarketStatus.AFTER_HOURS)
            
            if extended_data:
                current_price = float(extended_data.price_data.price)
                prev_close = float(extended_data.regular_session_close)
                gap_pct = float(extended_data.gap_percent)
                gap_amount = float(extended_data.gap_amount)
                volume = extended_data.price_data.volume
                
                # Display row
                print(f"{symbol:<8} ${current_price:<9.2f} ${prev_close:<9.2f} {gap_pct:<7.2f}% ${gap_amount:<7.2f} {volume:<12,}")
                
                # Store result
                results.append({
                    'symbol': symbol,
                    'current_price': current_price,
                    'previous_close': prev_close,
                    'gap_percent': gap_pct,
                    'gap_amount': gap_amount,
                    'volume': volume,
                    'timestamp': datetime.now().isoformat()
                })
                
                successful += 1
            else:
                print(f"{symbol:<8} {'NO DATA':<9} {'NO DATA':<9} {'N/A':<7} {'N/A':<7} {'N/A':<12}")
                failed += 1
                
        except Exception as e:
            print(f"{symbol:<8} ERROR: {str(e)[:50]}")
            failed += 1
            continue
    
    print("-" * 80)
    print(f"✅ Successfully processed: {successful}")
    print(f"❌ Failed to process: {failed}")
    print(f"📊 Success rate: {successful/(successful+failed)*100:.1f}%")
    
    # Sort by gap percentage
    results.sort(key=lambda x: x['gap_percent'], reverse=True)
    
    print(f"\n🏆 TOP 10 GAINERS:")
    print("-" * 50)
    for i, result in enumerate(results[:10], 1):
        print(f"{i:2d}. {result['symbol']:<6} +{result['gap_percent']:.2f}% (${result['current_price']:.2f})")
    
    print(f"\n📉 BOTTOM 10 (LOSERS):")
    print("-" * 50)
    for i, result in enumerate(results[-10:], 1):
        print(f"{i:2d}. {result['symbol']:<6} {result['gap_percent']:.2f}% (${result['current_price']:.2f})")
    
    # Save detailed results
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_symbols': len(symbols),
        'successful': successful,
        'failed': failed,
        'success_rate': successful/(successful+failed)*100 if (successful+failed) > 0 else 0,
        'results': results
    }
    
    os.makedirs("data/examples", exist_ok=True)
    with open("data/examples/universe_scan_results.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n💾 Detailed results saved to data/examples/universe_scan_results.json")
    
    return results

if __name__ == "__main__":
    scan_universe()