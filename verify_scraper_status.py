#!/usr/bin/env python3
"""
Verify the actual implementation status of all scrapers
"""

import sys
sys.path.insert(0, 'src')

def check_scraper_implementation(scraper_file):
    """Check if a scraper has real implementation or just stubs"""
    with open(scraper_file, 'r') as f:
        content = f.read()
    
    # Look for implementation indicators
    stub_indicators = [
        'not yet implemented',
        'not yet supported',
        'logger.warning',
        'return []',
        'implementation_status": "stub'
    ]
    
    real_implementation_indicators = [
        '_fetch_premarket_data',
        '_parse_premarket',
        'premarket_url',
        'selenium',
        'BeautifulSoup'
    ]
    
    # Check pre-market methods specifically
    premarket_gainers_start = content.find('def get_premarket_gainers')
    premarket_losers_start = content.find('def get_premarket_losers')
    
    if premarket_gainers_start == -1 or premarket_losers_start == -1:
        return "Missing Methods"
    
    # Get the method content (next 10 lines after method definition)
    gainers_section = content[premarket_gainers_start:premarket_gainers_start+500]
    losers_section = content[premarket_losers_start:premarket_losers_start+500]
    
    # Check for stub patterns
    gainers_is_stub = any(indicator in gainers_section for indicator in stub_indicators)
    losers_is_stub = any(indicator in losers_section for indicator in stub_indicators)
    
    # Check for real implementation patterns
    has_real_implementation = any(indicator in content for indicator in real_implementation_indicators)
    
    if gainers_is_stub or losers_is_stub:
        return "Stub Implementation"
    elif has_real_implementation:
        return "Full Implementation"
    else:
        return "Unknown Status"

def main():
    scrapers = [
        'src/tradescout/data_sources_scraping/tradingview_scraper.py',
        'src/tradescout/data_sources_scraping/marketwatch_scraper.py', 
        'src/tradescout/data_sources_scraping/cnn_scraper.py',
        'src/tradescout/data_sources_scraping/investing_com_scraper.py',
        'src/tradescout/data_sources_scraping/tipranks_scraper.py',
        'src/tradescout/data_sources_scraping/advfn_scraper.py'
    ]
    
    print("Scraper Pre-Market Implementation Status")
    print("=" * 50)
    
    full_implementations = 0
    stub_implementations = 0
    
    for scraper_file in scrapers:
        scraper_name = scraper_file.split('/')[-1].replace('_scraper.py', '').upper()
        status = check_scraper_implementation(scraper_file)
        
        if status == "Full Implementation":
            print(f"✅ {scraper_name:<15}: {status}")
            full_implementations += 1
        elif status == "Stub Implementation":
            print(f"⚠️  {scraper_name:<15}: {status}")
            stub_implementations += 1
        else:
            print(f"❓ {scraper_name:<15}: {status}")
    
    print(f"\nSummary:")
    print(f"  Full implementations: {full_implementations}")
    print(f"  Stub implementations: {stub_implementations}")
    print(f"  Total scrapers: {len(scrapers)}")
    
    if stub_implementations > 0:
        print(f"\n⚠️  {stub_implementations} scrapers still need pre-market implementation!")

if __name__ == "__main__":
    main()