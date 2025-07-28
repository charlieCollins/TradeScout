#!/usr/bin/env python3
"""Debug MarketWatch scraper to see why it's missing MDU"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time

# Setup Chrome
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")

import os
user_data_dir = "/home/ccollins/projects/TradeScout/data/chrome_session"
os.makedirs(user_data_dir, exist_ok=True)
chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
chrome_options.add_argument("--profile-directory=MarketWatch_Debug")

driver = webdriver.Chrome(options=chrome_options)

try:
    url = "https://www.marketwatch.com/tools/screener/after-hours"
    print(f"Loading: {url}")
    driver.get(url)
    time.sleep(5)
    
    # Parse the page
    soup = BeautifulSoup(driver.page_source, "html.parser")
    
    # Find ALL tables and debug each one
    tables = soup.find_all("table")
    print(f"\nFound {len(tables)} tables total")
    
    for table_idx, table in enumerate(tables):
        print(f"\n=== TABLE {table_idx + 1} ===")
        
        # Check for headers
        headers = table.find_all("th")
        if headers:
            header_text = " | ".join([h.get_text().strip() for h in headers[:6]])
            print(f"Headers: {header_text}")
        
        # Get tbody
        tbody = table.find("tbody")
        if tbody:
            rows = tbody.find_all("tr")
            print(f"Found {len(rows)} rows in tbody")
            
            # Show first 3 rows in detail
            for row_idx, row in enumerate(rows[:3]):
                cells = row.find_all(["td", "th"])
                print(f"\nRow {row_idx + 1}: {len(cells)} cells")
                
                for cell_idx, cell in enumerate(cells[:6]):
                    # Check if cell has a link
                    link = cell.find("a")
                    if link:
                        text = link.get_text().strip()
                        print(f"  Cell {cell_idx}: '{text}' (link)")
                    else:
                        text = cell.get_text().strip()
                        print(f"  Cell {cell_idx}: '{text}'")
        else:
            # No tbody, check for rows directly
            rows = table.find_all("tr")
            print(f"No tbody, found {len(rows)} rows directly")
            
            for row_idx, row in enumerate(rows[:2]):
                cells = row.find_all(["td", "th"])
                cell_texts = [c.get_text().strip() for c in cells[:4]]
                print(f"  Row {row_idx + 1}: {cell_texts}")
    
    # Also look for the specific "LEADERS" section
    print("\n=== Looking for LEADERS section ===")
    leaders_header = soup.find(text="LEADERS")
    if leaders_header:
        print("Found LEADERS header")
        # Find the parent and then the table
        parent = leaders_header.parent
        while parent and parent.name != "table":
            parent = parent.parent
        if parent:
            print("Found LEADERS table")
    
    input("\nPress Enter to close browser...")
    
finally:
    driver.quit()