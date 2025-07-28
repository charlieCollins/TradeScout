"""
MarketWatch After-Hours Scraper Implementation

Implements the AfterHoursWebScraper interface for MarketWatch after-hours data.
URL: https://www.marketwatch.com/tools/screener/after-hours
"""

import logging
import time as time_module
from datetime import datetime, time
from decimal import Decimal
from typing import Dict, List, Optional

import pytz
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .interfaces import AfterHoursWebScraper

logger = logging.getLogger(__name__)


class MarketWatchAfterHoursScraper(AfterHoursWebScraper):
    """
    MarketWatch after-hours data scraper implementation using Selenium
    """

    def __init__(self, delay_seconds: float = 1.0, headless: bool = True):
        """
        Initialize MarketWatch after-hours scraper with Selenium

        Args:
            delay_seconds: Delay between requests to be respectful
            headless: Run browser in headless mode (default: True)
        """
        # Try different potential MarketWatch after-hours URLs
        self.potential_urls = [
            "https://www.marketwatch.com/tools/screener/after-hours",
            "https://www.marketwatch.com/markets/after-hours",
            "https://www.marketwatch.com/investing/stocks/after-hours",
            "https://www.marketwatch.com/tools/markets/after-hours-movers",
        ]
        self.delay_seconds = delay_seconds
        self.headless = headless
        self.driver = None
        self.working_url = None

    def _setup_driver(self):
        """Setup Chrome driver with persistent session for MarketWatch"""
        if self.driver is not None:
            return

        chrome_options = Options()

        if self.headless:
            chrome_options.add_argument("--headless")

        # Mimic a real browser
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # Set realistic user agent
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        chrome_options.add_argument("--window-size=1920,1080")

        # Use persistent user data directory for MarketWatch
        import os
        user_data_dir = "/home/ccollins/projects/TradeScout/data/chrome_session"
        os.makedirs(user_data_dir, exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
        chrome_options.add_argument("--profile-directory=MarketWatch_Scraper")

        # Standard options
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-infobars")

        chrome_options.add_experimental_option(
            "prefs",
            {
                "profile.default_content_setting_values": {
                    "notifications": 2,
                    "popups": 2,
                    "cookies": 1,
                    "images": 1,
                    "javascript": 1,
                },
            },
        )

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
        except Exception as e:
            logger.error(f"Failed to setup Chrome driver: {e}")
            raise

    def _cleanup_driver(self):
        """Clean up the selenium driver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

    def _find_working_url(self) -> str:
        """Find a working MarketWatch after-hours URL"""
        if self.working_url:
            return self.working_url

        for url in self.potential_urls:
            try:
                logger.info(f"Trying MarketWatch URL: {url}")
                self.driver.get(url)
                time_module.sleep(3)

                # Check if page loaded successfully (not 404)
                page_title = self.driver.title.lower()
                current_url = self.driver.current_url

                if ("404" not in page_title and 
                    "error" not in page_title and 
                    "marketwatch" in page_title):
                    
                    # Look for data tables or stock-related content
                    tables = self.driver.find_elements(By.TAG_NAME, "table")
                    stock_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), '%') or contains(@class, 'stock') or contains(@class, 'symbol')]")
                    
                    if tables or len(stock_elements) > 5:
                        logger.info(f"Found working MarketWatch URL: {url}")
                        self.working_url = url
                        return url

            except Exception as e:
                logger.debug(f"URL {url} failed: {e}")
                continue

        # Fallback to main MarketWatch markets page
        fallback_url = "https://www.marketwatch.com/markets"
        logger.warning(f"No dedicated after-hours page found, using fallback: {fallback_url}")
        self.working_url = fallback_url
        return fallback_url

    def get_after_hours_gainers(self, limit: int = 10) -> List[Dict[str, any]]:
        """
        Get top after-hours gaining stocks from MarketWatch

        Args:
            limit: Number of top after-hours gainers to return

        Returns:
            List of dictionaries with after-hours gainer data
        """
        try:
            self._setup_driver()

            # Find working URL
            url = self._find_working_url()
            logger.info(f"Loading MarketWatch page: {url}")
            self.driver.get(url)

            # Wait for page to load
            time_module.sleep(5)

            # Check if page loaded properly
            page_title = self.driver.title.lower()
            if "marketwatch" not in page_title:
                logger.warning("MarketWatch page may not have loaded correctly")
                return []
            else:
                logger.info("MarketWatch page loaded successfully")

            # Look for after-hours data or gainers section
            gainers = self._find_and_parse_gainers(limit)

            time_module.sleep(self.delay_seconds)
            return gainers

        except WebDriverException as e:
            logger.error(f"Selenium error fetching MarketWatch after-hours gainers: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing MarketWatch after-hours gainers: {e}")
            return []
        finally:
            self._cleanup_driver()

    def get_after_hours_losers(self, limit: int = 10) -> List[Dict[str, any]]:
        """
        Get top after-hours losing stocks from MarketWatch

        Args:
            limit: Number of top after-hours losers to return

        Returns:
            List of dictionaries with after-hours loser data
        """
        try:
            self._setup_driver()

            # Find working URL
            url = self._find_working_url()
            logger.info(f"Loading MarketWatch page: {url}")
            self.driver.get(url)

            # Wait for page to load
            time_module.sleep(5)

            # Look for after-hours data or losers section
            losers = self._find_and_parse_losers(limit)

            time_module.sleep(self.delay_seconds)
            return losers

        except WebDriverException as e:
            logger.error(f"Selenium error fetching MarketWatch after-hours losers: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing MarketWatch after-hours losers: {e}")
            return []
        finally:
            self._cleanup_driver()

    def _find_and_parse_gainers(self, limit: int) -> List[Dict[str, any]]:
        """Find and parse gainers data from MarketWatch page"""
        # Take screenshot for debugging
        try:
            self.driver.save_screenshot("/home/ccollins/projects/TradeScout/data/examples/marketwatch_debug.png")
        except:
            pass

        # Get page source and parse
        soup = BeautifulSoup(self.driver.page_source, "html.parser")

        # Look for gainers section - try different approaches
        gainers = []

        # Strategy 1: Look for dedicated after-hours table
        after_hours_tables = soup.find_all("table", {"class": lambda x: x and ("after" in x.lower() or "hours" in x.lower())})
        if after_hours_tables:
            logger.info("Found dedicated after-hours table")
            gainers = self._parse_marketwatch_table(after_hours_tables[0], "gainers", limit)

        # Strategy 2: Look for general data tables with gainers
        if not gainers:
            tables = soup.find_all("table")
            logger.info(f"Found {len(tables)} tables, searching for gainers data")
            
            for table in tables:
                parsed_data = self._parse_marketwatch_table(table, "gainers", limit)
                if parsed_data:
                    gainers = parsed_data
                    break

        # Strategy 3: Look for div-based data structures
        if not gainers:
            logger.info("No table data found, looking for div-based structures")
            gainers = self._parse_marketwatch_divs(soup, "gainers", limit)

        return gainers

    def _find_and_parse_losers(self, limit: int) -> List[Dict[str, any]]:
        """Find and parse losers data from MarketWatch page"""
        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        return self._parse_marketwatch_divs(soup, "losers", limit)

    def _parse_marketwatch_table(self, table, mover_type: str, limit: int) -> List[Dict[str, any]]:
        """Parse data from MarketWatch table structure"""
        movers = []
        
        try:
            tbody = table.find("tbody")
            if not tbody:
                return []

            rows = tbody.find_all("tr")[:limit]
            
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 6:  # MarketWatch has 6 columns: Symbol, Company, Price, Volume, CHG, CHG%
                    continue

                try:
                    # MarketWatch table structure from screenshot:
                    # Column 0: Symbol (link)
                    # Column 1: Company Name
                    # Column 2: Price
                    # Column 3: Volume
                    # Column 4: CHG (dollar change)
                    # Column 5: CHG % (percentage with visual bar)
                    
                    # Extract symbol from first cell (usually a link)
                    symbol_cell = cells[0]
                    symbol_link = symbol_cell.find("a")
                    symbol = symbol_link.get_text().strip() if symbol_link else symbol_cell.get_text().strip()
                    
                    # Extract company name
                    company_name = cells[1].get_text().strip()
                    
                    # Extract price
                    price_text = cells[2].get_text().strip().replace("$", "").replace(",", "")
                    price = float(price_text) if price_text else 0.0
                    
                    # Extract volume and parse K/M notation
                    volume_text = cells[3].get_text().strip()
                    volume = self._parse_volume(volume_text)
                    
                    # Extract dollar change
                    change_text = cells[4].get_text().strip().replace("$", "").replace(",", "")
                    change = float(change_text) if change_text and change_text != "N/A" else 0.0
                    
                    # Extract percentage change
                    percent_text = cells[5].get_text().strip()
                    change_percent = 0.0
                    if "%" in percent_text:
                        # Extract just the number part
                        percent_value = percent_text.split("%")[0].strip().replace("+", "")
                        try:
                            change_percent = float(percent_value)
                        except:
                            pass

                    # Filter based on mover type
                    if mover_type == "gainers" and change_percent <= 0:
                        continue
                    elif mover_type == "losers" and change_percent >= 0:
                        continue

                    if symbol and price > 0:
                        # Calculate regular close from current price and change
                        regular_close = price - change if change else price * (1 - change_percent/100)
                        
                        mover_data = {
                            "symbol": symbol,
                            "company_name": company_name,
                            "regular_close": round(regular_close, 2),
                            "after_hours_price": price,
                            "after_hours_change": change,
                            "after_hours_change_percent": abs(change_percent),
                            "after_hours_volume": volume,
                            "source": "marketwatch_after_hours",
                            "timestamp": datetime.now(),
                            "session": "after_hours",
                        }
                        movers.append(mover_data)

                except Exception as e:
                    logger.debug(f"Error parsing MarketWatch row: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Error parsing MarketWatch table: {e}")

        return movers
    
    def _parse_volume(self, volume_text: str) -> int:
        """Parse volume with K/M/B notation"""
        try:
            volume_text = volume_text.strip().upper()
            if not volume_text or volume_text == "N/A":
                return 0
            
            # Remove any commas
            volume_text = volume_text.replace(",", "")
            
            # Handle K, M, B notation
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

    def _parse_marketwatch_divs(self, soup: BeautifulSoup, mover_type: str, limit: int) -> List[Dict[str, any]]:
        """Parse data from MarketWatch div-based structures"""
        movers = []
        
        # Look for any elements containing stock symbols and percentages
        try:
            # Find elements with percentage signs
            percent_elements = soup.find_all(string=lambda text: text and "%" in str(text))
            
            # Try to find associated symbols near percentage elements
            for i, percent_text in enumerate(percent_elements[:limit*2]):  # Check more than limit
                try:
                    # Clean percentage text
                    clean_percent = str(percent_text).strip().replace("%", "").replace("+", "").replace("(", "").replace(")", "")
                    change_percent = float(clean_percent)
                    
                    # Only interested in significant moves for after-hours
                    if abs(change_percent) < 1.0:  # Skip small moves
                        continue
                    
                    # Look for symbol near this percentage
                    parent = percent_text.parent if hasattr(percent_text, 'parent') else None
                    if parent:
                        # Look for text that looks like a stock symbol
                        all_text = parent.get_text()
                        words = all_text.split()
                        
                        for word in words:
                            word = word.strip().upper()
                            if (len(word) >= 2 and len(word) <= 6 and 
                                word.isalpha() and word != word.lower()):
                                
                                # Found potential symbol
                                mover_data = {
                                    "symbol": word,
                                    "company_name": "",
                                    "regular_close": 0.0,  # Not available in this parsing method
                                    "after_hours_price": 0.0,  # Not available
                                    "after_hours_change": 0.0,  # Not available
                                    "after_hours_change_percent": change_percent,
                                    "after_hours_volume": 0,
                                    "source": "marketwatch_after_hours",
                                    "timestamp": datetime.now(),
                                    "session": "after_hours",
                                }
                                movers.append(mover_data)
                                break
                        
                        if len(movers) >= limit:
                            break
                            
                except (ValueError, AttributeError):
                    continue
                    
        except Exception as e:
            logger.warning(f"Error parsing MarketWatch divs: {e}")

        return movers[:limit]

    def is_after_hours_session(self) -> bool:
        """Check if we're currently in after-hours trading session (4 PM - 8 PM ET)"""
        et_tz = pytz.timezone("America/New_York")
        now_et = datetime.now(et_tz).time()

        after_hours_start = time(16, 0)  # 4:00 PM ET
        after_hours_end = time(20, 0)  # 8:00 PM ET

        return after_hours_start <= now_et <= after_hours_end

    def get_session_info(self) -> Dict[str, any]:
        """Get information about the current trading session and MarketWatch data source"""
        et_tz = pytz.timezone("America/New_York")
        now_et = datetime.now(et_tz)

        # Determine current session
        current_time = now_et.time()
        if time(4, 0) <= current_time <= time(9, 30):
            session = "premarket"
        elif time(9, 30) <= current_time <= time(16, 0):
            session = "regular"
        elif time(16, 0) <= current_time <= time(20, 0):
            session = "after_hours"
        else:
            session = "closed"

        return {
            "current_session": session,
            "session_start": "4:00 PM ET",
            "session_end": "8:00 PM ET",
            "source_name": "MarketWatch After Hours",
            "source_url": self.working_url or "https://www.marketwatch.com/markets",
            "data_delay": "real_time",
            "last_updated": now_et,
            "timezone": "America/New_York",
        }

    def is_source_accessible(self) -> bool:
        """Check if MarketWatch after-hours page is currently accessible"""
        try:
            self._setup_driver()
            url = self._find_working_url()
            
            if url:
                page_title = self.driver.title.lower()
                return "marketwatch" in page_title
            return False

        except Exception as e:
            logger.error(f"MarketWatch accessibility check failed: {e}")
            return False
        finally:
            self._cleanup_driver()