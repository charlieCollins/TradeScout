#!/usr/bin/env python3
"""
Demo: API Cache System for Rate-Limited APIs

Shows how the cache protects against rate limits and speeds up development.
"""

import time
from data_models.api_cache import (
    APICache, CachePolicy, cached_api_call, 
    cache_stats, clear_cache, cleanup_cache
)

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

def demo_cache_behavior():
    """Demonstrate cache hit/miss behavior"""
    print("🗂️ API CACHE DEMONSTRATION")
    print("=" * 50)
    
    cache = APICache()
    
    print("\n1️⃣ FIRST CALLS (Cache Misses)")
    print("-" * 30)
    
    # First call - will be cache miss
    start_time = time.time()
    data1 = cached_api_call(
        provider="polygon",
        endpoint="get_quote",
        params={"symbol": "NVDA"},
        api_function=lambda: mock_polygon_api_call("NVDA"),
        policy=CachePolicy.REAL_TIME
    )
    first_call_time = time.time() - start_time
    print(f"  ⏱️ First call took: {first_call_time:.2f}s")
    
    # Different provider, same symbol
    start_time = time.time()
    data2 = cached_api_call(
        provider="yfinance", 
        endpoint="get_quote",
        params={"symbol": "NVDA"},
        api_function=lambda: mock_yfinance_call("NVDA"),
        policy=CachePolicy.INTRADAY
    )
    second_call_time = time.time() - start_time
    print(f"  ⏱️ Second call took: {second_call_time:.2f}s")
    
    print("\n2️⃣ REPEAT CALLS (Cache Hits)")
    print("-" * 30)
    
    # Same calls again - should be cache hits
    start_time = time.time()
    data3 = cached_api_call(
        provider="polygon",
        endpoint="get_quote", 
        params={"symbol": "NVDA"},
        api_function=lambda: mock_polygon_api_call("NVDA"),
        policy=CachePolicy.REAL_TIME
    )
    third_call_time = time.time() - start_time
    print(f"  ⚡ Third call (cached) took: {third_call_time:.3f}s")
    
    start_time = time.time()
    data4 = cached_api_call(
        provider="yfinance",
        endpoint="get_quote",
        params={"symbol": "NVDA"}, 
        api_function=lambda: mock_yfinance_call("NVDA"),
        policy=CachePolicy.INTRADAY
    )
    fourth_call_time = time.time() - start_time
    print(f"  ⚡ Fourth call (cached) took: {fourth_call_time:.3f}s")
    
    print(f"\n📊 PERFORMANCE IMPROVEMENT")
    print("-" * 30)
    print(f"Speed improvement: {first_call_time/third_call_time:.0f}x faster!")
    print(f"API calls saved: 2 out of 4 calls (50%)")
    
    return data1, data2, data3, data4

def demo_cache_policies():
    """Demonstrate different cache policies"""
    print("\n3️⃣ CACHE POLICIES DEMO")
    print("-" * 30)
    
    symbols = ["AAPL", "MSFT", "GOOGL"]
    
    for i, symbol in enumerate(symbols):
        policy = [CachePolicy.REAL_TIME, CachePolicy.INTRADAY, CachePolicy.DAILY][i]
        
        print(f"  📈 {symbol} with {policy.value} policy (TTL: varies)")
        
        cached_api_call(
            provider="polygon",
            endpoint="get_quote",
            params={"symbol": symbol},
            api_function=lambda s=symbol: mock_polygon_api_call(s),
            policy=policy
        )

def demo_cache_management():
    """Demonstrate cache management functions"""
    print("\n4️⃣ CACHE MANAGEMENT")
    print("-" * 30)
    
    print("📊 Current cache statistics:")
    cache_stats()
    
    print(f"\n🗑️ Clearing cache for specific provider...")
    removed = clear_cache("yfinance")
    print(f"   Removed {removed} yfinance cache entries")
    
    print(f"\n🧹 Cleaning up expired entries...")
    expired = cleanup_cache()
    print(f"   Removed {expired} expired entries")
    
    print(f"\n📊 Updated cache statistics:")
    cache_stats()

def demo_rate_limit_protection():
    """Demonstrate rate limit protection"""
    print("\n5️⃣ RATE LIMIT PROTECTION DEMO")
    print("-" * 30)
    print("Simulating multiple rapid API calls...")
    
    # Simulate rapid calls that would hit rate limits
    symbols = ["NVDA", "TSLA", "AMD", "INTC", "NVDA", "TSLA"]  # Repeated symbols
    
    total_time = 0
    api_calls_made = 0
    
    for symbol in symbols:
        start_time = time.time()
        
        # This would normally hit rate limits, but cache protects us
        was_cached = False
        def api_call_tracker():
            nonlocal api_calls_made
            api_calls_made += 1
            return mock_polygon_api_call(symbol)
        
        data = cached_api_call(
            provider="polygon",
            endpoint="rapid_calls",
            params={"symbol": symbol},
            api_function=api_call_tracker,
            policy=CachePolicy.REAL_TIME
        )
        
        call_time = time.time() - start_time
        total_time += call_time
        
        print(f"  📈 {symbol}: {call_time:.3f}s")
    
    print(f"\n🛡️ RATE LIMIT PROTECTION RESULTS:")
    print(f"   Total time: {total_time:.2f}s")
    print(f"   API calls made: {api_calls_made}/{len(symbols)}")
    print(f"   Rate limit protection: {((len(symbols) - api_calls_made) / len(symbols)):.0%}")

if __name__ == "__main__":
    try:
        # Clear cache to start fresh
        clear_cache()
        
        # Run demos
        data = demo_cache_behavior()
        demo_cache_policies()
        demo_cache_management()
        demo_rate_limit_protection()
        
        print("\n✅ API CACHE DEMO COMPLETE!")
        print("=" * 50)
        print("Key Benefits Demonstrated:")
        print("• ⚡ 10-100x faster cached responses")
        print("• 🛡️ Automatic rate limit protection")  
        print("• 🎯 Smart TTL policies by data type")
        print("• 📊 Cache statistics and management")
        print("• 💾 Automatic size management and cleanup")
        
    except KeyboardInterrupt:
        print("\n\n⏹️ Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()