#!/usr/bin/env python3
"""Test MarketWatch scraper to show current after-hours data"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tradescout.web_scraping.marketwatch_after_hours_scraper import MarketWatchAfterHoursScraper
import json
from datetime import datetime

def test_marketwatch_data():
    """Test MarketWatch scraper and show current data"""
    print("\n=== MarketWatch After-Hours Data ===")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Initialize scraper
    scraper = MarketWatchAfterHoursScraper(headless=False)
    
    # Check session info
    session_info = scraper.get_session_info()
    print(f"Current Session: {session_info['current_session']}")
    print(f"Source URL: {session_info['source_url']}\n")
    
    # Get after-hours gainers
    print("--- After-Hours GAINERS ---")
    gainers = scraper.get_after_hours_gainers(limit=20)
    
    if gainers:
        print(f"\nFound {len(gainers)} gainers:\n")
        for i, stock in enumerate(gainers, 1):
            print(f"{i:2d}. {stock['symbol']:<6} | {stock['company_name']:<40} | "
                  f"${stock['after_hours_price']:>8.2f} | "
                  f"{stock['after_hours_change']:>+7.2f} ({stock['after_hours_change_percent']:>6.2f}%) | "
                  f"Vol: {stock['after_hours_volume']:>10,}")
    else:
        print("No gainers found")
    
    # Get after-hours losers
    print("\n--- After-Hours LOSERS ---")
    losers = scraper.get_after_hours_losers(limit=20)
    
    if losers:
        print(f"\nFound {len(losers)} losers:\n")
        for i, stock in enumerate(losers, 1):
            print(f"{i:2d}. {stock['symbol']:<6} | {stock['company_name']:<40} | "
                  f"${stock['after_hours_price']:>8.2f} | "
                  f"{stock['after_hours_change']:>7.2f} ({stock['after_hours_change_percent']:>6.2f}%) | "
                  f"Vol: {stock['after_hours_volume']:>10,}")
    else:
        print("No losers found")
    
    # Save to JSON for detailed analysis
    results = {
        "timestamp": datetime.now().isoformat(),
        "session_info": session_info,
        "gainers": gainers,
        "losers": losers,
        "total_stocks": len(gainers) + len(losers)
    }
    
    output_file = '/home/ccollins/projects/TradeScout/data/examples/marketwatch_current_data.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n\nDetailed data saved to: {output_file}")
    
    # Show data completeness
    print("\n--- Data Completeness Analysis ---")
    all_stocks = gainers + losers
    if all_stocks:
        with_company_names = sum(1 for s in all_stocks if s.get('company_name'))
        with_volume = sum(1 for s in all_stocks if s.get('after_hours_volume', 0) > 0)
        with_price = sum(1 for s in all_stocks if s.get('after_hours_price', 0) > 0)
        
        print(f"Total stocks: {len(all_stocks)}")
        print(f"With company names: {with_company_names} ({with_company_names/len(all_stocks)*100:.1f}%)")
        print(f"With volume data: {with_volume} ({with_volume/len(all_stocks)*100:.1f}%)")
        print(f"With price data: {with_price} ({with_price/len(all_stocks)*100:.1f}%)")

if __name__ == "__main__":
    test_marketwatch_data()