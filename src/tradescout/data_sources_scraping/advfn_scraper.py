"""
ADVFN Web Scraper Implementation

Implements the AfterHoursWebScraper interface for ADVFN extended hours data.
Currently supports after-hours data, may be extended for pre-market in the future.
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

from .interfaces import AfterHoursWebScraper, PreMarketWebScraper

logger = logging.getLogger(__name__)


class ADVFNScraper(AfterHoursWebScraper, PreMarketWebScraper):
    """
    ADVFN web scraper implementation using Selenium
    Currently supports after-hours data, may be extended for pre-market in the future.
    """

    def __init__(
        self,
        exchange: str = "nasdaq",
        delay_seconds: float = 1.0,
        headless: bool = True,
    ):
        """
        Initialize ADVFN web scraper with Selenium

        Args:
            exchange: The stock exchange to scrape ('nasdaq', 'nyse', 'amex').
            delay_seconds: Delay between requests to be respectful.
            headless: Run browser in headless mode (default: True).
        """
        # ADVFN after-hours URLs for different exchanges
        self.urls = {
            "nasdaq": "https://www.advfn.com/markets/nasdaq/afterhours",
            "nyse": "https://www.advfn.com/markets/nyse/afterhours",
            "amex": "https://www.advfn.com/markets/amex/afterhours",
        }
        # ADVFN pre-market URLs for different exchanges
        self.premarket_urls = {
            "nasdaq": "https://www.advfn.com/markets/nasdaq/premarket",
            "nyse": "https://www.advfn.com/markets/nyse/premarket",
            "amex": "https://www.advfn.com/markets/amex/premarket",
        }
        if exchange.lower() not in self.urls:
            raise ValueError(
                f"Unsupported exchange: '{exchange}'. Supported exchanges are: {list(self.urls.keys())}"
            )
        self.exchange = exchange.lower()
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

        user_data_dir = "data/chrome_session"
        os.makedirs(user_data_dir, exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={os.path.abspath(user_data_dir)}")
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

    def get_after_hours_gainers(self, limit: int = 10) -> List[Dict[str, any]]:
        """
        Get top after-hours gaining stocks from ADVFN

        Args:
            limit: Number of top after-hours gainers to return

        Returns:
            List of dictionaries with after-hours gainer data
        """
        try:
            self._setup_driver()

            # Use the appropriate URL for the exchange
            url = self.urls[self.exchange]
            logger.info(f"Loading ADVFN {self.exchange} after-hours page: {url}")

            self.driver.get(url)
            time_module.sleep(5)  # Wait for page to load

            # Take screenshot for debugging
            self.driver.save_screenshot(
                f"/home/ccollins/projects/TradeScout/data/examples/advfn_{self.exchange}_afterhours.png"
            )

            # Parse the page
            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            # Look for the after-hours data table
            gainers = self._parse_advfn_data(soup, "gainers", limit, "after_hours")

            logger.info(f"Found {len(gainers)} gainers on ADVFN {self.exchange}")
            return gainers

        except WebDriverException as e:
            logger.error(f"Selenium error fetching ADVFN after-hours gainers: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing ADVFN after-hours gainers: {e}")
            return []
        finally:
            self._cleanup_driver()

    def get_after_hours_losers(self, limit: int = 10) -> List[Dict[str, any]]:
        """
        Get top after-hours losing stocks from ADVFN

        Args:
            limit: Number of top after-hours losers to return

        Returns:
            List of dictionaries with after-hours loser data
        """
        try:
            self._setup_driver()

            # Use the appropriate URL for the exchange
            url = self.urls[self.exchange]
            logger.info(f"Loading ADVFN {self.exchange} after-hours page: {url}")

            self.driver.get(url)
            time_module.sleep(5)  # Wait for page to load

            # Parse the page
            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            # Look for the after-hours data table
            losers = self._parse_advfn_data(soup, "losers", limit, "after_hours")

            logger.info(f"Found {len(losers)} losers on ADVFN {self.exchange}")
            return losers

        except WebDriverException as e:
            logger.error(f"Selenium error fetching ADVFN after-hours losers: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing ADVFN after-hours losers: {e}")
            return []
        finally:
            self._cleanup_driver()

    def _parse_advfn_data(
        self,
        soup: BeautifulSoup,
        mover_type: str,
        limit: int,
        session: str = "after_hours",
    ) -> List[Dict[str, any]]:
        """
        Parse movers data from ADVFN page by finding specific headers and their sibling tables.
        """
        movers = []

        # Determine the header text to search for
        if mover_type == "gainers":
            header_text = "Top Gainers"
        elif mover_type == "losers":
            header_text = "Top Losers"
        else:
            logger.error(f"Invalid mover_type: {mover_type}")
            return []

        try:
            # Find the header element (h3) containing the specified text
            header = soup.find(
                lambda tag: tag.name == "h3" and header_text in tag.get_text()
            )

            if not header:
                logger.warning(f"Could not find '{header_text}' header on the page.")
                return []

            # Find the table that is the sibling of the header
            table = header.find_next_sibling("table")

            if not table:
                logger.warning(f"Could not find data table for '{header_text}'.")
                return []

            rows = table.find_all("tr")[1:]  # Skip header row

            for row in rows:
                if len(movers) >= limit:
                    break

                cells = row.find_all("td")
                if len(cells) < 6:
                    continue

                try:
                    # Extract data based on column order: Symbol, Name, Price, Change, Change %, Volume
                    symbol = cells[0].get_text(strip=True)
                    company_name = cells[1].get_text(strip=True)

                    # Clean and convert numeric values
                    after_hours_price_text = (
                        cells[2].get_text(strip=True).replace(",", "")
                    )
                    after_hours_price = (
                        float(after_hours_price_text) if after_hours_price_text else 0.0
                    )

                    change_text = cells[3].get_text(strip=True).replace(",", "")
                    change = float(change_text) if change_text else 0.0

                    change_percent_text = (
                        cells[4].get_text(strip=True).replace("%", "").replace(",", "")
                    )
                    change_percent = (
                        float(change_percent_text) if change_percent_text else 0.0
                    )

                    volume_text = cells[5].get_text(strip=True)
                    volume = self._parse_volume(volume_text)

                    # Skip if there's no movement
                    if change == 0 and change_percent == 0 and volume == 0:
                        continue

                    # Calculate regular close price
                    regular_close = after_hours_price - change

                    if session == "premarket":
                        mover_data = {
                            "symbol": symbol,
                            "company_name": company_name,
                            "previous_close": round(regular_close, 4),
                            "premarket_price": after_hours_price,
                            "premarket_change": change,
                            "premarket_change_percent": change_percent,
                            "premarket_volume": volume,
                            "source": f"advfn_{self.exchange}",
                            "timestamp": datetime.now(
                                pytz.timezone("America/New_York")
                            ),
                            "session": "premarket",
                        }
                    else:
                        mover_data = {
                            "symbol": symbol,
                            "company_name": company_name,
                            "regular_close": round(regular_close, 4),
                            "after_hours_price": after_hours_price,
                            "after_hours_change": change,
                            "after_hours_change_percent": change_percent,
                            "after_hours_volume": volume,
                            "source": f"advfn_{self.exchange}_after_hours",
                            "timestamp": datetime.now(),
                            "session": "after_hours",
                        }
                    movers.append(mover_data)
                    logger.debug(
                        f"Parsed {mover_type}: {symbol} at {after_hours_price}"
                    )

                except (ValueError, IndexError) as e:
                    logger.warning(
                        f"Could not parse row: {row.get_text().strip()}. Error: {e}"
                    )
                    continue

        except Exception as e:
            logger.error(
                f"An unexpected error occurred while parsing ADVFN {mover_type} data: {e}"
            )

        return movers

    def _parse_volume(self, volume_text: str) -> int:
        """
        Parse volume string like "1.2M", "850K", or "1.5B" to integer.
        """
        volume_text = volume_text.upper().replace(",", "").strip()
        if not volume_text or volume_text == "N/A":
            return 0
        try:
            if "B" in volume_text:
                return int(float(volume_text.replace("B", "")) * 1_000_000_000)
            if "M" in volume_text:
                return int(float(volume_text.replace("M", "")) * 1_000_000)
            elif "K" in volume_text:
                return int(float(volume_text.replace("K", "")) * 1_000)
            else:
                return int(volume_text)
        except (ValueError, TypeError):
            logger.debug(f"Could not parse volume string: '{volume_text}'")
            return 0

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

    def _fetch_premarket_data(
        self, mover_type: str, limit: int
    ) -> List[Dict[str, any]]:
        """
        Fetch pre-market data from ADVFN using the pre-market URL
        """
        try:
            self._setup_driver()

            # Use the appropriate pre-market URL for the exchange
            url = self.premarket_urls[self.exchange]
            logger.info(f"Loading ADVFN {self.exchange} pre-market page: {url}")

            self.driver.get(url)
            time_module.sleep(5)  # Wait for page to load

            # Take screenshot for debugging
            try:
                screenshot_path = f"data/examples/advfn_{self.exchange}_premarket_{mover_type}_debug.png"
                self.driver.save_screenshot(screenshot_path)
                logger.info(f"Debug screenshot saved: {screenshot_path}")
            except:
                pass

            # Parse the page
            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            # Look for the pre-market data table
            movers = self._parse_advfn_data(soup, mover_type, limit, "premarket")

            logger.info(
                f"Found {len(movers)} {mover_type} on ADVFN {self.exchange} pre-market"
            )
            return movers

        except WebDriverException as e:
            logger.error(f"Selenium error fetching ADVFN pre-market {mover_type}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing ADVFN pre-market {mover_type}: {e}")
            return []
        finally:
            self._cleanup_driver()

    # PreMarketWebScraper interface implementation
    def get_premarket_gainers(self, limit: int = 10) -> List[Dict[str, any]]:
        """Get top pre-market gaining stocks from ADVFN"""
        return self._fetch_premarket_data("gainers", limit)

    def get_premarket_losers(self, limit: int = 10) -> List[Dict[str, any]]:
        """Get top pre-market losing stocks from ADVFN"""
        return self._fetch_premarket_data("losers", limit)

    def is_premarket_session(self) -> bool:
        """Check if we're currently in pre-market trading session (4 AM - 9:30 AM ET)"""
        et_tz = pytz.timezone("America/New_York")
        now_et = datetime.now(et_tz).time()
        premarket_start = time(4, 0)
        premarket_end = time(9, 30)
        return premarket_start <= now_et < premarket_end

    def get_premarket_session_info(self) -> Dict[str, any]:
        """Get information about the current pre-market trading session and data source"""
        et_tz = pytz.timezone("America/New_York")
        now_et = datetime.now(et_tz)
        current_time = now_et.time()

        if time(4, 0) <= current_time < time(9, 30):
            session = "premarket"
        elif time(9, 30) <= current_time < time(16, 0):
            session = "regular"
        elif time(16, 0) <= current_time <= time(20, 0):
            session = "after_hours"
        else:
            session = "closed"

        return {
            "current_session": session,
            "session_start": "4:00 AM ET",
            "session_end": "9:30 AM ET",
            "source_name": "ADVFN Pre-Market",
            "source_url": self.premarket_urls[self.exchange],
            "data_delay": "real_time",
            "last_updated": now_et,
            "timezone": "America/New_York",
            "exchanges": ["nasdaq", "nyse", "amex"],
            "is_premarket_session": self.is_premarket_session(),
        }
