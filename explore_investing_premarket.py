#!/usr/bin/env python3
"""
Explore Investing.com for pre-market data availability
"""

import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import os

def explore_investing_premarket():
    chrome_options = Options()
    # Run in visible mode for debugging
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Use persistent session
    user_data_dir = "data/chrome_session"
    os.makedirs(user_data_dir, exist_ok=True)
    chrome_options.add_argument(f"--user-data-dir={os.path.abspath(user_data_dir)}")
    chrome_options.add_argument("--profile-directory=Investing_Premarket_Explorer")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    # URLs to check for pre-market data
    potential_urls = [
        "https://www.investing.com/pre-market",
        "https://www.investing.com/premarket", 
        "https://www.investing.com/markets/pre-market",
        "https://www.investing.com/markets/premarket",
        "https://www.investing.com/equities/pre-market",
        "https://www.investing.com/equities/premarket",
        "https://www.investing.com/stock-screener/Service_PreMarket",
        "https://www.investing.com/markets/after-hours",  # Check after-hours page for pre-market links/tabs
        "https://www.investing.com/equities/united-states-pre-market",
        "https://www.investing.com/stock-screener",  # Main screener page
    ]
    
    working_urls = []
    
    for url in potential_urls:
        try:
            print(f"\nTesting URL: {url}")
            driver.get(url)
            time.sleep(3)
            
            # Check if page loaded successfully
            page_title = driver.title
            print(f"  Page title: {page_title}")
            
            if "404" in page_title or "Not Found" in page_title or "Error" in page_title:
                print("  ❌ Page not found")
                continue
            
            # Look for pre-market related content
            page_source = driver.page_source.lower()
            
            # Check for pre-market indicators
            premarket_indicators = [
                "pre-market", "premarket", "pre market",
                "before hours", "extended hours",
                "morning trading", "early trading"
            ]
            
            found_indicators = [indicator for indicator in premarket_indicators if indicator in page_source]
            
            if found_indicators:
                print(f"  ✅ Found indicators: {found_indicators}")
                working_urls.append(url)
                
                # Look for data tables or stock data
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                tables = soup.find_all('table')
                
                if tables:
                    print(f"    Found {len(tables)} tables")
                    
                    # Look for stock data patterns
                    for i, table in enumerate(tables[:3]):
                        table_text = table.get_text().lower()
                        if any(word in table_text for word in ['symbol', 'ticker', 'price', 'change', '%']):
                            print(f"    Table {i+1} appears to contain stock data")
                            break
                            
                # Look for other stock data structures
                stock_elements = soup.find_all(string=lambda text: text and '%' in str(text))
                if stock_elements:
                    print(f"    Found {len(stock_elements)} elements with percentage signs")
                    
                # Look for screener-like elements
                screener_elements = soup.find_all(['div', 'section'], class_=lambda x: x and 'screener' in str(x).lower())
                if screener_elements:
                    print(f"    Found {len(screener_elements)} screener-like elements")
                
                # Save screenshot
                screenshot_path = f"data/examples/investing_premarket_{url.split('/')[-1]}_screenshot.png"
                os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
                driver.save_screenshot(screenshot_path)
                print(f"    Screenshot saved: {screenshot_path}")
                
            else:
                print("  ❌ No pre-market indicators found")
        
        except Exception as e:
            print(f"  ❌ Error loading {url}: {e}")
            continue
    
    print(f"\n{'='*60}")
    print("SUMMARY:")
    print(f"{'='*60}")
    
    if working_urls:
        print("✅ Found working pre-market URLs:")
        for url in working_urls:
            print(f"  - {url}")
    else:
        print("❌ No pre-market URLs found")
        print("\nLet's check the main screener page for pre-market filters...")
        
        # Check main screener page more thoroughly
        try:
            driver.get("https://www.investing.com/stock-screener")
            time.sleep(5)
            
            # Look for pre-market filter options
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Look for filter dropdowns or options
            filter_elements = soup.find_all(['select', 'option', 'div', 'button'], string=lambda text: text and any(term in str(text).lower() for term in ['pre-market', 'premarket', 'extended', 'hours']))
            
            if filter_elements:
                print("🔍 Found potential pre-market filter options:")
                for elem in filter_elements[:10]:
                    print(f"  - {elem.name}: {elem.get_text(strip=True)}")
            
            # Save screener page for analysis
            screenshot_path = "data/examples/investing_screener_analysis_screenshot.png"
            driver.save_screenshot(screenshot_path)
            print(f"\nScreener page screenshot saved: {screenshot_path}")
            
        except Exception as e:
            print(f"Error analyzing screener page: {e}")
    
    driver.quit()

if __name__ == "__main__":
    explore_investing_premarket()