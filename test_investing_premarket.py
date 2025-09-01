#!/usr/bin/env python3
"""
Test script for Investing.com pre-market data scraper
"""

import json
import os
from datetime import datetime

# Add the src directory to Python path for imports
import sys
sys.path.insert(0, 'src')

from tradescout.data_sources_scraping.investing_com_scraper import InvestingComScraper

def test_investing_premarket():
    """Test the Investing.com pre-market scraper implementation."""
    print("Testing Investing.com Pre-Market Scraper")
    print("=" * 50)
    
    scraper = InvestingComScraper(delay_seconds=2.0, headless=False)
    
    try:
        # Test session info
        session_info = scraper.get_premarket_session_info()
        print(f"Session Info: {json.dumps(session_info, indent=2, default=str)}")
        print()
        
        # Test pre-market gainers
        print("Fetching pre-market gainers...")
        gainers = scraper.get_premarket_gainers(limit=5)
        print(f"Found {len(gainers)} gainers:")
        for i, stock in enumerate(gainers, 1):
            print(f"  {i}. {stock['symbol']}: {stock['premarket_change_percent']:.2f}% (${stock['premarket_price']:.2f})")
        print()
        
        # Test pre-market losers
        print("Fetching pre-market losers...")
        losers = scraper.get_premarket_losers(limit=5)
        print(f"Found {len(losers)} losers:")
        for i, stock in enumerate(losers, 1):
            print(f"  {i}. {stock['symbol']}: {stock['premarket_change_percent']:.2f}% (${stock['premarket_price']:.2f})")
        print()
        
        # Save results to file for analysis
        results = {
            "timestamp": datetime.now().isoformat(),
            "source": "Investing.com Pre-Market",
            "gainers": gainers,
            "losers": losers,
            "session_info": session_info
        }
        
        # Save to examples directory
        os.makedirs("data/examples", exist_ok=True)
        filename = f"data/examples/investing_premarket_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"Results saved to: {filename}")
        
        return True
        
    except Exception as e:
        print(f"Error testing Investing.com pre-market scraper: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_investing_premarket()
    if success:
        print("\n✅ Investing.com pre-market scraper test completed successfully!")
    else:
        print("\n❌ Investing.com pre-market scraper test failed!")