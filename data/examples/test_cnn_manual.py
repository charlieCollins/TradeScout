#!/usr/bin/env python3
"""
Manual CNN scraper test - runs non-headless to see popup
"""

import sys
import os
sys.path.append('/home/ccollins/projects/TradeScout/src')

from tradescout.web_scraping.cnn_after_hours_scraper import CNNAfterHoursScraper
import logging
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_cnn_manual():
    """Test CNN scraper non-headless to see popup"""
    print("Testing CNN Manual Scraper - Non-Headless")
    print("=" * 50)
    
    # Create scraper instance with headless=False to see the popup
    scraper = CNNAfterHoursScraper(delay_seconds=1.0, headless=False)
    
    print("Opening browser to see popup...")
    scraper._setup_driver()
    scraper.driver.get("https://www.cnn.com/markets/after-hours")
    
    print("Waiting 20 seconds - check browser window for popup...")
    time.sleep(20)
    
    # Check what's on page
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(scraper.driver.page_source, 'html.parser')
    
    # Look for any elements containing "accept", "privacy", "terms"
    accept_elements = soup.find_all(string=lambda text: text and "accept" in text.lower())
    privacy_elements = soup.find_all(string=lambda text: text and "privacy" in text.lower()) 
    terms_elements = soup.find_all(string=lambda text: text and "terms" in text.lower())
    
    print(f"\nFound {len(accept_elements)} elements with 'accept' text:")
    for elem in accept_elements[:5]:  # First 5
        print(f"  - {elem.strip()}")
    
    print(f"\nFound {len(privacy_elements)} elements with 'privacy' text:")
    for elem in privacy_elements[:5]:  # First 5
        print(f"  - {elem.strip()}")
        
    print(f"\nFound {len(terms_elements)} elements with 'terms' text:")
    for elem in terms_elements[:5]:  # First 5
        print(f"  - {elem.strip()}")
    
    print("\nKeeping browser open for 10 more seconds...")
    time.sleep(10)
    
    scraper._cleanup_driver()
    print("\n✅ Manual CNN test completed!")

if __name__ == "__main__":
    test_cnn_manual()