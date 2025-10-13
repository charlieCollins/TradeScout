#!/usr/bin/env python3
"""
Test E*TRADE Quote API - Explore All, ExtendedHourQuoteDetail, IntraDayQuoteDetail
"""

import json
import sys
import os

# Check for library
try:
    from requests_oauthlib import OAuth1Session
except ImportError:
    print("❌ ERROR: requests-oauthlib not installed")
    sys.exit(1)

# Load tokens from etrade_tokens.env
if not os.path.exists('../etrade_tokens.env'):
    print("❌ ERROR: etrade_tokens.env not found")
    print("Run ./venv/bin/python etrade_oauth.py first")
    sys.exit(1)

# Parse tokens file
tokens = {}
with open('../etrade_tokens.env') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            key, value = line.strip().split('=', 1)
            tokens[key] = value.strip('"')

CONSUMER_KEY = tokens.get('ETRADE_CONSUMER_KEY')
CONSUMER_SECRET = tokens.get('ETRADE_CONSUMER_SECRET')
ACCESS_TOKEN = tokens.get('ETRADE_ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = tokens.get('ETRADE_ACCESS_TOKEN_SECRET')
BASE_URL = tokens.get('ETRADE_BASE_URL', 'https://api.etrade.com')

# Create OAuth session
oauth = OAuth1Session(
    CONSUMER_KEY,
    client_secret=CONSUMER_SECRET,
    resource_owner_key=ACCESS_TOKEN,
    resource_owner_secret=ACCESS_TOKEN_SECRET
)

# Test symbols
symbols = ['AAPL', 'NVDA', 'TSLA']

print("="*80)
print("E*TRADE Quote Details Test")
print("="*80)
print("\nTesting symbols:", ', '.join(symbols))
print()

for symbol in symbols:
    print("="*80)
    print(f"Symbol: {symbol}")
    print("="*80)

    # Get quote with ALL details
    url = f"{BASE_URL}/v1/market/quote/{symbol}.json"
    params = {'detailFlag': 'ALL'}

    try:
        response = oauth.get(url, params=params)

        if response.status_code != 200:
            print(f"❌ ERROR: {response.status_code}")
            print(response.text)
            continue

        data = response.json()
        quote_data = data['QuoteResponse']['QuoteData'][0]

        # Show what sections exist
        print("\n📦 Available sections:")
        for key in quote_data.keys():
            print(f"  - {key}")

        # Extract the three sections we care about
        all_data = quote_data.get('All', {})
        extended_hours = all_data.get('ExtendedHourQuoteDetail', {})
        intraday = quote_data.get('Intraday', {})  # Might be here or in All

        # Show All section (core data)
        print("\n" + "-"*80)
        print("ALL QUOTE DETAILS:")
        print("-"*80)
        print(f"Company: {all_data.get('companyName')}")
        print(f"Last Trade: ${all_data.get('lastTrade')}")
        print(f"Bid: ${all_data.get('bid')} x {all_data.get('bidSize')}")
        print(f"Ask: ${all_data.get('ask')} x {all_data.get('askSize')}")
        print(f"Change: ${all_data.get('changeClose')} ({all_data.get('changeClosePercentage')}%)")
        print(f"")
        print(f"Open: ${all_data.get('open')}")
        print(f"High: ${all_data.get('high')}")
        print(f"Low: ${all_data.get('low')}")
        print(f"Previous Close: ${all_data.get('previousClose')}")
        print(f"")
        print(f"Volume: {all_data.get('totalVolume'):,}")
        print(f"Avg Volume: {all_data.get('averageVolume'):,}")
        print(f"Previous Day Volume: {all_data.get('previousDayVolume'):,}")
        print(f"")
        print(f"Market Cap: ${all_data.get('marketCap'):,.0f}")
        print(f"52-Week High: ${all_data.get('high52')}")
        print(f"52-Week Low: ${all_data.get('low52')}")
        print(f"PE Ratio: {all_data.get('pe')}")
        print(f"Beta: {all_data.get('beta')}")

        # Show ExtendedHourQuoteDetail section
        if extended_hours:
            print("\n" + "-"*80)
            print("EXTENDED HOUR QUOTE DETAIL:")
            print("-"*80)
            print(f"Last Price: ${extended_hours.get('lastPrice')}")
            print(f"Change: ${extended_hours.get('change')} ({extended_hours.get('percentChange')}%)")
            print(f"Bid: ${extended_hours.get('bid')} x {extended_hours.get('bidSize')}")
            print(f"Ask: ${extended_hours.get('ask')} x {extended_hours.get('askSize')}")
            print(f"Volume: {extended_hours.get('volume'):,}")
            print(f"Time of Last Trade: {extended_hours.get('timeOfLastTrade')}")
            print(f"Quote Status: {extended_hours.get('quoteStatus')}")
            print(f"Time Zone: {extended_hours.get('timeZone')}")
        else:
            print("\n⚠️  ExtendedHourQuoteDetail: Not available")

        # Show IntraDayQuoteDetail section
        if intraday:
            print("\n" + "-"*80)
            print("INTRADAY QUOTE DETAIL:")
            print("-"*80)
            print(json.dumps(intraday, indent=2))
        else:
            print("\n⚠️  IntraDayQuoteDetail: Not available")

        # Show raw JSON for the three sections
        print("\n" + "-"*80)
        print("RAW JSON - All:")
        print("-"*80)
        print(json.dumps(all_data, indent=2)[:500] + "...")

        if extended_hours:
            print("\n" + "-"*80)
            print("RAW JSON - ExtendedHourQuoteDetail:")
            print("-"*80)
            print(json.dumps(extended_hours, indent=2))

        print("\n")
        input("Press Enter to continue to next symbol...")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "="*80)
print("✓ Testing Complete!")
print("="*80)
