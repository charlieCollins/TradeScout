"""
ADVFN After-Hours Scraper Implementation

Implements the AfterHoursWebScraper interface for ADVFN after-hours data.
URL: https://www.advfn.com/markets/nasdaq/afterhours
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


class ADVFNAfterHoursScraper(AfterHoursWebScraper):
    """
    ADVFN after-hours data scraper implementation using Selenium
    """

    def __init__(self, delay_seconds: float = 1.0, headless: bool = True):
        """
        Initialize ADVFN after-hours scraper with Selenium

        Args:
            delay_seconds: Delay between requests to be respectful
            headless: Run browser in headless mode (default: True)
        """
        # ADVFN after-hours URLs for different exchanges
        self.urls = {
            "nasdaq": "https://www.advfn.com/markets/nasdaq/afterhours",
            "nyse": "https://www.advfn.com/markets/nyse/afterhours",
            "amex": "https://www.advfn.com/markets/amex/afterhours",
        }
        self.delay_seconds = delay_seconds
        self.headless = headless
        self.driver = None

    def _setup_driver(self):
        """Setup Chrome driver with persistent session for ADVFN"""
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

        # Use persistent user data directory for ADVFN
        import os
        user_data_dir = "/home/ccollins/projects/TradeScout/data/chrome_session"
        os.makedirs(user_data_dir, exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
        chrome_options.add_argument("--profile-directory=ADVFN_Scraper")

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

    def get_after_hours_gainers(self, limit: int = 10, exchange: str = "nasdaq") -> List[Dict[str, any]]:
        """
        Get top after-hours gaining stocks from ADVFN

        Args:
            limit: Number of top after-hours gainers to return
            exchange: Exchange to fetch data from (nasdaq, nyse, amex)

        Returns:
            List of dictionaries with after-hours gainer data
        """
        try:
            self._setup_driver()

            # Use the appropriate URL for the exchange
            url = self.urls.get(exchange.lower(), self.urls["nasdaq"])
            logger.info(f"Loading ADVFN {exchange} after-hours page: {url}")
            
            self.driver.get(url)
            time_module.sleep(5)  # Wait for page to load

            # Take screenshot for debugging
            self.driver.save_screenshot(
                f"/home/ccollins/projects/TradeScout/data/examples/advfn_{exchange}_afterhours.png"
            )

            # Parse the page
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            
            # Look for the after-hours data table
            gainers = self._parse_advfn_data(soup, "gainers", limit)
            
            logger.info(f"Found {len(gainers)} gainers on ADVFN {exchange}")
            return gainers

        except WebDriverException as e:
            logger.error(f"Selenium error fetching ADVFN after-hours gainers: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing ADVFN after-hours gainers: {e}")
            return []
        finally:
            self._cleanup_driver()

    def get_after_hours_losers(self, limit: int = 10, exchange: str = "nasdaq") -> List[Dict[str, any]]:
        """
        Get top after-hours losing stocks from ADVFN

        Args:
            limit: Number of top after-hours losers to return
            exchange: Exchange to fetch data from (nasdaq, nyse, amex)

        Returns:
            List of dictionaries with after-hours loser data
        """
        try:
            self._setup_driver()

            # Use the appropriate URL for the exchange
            url = self.urls.get(exchange.lower(), self.urls["nasdaq"])
            logger.info(f"Loading ADVFN {exchange} after-hours page: {url}")
            
            self.driver.get(url)
            time_module.sleep(5)  # Wait for page to load

            # Parse the page
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            
            # Look for the after-hours data table
            losers = self._parse_advfn_data(soup, "losers", limit)
            
            logger.info(f"Found {len(losers)} losers on ADVFN {exchange}")
            return losers

        except WebDriverException as e:
            logger.error(f"Selenium error fetching ADVFN after-hours losers: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing ADVFN after-hours losers: {e}")
            return []
        finally:
            self._cleanup_driver()

    def _parse_advfn_data(self, soup: BeautifulSoup, mover_type: str, limit: int) -> List[Dict[str, any]]:
        """Parse movers data from ADVFN page"""
        movers = []
        
        try:
            # Look for tables with stock data
            tables = soup.find_all("table")
            logger.info(f"Found {len(tables)} tables on ADVFN page")
            
            for table in tables:
                # Check if this table contains stock data
                headers = table.find_all("th")
                header_text = " ".join([h.get_text().lower() for h in headers])
                
                # Look for tables with relevant headers
                if any(word in header_text for word in ["symbol", "stock", "change", "price", "%"]):
                    logger.info("Found potential stock data table")
                    
                    tbody = table.find("tbody")
                    if tbody:
                        rows = tbody.find_all("tr")
                    else:
                        rows = table.find_all("tr")[1:]  # Skip header row
                    
                    for row in rows[:limit * 2]:  # Process more rows than needed
                        try:
                            cells = row.find_all(["td", "th"])
                            if len(cells) < 3:
                                continue
                            
                            # Extract data from cells
                            symbol = ""
                            company_name = ""
                            price = 0.0
                            change = 0.0
                            change_percent = 0.0
                            volume = 0
                            
                            for i, cell in enumerate(cells):
                                text = cell.get_text().strip()
                                
                                # Symbol is usually in first cell or a link
                                if i == 0 or (not symbol and text.isupper() and len(text) <= 6):
                                    symbol = text
                                
                                # Company name might be in second cell
                                elif i == 1 and not text.replace(".", "").replace("-", "").isdigit():
                                    company_name = text
                                
                                # Look for percentage
                                elif "%" in text:
                                    try:
                                        change_percent = float(
                                            text.replace("%", "").replace("+", "").replace("(", "").replace(")", "")
                                        )
                                    except:
                                        pass
                                
                                # Look for price (number with decimal)
                                elif "." in text and not "%" in text:
                                    try:
                                        value = float(text.replace("$", "").replace(",", ""))
                                        if value > 0 and value < 10000:  # Reasonable price range
                                            if price == 0:
                                                price = value
                                            else:
                                                change = value - price
                                    except:
                                        pass
                                
                                # Look for volume
                                elif text.replace(",", "").isdigit():
                                    try:
                                        volume = int(text.replace(",", ""))
                                    except:
                                        pass
                            
                            # Only add if we have essential data and it matches mover type
                            if symbol and change_percent != 0:
                                if (mover_type == "gainers" and change_percent > 0) or \
                                   (mover_type == "losers" and change_percent < 0):
                                    
                                    mover_data = {
                                        "symbol": symbol,
                                        "company_name": company_name,
                                        "regular_close": price * (1 - change_percent/100) if price > 0 else 0.0,
                                        "after_hours_price": price,
                                        "after_hours_change": change,
                                        "after_hours_change_percent": abs(change_percent),
                                        "after_hours_volume": volume,
                                        "source": "advfn_after_hours",
                                        "timestamp": datetime.now(),
                                        "session": "after_hours",
                                    }
                                    movers.append(mover_data)
                                    
                                    if len(movers) >= limit:
                                        return movers
                        
                        except Exception as e:
                            logger.debug(f"Error parsing row: {e}")
                            continue
            
            # If no tables found, try looking for div-based layouts
            if not movers:
                logger.info("No table data found, looking for div-based structures")
                stock_divs = soup.find_all("div", {"class": lambda x: x and any(
                    word in str(x).lower() for word in ["stock", "symbol", "quote", "ticker"]
                )})
                
                logger.info(f"Found {len(stock_divs)} potential stock divs")
                
        except Exception as e:
            logger.error(f"Error parsing ADVFN data: {e}")
        
        return movers[:limit]

    def is_after_hours_session(self) -> bool:
        """Check if we're currently in after-hours trading session (4 PM - 8 PM ET)"""
        et_tz = pytz.timezone("America/New_York")
        now_et = datetime.now(et_tz).time()

        after_hours_start = time(16, 0)  # 4:00 PM ET
        after_hours_end = time(20, 0)  # 8:00 PM ET

        return after_hours_start <= now_et <= after_hours_end

    def get_session_info(self) -> Dict[str, any]:
        """Get information about the current trading session and ADVFN data source"""
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
            "source_name": "ADVFN After Hours",
            "source_url": "https://www.advfn.com/markets/nasdaq/afterhours",
            "data_delay": "real_time",
            "last_updated": now_et,
            "timezone": "America/New_York",
            "exchanges": ["nasdaq", "nyse", "amex"],
        }

    def is_source_accessible(self) -> bool:
        """Check if ADVFN after-hours page is currently accessible"""
        try:
            self._setup_driver()
            self.driver.get(self.urls["nasdaq"])
            time_module.sleep(2)
            
            page_title = self.driver.title.lower()
            return "advfn" in page_title or "after" in page_title

        except Exception as e:
            logger.error(f"ADVFN accessibility check failed: {e}")
            return False
        finally:
            self._cleanup_driver()