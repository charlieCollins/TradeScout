"""
TipRanks After-Hours Scraper Implementation

Implements the AfterHoursWebScraper interface for TipRanks after-hours data.
URL: https://www.tipranks.com/markets/after-hours/gainers
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

from .interfaces import AfterHoursWebScraper

logger = logging.getLogger(__name__)


class TipRanksAfterHoursScraper(AfterHoursWebScraper):
    """
    TipRanks after-hours data scraper implementation using Selenium.
    This scraper handles dynamically loaded content.
    """

    def __init__(self, delay_seconds: float = 2.0, headless: bool = True):
        """
        Initialize TipRanks after-hours scraper.
        A longer delay is used to accommodate dynamic content loading.
        """
        self.base_url = "https://www.tipranks.com/markets/after-hours"
        self.delay_seconds = delay_seconds
        self.headless = headless
        self.driver = None

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
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        chrome_options.add_argument("--window-size=1920,1080")

        import os
        user_data_dir = "data/chrome_session"
        os.makedirs(user_data_dir, exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={os.path.abspath(user_data_dir)}")
        chrome_options.add_argument("--profile-directory=TipRanks_Scraper")

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
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

    def _fetch_page(self, mover_type: str) -> Optional[BeautifulSoup]:
        """Fetches the page and waits for dynamic content to load."""
        url = f"{self.base_url}/{mover_type}"
        try:
            self._setup_driver()
            logger.info(f"Loading TipRanks page: {url}")
            self.driver.get(url)

            # Wait for the table to appear and for the data to load.
            # We can check if the loading dash '―' is no longer present in a key cell.
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'rt-tr-group')]"))
            )
            # Additional wait for the dynamic data to populate
            time_module.sleep(self.delay_seconds)

            return BeautifulSoup(self.driver.page_source, "html.parser")

        except TimeoutException:
            logger.warning(f"Timeout waiting for dynamic content on {url}")
            return None
        except WebDriverException as e:
            logger.error(f"Selenium error fetching {url}: {e}")
            return None
        finally:
            self._cleanup_driver()

    def get_after_hours_gainers(self, limit: int = 10) -> List[Dict[str, any]]:
        """Get top after-hours gaining stocks from TipRanks."""
        soup = self._fetch_page("gainers")
        if not soup:
            return []

        return self._parse_data(soup, limit, "gainers")

    def get_after_hours_losers(self, limit: int = 10) -> List[Dict[str, any]]:
        """Get top after-hours losing stocks from TipRanks."""
        soup = self._fetch_page("losers")
        if not soup:
            return []

        return self._parse_data(soup, limit, "losers")

    def _parse_data(self, soup: BeautifulSoup, limit: int, mover_type: str) -> List[Dict[str, any]]:
        """Parses the data from the TipRanks table."""
        movers = []
        # TipRanks uses a div-based table structure with role="rowgroup"
        rows = soup.find_all("div", role="row")

        # The first row is the header
        for row in rows[1:]:
            if len(movers) >= limit:
                break

            cells = row.find_all("div", role="gridcell")
            if len(cells) < 8:
                continue

            try:
                # Columns: No., Symbol, Name, AI Catalyst, % Change, Stock Price, Volume, Market Cap
                symbol = cells[1].get_text(strip=True)
                company_name = cells[2].get_text(strip=True)

                change_percent_text = cells[4].get_text(strip=True).replace("%", "").replace("+", "")
                if "―" in change_percent_text: continue # Skip rows without data
                change_percent = float(change_percent_text)

                price_text = cells[5].get_text(strip=True).replace("$", "").replace(",", "")
                price = float(price_text)

                volume_text = cells[6].get_text(strip=True)
                volume = self._parse_volume(volume_text)

                # TipRanks provides change percent, so we calculate the change amount
                change = price * (change_percent / (100 + change_percent)) if change_percent > -100 else 0
                regular_close = price - change

                mover_data = {
                    "symbol": symbol,
                    "company_name": company_name,
                    "regular_close": round(regular_close, 4),
                    "after_hours_price": price,
                    "after_hours_change": round(change, 4),
                    "after_hours_change_percent": change_percent,
                    "after_hours_volume": volume,
                    "source": f"tipranks_after_hours_{mover_type}",
                    "timestamp": datetime.now(),
                    "session": "after_hours",
                }
                movers.append(mover_data)

            except (ValueError, IndexError) as e:
                logger.warning(f"Could not parse row for TipRanks: {row.get_text().strip()}. Error: {e}")
                continue

        return movers

    def _parse_volume(self, volume_text: str) -> int:
        """Parse volume string like "1.2M" or "850K" to integer."""
        volume_text = volume_text.upper().strip()
        if not volume_text or "―" in volume_text:
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
            "source_name": "TipRanks After Hours",
            "source_url": self.base_url,
            "data_delay": "real_time", # Assumption
            "last_updated": now_et,
            "timezone": "America/New_York",
        }
