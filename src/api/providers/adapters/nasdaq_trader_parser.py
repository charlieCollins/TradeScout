"""NASDAQ Trader file parser for bulk ticker data.

Downloads and parses nasdaqtraded.txt from NASDAQ Trader,
which contains ALL US-listed securities across NYSE, NASDAQ,
NYSE Arca, NYSE Amex, and BATS exchanges.

Source: https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt
Format: Pipe-delimited text, updated daily
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime

import requests

from models.dataclass.asset import Asset, AssetType, AssetClass

logger = logging.getLogger(__name__)

NASDAQTRADED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"

# Map NASDAQ Trader listing exchange codes to MIC codes
EXCHANGE_CODE_TO_MIC = {
    "Q": "XNAS",  # NASDAQ Global Select Market
    "G": "XNAS",  # NASDAQ Global Market
    "S": "XNAS",  # NASDAQ Capital Market
    "N": "XNYS",  # NYSE
    "A": "XNYS",  # NYSE American (Amex)
    "P": "XNYS",  # NYSE Arca
    "Z": "XNYS",  # BATS
}


def fetch_nasdaqtraded_file(url: str = NASDAQTRADED_URL, timeout: int = 30) -> str:
    """Download nasdaqtraded.txt from NASDAQ Trader.

    Args:
        url: URL to fetch (default: official NASDAQ Trader URL)
        timeout: Request timeout in seconds

    Returns:
        Raw text content of the file

    Raises:
        requests.RequestException: On network/HTTP errors
    """
    logger.info(f"Downloading NASDAQ Trader file from {url}")
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    logger.info(f"Downloaded {len(response.text)} bytes")
    return response.text


def parse_nasdaqtraded(
    text: str,
    market_code_to_id: Dict[str, int],
    provider_id: int
) -> List[Asset]:
    """Parse nasdaqtraded.txt content into Asset objects.

    Args:
        text: Raw text content of nasdaqtraded.txt
        market_code_to_id: Mapping of MIC codes (XNYS, XNAS) to database market IDs
        provider_id: Database provider ID for the nasdaq_trader provider

    Returns:
        List of Asset objects ready for database storage
    """
    lines = text.strip().split("\n")

    if len(lines) < 2:
        logger.warning("NASDAQ Trader file appears empty or malformed")
        return []

    # First line is the header
    header = lines[0].split("|")
    logger.debug(f"Header columns: {header}")

    # Find column indices
    col_map = {name.strip(): idx for idx, name in enumerate(header)}

    required_cols = ["Symbol", "Security Name", "Listing Exchange", "ETF", "Test Issue"]
    for col in required_cols:
        if col not in col_map:
            logger.error(f"Missing required column '{col}' in NASDAQ Trader file")
            return []

    sym_idx = col_map["Symbol"]
    name_idx = col_map["Security Name"]
    exchange_idx = col_map["Listing Exchange"]
    etf_idx = col_map["ETF"]
    test_idx = col_map["Test Issue"]
    lot_idx = col_map.get("Round Lot Size")
    traded_idx = col_map.get("Nasdaq Traded")

    assets = []
    skipped_test = 0
    skipped_exchange = 0
    skipped_not_traded = 0
    now = datetime.now()

    # Process data lines (skip header, skip trailing timestamp line)
    for line in lines[1:]:
        # Skip empty lines and the trailing "File Creation Time:" line
        if not line.strip() or line.startswith("File Creation Time"):
            continue

        fields = line.split("|")
        if len(fields) < len(required_cols):
            continue

        # Skip test issues
        if fields[test_idx].strip() == "Y":
            skipped_test += 1
            continue

        # Skip if not NASDAQ-traded (if column exists)
        if traded_idx is not None and fields[traded_idx].strip() != "Y":
            skipped_not_traded += 1
            continue

        symbol = fields[sym_idx].strip()
        name = fields[name_idx].strip()
        exchange_code = fields[exchange_idx].strip()
        is_etf = fields[etf_idx].strip() == "Y"

        if not symbol or not name:
            continue

        # Map exchange code to MIC
        mic_code = EXCHANGE_CODE_TO_MIC.get(exchange_code)
        if not mic_code:
            skipped_exchange += 1
            logger.debug(f"Unknown exchange code '{exchange_code}' for {symbol}, skipping")
            continue

        # Resolve market_id
        market_id = market_code_to_id.get(mic_code)
        if market_id is None:
            skipped_exchange += 1
            logger.debug(f"No market_id for MIC '{mic_code}' (symbol {symbol}), skipping")
            continue

        # Determine asset type
        asset_type = AssetType.ETF if is_etf else AssetType.STOCK

        # Parse lot size
        lot_size = 100
        if lot_idx is not None:
            try:
                lot_size = int(fields[lot_idx].strip())
            except (ValueError, IndexError):
                lot_size = 100

        asset = Asset(
            id=0,
            symbol=symbol,
            name=name,
            asset_type=asset_type,
            asset_class=AssetClass.EQUITY,
            market_id=market_id,
            currency="USD",
            provider_id=provider_id,
            created_at=now,
            updated_at=now,
            is_active=True,
            is_delisted=False,
            lot_size=lot_size,
        )
        assets.append(asset)

    logger.info(
        f"Parsed {len(assets)} assets from NASDAQ Trader file "
        f"(skipped: {skipped_test} test, {skipped_exchange} unknown exchange, "
        f"{skipped_not_traded} not traded)"
    )
    return assets
