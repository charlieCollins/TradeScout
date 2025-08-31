import logging
from tradescout.data_sources_scraping.tipranks_after_hours_scraper import TipRanksAfterHoursScraper
from tradescout.data_sources_scraping.advfn_after_hours_scraper import ADVFNAfterHoursScraper
from tradescout.data_sources_scraping.investing_com_after_hours_scraper import InvestingComAfterHoursScraper
from tradescout.data_sources_scraping.cnn_after_hours_scraper import CNNAfterHoursScraper
from tradescout.data_sources_scraping.marketwatch_after_hours_scraper import MarketWatchAfterHoursScraper

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def run_debug():
    log.info("--- Starting Scraper Initialization Debug ---")

    scrapers_to_test = {
        "TipRanks": TipRanksAfterHoursScraper,
        "ADVFN": ADVFNAfterHoursScraper,
        "Investing.com": InvestingComAfterHoursScraper,
        "CNN": CNNAfterHoursScraper,
        "MarketWatch": MarketWatchAfterHoursScraper,
    }

    for name, scraper_class in scrapers_to_test.items():
        log.info(f"--- Testing {name} Scraper ---")
        try:
            log.info(f"Initializing {name} scraper...")
            # We only need to test initialization and driver setup
            scraper = scraper_class(headless=True)
            scraper._setup_driver()
            log.info(f"{name} scraper setup driver successfully.")
            scraper._cleanup_driver()
            log.info(f"{name} scraper cleaned up successfully.")
        except Exception as e:
            log.error(f"An error occurred with {name} scraper: {e}", exc_info=True)
        log.info(f"--- Finished Testing {name} Scraper ---")

    log.info("--- Scraper Initialization Debug Finished ---")

if __name__ == "__main__":
    run_debug()
