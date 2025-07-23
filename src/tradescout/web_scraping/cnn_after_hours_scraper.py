"""
CNN Markets After-Hours Scraper Implementation

Implements the AfterHoursWebScraper interface for CNN Markets after-hours data.
URL: https://www.cnn.com/markets/after-hours
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup
from datetime import datetime, time
import pytz
from typing import List, Dict, Optional
import logging
from decimal import Decimal
import time as time_module

from .interfaces import AfterHoursWebScraper

logger = logging.getLogger(__name__)


class CNNAfterHoursScraper(AfterHoursWebScraper):
    """
    CNN Markets after-hours data scraper implementation using Selenium
    """
    
    def __init__(self, delay_seconds: float = 1.0, headless: bool = True):
        """
        Initialize CNN after-hours scraper with Selenium
        
        Args:
            delay_seconds: Delay between requests to be respectful
            headless: Run browser in headless mode (default: True)
        """
        self.base_url = "https://www.cnn.com/markets/after-hours"
        self.delay_seconds = delay_seconds
        self.headless = headless
        self.driver = None
        
    def _setup_driver(self):
        """Setup Chrome driver with proper options to mimic real browser"""
        if self.driver is not None:
            return
            
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument("--headless")
            
        # Mimic a real browser to avoid detection
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Set realistic user agent
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Set window size to mimic desktop browser
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Ad blocking and popup prevention
        chrome_options.add_argument("--block-new-web-contents")  # Block popups
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-extensions-except")
        chrome_options.add_argument("--disable-plugins-discovery")
        chrome_options.add_argument("--disable-translate")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-features=TranslateUI")
        chrome_options.add_argument("--disable-ipc-flooding-protection")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        
        # Block ads and trackers at DNS level
        chrome_options.add_experimental_option("prefs", {
            "profile.default_content_setting_values": {
                "notifications": 2,  # Block notifications
                "popups": 2,  # Block popups
                "media_stream": 2,  # Block media stream
                "plugins": 2,  # Block plugins
                "automatic_downloads": 2,  # Block automatic downloads
                "cookies": 1,  # Allow cookies (needed for functionality)
                "images": 1,  # Allow images
                "javascript": 1,  # Allow JavaScript
                "geolocation": 2,  # Block location
                "microphone": 2,  # Block microphone
                "camera": 2,  # Block camera
            },
            "profile.managed_default_content_settings": {
                "images": 1
            }
        })
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            # Execute script to remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
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
        Get top after-hours gaining stocks from CNN Markets using Selenium
        
        Args:
            limit: Number of top after-hours gainers to return
            
        Returns:
            List of dictionaries with after-hours gainer data
        """
        try:
            self._setup_driver()
            
            logger.info(f"Loading CNN after-hours page: {self.base_url}")
            self.driver.get(self.base_url)
            
            # Wait for page to load and check if we got blocked
            time_module.sleep(3)
            
            # Check for common blocking indicators
            page_source = self.driver.page_source.lower()
            if ("451" in page_source and ("unavailable" in page_source or "blocked" in page_source)):
                logger.warning("CNN page appears to be blocked or unavailable")
                return []
            
            # Wait for content to load (adjust selector as needed)
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except TimeoutException:
                logger.warning("Timeout waiting for CNN page to load")
                return []
            
            # Aggressively dismiss any popups/overlays
            try:
                # Wait longer for consent/cookie popups to appear
                time_module.sleep(4)
                logger.info("Attempting to dismiss popups/consent dialogs...")
                
                # Remove overlay divs with high z-index (likely popups/ads)
                self.driver.execute_script("""
                    var overlays = document.querySelectorAll('div[style*="z-index"]');
                    overlays.forEach(function(overlay) {
                        var zIndex = window.getComputedStyle(overlay).zIndex;
                        if (zIndex && parseInt(zIndex) > 1000) {
                            overlay.style.display = 'none';
                            overlay.remove();
                        }
                    });
                """)
                
                # Remove fixed position elements that might be overlays
                self.driver.execute_script("""
                    var fixedElements = document.querySelectorAll('*');
                    for (var i = 0; i < fixedElements.length; i++) {
                        var style = window.getComputedStyle(fixedElements[i]);
                        if (style.position === 'fixed' && style.backgroundColor.includes('rgba') && 
                            (style.backgroundColor.includes('0.4') || style.backgroundColor.includes('0.5'))) {
                            fixedElements[i].style.display = 'none';
                            fixedElements[i].remove();
                        }
                    }
                """)
                
                # Try common close button selectors including consent/terms popups
                popup_dismissers = [
                    # CNN specific "Agree" button (user confirmed this is the exact text)
                    "//button[text()='Agree']",
                    "//button[contains(text(), 'Agree')]",
                    "//*[text()='Agree']",
                    "//*[contains(text(), 'Agree') and (@role='button' or name()='button')]",
                    
                    # Legal terms and privacy specific selectors
                    "//button[contains(text(), 'legal terms and privacy')]",
                    "//button[contains(text(), 'Legal Terms and Privacy')]",
                    "//button[contains(text(), 'Terms of Use')]",
                    "//button[contains(text(), 'Privacy Policy')]",
                    "//button[contains(text(), 'I Understand')]",
                    "//button[contains(text(), 'I Accept')]",
                    "//button[contains(text(), 'Proceed')]",
                    "//button[contains(text(), 'Enter Site')]",
                    
                    # Cookie/consent popup buttons  
                    "//button[contains(text(), 'Accept')]",
                    "//button[contains(text(), 'Accept All')]",
                    "//button[contains(text(), 'Continue')]",
                    "//button[contains(text(), 'OK')]",
                    "//button[contains(text(), 'Got it')]",
                    "//button[contains(@class, 'accept')]",
                    "//button[contains(@class, 'agree')]",
                    "//button[contains(@class, 'consent')]",
                    "//button[contains(@id, 'accept')]",
                    "//button[contains(@id, 'consent')]",
                    
                    # Generic close buttons
                    "//button[contains(@class, 'close')]",
                    "//div[@class='close']", 
                    "//span[contains(@class, 'close')]",
                    "//button[contains(text(), '×')]",
                    "//button[contains(text(), 'Close')]",
                    "//button[contains(@aria-label, 'close')]",
                    "//div[contains(@class, 'modal')]//button",
                    "//div[contains(@class, 'overlay')]//button",
                    
                    # CNN specific selectors
                    "//button[contains(@class, 'btn')]",
                    "//*[contains(@class, 'cmp')]//button"
                ]
                
                buttons_found = 0
                for dismisser in popup_dismissers:
                    try:
                        close_buttons = self.driver.find_elements(By.XPATH, dismisser)
                        for close_button in close_buttons:
                            if close_button.is_displayed():
                                try:
                                    button_text = close_button.text.strip()
                                    logger.info(f"Clicking button: '{button_text}' with selector: {dismisser}")
                                    self.driver.execute_script("arguments[0].click();", close_button)
                                    buttons_found += 1
                                    time_module.sleep(1)
                                except Exception as e:
                                    logger.debug(f"Failed to click button: {e}")
                    except:
                        continue
                        
                logger.info(f"Dismissed {buttons_found} popup button(s)")
                
                # Wait and then take a screenshot to see current page state
                time_module.sleep(2)
                try:
                    self.driver.save_screenshot("/home/ccollins/projects/TradeScout/data/examples/cnn_after_popup_dismissal.png")
                    logger.info("Screenshot saved after popup dismissal")
                except:
                    logger.debug("Could not save screenshot")
                
                time_module.sleep(2)  # Wait after dismissing popups
                        
                logger.info("Overlay dismissal completed")
                
            except Exception as e:
                logger.debug(f"Error dismissing overlays: {e}")
            
            # Try to click the "Gainers" button/tab if it exists
            try:
                # Look for Gainers button/tab - use more specific selector for CNN
                gainers_selector = "//span[contains(@class, 'market-ticker__view-links-container') and contains(text(), 'Gainers')]"
                
                try:
                    gainers_element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, gainers_selector))
                    )
                    
                    logger.info("Found Gainers button - attempting JavaScript click")
                    # Force click with JavaScript to bypass any overlays
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", gainers_element)
                    time_module.sleep(1)
                    self.driver.execute_script("arguments[0].click();", gainers_element)
                    time_module.sleep(3)  # Wait longer for content to load after click
                    logger.info("Successfully clicked Gainers button")
                    
                except TimeoutException:
                    logger.info("No specific Gainers button found - data might be already visible")
                    
            except Exception as e:
                logger.warning(f"Could not click Gainers button: {e}")
            
            # Get page source and parse with BeautifulSoup
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Parse gainers data from CNN's HTML structure
            gainers = self._parse_movers_data(soup, "gainers", limit)
            
            time_module.sleep(self.delay_seconds)
            return gainers
            
        except WebDriverException as e:
            logger.error(f"Selenium error fetching CNN after-hours gainers: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing CNN after-hours gainers: {e}")
            return []
        finally:
            self._cleanup_driver()
    
    def get_after_hours_losers(self, limit: int = 10) -> List[Dict[str, any]]:
        """
        Get top after-hours losing stocks from CNN Markets using Selenium
        
        Args:
            limit: Number of top after-hours losers to return
            
        Returns:
            List of dictionaries with after-hours loser data
        """
        try:
            self._setup_driver()
            
            logger.info(f"Loading CNN after-hours page: {self.base_url}")
            self.driver.get(self.base_url)
            
            # Wait for page to load and check if we got blocked
            time_module.sleep(3)
            
            # Check for common blocking indicators
            page_source = self.driver.page_source.lower()
            if ("451" in page_source and ("unavailable" in page_source or "blocked" in page_source)):
                logger.warning("CNN page appears to be blocked or unavailable")
                return []
            
            # Wait for content to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except TimeoutException:
                logger.warning("Timeout waiting for CNN page to load")
                return []
            
            # Try to click the "Losers" button/tab if it exists
            try:
                # Look for Losers button/tab - try common selectors
                losers_selectors = [
                    "//button[contains(text(), 'Loser')]",
                    "//a[contains(text(), 'Loser')]", 
                    "//span[contains(text(), 'Loser')]",
                    "//div[contains(text(), 'Loser')]",
                    "//*[contains(@class, 'loser')]",
                    "//*[contains(@data-tab, 'loser')]"
                ]
                
                losers_element = None
                for selector in losers_selectors:
                    try:
                        losers_element = WebDriverWait(self.driver, 2).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        break
                    except TimeoutException:
                        continue
                
                if losers_element:
                    logger.info("Found and clicking Losers button")
                    # Try clicking with JavaScript to avoid interception
                    try:
                        self.driver.execute_script("arguments[0].click();", losers_element)
                        time_module.sleep(2)  # Wait for content to load after click
                        logger.info("Successfully clicked Losers button")
                    except Exception as click_error:
                        logger.warning(f"JavaScript click failed: {click_error}")
                        # Fallback to regular click
                        try:
                            losers_element.click()
                            time_module.sleep(2)
                        except Exception as fallback_error:
                            logger.warning(f"Regular click also failed: {fallback_error}")
                else:
                    logger.info("No Losers button found - data might be already visible")
                    
            except Exception as e:
                logger.warning(f"Could not click Losers button: {e}")
            
            # Get page source and parse with BeautifulSoup
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Parse losers data from CNN's HTML structure
            losers = self._parse_movers_data(soup, "losers", limit)
            
            time_module.sleep(self.delay_seconds)
            return losers
            
        except WebDriverException as e:
            logger.error(f"Selenium error fetching CNN after-hours losers: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing CNN after-hours losers: {e}")
            return []
        finally:
            self._cleanup_driver()
    
    def is_after_hours_session(self) -> bool:
        """
        Check if we're currently in after-hours trading session (4 PM - 8 PM ET)
        
        Returns:
            True if currently in after-hours trading period
        """
        et_tz = pytz.timezone('America/New_York')
        now_et = datetime.now(et_tz).time()
        
        after_hours_start = time(16, 0)  # 4:00 PM ET
        after_hours_end = time(20, 0)    # 8:00 PM ET
        
        return after_hours_start <= now_et <= after_hours_end
    
    def get_session_info(self) -> Dict[str, any]:
        """
        Get information about the current trading session and CNN data source
        
        Returns:
            Dictionary with session and source metadata
        """
        et_tz = pytz.timezone('America/New_York')
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
            "source_name": "CNN Markets After Hours",
            "source_url": self.base_url,
            "data_delay": "real_time",  # Assumption - would need to verify
            "last_updated": now_et,
            "timezone": "America/New_York"
        }
    
    def is_source_accessible(self) -> bool:
        """
        Check if CNN Markets after-hours page is currently accessible using Selenium
        
        Returns:
            True if source can be reached and loads properly
        """
        try:
            self._setup_driver()
            self.driver.get(self.base_url)
            
            # Wait a moment for page to load
            time_module.sleep(2)
            
            # Check for blocking indicators
            page_source = self.driver.page_source.lower()
            
            # If we see these indicators, the site is blocked
            if ("451" in page_source and ("unavailable" in page_source or "blocked" in page_source)):
                return False
                
            # If we can find a body tag and page title contains expected content, the page loaded
            try:
                self.driver.find_element(By.TAG_NAME, "body")
                page_title = self.driver.title.lower()
                logger.info(f"Page title: '{page_title}'")
                result = "after-hours" in page_title or "stock" in page_title or "markets" in page_title
                logger.info(f"Title check result: {result}")
                return result
            except Exception as e:
                logger.error(f"Body/title check failed: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Accessibility check failed: {e}")
            return False
        finally:
            self._cleanup_driver()
    
    def _parse_movers_data(self, soup: BeautifulSoup, mover_type: str, limit: int) -> List[Dict[str, any]]:
        """
        Parse gainers or losers data from CNN's HTML structure
        
        Args:
            soup: BeautifulSoup object of the page
            mover_type: "gainers" or "losers"
            limit: Number of results to return
            
        Returns:
            List of parsed mover data
        """
        movers = []
        
        try:
            # Find the after-hours stock movers table
            # CNN uses specific class names for their market ticker component
            table_container = soup.select_one('.basic-table__container-view-21fmzH')
            
            if not table_container:
                logger.warning("Could not find CNN after-hours table container")
                return []
            
            # Find all stock rows in the table
            stock_rows = table_container.select('.basic-table__entry-GjSB5a')[:limit]
            logger.info(f"Found {len(stock_rows)} stock rows for {mover_type}")
            
            for row in stock_rows:
                try:
                    # Extract symbol from ticker link
                    symbol_link = row.select_one('.ticker a')
                    if not symbol_link:
                        continue
                    symbol = symbol_link.text.strip()
                    
                    # Extract company name from title
                    name_element = row.select_one('.title-container-2Ixr2 .title-2SLlK5')
                    company_name = name_element.text.strip() if name_element else ""
                    
                    # Extract current price
                    price_element = row.select_one('.basic-table__price-2g8cqY')
                    if not price_element:
                        continue
                    current_price = float(price_element.text.strip())
                    
                    # Extract change amount and percentage
                    change_elements = row.select('.basic-table__change-3ipwW5 span')
                    if len(change_elements) < 2:
                        continue
                        
                    change_amount_text = change_elements[0].text.strip()
                    change_percent_text = change_elements[1].text.strip()
                    
                    # Parse change amount (remove + or - and convert to float)
                    change_amount = float(change_amount_text.replace('+', '').replace('-', '').strip())
                    if change_amount_text.startswith('-'):
                        change_amount = -change_amount
                    
                    # Parse percentage (remove % and convert to float)
                    change_percent = float(change_percent_text.replace('%', '').strip())
                    if change_amount_text.startswith('-'):
                        change_percent = -change_percent
                    
                    # Extract volume
                    volume_element = row.select_one('.basic-table__volume-3hCUx0')
                    volume_text = volume_element.text.strip() if volume_element else "0"
                    volume = self._parse_volume(volume_text)
                    
                    # Calculate regular close price (current price - change)
                    regular_close = current_price - change_amount
                    
                    mover_data = {
                        "symbol": symbol,
                        "company_name": company_name,
                        "regular_close": regular_close,
                        "after_hours_price": current_price,
                        "after_hours_change": change_amount,
                        "after_hours_change_percent": change_percent,
                        "after_hours_volume": volume,
                        "source": "cnn_markets_after_hours",
                        "timestamp": datetime.now(),
                        "session": "after_hours"
                    }
                    
                    movers.append(mover_data)
                    logger.debug(f"Parsed {symbol}: ${current_price} ({change_percent:+.2f}%)")
                    
                except Exception as e:
                    logger.warning(f"Error parsing stock row: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error finding {mover_type} data in CNN page: {e}")
        
        return movers
    
    def _parse_volume(self, volume_text: str) -> int:
        """
        Parse volume string like "1.2M" or "850K" to integer
        
        Args:
            volume_text: Volume string from webpage
            
        Returns:
            Volume as integer
        """
        try:
            volume_text = volume_text.upper().replace(',', '')
            
            if 'M' in volume_text:
                return int(float(volume_text.replace('M', '')) * 1_000_000)
            elif 'K' in volume_text:
                return int(float(volume_text.replace('K', '')) * 1_000)
            else:
                return int(volume_text)
        except:
            return 0