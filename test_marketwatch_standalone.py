#!/usr/bin/env python3
"""Standalone test of MarketWatch scraper"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import json
from datetime import datetime

def parse_volume(volume_text):
    """Parse volume with K/M/B notation"""
    try:
        volume_text = volume_text.strip().upper()
        if not volume_text or volume_text == "N/A":
            return 0
        
        volume_text = volume_text.replace(",", "")
        
        if volume_text.endswith("K"):
            return int(float(volume_text[:-1]) * 1000)
        elif volume_text.endswith("M"):
            return int(float(volume_text[:-1]) * 1000000)
        elif volume_text.endswith("B"):
            return int(float(volume_text[:-1]) * 1000000000)
        else:
            return int(float(volume_text))
    except:
        return 0

def test_marketwatch():
    """Test MarketWatch after-hours data extraction"""
    print("\n=== Testing MarketWatch After-Hours Data ===")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Setup Chrome
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Use persistent session
    import os
    user_data_dir = "/home/ccollins/projects/TradeScout/data/chrome_session"
    os.makedirs(user_data_dir, exist_ok=True)
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
    chrome_options.add_argument("--profile-directory=MarketWatch_Test")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        url = "https://www.marketwatch.com/tools/screener/after-hours"
        print(f"Loading: {url}")
        driver.get(url)
        time.sleep(5)
        
        # Take screenshot
        driver.save_screenshot("/home/ccollins/projects/TradeScout/data/examples/marketwatch_current.png")
        print("Screenshot saved to data/examples/marketwatch_current.png")
        
        # Parse the page
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Find all tables
        tables = soup.find_all("table")
        print(f"\nFound {len(tables)} tables on page")
        
        all_stocks = []
        
        # Look for the main data table
        for table_idx, table in enumerate(tables):
            tbody = table.find("tbody")
            if not tbody:
                continue
                
            rows = tbody.find_all("tr")
            if not rows:
                continue
                
            print(f"\nTable {table_idx + 1}: Found {len(rows)} rows")
            
            # Parse each row
            for row_idx, row in enumerate(rows[:20]):  # Limit to first 20 rows
                cells = row.find_all(["td", "th"])
                
                if len(cells) >= 6:  # MarketWatch has 6 columns
                    try:
                        # Extract data from each cell
                        symbol_cell = cells[0]
                        symbol_link = symbol_cell.find("a")
                        symbol = symbol_link.get_text().strip() if symbol_link else symbol_cell.get_text().strip()
                        
                        company_name = cells[1].get_text().strip()
                        
                        price_text = cells[2].get_text().strip().replace("$", "").replace(",", "")
                        price = float(price_text) if price_text else 0.0
                        
                        volume_text = cells[3].get_text().strip()
                        volume = parse_volume(volume_text)
                        
                        change_text = cells[4].get_text().strip().replace("$", "").replace(",", "")
                        change = float(change_text) if change_text and change_text != "N/A" else 0.0
                        
                        percent_text = cells[5].get_text().strip()
                        change_percent = 0.0
                        if "%" in percent_text:
                            percent_value = percent_text.split("%")[0].strip().replace("+", "")
                            try:
                                change_percent = float(percent_value)
                            except:
                                pass
                        
                        if symbol and price > 0:
                            stock_data = {
                                "symbol": symbol,
                                "company_name": company_name,
                                "price": price,
                                "change": change,
                                "change_percent": change_percent,
                                "volume": volume,
                                "volume_text": volume_text
                            }
                            all_stocks.append(stock_data)
                            
                            # Print the data
                            if row_idx < 10:  # Show first 10
                                print(f"{row_idx + 1:2d}. {symbol:<6} | {company_name:<40} | "
                                      f"${price:>8.2f} | {change:>+7.2f} ({change_percent:>+6.2f}%) | "
                                      f"Vol: {volume_text:>10}")
                    
                    except Exception as e:
                        print(f"Error parsing row {row_idx}: {e}")
        
        print(f"\n\nTotal stocks found: {len(all_stocks)}")
        
        # Categorize as gainers/losers
        gainers = [s for s in all_stocks if s['change_percent'] > 0]
        losers = [s for s in all_stocks if s['change_percent'] < 0]
        
        print(f"Gainers: {len(gainers)}")
        print(f"Losers: {len(losers)}")
        
        # Save results
        results = {
            "timestamp": datetime.now().isoformat(),
            "url": url,
            "total_stocks": len(all_stocks),
            "gainers_count": len(gainers),
            "losers_count": len(losers),
            "all_stocks": all_stocks,
            "gainers": sorted(gainers, key=lambda x: x['change_percent'], reverse=True),
            "losers": sorted(losers, key=lambda x: x['change_percent'])
        }
        
        with open('/home/ccollins/projects/TradeScout/data/examples/marketwatch_current_data.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print("\nData saved to data/examples/marketwatch_current_data.json")
        
        # Show top movers
        if gainers:
            print("\n--- Top 5 Gainers ---")
            for i, stock in enumerate(sorted(gainers, key=lambda x: x['change_percent'], reverse=True)[:5], 1):
                print(f"{i}. {stock['symbol']} ({stock['company_name'][:30]}) +{stock['change_percent']:.2f}%")
        
        if losers:
            print("\n--- Top 5 Losers ---")
            for i, stock in enumerate(sorted(losers, key=lambda x: x['change_percent'])[:5], 1):
                print(f"{i}. {stock['symbol']} ({stock['company_name'][:30]}) {stock['change_percent']:.2f}%")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        driver.quit()

if __name__ == "__main__":
    test_marketwatch()