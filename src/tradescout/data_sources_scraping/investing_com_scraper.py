"""
Investing.com Web Scraper Implementation

Implements the AfterHoursWebScraper interface for Investing.com extended hours data.
Currently supports after-hours data, may be extended for pre-market in the future.
URL: https://www.investing.com/equities/after-hours
"""

import logging
import time as time_module
from datetime import datetime, time
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


class InvestingComScraper(AfterHoursWebScraper, PreMarketWebScraper):
    """
    Investing.com web scraper implementation using Selenium.
    Currently supports after-hours data, may be extended for pre-market in the future.
    """

    def __init__(self, delay_seconds: float = 1.0, headless: bool = True):
        """
        Initialize Investing.com web scraper.
        """
        self.base_url = "https://www.investing.com/equities/after-hours"
        self.premarket_url = "https://www.investing.com/equities/pre-market"
        self.delay_seconds = delay_seconds
        self.headless = headless
        self.driver = None
        self._all_movers_cache = None
        self._cache_timestamp = None
        self._premarket_movers_cache = None
        self._premarket_cache_timestamp = None

    def _setup_driver(self):
        """Setup Chrome driver with persistent session."""
        if self.driver:
            return

        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        chrome_options.add_argument("--window-size=1920,1080")

        import os

        user_data_dir = "data/chrome_session"
        os.makedirs(user_data_dir, exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={os.path.abspath(user_data_dir)}")
        chrome_options.add_argument("--profile-directory=InvestingCom_Scraper")

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
        except Exception as e:
            logger.error(f"Failed to setup Chrome driver: {e}")
            raise

    def _cleanup_driver(self):
        """Clean up the selenium driver."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def _fetch_and_parse_data(self) -> List[Dict[str, any]]:
        """
        Fetches the page data and parses the 'Most Active' table.
        Caches the result for a short period to avoid redundant parsing
        when get_after_hours_gainers and get_after_hours_losers are called in succession.
        """
        # Check cache first
        if (
            self._all_movers_cache
            and self._cache_timestamp
            and (datetime.now() - self._cache_timestamp).total_seconds() < 60
        ):
            logger.info("Returning cached data from Investing.com.")
            return self._all_movers_cache

        try:
            self._setup_driver()
            logger.info(f"Loading Investing.com after-hours page: {self.base_url}")
            self.driver.get(self.base_url)

            # Wait for the table to be present. The table has an id 'afterhours'.
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.ID, "afterhours"))
            )
            time_module.sleep(self.delay_seconds)  # Small delay for dynamic content

            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            # The main data is in the table with id="afterhours"
            table = soup.find("table", id="afterhours")
            if not table:
                logger.warning(
                    "Could not find the 'afterhours' data table on the page."
                )
                return []

            parsed_data = self._parse_active_movers_table(table)

            # Cache the result
            self._all_movers_cache = parsed_data
            self._cache_timestamp = datetime.now()

            return parsed_data

        except WebDriverException as e:
            logger.error(f"Selenium error fetching Investing.com data: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing Investing.com data: {e}")
            return []
        finally:
            self._cleanup_driver()

    def get_after_hours_gainers(self, limit: int = 10) -> List[Dict[str, any]]:
        """Get top after-hours gaining stocks from Investing.com."""
        all_movers = self._fetch_and_parse_data()

        # Sort by percentage change (descending)
        gainers = sorted(
            all_movers,
            key=lambda x: x.get("after_hours_change_percent", 0),
            reverse=True,
        )

        return gainers[:limit]

    def get_after_hours_losers(self, limit: int = 10) -> List[Dict[str, any]]:
        """Get top after-hours losing stocks from Investing.com."""
        all_movers = self._fetch_and_parse_data()

        # Sort by percentage change (ascending)
        losers = sorted(
            all_movers, key=lambda x: x.get("after_hours_change_percent", 0)
        )

        return losers[:limit]

    def _parse_active_movers_table(
        self, table: BeautifulSoup, session_type: str = "after_hours"
    ) -> List[Dict[str, any]]:
        """Parses the content of the 'Most Active' stocks table."""
        movers = []
        tbody = table.find("tbody")
        if not tbody:
            return []

        rows = tbody.find_all("tr")

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 7:
                continue

            try:
                # Column order: Name, Symbol, Last, Chg., Chg. %, Vol., Time
                company_name = cells[0].get_text(strip=True)
                symbol = cells[1].get_text(strip=True)

                price_text = cells[2].get_text(strip=True).replace(",", "")
                price = float(price_text) if price_text else 0.0

                change_text = cells[3].get_text(strip=True)
                change = float(change_text) if change_text else 0.0

                change_percent_text = (
                    cells[4].get_text(strip=True).replace("%", "").replace("+", "")
                )
                change_percent = (
                    float(change_percent_text) if change_percent_text else 0.0
                )

                volume_text = cells[5].get_text(strip=True)
                volume = self._parse_volume(volume_text)

                regular_close = price - change

                if session_type == "premarket":
                    mover_data = {
                        "symbol": symbol,
                        "company_name": company_name,
                        "previous_close": round(regular_close, 4),
                        "premarket_price": price,
                        "premarket_change": change,
                        "premarket_change_percent": change_percent,
                        "premarket_volume": volume,
                        "source": "investing_com",
                        "timestamp": datetime.now(pytz.timezone("America/New_York")),
                        "session": "premarket",
                    }
                else:
                    mover_data = {
                        "symbol": symbol,
                        "company_name": company_name,
                        "regular_close": round(regular_close, 4),
                        "after_hours_price": price,
                        "after_hours_change": change,
                        "after_hours_change_percent": change_percent,
                        "after_hours_volume": volume,
                        "source": "investing_com_after_hours",
                        "timestamp": datetime.now(),
                        "session": "after_hours",
                    }
                movers.append(mover_data)

            except (ValueError, IndexError) as e:
                logger.warning(
                    f"Could not parse row for Investing.com: {row.get_text().strip()}. Error: {e}"
                )
                continue

        return movers

    def _parse_volume(self, volume_text: str) -> int:
        """Parse volume string like "1.2M" or "850K" to integer."""
        volume_text = volume_text.upper().strip()
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
                return int(volume_text.replace(",", ""))
        except (ValueError, TypeError):
            return 0

    def is_after_hours_session(self) -> bool:
        """Check if we're currently in after-hours trading session (4 PM - 8 PM ET)."""
        et_tz = pytz.timezone("America/New_York")
        now_et = datetime.now(et_tz).time()
        after_hours_start = time(16, 0)
        after_hours_end = time(20, 0)
        return after_hours_start <= now_et <= after_hours_end

    def get_session_info(self) -> Dict[str, any]:
        """Get information about the current trading session and data source."""
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
            "session_start": "4:00 PM ET",
            "session_end": "8:00 PM ET",
            "source_name": "Investing.com After Hours",
            "source_url": self.base_url,
            "data_delay": "real_time",
            "last_updated": now_et,
            "timezone": "America/New_York",
        }

    def _fetch_premarket_data(self) -> List[Dict[str, any]]:
        """
        Fetches the pre-market page data and parses the table.
        Caches the result for a short period to avoid redundant parsing.
        """
        # Check cache first
        if (
            self._premarket_movers_cache
            and self._premarket_cache_timestamp
            and (datetime.now() - self._premarket_cache_timestamp).total_seconds() < 60
        ):
            logger.info("Returning cached pre-market data from Investing.com.")
            return self._premarket_movers_cache

        try:
            self._setup_driver()
            logger.info(f"Loading Investing.com pre-market page: {self.premarket_url}")
            self.driver.get(self.premarket_url)

            # Wait for the table to be present. Looking for common table identifiers
            WebDriverWait(self.driver, 20).until(
                lambda driver: driver.find_element(By.TAG_NAME, "table")
            )
            time_module.sleep(self.delay_seconds)

            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            # Look for the main data table - try different approaches
            table = None

            # First try: look for table with id "premarket" or similar
            table = soup.find("table", id="premarket")
            if not table:
                # Second try: look for the first table with stock data structure
                tables = soup.find_all("table")
                for t in tables:
                    headers = t.find_all(["th", "td"])
                    header_text = " ".join([h.get_text().lower() for h in headers[:10]])
                    if any(
                        keyword in header_text
                        for keyword in ["symbol", "name", "change", "price", "volume"]
                    ):
                        table = t
                        break

            if not table:
                logger.warning(
                    "Could not find pre-market data table on Investing.com page."
                )
                return []

            parsed_data = self._parse_active_movers_table(table, "premarket")

            # Cache the result
            self._premarket_movers_cache = parsed_data
            self._premarket_cache_timestamp = datetime.now()

            return parsed_data

        except WebDriverException as e:
            logger.error(f"Selenium error fetching Investing.com pre-market data: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing Investing.com pre-market data: {e}")
            return []
        finally:
            self._cleanup_driver()

    # PreMarketWebScraper interface implementation
    def get_premarket_gainers(self, limit: int = 10) -> List[Dict[str, any]]:
        """Get top pre-market gaining stocks from Investing.com."""
        all_movers = self._fetch_premarket_data()

        # Sort by percentage change (descending)
        gainers = sorted(
            all_movers, key=lambda x: x.get("premarket_change_percent", 0), reverse=True
        )

        return gainers[:limit]

    def get_premarket_losers(self, limit: int = 10) -> List[Dict[str, any]]:
        """Get top pre-market losing stocks from Investing.com."""
        all_movers = self._fetch_premarket_data()

        # Sort by percentage change (ascending)
        losers = sorted(all_movers, key=lambda x: x.get("premarket_change_percent", 0))

        return losers[:limit]

    def is_premarket_session(self) -> bool:
        """Check if we're currently in pre-market trading session (4 AM - 9:30 AM ET)."""
        et_tz = pytz.timezone("America/New_York")
        now_et = datetime.now(et_tz).time()
        premarket_start = time(4, 0)
        premarket_end = time(9, 30)
        return premarket_start <= now_et < premarket_end

    def get_premarket_session_info(self) -> Dict[str, any]:
        """Get information about the current pre-market trading session and data source."""
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
            "source_name": "Investing.com Pre-Market",
            "source_url": self.premarket_url,
            "data_delay": "real_time",
            "last_updated": now_et,
            "timezone": "America/New_York",
            "is_premarket_session": self.is_premarket_session(),
        }
