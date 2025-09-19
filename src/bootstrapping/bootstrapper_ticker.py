"""Bootstrap all tickers from Polygon API into the database."""

import os
import requests
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TickerBootstrapper:
    """Bootstrap all available tickers from Polygon API."""

    def __init__(self, api_key: Optional[str] = None, db_manager=None):
        """Initialize with API key and database manager."""
        self.api_key = api_key or os.environ.get("POLYGON_API_KEY")
        if not self.api_key:
            raise ValueError("POLYGON_API_KEY environment variable required")

        self.db_manager = db_manager
        self.base_url = "https://api.polygon.io"

    def fetch_all_tickers(self) -> List[Dict[str, Any]]:
        """Fetch all tickers from Polygon reference API with pagination."""
        all_tickers = []
        cursor = None
        page = 1

        logger.info("Starting ticker fetch from Polygon API")

        while True:
            logger.info(f"Fetching page {page}")

            # Build request parameters
            params = {
                "apikey": self.api_key,
                "market": "stocks",  # Only stock market
                "active": "true",    # Only active tickers
                "limit": 1000       # Max results per page
            }

            if cursor:
                params["cursor"] = cursor

            # Make API request
            url = f"{self.base_url}/v3/reference/tickers"
            response = requests.get(url, params=params)
            time.sleep(0.12)  # Rate limiting (5 calls per minute)

            if response.status_code != 200:
                if response.status_code == 429:
                    logger.warning("Rate limit hit, waiting 60 seconds...")
                    time.sleep(60)
                    continue
                else:
                    raise Exception(f"API error: {response.status_code} - {response.text}")

            data = response.json()

            if "results" not in data or not data["results"]:
                logger.info("No more results, pagination complete")
                break

            # Add to collection
            page_results = data["results"]
            all_tickers.extend(page_results)
            logger.debug(f"Page {page}: {len(page_results)} tickers")

            # Check for next page
            cursor = data.get("next_url")
            if cursor and "cursor=" in cursor:
                cursor = cursor.split("cursor=")[1].split("&")[0]
            else:
                logger.info("No next cursor, pagination complete")
                break

            page += 1

        logger.info(f"Total tickers fetched: {len(all_tickers)} across {page} pages")
        return all_tickers

    def upsert_tickers(self, tickers: List[Dict[str, Any]]) -> Dict[str, int]:
        """Upsert tickers into database. Returns statistics."""
        if not self.db_manager:
            raise ValueError("Database manager required for upsert operations")

        stats = {"inserted": 0, "updated": 0, "errors": 0}

        for ticker_data in tickers:
            try:
                # Extract data from Polygon response
                symbol = ticker_data.get("ticker")
                name = ticker_data.get("name")
                market = ticker_data.get("market", "stocks")
                ticker_type = ticker_data.get("type")
                currency = ticker_data.get("currency_name", "USD")
                is_active = ticker_data.get("active", False)

                # Skip if missing required fields
                if not symbol or not name:
                    stats["errors"] += 1
                    continue

                # TODO: Get market_id from markets table based on exchange
                # For now, assume market_id = 1 (will need proper lookup)
                market_id = 1

                # UPSERT logic (simplified - needs actual SQL implementation)
                # This is a placeholder showing the data structure
                asset_data = {
                    "symbol": symbol,
                    "name": name,
                    "market_id": market_id,
                    "asset_type": "stock",  # From config
                    "asset_class": "equity", # From config
                    "currency": currency,
                    "is_active": is_active,
                    "data_source": "polygon"
                }

                # TODO: Implement actual database upsert
                logger.debug(f"Would upsert: {symbol} - {name}")
                stats["inserted"] += 1

            except Exception as e:
                logger.error(f"Error processing ticker {ticker_data.get('ticker', 'unknown')}: {e}")
                stats["errors"] += 1

        logger.info(f"Upsert complete: {stats}")
        return stats

    def bootstrap_all_tickers(self) -> Dict[str, int]:
        """Complete bootstrap process: fetch and upsert all tickers."""
        logger.info("Starting complete ticker bootstrap")

        # Fetch all tickers from API
        tickers = self.fetch_all_tickers()

        # Upsert into database
        stats = self.upsert_tickers(tickers)

        logger.info(f"Bootstrap complete: {len(tickers)} tickers processed")
        return stats