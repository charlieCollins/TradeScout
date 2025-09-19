#!/usr/bin/env python3
"""Test what data we actually get with Polygon Starter plan"""

import os
import requests
from datetime import datetime, timedelta
import json

api_key = os.environ.get("POLYGON_API_KEY")
if not api_key:
    print("Error: POLYGON_API_KEY not set")
    exit(1)

symbol = "AAPL"
today = datetime.now().strftime("%Y-%m-%d")

print(f"Testing Polygon APIs for {symbol} on {today}")
print(f"Expected: Regular close ~$237.88, After-hours ~$238.07")
print("=" * 60)

# Test 1: Snapshot API
print("\n1. SNAPSHOT API TEST:")
print("-" * 40)
snapshot_url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}"
params = {"apiKey": api_key}

response = requests.get(snapshot_url, params=params)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    if "ticker" in data:
        ticker = data["ticker"]
        print(f"\nSnapshot data for {symbol}:")

        # Day data (regular session)
        if "day" in ticker:
            day = ticker["day"]
            print(f"  Day Close: ${day.get('c', 'N/A')}")
            print(f"  Day Open: ${day.get('o', 'N/A')}")
            print(f"  Day Volume: {day.get('v', 'N/A'):,}")

        # Previous day
        if "prevDay" in ticker:
            prev = ticker["prevDay"]
            print(f"  Prev Close: ${prev.get('c', 'N/A')}")

        # Last quote/trade
        if "lastQuote" in ticker:
            quote = ticker["lastQuote"]
            print(f"  Last Quote - Bid: ${quote.get('p', 'N/A')}, Ask: ${quote.get('P', 'N/A')}")

        if "lastTrade" in ticker:
            trade = ticker["lastTrade"]
            print(f"  Last Trade: ${trade.get('p', 'N/A')}")

        # Minute bar
        if "min" in ticker:
            min_data = ticker["min"]
            min_time = datetime.fromtimestamp(min_data.get('t', 0) / 1000)
            print(f"  Last Minute: ${min_data.get('c', 'N/A')} at {min_time.strftime('%H:%M:%S')}")

        print(f"\n  Full ticker keys: {list(ticker.keys())}")
else:
    print(f"Error: {response.text}")

# Test 2: Custom Bars for after-hours (4:00 PM - 8:00 PM)
print("\n2. CUSTOM BARS API TEST (Full day including after-hours):")
print("-" * 40)

# Get all bars for today
bars_url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/minute/{today}/{today}"
params = {
    "apiKey": api_key,
    "adjusted": "true",
    "sort": "asc"  # Chronological order
}

response = requests.get(bars_url, params=params)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    if "results" in data and data["results"]:
        results = data["results"]
        print(f"Got {len(results)} total bars for today")

        # Analyze by session
        after_hours = []
        for bar in results:
            bar_time = datetime.fromtimestamp(bar["t"] / 1000)
            hour = bar_time.hour
            minute = bar_time.minute
            decimal_hour = hour + minute / 60

            if decimal_hour >= 16:  # After 4:00 PM
                after_hours.append(bar)

        print(f"After-hours bars (after 4:00 PM): {len(after_hours)}")

        if after_hours:
            # Show last few after-hours bars
            print("\nLast 5 after-hours bars:")
            for bar in after_hours[-5:]:
                bar_time = datetime.fromtimestamp(bar["t"] / 1000)
                print(f"  {bar_time.strftime('%H:%M:%S')} - Open: ${bar['o']:.2f}, Close: ${bar['c']:.2f}, Volume: {bar['v']:,}")

            # Get the very last after-hours price
            latest_bar = after_hours[-1]
            latest_time = datetime.fromtimestamp(latest_bar["t"] / 1000)
            print(f"\nLatest after-hours price: ${latest_bar['c']:.2f} at {latest_time.strftime('%H:%M:%S')}")

        # Also find the regular session close from the same data
        print("\n3. REGULAR SESSION CLOSE (from same data):")
        print("-" * 40)

        # Find bars around 4:00 PM
        for bar in results:
            bar_time = datetime.fromtimestamp(bar["t"] / 1000)
            if bar_time.hour == 15 and bar_time.minute >= 58:  # Last minutes of regular session
                print(f"  {bar_time.strftime('%H:%M:%S')} - Close: ${bar['c']:.2f}, Volume: {bar['v']:,}")
                if bar_time.minute == 59:
                    print(f"  ^^^ Regular session close: ${bar['c']:.2f}")
            if bar_time.hour == 16 and bar_time.minute < 2:
                print(f"  {bar_time.strftime('%H:%M:%S')} - Close: ${bar['c']:.2f}, Volume: {bar['v']:,}")
                break
    else:
        print("No bars found")
        print(f"Response: {json.dumps(data, indent=2)}")
else:
    print(f"Error: {response.text}")