#!/usr/bin/env python3
"""Test Polygon custom bars API for extended hours data"""

import os
import requests
from datetime import datetime, timedelta
import json

# Get API key from environment
api_key = os.environ.get("POLYGON_API_KEY")
if not api_key:
    print("Error: POLYGON_API_KEY not set in environment")
    exit(1)

# Test parameters
symbol = "AAPL"
today = datetime.now().strftime("%Y-%m-%d")
yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

print(f"Testing Polygon custom bars API for {symbol}")
print(f"Date range: {yesterday} to {today}")
print("-" * 60)

# Test 1: Get minute bars for full day including extended hours
url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/minute/{yesterday}/{today}"
params = {
    "apiKey": api_key,
    "adjusted": "true",
    "sort": "asc",
    "limit": 50000
}

response = requests.get(url, params=params)
print(f"API Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()

    if "results" in data and data["results"]:
        results = data["results"]
        print(f"Total bars received: {len(results)}")

        # Analyze the time distribution
        pre_market = []  # 4:00 AM - 9:30 AM ET
        regular = []     # 9:30 AM - 4:00 PM ET
        after_hours = [] # 4:00 PM - 8:00 PM ET

        for bar in results:
            # Convert timestamp to datetime (milliseconds to seconds)
            bar_time = datetime.fromtimestamp(bar["t"] / 1000)
            hour = bar_time.hour
            minute = bar_time.minute

            # Convert to decimal hours for easier comparison
            decimal_hour = hour + minute / 60

            # Categorize by session (assuming Eastern Time)
            if 4 <= decimal_hour < 9.5:  # 4:00 AM - 9:30 AM
                pre_market.append(bar)
            elif 9.5 <= decimal_hour < 16:  # 9:30 AM - 4:00 PM
                regular.append(bar)
            elif 16 <= decimal_hour < 20:  # 4:00 PM - 8:00 PM
                after_hours.append(bar)

        print(f"\nSession breakdown:")
        print(f"Pre-market bars (4:00-9:30 AM): {len(pre_market)}")
        print(f"Regular session bars (9:30 AM-4:00 PM): {len(regular)}")
        print(f"After-hours bars (4:00-8:00 PM): {len(after_hours)}")

        # Show some examples from each session
        if pre_market:
            print(f"\nFirst pre-market bar:")
            bar = pre_market[0]
            bar_time = datetime.fromtimestamp(bar["t"] / 1000)
            print(f"  Time: {bar_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  Open: ${bar['o']:.2f}, Close: ${bar['c']:.2f}")
            print(f"  Volume: {bar['v']:,}")

        if after_hours:
            print(f"\nLast after-hours bar:")
            bar = after_hours[-1]
            bar_time = datetime.fromtimestamp(bar["t"] / 1000)
            print(f"  Time: {bar_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  Open: ${bar['o']:.2f}, Close: ${bar['c']:.2f}")
            print(f"  Volume: {bar['v']:,}")

        # Test 2: Get just pre-market hours for today
        print("\n" + "=" * 60)
        print(f"Testing pre-market only (4:00-9:30 AM) for {today}")

        # Build timestamps for pre-market window
        premarket_start = f"{today}T04:00:00"
        premarket_end = f"{today}T09:30:00"

        url2 = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/minute/{premarket_start}/{premarket_end}"
        response2 = requests.get(url2, params=params)

        if response2.status_code == 200:
            data2 = response2.json()
            if "results" in data2:
                print(f"Pre-market bars received: {len(data2.get('results', []))}")
                if data2["results"]:
                    first = data2["results"][0]
                    last = data2["results"][-1]
                    first_time = datetime.fromtimestamp(first["t"] / 1000)
                    last_time = datetime.fromtimestamp(last["t"] / 1000)
                    print(f"Time range: {first_time.strftime('%H:%M')} - {last_time.strftime('%H:%M')}")
                    print(f"Price movement: ${first['o']:.2f} -> ${last['c']:.2f}")

    else:
        print("No results in response")
        print(f"Response: {json.dumps(data, indent=2)}")
else:
    print(f"Error: {response.text}")