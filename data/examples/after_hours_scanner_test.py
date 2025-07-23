#!/usr/bin/env python3
"""
Test script to explore after-hours data collection capabilities

This script tests our ability to get after-hours gainers/losers data
from various sources for gap trading analysis.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import json
import os

def get_sp500_symbols(limit=50):
    """Get a sample of S&P 500 symbols for testing"""
    # Common large-cap symbols for testing
    symbols = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'BRK-B',
        'UNH', 'JNJ', 'V', 'WMT', 'JPM', 'PG', 'MA', 'HD', 'CVX', 'ABBV',
        'PFE', 'KO', 'PEP', 'AVGO', 'TMO', 'COST', 'MRK', 'DHR', 'VZ',
        'ABT', 'ACN', 'NFLX', 'ADBE', 'CRM', 'AMD', 'NKE', 'T', 'LIN',
        'TXN', 'RTX', 'QCOM', 'LOW', 'UPS', 'ORCL', 'PM', 'HON', 'IBM',
        'SBUX', 'CAT', 'INTU', 'AXP'
    ]
    return symbols[:limit]

def get_after_hours_activity(symbol):
    """Get after-hours activity for a symbol"""
    try:
        ticker = yf.Ticker(symbol)
        
        # Get pre/post market data for today
        hist = ticker.history(period="1d", interval="1m", prepost=True)
        
        if hist.empty:
            return None
            
        # Get regular market hours (9:30 AM - 4:00 PM ET)
        # Make datetime objects timezone-aware to match yfinance data
        import pytz
        et_tz = pytz.timezone('America/New_York')
        
        today = datetime.now(et_tz).date()
        market_open = et_tz.localize(datetime.combine(today, datetime.min.time().replace(hour=9, minute=30)))
        market_close = et_tz.localize(datetime.combine(today, datetime.min.time().replace(hour=16, minute=0)))
        
        # Filter for after-hours (4:00 PM - 8:00 PM ET)
        after_hours_start = market_close
        after_hours_end = market_close + timedelta(hours=4)
        
        # Get the last regular session close
        regular_hours = hist[(hist.index >= market_open) & (hist.index <= market_close)]
        if regular_hours.empty:
            return None
            
        regular_close = float(regular_hours['Close'].iloc[-1])
        
        # Get after-hours data
        after_hours = hist[(hist.index > after_hours_start) & (hist.index <= after_hours_end)]
        
        if after_hours.empty:
            return {
                'symbol': symbol,
                'has_activity': False,
                'regular_close': regular_close
            }
            
        # Calculate after-hours metrics
        ah_open = float(after_hours['Open'].iloc[0])
        ah_close = float(after_hours['Close'].iloc[-1])
        ah_high = float(after_hours['High'].max())
        ah_low = float(after_hours['Low'].min())
        ah_volume = int(after_hours['Volume'].sum())
        
        # Calculate changes from regular session close
        change_amount = ah_close - regular_close
        change_percent = (change_amount / regular_close) * 100 if regular_close > 0 else 0
        
        return {
            'symbol': symbol,
            'has_activity': True,
            'regular_close': regular_close,
            'after_hours_open': ah_open,
            'after_hours_close': ah_close,
            'after_hours_high': ah_high,
            'after_hours_low': ah_low,
            'after_hours_volume': ah_volume,
            'change_amount': change_amount,
            'change_percent': change_percent,
            'is_significant': abs(change_percent) >= 1.0  # 1%+ move
        }
        
    except Exception as e:
        print(f"Error processing {symbol}: {e}")
        return None

def scan_after_hours_movers(symbols, min_change_percent=1.0):
    """Scan for after-hours movers"""
    print(f"Scanning {len(symbols)} symbols for after-hours activity...")
    
    gainers = []
    losers = []
    all_activity = []
    
    for i, symbol in enumerate(symbols):
        print(f"Processing {symbol} ({i+1}/{len(symbols)})...")
        
        activity = get_after_hours_activity(symbol)
        if activity and activity['has_activity']:
            all_activity.append(activity)
            
            change_pct = activity['change_percent']
            if change_pct >= min_change_percent:
                gainers.append(activity)
            elif change_pct <= -min_change_percent:
                losers.append(activity)
    
    # Sort by change percentage
    gainers.sort(key=lambda x: x['change_percent'], reverse=True)
    losers.sort(key=lambda x: x['change_percent'])
    
    return {
        'scan_time': datetime.now().isoformat(),
        'symbols_scanned': len(symbols),
        'active_symbols': len(all_activity),
        'gainers': gainers[:10],  # Top 10
        'losers': losers[:10],   # Top 10
        'all_activity': all_activity
    }

if __name__ == "__main__":
    # Test the after-hours scanning
    symbols = get_sp500_symbols(30)  # Test with 30 symbols
    
    print("Testing After-Hours Market Scanning")
    print("=" * 50)
    
    results = scan_after_hours_movers(symbols)
    
    print(f"\nScan Results:")
    print(f"Symbols scanned: {results['symbols_scanned']}")
    print(f"Active symbols: {results['active_symbols']}")
    print(f"Gainers found: {len(results['gainers'])}")
    print(f"Losers found: {len(results['losers'])}")
    
    # Save results
    os.makedirs('data/examples', exist_ok=True)
    with open(f'data/examples/after_hours_scan_{datetime.now().strftime("%Y%m%d_%H%M")}.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    # Display top movers
    if results['gainers']:
        print(f"\n🟢 Top After-Hours Gainers:")
        for gainer in results['gainers'][:5]:
            print(f"  {gainer['symbol']}: +{gainer['change_percent']:.2f}% (${gainer['change_amount']:.2f})")
    
    if results['losers']:
        print(f"\n🔴 Top After-Hours Losers:")
        for loser in results['losers'][:5]:
            print(f"  {loser['symbol']}: {loser['change_percent']:.2f}% (${loser['change_amount']:.2f})")