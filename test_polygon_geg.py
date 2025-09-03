#!/usr/bin/env python3
"""
Test script to check GEG after-hours price via Polygon.io API
"""

import requests
import json
from datetime import datetime
import os

# Polygon API configuration
POLYGON_API_KEY = "HcbSpRgH0pXVMMY7A6nv_prpkeR0wG19"
BASE_URL = "https://api.polygon.io"

def test_polygon_real_time_quote(symbol: str):
    """Test real-time quote endpoint"""
    url = f"{BASE_URL}/v2/last/trade/{symbol}"
    params = {"apikey": POLYGON_API_KEY}
    
    print(f"Testing real-time quote for {symbol}...")
    print(f"URL: {url}")
    
    response = requests.get(url, params=params)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("Response:")
        print(json.dumps(data, indent=2))
        return data
    else:
        print(f"Error: {response.text}")
        return None

def test_polygon_previous_close(symbol: str):
    """Test previous close endpoint"""
    url = f"{BASE_URL}/v2/aggs/ticker/{symbol}/prev"
    params = {"apikey": POLYGON_API_KEY}
    
    print(f"\nTesting previous close for {symbol}...")
    print(f"URL: {url}")
    
    response = requests.get(url, params=params)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("Response:")
        print(json.dumps(data, indent=2))
        return data
    else:
        print(f"Error: {response.text}")
        return None

def test_polygon_snapshot(symbol: str):
    """Test market snapshot endpoint"""
    url = f"{BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}"
    params = {"apikey": POLYGON_API_KEY}
    
    print(f"\nTesting market snapshot for {symbol}...")
    print(f"URL: {url}")
    
    response = requests.get(url, params=params)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("Response:")
        print(json.dumps(data, indent=2))
        return data
    else:
        print(f"Error: {response.text}")
        return None

def calculate_gap_if_possible(quote_data, prev_data):
    """Calculate gap percentage if we have both current and previous close"""
    try:
        if quote_data and prev_data:
            # Extract current price from quote
            current_price = None
            if 'results' in quote_data and quote_data['results']:
                current_price = quote_data['results'].get('p')  # price from last trade
            
            # Extract previous close
            prev_close = None
            if 'results' in prev_data and prev_data['results']:
                prev_close = prev_data['results'][0].get('c')  # close price
            
            if current_price and prev_close and prev_close > 0:
                gap_pct = ((current_price - prev_close) / prev_close) * 100
                print(f"\n📊 GAP CALCULATION:")
                print(f"Current Price: ${current_price}")
                print(f"Previous Close: ${prev_close}")
                print(f"Gap: {gap_pct:.2f}%")
                return gap_pct
                
    except Exception as e:
        print(f"Error calculating gap: {e}")
    
    print("\n❌ Could not calculate gap - insufficient data")
    return None

if __name__ == "__main__":
    symbol = "GEG"
    
    print(f"🔍 Testing Polygon.io API for {symbol}")
    print(f"Timestamp: {datetime.now()}")
    print("=" * 50)
    
    # Test different endpoints
    quote_data = test_polygon_real_time_quote(symbol)
    prev_data = test_polygon_previous_close(symbol)
    snapshot_data = test_polygon_snapshot(symbol)
    
    # Try to calculate gap
    gap_pct = calculate_gap_if_possible(quote_data, prev_data)
    
    # Save results for analysis
    results = {
        "symbol": symbol,
        "timestamp": datetime.now().isoformat(),
        "quote_data": quote_data,
        "prev_data": prev_data,
        "snapshot_data": snapshot_data,
        "gap_percentage": gap_pct
    }
    
    os.makedirs("data/examples", exist_ok=True)
    with open(f"data/examples/{symbol.lower()}_polygon_test.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to data/examples/{symbol.lower()}_polygon_test.json")