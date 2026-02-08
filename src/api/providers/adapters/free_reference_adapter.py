"""Composite free reference data adapter.

Combines NASDAQ Trader (bulk ticker listing) with YFinance (single-ticker details)
to implement the full ReferenceDataProvider protocol without any paid APIs.
"""

import logging
from typing import Optional, List, Dict, Any

from models.dataclass.asset import Asset
from models.dataclass.market import Market
from api.providers.protocols.reference_data_provider import ReferenceDataProvider
from api.providers.adapters.yfinance_reference_adapter import (
    YFinanceReferenceAdapter,
    US_EXCHANGES,
)
from api.providers.adapters.nasdaq_trader_parser import (
    fetch_nasdaqtraded_file,
    parse_nasdaqtraded,
)

logger = logging.getLogger(__name__)


class FreeReferenceAdapter(ReferenceDataProvider):
    """Composite adapter combining NASDAQ Trader + YFinance.

    - fetch_all_tickers(): NASDAQ Trader nasdaqtraded.txt (all US securities)
    - fetch_all_exchanges(): Hardcoded NYSE/NASDAQ
    - fetch_ticker_details(): YFinance single-ticker lookup
    - fetch_ticker_details_raw(): YFinance raw .info dict
    """

    def __init__(self):
        self._yfinance = YFinanceReferenceAdapter()

    def fetch_all_tickers(
        self,
        market: str = "stocks",
        active: bool = True,
        limit: Optional[int] = None,
        market_code_to_id: Optional[Dict[str, int]] = None
    ) -> List[Asset]:
        """Fetch all US-listed tickers from NASDAQ Trader.

        Args:
            market: Ignored (NASDAQ Trader covers all US markets)
            active: Ignored (NASDAQ Trader only lists active securities)
            limit: Ignored (returns all)
            market_code_to_id: Mapping of MIC codes to DB market IDs.
                Must include "__provider_id__" key.

        Returns:
            List of Asset objects for all US-listed securities
        """
        if not market_code_to_id:
            raise ValueError("market_code_to_id is required for NASDAQ Trader parsing")

        provider_id = market_code_to_id.get("__provider_id__")
        if provider_id is None:
            raise ValueError("market_code_to_id must include '__provider_id__' key")

        text = fetch_nasdaqtraded_file()
        return parse_nasdaqtraded(text, market_code_to_id, provider_id)

    def fetch_all_exchanges(
        self,
        asset_class: str = "stocks",
        locale: str = "us"
    ) -> List[Market]:
        """Return hardcoded US exchanges (NYSE, NASDAQ).

        Args:
            asset_class: Ignored
            locale: Only 'us' supported

        Returns:
            List of Market objects for NYSE and NASDAQ
        """
        if locale != "us":
            logger.warning(f"Only US exchanges supported, got locale={locale}")
            return []
        return US_EXCHANGES

    def fetch_ticker_details(
        self,
        symbol: str,
        market_code_to_id: Optional[Dict[str, int]] = None
    ) -> Optional[Asset]:
        """Fetch single ticker details via YFinance."""
        return self._yfinance.fetch_ticker_details(symbol, market_code_to_id)

    def fetch_ticker_details_raw(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch raw ticker details via YFinance."""
        return self._yfinance.fetch_ticker_details_raw(symbol)

    def get_provider_name(self) -> str:
        return "nasdaq_trader"
