"""
TradingView Web Scraper Implementation

Implements the AfterHoursWebScraper interface for TradingView extended hours data.
Currently supports after-hours data, may be extended for pre-market in the future.
URLs:
- After-hours gainers: https://www.tradingview.com/markets/stocks-usa/market-movers-after-hours-gainers/
- After-hours losers: https://www.tradingview.com/markets/stocks-usa/market-movers-after-hours-losers/
"""

import logging
import time as time_module
from datetime import datetime, time
from decimal import Decimal
from typing import Dict, List, Optional
import re

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


class TradingViewScraper(AfterHoursWebScraper, PreMarketWebScraper):
    """
    TradingView web scraper implementation using Selenium.
    TradingView provides professional-grade market data with comprehensive after-hours information.
    """

    def __init__(self, delay_seconds: float = 3.0, headless: bool = True):
        """
        Initialize TradingView web scraper.

        Args:
            delay_seconds: Delay between requests to be respectful (default: 3.0)
            headless: Run browser in headless mode (default: True)
        """
        self.base_url = "https://www.tradingview.com/markets/stocks-usa/market-movers"
        self.delay_seconds = delay_seconds
        self.headless = headless
        self.driver = None

    def _setup_driver(self):
        """Setup Chrome driver with persistent session for TradingView."""
        if self.driver:
            return

        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")

        # Standard Chrome options for web scraping
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        chrome_options.add_argument("--window-size=1920,1080")

        # Persistent session to handle cookies/preferences
        import os

        user_data_dir = "data/chrome_session"
        os.makedirs(user_data_dir, exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={os.path.abspath(user_data_dir)}")
        chrome_options.add_argument("--profile-directory=TradingView_Scraper")

        # Disable notifications and popups
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_experimental_option(
            "prefs",
            {
                "profile.default_content_setting_values": {
                    "notifications": 2,
                    "popups": 2,
                },
            },
        )

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            # Make webdriver undetectable
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

    def _parse_volume(self, volume_text: str) -> int:
        """Parse volume text with K, M, B suffixes."""
        if not volume_text or volume_text == "—":
            return 0

        volume_text = volume_text.strip().upper()
        multiplier = 1

        if volume_text.endswith("K"):
            multiplier = 1000
            volume_text = volume_text[:-1]
        elif volume_text.endswith("M"):
            multiplier = 1000000
            volume_text = volume_text[:-1]
        elif volume_text.endswith("B"):
            multiplier = 1000000000
            volume_text = volume_text[:-1]

        try:
            return int(float(volume_text) * multiplier)
        except ValueError:
            logger.warning(f"Could not parse volume: {volume_text}")
            return 0

    def _parse_price(self, price_text: str) -> float:
        """Parse price text, handling currency symbols."""
        if not price_text or price_text == "—":
            return 0.0

        # Remove currency symbols and 'USD'
        price_text = re.sub(r"[^\d.-]", "", price_text)

        try:
            return float(price_text)
        except ValueError:
            logger.warning(f"Could not parse price: {price_text}")
            return 0.0

    def _parse_percentage(self, percent_text: str) -> float:
        """Parse percentage text."""
        if not percent_text or percent_text == "—":
            return 0.0

        # Remove % sign and handle various minus signs
        percent_text = percent_text.strip().replace("%", "").replace("+", "")
        # Replace unicode minus sign with regular minus
        percent_text = percent_text.replace("−", "-").replace("–", "-")

        try:
            return float(percent_text)
        except ValueError:
            logger.warning(f"Could not parse percentage: {percent_text}")
            return 0.0

    def _fetch_and_parse(self, url_suffix: str, limit: int) -> List[Dict[str, any]]:
        """Fetch page and parse the after-hours data table."""
        url = f"{self.base_url}-{url_suffix}/"

        try:
            self._setup_driver()
            logger.info(f"Loading TradingView page: {url}")
            self.driver.get(url)

            # Wait for the table rows with data-rowkey to load
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-rowkey]"))
            )

            # Additional wait for data to populate
            time_module.sleep(self.delay_seconds)

            # Parse the page
            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            movers = []

            # Find all rows with data-rowkey attribute (these contain the actual stock data)
            rows = soup.find_all("tr", {"data-rowkey": True})

            if not rows:
                logger.warning("Could not find data rows on TradingView page")
                return []

            for row in rows[:limit]:
                try:
                    # Extract symbol from data-rowkey attribute (format: "NASDAQ:SYMBOL")
                    rowkey = row.get("data-rowkey", "")
                    if ":" in rowkey:
                        exchange, symbol = rowkey.split(":", 1)
                    else:
                        symbol = rowkey
                        exchange = ""

                    cells = row.find_all("td")
                    if len(cells) < 9:  # Need at least 9 columns based on screenshot
                        continue

                    # Extract company name from first cell
                    symbol_cell = cells[0]
                    company_name = ""

                    # Get the text content, skipping the data mode indicator
                    cell_text = symbol_cell.get_text(separator=" ", strip=True)

                    # The cell format is usually: "D SYMBOL Company Name" or just "SYMBOL Company Name"
                    # Split and find the company name
                    parts = cell_text.split()

                    # Skip data mode indicators (D, R, etc.) and symbol to get company name
                    if parts:
                        # Find where the symbol appears and take everything after it
                        try:
                            symbol_index = parts.index(symbol)
                            if symbol_index < len(parts) - 1:
                                company_name = " ".join(parts[symbol_index + 1 :])
                        except ValueError:
                            # Symbol not found in expected format, try alternative parsing
                            # Remove common prefixes and the symbol itself
                            for prefix in ["D", "R", "RT"]:
                                if parts[0] == prefix:
                                    parts = parts[1:]
                                    break
                            if parts and parts[0] == symbol:
                                company_name = " ".join(parts[1:])
                            else:
                                # Last resort: take all text except first word if it looks like a symbol
                                if parts and len(parts[0]) <= 5 and parts[0].isupper():
                                    company_name = " ".join(parts[1:])
                                else:
                                    company_name = cell_text

                    # Extract data from other cells
                    # Columns: Symbol, Post-market Chg %, Post-market Price, Post-market Chg,
                    #          Post-market Vol, Price, Change %, Volume, Market cap

                    post_market_change_pct = self._parse_percentage(
                        cells[1].get_text(strip=True)
                    )
                    post_market_price = self._parse_price(cells[2].get_text(strip=True))
                    post_market_change = self._parse_price(
                        cells[3].get_text(strip=True)
                    )
                    post_market_volume = self._parse_volume(
                        cells[4].get_text(strip=True)
                    )
                    regular_price = self._parse_price(cells[5].get_text(strip=True))

                    # Calculate regular close from post-market data
                    regular_close = post_market_price - post_market_change
                    if regular_close <= 0:
                        regular_close = regular_price

                    mover = {
                        "symbol": symbol,
                        "company_name": company_name,
                        "exchange": exchange,
                        "regular_close": regular_close,
                        "after_hours_price": post_market_price,
                        "after_hours_change": post_market_change,
                        "after_hours_change_percent": post_market_change_pct,
                        "after_hours_volume": post_market_volume,
                        "source": "tradingview",
                        "timestamp": datetime.now(pytz.UTC),
                        "session": "after_hours",
                    }

                    movers.append(mover)

                except Exception as e:
                    logger.warning(f"Error parsing row: {e}")
                    import traceback

                    traceback.print_exc()
                    continue

            logger.info(f"Successfully extracted {len(movers)} movers from TradingView")
            return movers

        except TimeoutException:
            logger.error(f"Timeout waiting for TradingView page to load: {url}")
            return []
        except WebDriverException as e:
            logger.error(f"Selenium error fetching TradingView page: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching TradingView data: {e}")
            return []
        finally:
            self._cleanup_driver()

    def _fetch_and_parse_premarket(
        self, url_suffix: str, limit: int
    ) -> List[Dict[str, any]]:
        """Fetch page and parse the pre-market data table."""
        url = f"{self.base_url}-{url_suffix}/"

        try:
            self._setup_driver()
            logger.info(f"Loading TradingView pre-market page: {url}")
            self.driver.get(url)

            # Wait for the table rows with data-rowkey to load
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-rowkey]"))
            )

            # Additional wait for data to populate
            time_module.sleep(self.delay_seconds)

            # Parse the page
            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            movers = []

            # Find all rows with data-rowkey attribute (these contain the actual stock data)
            rows = soup.find_all("tr", {"data-rowkey": True})

            if not rows:
                logger.warning(
                    "Could not find data rows on TradingView pre-market page"
                )
                return []

            for row in rows[:limit]:
                try:
                    # Extract symbol from data-rowkey attribute (format: "NASDAQ:SYMBOL")
                    rowkey = row.get("data-rowkey", "")
                    if ":" in rowkey:
                        exchange, symbol = rowkey.split(":", 1)
                    else:
                        symbol = rowkey
                        exchange = ""

                    cells = row.find_all("td")
                    if len(cells) < 9:  # Need at least 9 columns for pre-market data
                        continue

                    # Extract company name from first cell
                    symbol_cell = cells[0]
                    company_name = ""

                    # Get the text content, skipping the data mode indicator
                    cell_text = symbol_cell.get_text(separator=" ", strip=True)

                    # The cell format is usually: "D SYMBOL Company Name" or just "SYMBOL Company Name"
                    # Split and find the company name
                    parts = cell_text.split()

                    # Skip data mode indicators (D, R, etc.) and symbol to get company name
                    if parts:
                        # Find where the symbol appears and take everything after it
                        try:
                            symbol_index = parts.index(symbol)
                            if symbol_index < len(parts) - 1:
                                company_name = " ".join(parts[symbol_index + 1 :])
                        except ValueError:
                            # Symbol not found in expected format, try alternative parsing
                            # Remove common prefixes and the symbol itself
                            for prefix in ["D", "R", "RT"]:
                                if parts[0] == prefix:
                                    parts = parts[1:]
                                    break
                            if parts and parts[0] == symbol:
                                company_name = " ".join(parts[1:])
                            else:
                                # Last resort: take all text except first word if it looks like a symbol
                                if parts and len(parts[0]) <= 5 and parts[0].isupper():
                                    company_name = " ".join(parts[1:])
                                else:
                                    company_name = cell_text

                    # Extract data from other cells
                    # Pre-market columns: Symbol, Pre-market Chg %, Pre-market Price, Pre-market Chg,
                    #                     Pre-market Vol, Pre-market Gap %, Price, Change %, Volume, Market cap

                    premarket_change_pct = self._parse_percentage(
                        cells[1].get_text(strip=True)
                    )
                    premarket_price = self._parse_price(cells[2].get_text(strip=True))
                    premarket_change = self._parse_price(cells[3].get_text(strip=True))
                    premarket_volume = self._parse_volume(cells[4].get_text(strip=True))
                    premarket_gap_pct = self._parse_percentage(
                        cells[5].get_text(strip=True)
                    )
                    regular_price = self._parse_price(cells[6].get_text(strip=True))

                    # Calculate previous close from pre-market data
                    # Be careful with the calculation - premarket_change is the absolute change
                    if premarket_change_pct != 0:
                        # Use percentage to calculate previous close more accurately
                        previous_close = premarket_price / (
                            1 + premarket_change_pct / 100
                        )
                    else:
                        previous_close = premarket_price - premarket_change

                    # Fallback to regular price if calculation seems wrong
                    if previous_close <= 0 or previous_close > premarket_price * 10:
                        previous_close = (
                            regular_price if regular_price > 0 else premarket_price
                        )

                    mover = {
                        "symbol": symbol,
                        "company_name": company_name,
                        "exchange": exchange,
                        "previous_close": previous_close,
                        "premarket_price": premarket_price,
                        "premarket_change": premarket_change,
                        "premarket_change_percent": premarket_change_pct,
                        "premarket_volume": premarket_volume,
                        "premarket_gap_percent": premarket_gap_pct,
                        "source": "tradingview",
                        "timestamp": datetime.now(pytz.UTC),
                        "session": "premarket",
                    }

                    movers.append(mover)

                except Exception as e:
                    logger.warning(f"Error parsing pre-market row: {e}")
                    import traceback

                    traceback.print_exc()
                    continue

            logger.info(
                f"Successfully extracted {len(movers)} pre-market movers from TradingView"
            )
            return movers

        except TimeoutException:
            logger.error(
                f"Timeout waiting for TradingView pre-market page to load: {url}"
            )
            return []
        except WebDriverException as e:
            logger.error(f"Selenium error fetching TradingView pre-market page: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching TradingView pre-market data: {e}")
            return []
        finally:
            self._cleanup_driver()

    def get_after_hours_gainers(self, limit: int = 10) -> List[Dict[str, any]]:
        """Get top after-hours gaining stocks from TradingView."""
        return self._fetch_and_parse("after-hours-gainers", limit)

    def get_after_hours_losers(self, limit: int = 10) -> List[Dict[str, any]]:
        """Get top after-hours losing stocks from TradingView."""
        return self._fetch_and_parse("after-hours-losers", limit)

    def is_after_hours_session(self) -> bool:
        """Check if currently in after-hours trading session (4 PM - 8 PM ET)."""
        eastern = pytz.timezone("US/Eastern")
        now = datetime.now(eastern)

        # After-hours: 4:00 PM - 8:00 PM ET on weekdays
        if now.weekday() < 5:  # Monday = 0, Friday = 4
            after_hours_start = time(16, 0)  # 4:00 PM
            after_hours_end = time(20, 0)  # 8:00 PM
            current_time = now.time()

            return after_hours_start <= current_time <= after_hours_end

        return False

    def get_session_info(self) -> Dict[str, any]:
        """Get information about the current trading session."""
        eastern = pytz.timezone("US/Eastern")
        now = datetime.now(eastern)
        current_time = now.time()

        # Determine current session
        if now.weekday() >= 5:  # Weekend
            current_session = "closed"
        elif time(4, 0) <= current_time < time(9, 30):
            current_session = "premarket"
        elif time(9, 30) <= current_time < time(16, 0):
            current_session = "regular"
        elif time(16, 0) <= current_time <= time(20, 0):
            current_session = "after_hours"
        else:
            current_session = "closed"

        return {
            "current_session": current_session,
            "session_start": (
                "4:00 PM ET" if current_session == "after_hours" else "N/A"
            ),
            "session_end": "8:00 PM ET" if current_session == "after_hours" else "N/A",
            "source_name": "TradingView After Hours",
            "data_delay": "real_time",
            "last_updated": datetime.now(pytz.UTC),
        }

    # PreMarketWebScraper interface methods
    def get_premarket_gainers(self, limit: int = 10) -> List[Dict[str, any]]:
        """Get top pre-market gaining stocks from TradingView."""
        return self._fetch_and_parse_premarket("pre-market-gainers", limit)

    def get_premarket_losers(self, limit: int = 10) -> List[Dict[str, any]]:
        """Get top pre-market losing stocks from TradingView."""
        return self._fetch_and_parse_premarket("pre-market-losers", limit)

    def is_premarket_session(self) -> bool:
        """Check if currently in pre-market session - stub implementation."""
        eastern = pytz.timezone("US/Eastern")
        now = datetime.now(eastern)

        # Pre-market: 4:00 AM - 9:30 AM ET on weekdays
        if now.weekday() < 5:
            premarket_start = time(4, 0)
            premarket_end = time(9, 30)
            current_time = now.time()

            return premarket_start <= current_time < premarket_end

        return False

    def get_premarket_session_info(self) -> Dict[str, any]:
        """Get pre-market session info - stub implementation."""
        return {
            "current_session": "premarket" if self.is_premarket_session() else "other",
            "session_start": "4:00 AM ET",
            "session_end": "9:30 AM ET",
            "source_name": "TradingView Pre-Market",
            "data_delay": "real_time",
            "last_updated": datetime.now(pytz.UTC),
        }
