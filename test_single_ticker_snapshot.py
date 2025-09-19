#!/usr/bin/env python3
"""Test single ticker snapshot API to understand field mappings"""

import os
import requests
from datetime import datetime
import json

api_key = os.environ.get("POLYGON_API_KEY")
if not api_key:
    print("Error: POLYGON_API_KEY not set")
    exit(1)

symbol = "AGMH"
print(f"Testing Single Ticker Snapshot API for {symbol}")
print("=" * 60)

# Call single ticker snapshot
url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}"
params = {"apiKey": api_key}

response = requests.get(url, params=params)
print(f"Status: {response.status_code}\n")

if response.status_code == 200:
    data = response.json()

    # Pretty print the entire response first
    print("FULL RESPONSE:")
    print("-" * 40)
    print(json.dumps(data, indent=2))
    print("\n")

    # Now extract key fields if ticker exists
    if "ticker" in data:
        ticker = data["ticker"]

        print("KEY PRICE FIELDS:")
        print("-" * 40)

        # Day data (regular session)
        if "day" in ticker:
            day = ticker["day"]
            print(f"Day (Regular Session):")
            print(f"  Open:   ${day.get('o', 'N/A')}")
            print(f"  High:   ${day.get('h', 'N/A')}")
            print(f"  Low:    ${day.get('l', 'N/A')}")
            print(f"  Close:  ${day.get('c', 'N/A')} <-- REGULAR SESSION CLOSE")
            print(f"  Volume: {day.get('v', 'N/A'):,}")
            print(f"  VWAP:   ${day.get('vw', 'N/A')}")

        # Previous day
        if "prevDay" in ticker:
            prev = ticker["prevDay"]
            print(f"\nPrevious Day:")
            print(f"  Close:  ${prev.get('c', 'N/A')} <-- YESTERDAY'S CLOSE")

        # Last minute bar (could be extended hours)
        if "min" in ticker:
            min_data = ticker["min"]
            if min_data:  # Sometimes it's null
                min_time = datetime.fromtimestamp(min_data.get('t', 0) / 1000)
                print(f"\nLast Minute Bar:")
                print(f"  Time:   {min_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  Open:   ${min_data.get('o', 'N/A')}")
                print(f"  High:   ${min_data.get('h', 'N/A')}")
                print(f"  Low:    ${min_data.get('l', 'N/A')}")
                print(f"  Close:  ${min_data.get('c', 'N/A')} <-- CURRENT PRICE (from last minute)")
                print(f"  Volume: {min_data.get('v', 'N/A'):,}")

                # Determine session based on time
                hour = min_time.hour
                minute = min_time.minute
                time_decimal = hour + minute / 60

                if 4 <= time_decimal < 9.5:
                    session = "PRE-MARKET"
                elif 9.5 <= time_decimal < 16:
                    session = "REGULAR SESSION"
                elif 16 <= time_decimal < 20:
                    session = "AFTER-HOURS"
                else:
                    session = "CLOSED"

                print(f"  Session: {session}")

        # Change data
        print(f"\nChange Data:")
        print(f"  Today's Change:        ${ticker.get('todaysChange', 'N/A')}")
        print(f"  Today's Change %:      {ticker.get('todaysChangePerc', 'N/A')}%")

        # Updated timestamp
        if "updated" in ticker:
            updated_ns = ticker["updated"]
            # Polygon uses nanoseconds, convert to seconds
            updated_time = datetime.fromtimestamp(updated_ns / 1_000_000_000)
            print(f"\nLast Updated: {updated_time.strftime('%Y-%m-%d %H:%M:%S')}")

        print("\n" + "=" * 60)
        print("SUMMARY:")
        print("-" * 40)

        # Extract the key prices
        regular_close = ticker.get('day', {}).get('c', 'N/A')
        current_price = ticker.get('min', {}).get('c', 'N/A') if ticker.get('min') else regular_close

        print(f"Regular Session Close: ${regular_close}")
        print(f"Current Price:         ${current_price}")

        if regular_close != 'N/A' and current_price != 'N/A':
            if isinstance(regular_close, (int, float)) and isinstance(current_price, (int, float)):
                gap = current_price - regular_close
                gap_pct = (gap / regular_close) * 100 if regular_close != 0 else 0
                print(f"Gap:                   ${gap:.2f} ({gap_pct:.2f}%)")

else:
    print(f"Error: {response.text}")