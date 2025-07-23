#!/usr/bin/env python3
"""
Test script for CNN after-hours scraper with Selenium

Tests if we can bypass the 451 error and access CNN Markets after-hours data.
"""

import sys
import os
sys.path.append('/home/ccollins/projects/TradeScout/src')

from tradescout.web_scraping.cnn_after_hours_scraper import CNNAfterHoursScraper
import logging

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_cnn_scraper():
    """Test the CNN after-hours scraper"""
    print("Testing CNN After-Hours Scraper with Selenium")
    print("=" * 50)
    
    # Create scraper instance (headless=True for production)
    scraper = CNNAfterHoursScraper(delay_seconds=2.0, headless=True)
    
    # Test accessibility first
    print("1. Testing site accessibility...")
    is_accessible = scraper.is_source_accessible()
    print(f"   Site accessible: {is_accessible}")
    
    if not is_accessible:
        print("❌ CNN site accessibility check failed, but let's try scraping anyway...")
        print("   (The page loads correctly, accessibility check might be too strict)")
    
    # Test session info
    print("\n2. Getting session info...")
    session_info = scraper.get_session_info()
    print(f"   Current session: {session_info['current_session']}")
    print(f"   Source: {session_info['source_name']}")
    
    # Test after-hours check
    print("\n3. Checking if in after-hours session...")
    is_after_hours = scraper.is_after_hours_session()
    print(f"   Currently after-hours: {is_after_hours}")
    
    # Test getting gainers (limit to 3 for testing)
    print("\n4. Testing after-hours gainers...")
    try:
        # First let's inspect the HTML structure
        scraper._setup_driver()
        scraper.driver.get("https://www.cnn.com/markets/after-hours")
        import time
        
        # CNN uses JavaScript to load data, so we need to wait longer
        print("   Waiting for JavaScript to load stock data...")
        time.sleep(5)  # Wait for dynamic content to load
        
        # Look for Gainers button/tab and click it
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            # Try to find and click gainers tab/button
            print("   Looking for Gainers tab...")
            gainers_selectors = [
                "//button[contains(text(), 'Gainer')]",
                "//a[contains(text(), 'Gainer')]", 
                "//span[contains(text(), 'Gainer')]",
                "//div[contains(text(), 'Gainer')]",
                "//*[contains(@class, 'gainer')]",
                "//*[contains(@data-tab, 'gainer')]",
                "//button[contains(., 'Gainer')]",
                "//a[contains(., 'Gainer')]"
            ]
            
            gainers_element = None
            for selector in gainers_selectors:
                try:
                    gainers_element = WebDriverWait(scraper.driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    print(f"   Found Gainers element with selector: {selector}")
                    break
                except:
                    continue
            
            if gainers_element:
                print("   Clicking Gainers tab...")
                gainers_element.click()
                time.sleep(3)  # Wait for data to load after click
            else:
                print("   No Gainers tab found - data might be already visible")
                
        except Exception as e:
            print(f"   Error looking for Gainers tab: {e}")
        
        # Now inspect the updated page
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(scraper.driver.page_source, 'html.parser')
        
        # Look for tables, lists, or divs that might contain stock data
        print("   Inspecting page structure for stock data...")
        
        # Save the full HTML for inspection if needed
        with open('/home/ccollins/projects/TradeScout/data/examples/cnn_page_source_after_click.html', 'w') as f:
            f.write(scraper.driver.page_source)
        print("   Updated page source saved to data/examples/cnn_page_source_after_click.html")
        
        # Look for common patterns
        tables = soup.find_all('table')
        print(f"   Found {len(tables)} tables")
        
        # Look for elements that might contain stock symbols and percentages
        potential_stock_elements = soup.find_all(string=lambda text: text and ('%' in str(text) or '+' in str(text) or '-' in str(text)))
        stock_like_text = [text.strip() for text in potential_stock_elements if text.strip() and len(text.strip()) < 30][:15]
        print(f"   Sample percentage/change text found: {stock_like_text}")
        
        # Look specifically for stock symbols pattern
        import re
        symbol_pattern = r'\b[A-Z]{2,5}\b'
        all_text = soup.get_text()
        potential_symbols = re.findall(symbol_pattern, all_text)
        common_symbols = [s for s in potential_symbols if s in ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX']][:10]
        print(f"   Found common stock symbols: {common_symbols}")
        
        print("   Keeping browser open for 10 seconds for manual inspection...")
        time.sleep(10)
        
        scraper._cleanup_driver()
        
        gainers = scraper.get_after_hours_gainers(limit=3)
        print(f"   Found {len(gainers)} gainers")
        
        if gainers:
            print("   Sample gainer data:")
            for i, gainer in enumerate(gainers[:2]):
                print(f"     {i+1}. {gainer}")
        else:
            print("   No gainers found - need to update CSS selectors based on HTML structure")
            
    except Exception as e:
        print(f"   Error getting gainers: {e}")
    
    # Test getting losers (limit to 3 for testing)
    print("\n5. Testing after-hours losers...")
    try:
        losers = scraper.get_after_hours_losers(limit=3)
        print(f"   Found {len(losers)} losers")
        
        if losers:
            print("   Sample loser data:")
            for i, loser in enumerate(losers[:2]):
                print(f"     {i+1}. {loser}")
        else:
            print("   No losers found (may need to inspect HTML structure)")
            
    except Exception as e:
        print(f"   Error getting losers: {e}")
    
    print("\n✅ CNN scraper test completed!")

if __name__ == "__main__":
    test_cnn_scraper()