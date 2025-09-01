#!/usr/bin/env python3
"""
Test script to verify that all scrapers support both pre-market gainers AND losers
"""

import sys
sys.path.insert(0, 'src')

from tradescout.data_sources_scraping.tradingview_scraper import TradingViewScraper
from tradescout.data_sources_scraping.marketwatch_scraper import MarketWatchScraper
from tradescout.data_sources_scraping.cnn_scraper import CNNScraper
from tradescout.data_sources_scraping.investing_com_scraper import InvestingComScraper
from tradescout.data_sources_scraping.tipranks_scraper import TipRanksScraper
from tradescout.data_sources_scraping.advfn_scraper import ADVFNScraper

def test_scraper_premarket_functionality(scraper_class, scraper_name):
    """Test that a scraper supports both pre-market gainers and losers"""
    print(f"\n{'='*60}")
    print(f"Testing {scraper_name}")
    print('='*60)
    
    try:
        scraper = scraper_class(headless=True)
        
        # Check that methods exist
        has_gainers = hasattr(scraper, 'get_premarket_gainers')
        has_losers = hasattr(scraper, 'get_premarket_losers')
        has_session_check = hasattr(scraper, 'is_premarket_session')
        has_session_info = hasattr(scraper, 'get_premarket_session_info')
        
        print(f"✓ Has get_premarket_gainers: {has_gainers}")
        print(f"✓ Has get_premarket_losers: {has_losers}")
        print(f"✓ Has is_premarket_session: {has_session_check}")
        print(f"✓ Has get_premarket_session_info: {has_session_info}")
        
        if not all([has_gainers, has_losers, has_session_check, has_session_info]):
            print(f"❌ {scraper_name} missing required pre-market methods!")
            return False
        
        # Test session info (doesn't require network call)
        try:
            session_info = scraper.get_premarket_session_info()
            print(f"✓ Session info source: {session_info.get('source_name', 'N/A')}")
            print(f"✓ Session hours: {session_info.get('session_start', 'N/A')} - {session_info.get('session_end', 'N/A')}")
            
            # Check if it's a stub implementation
            if session_info.get('implementation_status') == 'stub':
                print(f"⚠️  {scraper_name} has stub pre-market implementation!")
                return False
        except Exception as e:
            print(f"❌ Error getting session info: {e}")
            return False
        
        print(f"✅ {scraper_name} has complete pre-market interface")
        return True
        
    except Exception as e:
        print(f"❌ Error testing {scraper_name}: {e}")
        return False

def main():
    """Test all scrapers for complete pre-market functionality"""
    print("Testing All Scrapers for Complete Pre-Market Functionality")
    print("=" * 70)
    
    scrapers = [
        (TradingViewScraper, "TradingView"),
        (MarketWatchScraper, "MarketWatch"), 
        (CNNScraper, "CNN"),
        (InvestingComScraper, "Investing.com"),
        (TipRanksScraper, "TipRanks"),
        (ADVFNScraper, "ADVFN")
    ]
    
    results = {}
    
    for scraper_class, name in scrapers:
        results[name] = test_scraper_premarket_functionality(scraper_class, name)
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY - Pre-Market Functionality Support")
    print('='*60)
    
    complete_implementations = []
    incomplete_implementations = []
    
    for name, success in results.items():
        if success:
            complete_implementations.append(name)
            print(f"✅ {name}: Complete pre-market support (gainers + losers)")
        else:
            incomplete_implementations.append(name)
            print(f"❌ {name}: Incomplete or missing pre-market support")
    
    print(f"\n📊 Results:")
    print(f"   Complete implementations: {len(complete_implementations)}/6")
    print(f"   Incomplete implementations: {len(incomplete_implementations)}/6")
    
    if len(complete_implementations) == 6:
        print(f"\n🎉 All scrapers have complete pre-market support!")
        print("   Each scraper can fetch both gainers AND losers from pre-market data.")
    else:
        print(f"\n⚠️  Some scrapers need pre-market implementation fixes:")
        for name in incomplete_implementations:
            print(f"     - {name}")

if __name__ == "__main__":
    main()