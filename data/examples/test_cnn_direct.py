#!/usr/bin/env python3
"""
Direct test of CNN scraper parsing logic with current data
"""

import sys
import os
sys.path.append('/home/ccollins/projects/TradeScout/src')

from tradescout.web_scraping.cnn_after_hours_scraper import CNNAfterHoursScraper
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def test_cnn_direct():
    """Test CNN scraper directly without clicking tabs"""
    print("Testing CNN Direct Scraper - Skip Tab Clicking")
    print("=" * 50)
    
    scraper = CNNAfterHoursScraper(delay_seconds=1.0, headless=False)
    
    print("1. Testing direct gainers extraction...")
    gainers = scraper.get_after_hours_gainers(limit=5)
    print(f"   Found {len(gainers)} gainers:")
    
    for i, gainer in enumerate(gainers[:3]):
        print(f"   {i+1}. {gainer['symbol']}: ${gainer['after_hours_price']:.2f} ({gainer['after_hours_change_percent']:+.2f}%)")
    
    print("\n2. Testing direct losers extraction...")
    losers = scraper.get_after_hours_losers(limit=5) 
    print(f"   Found {len(losers)} losers:")
    
    for i, loser in enumerate(losers[:3]):
        print(f"   {i+1}. {loser['symbol']}: ${loser['after_hours_price']:.2f} ({loser['after_hours_change_percent']:+.2f}%)")
    
    print("\n✅ Direct CNN test completed!")

if __name__ == "__main__":
    test_cnn_direct()