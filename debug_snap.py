#!/usr/bin/env python3

import sys
import os
sys.path.append('src')

from tradescout.data_sources_api.asset_data_provider_tiingo import AssetDataProviderTiingo
from tradescout.data_models.domain_models_core import Asset, AssetType, Market, MarketType, MarketStatus
from datetime import time, datetime

print('🔍 DEBUGGING SNAP AFTER-HOURS DATA')
print('=' * 50)

api_key = os.getenv('TIINGO_API_KEY', 'fd22b372d0196fa709b41e370617c5f918bd3c36')

# Create test market
market = Market(
    id="TEST_MARKET",
    name="Test Market", 
    market_type=MarketType.STOCK,
    timezone="America/New_York",
    currency="USD",
    regular_open=time(9, 30),
    regular_close=time(16, 0),
    pre_market_start=time(4, 0),
    after_hours_end=time(20, 0)
)

# Create Tiingo provider
provider = AssetDataProviderTiingo(api_key=api_key)

# Create SNAP asset
snap_asset = Asset(
    symbol="SNAP",
    name="Snap Inc.",
    asset_type=AssetType.COMMON_STOCK,
    market=market,
    currency="USD"
)

print(f'Current Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S EST")}')
print()

# Test raw IEX data first
print('🔍 Raw IEX Data for SNAP:')
raw_data = provider._fetch_iex_realtime_data("SNAP")
if raw_data:
    print(f'   tngoLast: {raw_data.get("tngoLast")}')
    print(f'   prevClose: {raw_data.get("prevClose")}')
    print(f'   mid: {raw_data.get("mid")}') 
    print(f'   bidPrice: {raw_data.get("bidPrice")}')
    print(f'   askPrice: {raw_data.get("askPrice")}')
    print(f'   volume: {raw_data.get("volume")}')
    print(f'   timestamp: {raw_data.get("timestamp")}')
    
    current = raw_data.get('tngoLast') or raw_data.get('mid') or raw_data.get('bidPrice')
    prev_close = raw_data.get('prevClose')
    if current and prev_close:
        gap = ((current - prev_close) / prev_close) * 100
        print(f'   Manual Gap Calc: {gap:.2f}%')
else:
    print('   No raw data available')

print()

# Test extended hours data
print('🔍 Extended Hours Data for SNAP:')
extended_data = provider.get_extended_hours_data(snap_asset, MarketStatus.AFTER_HOURS)
if extended_data:
    print(f'   Current Price: ${extended_data.price_data.price}')
    print(f'   Previous Close: ${extended_data.regular_session_close}')
    print(f'   Gap Amount: ${extended_data.gap_amount}')
    print(f'   Gap Percent: {extended_data.gap_percent:.2f}%')
    print(f'   Volume: {extended_data.price_data.volume:,}')
    print(f'   Timestamp: {extended_data.price_data.timestamp}')
    
    if abs(extended_data.gap_percent) >= 2.0:
        direction = "GAINER" if extended_data.gap_percent > 0 else "LOSER"
        print(f'   >>> QUALIFIED AS {direction} (>2% gap)')
    else:
        print(f'   >>> Not a significant gap (<2%)')
else:
    print('   No extended hours data available')

print('=' * 50)