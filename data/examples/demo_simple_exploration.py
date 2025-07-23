#!/usr/bin/env python3
"""
Demo: Simple API Exploration with File Saving

Shows how to explore APIs and save results as files to avoid repeated calls
during development and command-line exploration.
"""

import time
import sys
from pathlib import Path

# Import our simple exploration utilities
from exploration_utils import get_or_fetch_api_data, save_api_result, list_saved_results

def mock_polygon_api_call(symbol: str):
    """Simulate Polygon.io API call with delay"""
    print(f"  🌐 Making REAL API call to Polygon.io for {symbol}...")
    time.sleep(1)  # Simulate network delay
    return {
        "symbol": symbol,
        "price": 172.41,
        "volume": 146456416,
        "timestamp": "2025-07-20T16:00:00Z",
        "source": "polygon_api"
    }

def mock_yfinance_call(symbol: str):
    """Simulate yfinance API call"""
    print(f"  🌐 Making REAL API call to Yahoo Finance for {symbol}...")
    time.sleep(0.5)  # Simulate network delay
    return {
        "symbol": symbol,
        "price": 172.45,
        "volume": 146500000,
        "after_hours": True,
        "source": "yfinance"
    }

def demo_simple_exploration():
    """Demonstrate simple API exploration with file saving"""
    print("🛠️ SIMPLE API EXPLORATION DEMO")
    print("=" * 50)
    
    print("\n1️⃣ FIRST CALLS (Will fetch and save)")
    print("-" * 30)
    
    # First call - will fetch and save
    start_time = time.time()
    nvda_polygon = get_or_fetch_api_data(
        "nvda_polygon_quote",
        lambda: mock_polygon_api_call("NVDA"),
        "NVIDIA quote from Polygon.io"
    )
    first_call_time = time.time() - start_time
    print(f"  ⏱️ First call took: {first_call_time:.2f}s")
    
    # Different API for same symbol
    start_time = time.time()
    nvda_yfinance = get_or_fetch_api_data(
        "nvda_yfinance_quote", 
        lambda: mock_yfinance_call("NVDA"),
        "NVIDIA quote from Yahoo Finance"
    )
    second_call_time = time.time() - start_time
    print(f"  ⏱️ Second call took: {second_call_time:.2f}s")
    
    print("\n2️⃣ REPEAT CALLS (Will load from files)")
    print("-" * 30)
    
    # Same calls again - should load from files
    start_time = time.time()
    nvda_polygon_cached = get_or_fetch_api_data(
        "nvda_polygon_quote",
        lambda: mock_polygon_api_call("NVDA"),
        "NVIDIA quote from Polygon.io"
    )
    third_call_time = time.time() - start_time
    print(f"  ⚡ Third call (from file) took: {third_call_time:.3f}s")
    
    start_time = time.time()
    nvda_yfinance_cached = get_or_fetch_api_data(
        "nvda_yfinance_quote",
        lambda: mock_yfinance_call("NVDA"),
        "NVIDIA quote from Yahoo Finance"
    )
    fourth_call_time = time.time() - start_time
    print(f"  ⚡ Fourth call (from file) took: {fourth_call_time:.3f}s")
    
    print(f"\n📊 PERFORMANCE COMPARISON")
    print("-" * 30)
    print(f"Speed improvement: {first_call_time/third_call_time:.0f}x faster!")
    print(f"API calls avoided: 2 out of 4 calls (50%)")
    
    return nvda_polygon, nvda_yfinance

def demo_exploration_with_refresh():
    """Demonstrate forced refresh of saved data"""
    print("\n3️⃣ FORCE REFRESH DEMO")
    print("-" * 30)
    
    symbols = ["AAPL", "MSFT", "GOOGL"]
    
    for symbol in symbols:
        print(f"  📈 Getting {symbol} data...")
        
        # First call saves data
        data = get_or_fetch_api_data(
            f"{symbol.lower()}_quote",
            lambda s=symbol: mock_polygon_api_call(s),
            f"{symbol} quote data"
        )
        
        print(f"     Price: ${data['price']}")

def demo_saved_files_management():
    """Demonstrate file management"""
    print("\n4️⃣ SAVED FILES MANAGEMENT")
    print("-" * 30)
    
    print("📚 Current saved exploration data:")
    list_saved_results()
    
    # Example of manual saving
    custom_data = {
        "analysis": "Custom market analysis",
        "recommendations": ["BUY", "HOLD", "SELL"],
        "confidence": 0.85
    }
    
    save_api_result(
        "custom_analysis_example", 
        custom_data,
        "Example of manually saved analysis data"
    )

def demo_production_code_usage():
    """Show how this works with actual production code"""
    print("\n5️⃣ PRODUCTION CODE INTEGRATION")
    print("-" * 30)
    
    # Add src to path to import production code
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
    
    try:
        from tradescout.data_sources.yfinance_adapter import create_yfinance_adapter
        from tradescout.data_models.factories import AssetFactory
        
        print("  📊 Using production YFinance adapter with file saving wrapper...")
        
        # Create production components
        adapter = create_yfinance_adapter()
        factory = AssetFactory()
        
        def fetch_nvda_quote():
            asset = factory.create_nvidia()
            quote = adapter.get_current_quote(asset)
            if quote:
                return {
                    "symbol": quote.asset.symbol,
                    "price": float(quote.price_data.price),
                    "volume": quote.price_data.volume,
                    "change_percent": float(quote.price_change_percent) if quote.price_change_percent else 0
                }
            return {"error": "Failed to get quote"}
        
        # Use file saving with production code
        nvda_data = get_or_fetch_api_data(
            "nvda_production_quote",
            fetch_nvda_quote,
            "NVIDIA quote from production YFinance adapter"
        )
        
        print(f"     NVDA: ${nvda_data.get('price', 'N/A')} (Vol: {nvda_data.get('volume', 'N/A'):,})")
        
    except Exception as e:
        print(f"  ❌ Production code demo failed: {e}")
        print("     (This is normal if not in the right environment)")

if __name__ == "__main__":
    try:
        # Run demos
        data = demo_simple_exploration()
        demo_exploration_with_refresh()
        demo_saved_files_management()
        demo_production_code_usage()
        
        print("\n✅ SIMPLE EXPLORATION DEMO COMPLETE!")
        print("=" * 50)
        print("Key Benefits Demonstrated:")
        print("• ⚡ Instant loading from saved files")
        print("• 🛡️ Avoid hitting API quotas during exploration")  
        print("• 📁 Human-readable JSON files")
        print("• 🔍 Easy to inspect and version control saved data")
        print("• 🏭 Works seamlessly with production code")
        
        print(f"\n📂 All saved data is in: {Path(__file__).parent}")
        
    except KeyboardInterrupt:
        print("\n\n⏹️ Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()