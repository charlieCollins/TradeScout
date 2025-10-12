#!/usr/bin/env python3
"""
E*TRADE OAuth 1.0a Flow - Simple Python version
Uses requests-oauthlib which handles all the signature complexity
"""

import os
import sys

# FAIL FAST: Check for required library
try:
    from requests_oauthlib import OAuth1Session
except ImportError:
    print("❌ ERROR: requests-oauthlib is not installed")
    print("\nInstall it with:")
    print("  ./venv/bin/pip install requests-oauthlib")
    sys.exit(1)

# Load from environment
CONSUMER_KEY = os.getenv('ETRADE_CONSUMER_KEY')
CONSUMER_SECRET = os.getenv('ETRADE_CONSUMER_SECRET')

if not CONSUMER_KEY or not CONSUMER_SECRET:
    # Try loading from .env
    try:
        with open('../../.env') as f:
            for line in f:
                if line.startswith('ETRADE_CONSUMER_KEY='):
                    CONSUMER_KEY = line.split('=', 1)[1].strip()
                elif line.startswith('ETRADE_CONSUMER_SECRET='):
                    CONSUMER_SECRET = line.split('=', 1)[1].strip()
    except:
        pass

if not CONSUMER_KEY or not CONSUMER_SECRET:
    print("ERROR: E*TRADE credentials not found")
    print("Set ETRADE_CONSUMER_KEY and ETRADE_CONSUMER_SECRET")
    sys.exit(1)

BASE_URL = "https://api.etrade.com"

print("="*80)
print("E*TRADE OAuth Flow - Production API (Python)")
print("="*80)
print(f"\n✓ Consumer Key: {CONSUMER_KEY[:20]}...")
print(f"✓ Base URL: {BASE_URL}\n")

# Step 1: Get Request Token
print("="*80)
print("STEP 1: Getting Request Token")
print("="*80)

oauth = OAuth1Session(CONSUMER_KEY, client_secret=CONSUMER_SECRET, callback_uri='oob')

try:
    request_token_url = f"{BASE_URL}/oauth/request_token"
    print(f"Requesting: {request_token_url}\n")

    fetch_response = oauth.fetch_request_token(request_token_url)

    resource_owner_key = fetch_response.get('oauth_token')
    resource_owner_secret = fetch_response.get('oauth_token_secret')

    print(f"✓ oauth_token: {resource_owner_key}")
    print(f"✓ oauth_token_secret: {resource_owner_secret[:20]}...\n")

except Exception as e:
    print(f"❌ ERROR: {e}")
    sys.exit(1)

# Step 2: User Authorization
print("="*80)
print("STEP 2: User Authorization")
print("="*80)

# Build authorization URL - MUST use us.etrade.com (not api.etrade.com)
# From E*TRADE docs: User authorization happens on the us.etrade.com domain
authorization_url = f"https://us.etrade.com/e/t/etws/authorize?key={CONSUMER_KEY}&token={resource_owner_key}"

print(f"\nVisit this authorization URL in your browser:\n")
print(f"  {authorization_url}\n")

verifier = input("Enter verification code: ").strip()

if not verifier:
    print("❌ ERROR: Verification code required")
    sys.exit(1)

# Step 3: Get Access Token
print("\n" + "="*80)
print("STEP 3: Getting Access Token")
print("="*80)

oauth = OAuth1Session(
    CONSUMER_KEY,
    client_secret=CONSUMER_SECRET,
    resource_owner_key=resource_owner_key,
    resource_owner_secret=resource_owner_secret,
    verifier=verifier
)

try:
    access_token_url = f"{BASE_URL}/oauth/access_token"
    print(f"Requesting: {access_token_url}\n")

    oauth_tokens = oauth.fetch_access_token(access_token_url)

    access_token = oauth_tokens.get('oauth_token')
    access_token_secret = oauth_tokens.get('oauth_token_secret')

    print(f"✓ Access Token: {access_token}")
    print(f"✓ Access Token Secret: {access_token_secret[:20]}...\n")

except Exception as e:
    print(f"❌ ERROR: {e}")
    sys.exit(1)

# Save tokens
with open('../../etrade_tokens.env', 'w') as f:
    f.write(f"# E*TRADE OAuth Tokens\n")
    f.write(f"# Generated: {os.popen('date').read().strip()}\n\n")
    f.write(f'ETRADE_CONSUMER_KEY="{CONSUMER_KEY}"\n')
    f.write(f'ETRADE_CONSUMER_SECRET="{CONSUMER_SECRET}"\n')
    f.write(f'ETRADE_ACCESS_TOKEN="{access_token}"\n')
    f.write(f'ETRADE_ACCESS_TOKEN_SECRET="{access_token_secret}"\n')
    f.write(f'ETRADE_BASE_URL="{BASE_URL}"\n')

print("✓ Tokens saved to: etrade_tokens.env\n")

# Test with Quote API
print("="*80)
print("TEST: Quote API (AAPL with ALL details)")
print("="*80)

oauth = OAuth1Session(
    CONSUMER_KEY,
    client_secret=CONSUMER_SECRET,
    resource_owner_key=access_token,
    resource_owner_secret=access_token_secret
)

quote_url = f"{BASE_URL}/v1/market/quote/AAPL.json"
params = {'detailFlag': 'ALL'}

print(f"\nGET {quote_url}?detailFlag=ALL\n")

try:
    response = oauth.get(quote_url, params=params)

    if response.status_code == 200:
        import json
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"❌ ERROR: Status {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"❌ ERROR: {e}")

print("\n" + "="*80)
print("✓ OAuth Flow Complete!")
print("="*80)
