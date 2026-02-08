"""SEC EDGAR adapter for bulk fundamentals data.

Fetches company fundamentals (SIC codes, shares outstanding, company names)
from SEC EDGAR bulk downloads. Market cap is calculated from shares × price.

Data sources (all free, no API key required):
- company_tickers_exchange.json: ticker → CIK mapping
- submissions/CIK{cik}.json: SIC code + description per company
- XBRL Frames API: shares outstanding for all filers
- yfinance bulk download: last prices for market cap calculation
"""

import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
import yfinance as yf

logger = logging.getLogger(__name__)

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_XBRL_FRAMES_URL = "https://data.sec.gov/api/xbrl/frames/dei/EntityCommonStockSharesOutstanding/shares/CY{year}Q{quarter}I.json"


class RateLimiter:
    """Token bucket rate limiter for SEC's 10 req/sec limit."""

    def __init__(self, max_per_second: float = 9.0):
        self._lock = threading.Lock()
        self._min_interval = 1.0 / max_per_second
        self._last_call = 0.0

    def acquire(self):
        with self._lock:
            now = time.monotonic()
            wait = self._last_call + self._min_interval - now
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()


class EdgarFundamentalsAdapter:
    """Fetches bulk fundamentals from SEC EDGAR.

    Unlike per-ticker providers, this adapter downloads data in bulk:
    1. Ticker→CIK mapping (single bulk download)
    2. SIC codes via submissions (parallel with rate limiting)
    3. Shares outstanding via XBRL frames (single bulk download)
    4. Market cap calculated from shares × last price (yfinance bulk)
    """

    def __init__(self, user_agent: str = "TradeScout research@tradescout.dev"):
        self._headers = {"User-Agent": user_agent}
        self._rate_limiter = RateLimiter(max_per_second=9.0)
        self._session = requests.Session()
        self._session.headers.update(self._headers)

    def fetch_bulk_fundamentals(
        self,
        symbols: List[str],
        progress=None,
    ) -> Dict[str, dict]:
        """Fetch fundamentals for all symbols via SEC EDGAR bulk data.

        Args:
            symbols: List of ticker symbols to fetch fundamentals for
            progress: Optional progress reporter

        Returns:
            Dict mapping symbol to fundamentals data dict with keys:
            name, sic_code, sic_description, market_cap, shares_outstanding
        """
        results = {}

        # Phase 1: Download ticker → CIK mapping
        logger.info("Downloading SEC EDGAR ticker→CIK mapping...")
        ticker_to_cik, cik_to_name = self._download_ticker_cik_map()
        if not ticker_to_cik:
            logger.error("Failed to download ticker→CIK mapping")
            return results

        # Filter to only symbols we care about
        matched_symbols = {s: ticker_to_cik[s] for s in symbols if s in ticker_to_cik}
        unmatched = set(symbols) - set(matched_symbols)
        if unmatched:
            logger.info(f"{len(unmatched)} symbols have no SEC CIK match (ETFs, foreign, etc.)")
        logger.info(f"Matched {len(matched_symbols)}/{len(symbols)} symbols to CIKs")

        # Phase 2: Download XBRL frames for shares outstanding (bulk)
        logger.info("Downloading XBRL shares outstanding data...")
        cik_to_shares = self._download_shares_outstanding()
        logger.info(f"Got shares outstanding for {len(cik_to_shares)} filers")

        # Phase 3: Fetch SIC codes from submissions (parallel, rate-limited)
        unique_ciks = set(matched_symbols.values())
        logger.info(f"Fetching SIC codes for {len(unique_ciks)} companies (10 req/sec)...")
        cik_to_sic = self._fetch_sic_codes_parallel(unique_ciks, progress)
        logger.info(f"Got SIC codes for {len(cik_to_sic)} companies")

        # Phase 4: Bulk download last prices via yfinance
        symbols_needing_price = [s for s in matched_symbols if matched_symbols[s] in cik_to_shares]
        symbol_to_price = {}
        if symbols_needing_price:
            logger.info(f"Downloading last prices for {len(symbols_needing_price)} symbols...")
            symbol_to_price = self._download_last_prices(symbols_needing_price)
            logger.info(f"Got prices for {len(symbol_to_price)} symbols")

        # Phase 5: Assemble results
        for symbol, cik in matched_symbols.items():
            sic_info = cik_to_sic.get(cik, {})
            shares = cik_to_shares.get(cik)
            price = symbol_to_price.get(symbol)

            market_cap = None
            if shares and price:
                market_cap = int(shares * price)

            results[symbol] = {
                "name": cik_to_name.get(cik, symbol),
                "sic_code": sic_info.get("sic", ""),
                "sic_description": sic_info.get("sic_description", ""),
                "market_cap": market_cap,
                "shares_outstanding": shares,
            }

        logger.info(f"Assembled fundamentals for {len(results)} symbols")
        return results

    def _download_ticker_cik_map(self) -> Tuple[Dict[str, int], Dict[int, str]]:
        """Download SEC ticker→CIK mapping file.

        Returns:
            Tuple of (ticker→CIK dict, CIK→company_name dict)
        """
        try:
            resp = self._session.get(SEC_TICKERS_URL, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            fields = data.get("fields", [])
            rows = data.get("data", [])

            cik_idx = fields.index("cik")
            name_idx = fields.index("name")
            ticker_idx = fields.index("ticker")

            ticker_to_cik = {}
            cik_to_name = {}
            for row in rows:
                ticker = row[ticker_idx]
                cik = row[cik_idx]
                name = row[name_idx]
                if ticker and cik:
                    ticker_to_cik[ticker.upper()] = cik
                    cik_to_name[cik] = name

            logger.info(f"Downloaded {len(ticker_to_cik)} ticker→CIK mappings")
            return ticker_to_cik, cik_to_name

        except Exception as e:
            logger.error(f"Failed to download ticker→CIK mapping: {e}")
            return {}, {}

    def _download_shares_outstanding(self) -> Dict[int, int]:
        """Download shares outstanding from XBRL Frames API.

        Tries recent quarters until data is found.

        Returns:
            Dict mapping CIK to shares outstanding
        """
        now = datetime.now()
        year = now.year
        quarter = (now.month - 1) // 3

        # Try current and recent quarters (most recent filing period)
        periods_to_try = []
        for offset in range(4):
            q = quarter - offset
            y = year
            while q < 1:
                q += 4
                y -= 1
            periods_to_try.append((y, q))

        cik_to_shares = {}
        for y, q in periods_to_try:
            url = SEC_XBRL_FRAMES_URL.format(year=y, quarter=q)
            try:
                self._rate_limiter.acquire()
                resp = self._session.get(url, timeout=30)
                if resp.status_code != 200:
                    logger.debug(f"XBRL frames CY{y}Q{q}I: status {resp.status_code}")
                    continue

                data = resp.json()
                records = data.get("data", [])
                for record in records:
                    cik = record.get("cik")
                    val = record.get("val")
                    if cik and val and cik not in cik_to_shares:
                        cik_to_shares[cik] = int(val)

                logger.info(f"XBRL frames CY{y}Q{q}I: {len(records)} records")

            except Exception as e:
                logger.warning(f"Failed to fetch XBRL frames CY{y}Q{q}I: {e}")
                continue

        return cik_to_shares

    def _fetch_sic_codes_parallel(
        self,
        ciks: set,
        progress=None,
    ) -> Dict[int, dict]:
        """Fetch SIC codes from SEC submissions in parallel.

        Args:
            ciks: Set of CIK numbers to fetch
            progress: Optional progress reporter

        Returns:
            Dict mapping CIK to {sic, sic_description}
        """
        cik_to_sic = {}
        cik_list = list(ciks)
        total = len(cik_list)
        completed = 0
        errors = 0

        if progress:
            progress.start_operation("Fetching SIC codes from SEC EDGAR", total)

        def fetch_one(cik: int) -> Optional[Tuple[int, dict]]:
            self._rate_limiter.acquire()
            url = SEC_SUBMISSIONS_URL.format(cik=f"{cik:010d}")
            try:
                resp = self._session.get(url, timeout=15)
                if resp.status_code != 200:
                    return None
                data = resp.json()
                sic = data.get("sic", "")
                sic_desc = data.get("sicDescription", "")
                return (cik, {"sic": str(sic), "sic_description": sic_desc})
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(fetch_one, cik): cik for cik in cik_list}

            for future in as_completed(futures):
                completed += 1
                result = future.result()
                if result:
                    cik_to_sic[result[0]] = result[1]
                else:
                    errors += 1

                if progress and completed % 100 == 0:
                    progress.update_progress(completed, total)

        if progress:
            progress.complete_operation(success=True)

        if errors:
            logger.warning(f"Failed to fetch SIC for {errors}/{total} CIKs")

        return cik_to_sic

    def _download_last_prices(self, symbols: List[str], batch_size: int = 500) -> Dict[str, float]:
        """Download last closing prices via yfinance in batches.

        Args:
            symbols: List of ticker symbols
            batch_size: Max symbols per yfinance download call

        Returns:
            Dict mapping symbol to last closing price
        """
        symbol_to_price = {}
        total_batches = (len(symbols) + batch_size - 1) // batch_size

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            batch_num = i // batch_size + 1
            logger.info(f"Downloading prices batch {batch_num}/{total_batches} ({len(batch)} symbols)...")

            try:
                data = yf.download(
                    batch,
                    period="1d",
                    interval="1d",
                    threads=True,
                    progress=False,
                    auto_adjust=False,
                )

                if data.empty:
                    logger.warning(f"Batch {batch_num} returned empty data")
                    continue

                if len(batch) == 1:
                    close = data["Close"].iloc[-1]
                    if close and close > 0:
                        symbol_to_price[batch[0]] = float(close)
                else:
                    for symbol in batch:
                        try:
                            if symbol in data["Close"].columns:
                                close = data["Close"][symbol].iloc[-1]
                                if close and close > 0:
                                    symbol_to_price[symbol] = float(close)
                        except (KeyError, IndexError):
                            continue

            except Exception as e:
                logger.error(f"Batch {batch_num} failed: {e}")

            if batch_num < total_batches:
                time.sleep(2)

        return symbol_to_price

    def get_provider_name(self) -> str:
        return "edgar"
