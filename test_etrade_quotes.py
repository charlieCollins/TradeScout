#!/usr/bin/env python3
"""
Test E*TRADE Quote API with different detail flags.

Tests:
- ALL (AllQuoteDetails)
- FUNDAMENTAL (basic fundamentals)
- INTRADAY (IntraDayQuoteDetail)
- OPTIONS (option chain data)
- WEEK_52 (52-week high/low)

Focus on extended hours data for gap trading.
Uses PRODUCTION API for real market data.
"""

import json
import sys
from requests_oauthlib import OAuth1Session

# E*TRADE Production Credentials (for market data only)
CONSUMER_KEY = "387a005c91520bf0cc2840362fa5aecd"
CONSUMER_SECRET = "9024140d333c1e0a2e60cd0ea479288a5757a8ee72ca7cde56a39093e0be3c63"

# E*TRADE Production URLs
BASE_URL = "https://api.etrade.com"  # Production for real market data
REQUEST_TOKEN_URL = f"{BASE_URL}/oauth/request_token"
AUTHORIZE_URL = f"{BASE_URL}/e/t/etws/authorize"
ACCESS_TOKEN_URL = f"{BASE_URL}/oauth/access_token"

def get_oauth_session():
    """Get authenticated OAuth session for E*TRADE API.

    Returns OAuth1Session with access token.
    """
    print("="*80)
    print("E*TRADE OAuth 1.0a Authentication")
    print("="*80)

    # Step 1: Get request token
    print("\n1. Getting request token...")
    oauth = OAuth1Session(CONSUMER_KEY, client_secret=CONSUMER_SECRET)

    try:
        fetch_response = oauth.fetch_request_token(REQUEST_TOKEN_URL)
    except Exception as e:
        print(f"ERROR: Failed to get request token: {e}")
        sys.exit(1)

    resource_owner_key = fetch_response.get('oauth_token')
    resource_owner_secret = fetch_response.get('oauth_token_secret')

    print(f"   Request token: {resource_owner_key[:20]}...")

    # Step 2: User authorization
    print("\n2. User authorization required:")
    authorization_url = f"{AUTHORIZE_URL}?key={CONSUMER_KEY}&token={resource_owner_key}"
    print(f"\n   Visit this URL to authorize:\n   {authorization_url}\n")

    verifier = input("   Enter verification code from E*TRADE: ").strip()

    # Step 3: Get access token
    print("\n3. Getting access token...")
    oauth = OAuth1Session(
        CONSUMER_KEY,
        client_secret=CONSUMER_SECRET,
        resource_owner_key=resource_owner_key,
        resource_owner_secret=resource_owner_secret,
        verifier=verifier
    )

    try:
        oauth_tokens = oauth.fetch_access_token(ACCESS_TOKEN_URL)
    except Exception as e:
        print(f"ERROR: Failed to get access token: {e}")
        sys.exit(1)

    access_token = oauth_tokens.get('oauth_token')
    access_token_secret = oauth_tokens.get('oauth_token_secret')

    print(f"   Access token: {access_token[:20]}...")
    print("   ✅ Authentication successful!\n")

    # Return authenticated session
    return OAuth1Session(
        CONSUMER_KEY,
        client_secret=CONSUMER_SECRET,
        resource_owner_key=access_token,
        resource_owner_secret=access_token_secret
    )

def test_quote_api(session, symbol="AAPL", detail_flag="ALL"):
    """Test quote API with specified detail flag.

    Args:
        session: Authenticated OAuth1Session
        symbol: Stock symbol to query
        detail_flag: Detail level (ALL, FUNDAMENTAL, INTRADAY, etc.)
    """
    print("="*80)
    print(f"Testing Quote API: {symbol} with detailFlag={detail_flag}")
    print("="*80)

    # Quote endpoint
    url = f"{BASE_URL}/v1/market/quote/{symbol}.json"
    params = {
        "detailFlag": detail_flag
    }

    print(f"\nGET {url}")
    print(f"Params: {params}\n")

    try:
        response = session.get(url, params=params)

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("\n" + "="*80)
            print("RESPONSE JSON:")
            print("="*80)
            print(json.dumps(data, indent=2))

            # Extract key fields for gap trading
            if "QuoteResponse" in data:
                quote_data = data["QuoteResponse"]["QuoteData"][0]
                print("\n" + "="*80)
                print("KEY FIELDS FOR GAP TRADING:")
                print("="*80)

                product = quote_data.get("Product", {})
                all_data = quote_data.get("All", {})

                print(f"Symbol: {product.get('symbol')}")
                print(f"Company: {product.get('companyName')}")
                print(f"Exchange: {product.get('exchange')}")

                if all_data:
                    print(f"\nLast Price: ${all_data.get('lastTrade')}")
                    print(f"Change: ${all_data.get('change')} ({all_data.get('changePercent')}%)")
                    print(f"Bid: ${all_data.get('bid')} x {all_data.get('bidSize')}")
                    print(f"Ask: ${all_data.get('ask')} x {all_data.get('askSize')}")
                    print(f"Volume: {all_data.get('totalVolume'):,}")

                    # Extended hours data
                    print(f"\n--- EXTENDED HOURS ---")
                    print(f"Extended Last Trade: ${all_data.get('extendedHourLastTrade')}")
                    print(f"Extended Change: ${all_data.get('extendedHourChange')} ({all_data.get('extendedHourChangePercent')}%)")
                    print(f"Extended Volume: {all_data.get('extendedHourVolume')}")

                    # Day range
                    print(f"\n--- DAILY RANGE ---")
                    print(f"Open: ${all_data.get('open')}")
                    print(f"High: ${all_data.get('high')}")
                    print(f"Low: ${all_data.get('low')}")
                    print(f"Prev Close: ${all_data.get('previousClose')}")

                    # Market cap
                    print(f"\n--- FUNDAMENTALS ---")
                    print(f"Market Cap: ${all_data.get('marketCap')}")
                    print(f"52-Week High: ${all_data.get('week52High')}")
                    print(f"52-Week Low: ${all_data.get('week52Low')}")
                    print(f"PE Ratio: {all_data.get('peRatio')}")
                    print(f"Div Yield: {all_data.get('divYield')}%")
        else:
            print(f"\nERROR: {response.status_code}")
            print(response.text)

    except Exception as e:
        print(f"\nEXCEPTION: {e}")

def main():
    """Main test function."""
    print("\n" + "="*80)
    print("E*TRADE Quote API Test Script - PRODUCTION (Real Market Data)")
    print("="*80)
    print("\nThis script will test E*TRADE Quote API with different detail flags.")
    print("Focus: Extended hours data for gap trading\n")

    # Authenticate
    session = get_oauth_session()

    # Test different symbols and detail flags
    test_cases = [
        ("AAPL", "ALL"),           # Full quote data - see all available fields
        ("NVDA", "ALL"),           # Another mega-cap with after-hours activity
        ("AAPL", "INTRADAY"),      # Intraday quote details
        ("AAPL", "FUNDAMENTAL"),   # Basic fundamentals
        ("AAPL", "WEEK_52"),       # 52-week range
    ]

    print("Test cases:")
    for i, (symbol, detail_flag) in enumerate(test_cases, 1):
        print(f"  {i}. {symbol} with detailFlag={detail_flag}")

    print("\n" + "="*80 + "\n")

    for symbol, detail_flag in test_cases:
        test_quote_api(session, symbol, detail_flag)
        print("\n" + "="*80 + "\n")
        input("Press Enter to continue to next test...")

    print("\n✅ All tests complete!")

if __name__ == "__main__":
    main()
