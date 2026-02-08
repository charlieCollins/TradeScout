"""Yahoo Finance adapter for reference data (tickers, exchanges, fundamentals).

Implements ReferenceDataProvider protocol using yfinance library.
Provides free access to ticker details and fundamentals.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, time

import yfinance as yf

from models.dataclass.asset import Asset, AssetType, AssetClass
from models.dataclass.market import Market
from api.providers.protocols.reference_data_provider import ReferenceDataProvider

logger = logging.getLogger(__name__)

# Mapping of yfinance exchange names to MIC codes
EXCHANGE_TO_MIC = {
    "NYQ": "XNYS",
    "NMS": "XNAS",
    "NGM": "XNAS",
    "NCM": "XNAS",
    "NYS": "XNYS",
    "NAS": "XNAS",
    "PCX": "XNYS",  # NYSE Arca
    "BTS": "XNYS",  # BATS -> NYSE
    "ASE": "XNYS",  # AMEX -> NYSE
}

# Mapping of yfinance quoteType to AssetType
QUOTE_TYPE_MAP = {
    "EQUITY": AssetType.STOCK,
    "ETF": AssetType.ETF,
    "MUTUALFUND": AssetType.FUND,
}

# Hardcoded US exchanges for fetch_all_exchanges
US_EXCHANGES = [
    Market(
        id=0,
        code="XNYS",
        name="New York Stock Exchange",
        country="US",
        timezone="America/New_York",
        currency="USD",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        premarket_start_time=time(4, 0),
        premarket_end_time=time(9, 30),
        regular_open_time=time(9, 30),
        regular_close_time=time(16, 0),
        afterhours_start_time=time(16, 0),
        afterhours_end_time=time(20, 0),
        is_active=True,
    ),
    Market(
        id=0,
        code="XNAS",
        name="Nasdaq",
        country="US",
        timezone="America/New_York",
        currency="USD",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        premarket_start_time=time(4, 0),
        premarket_end_time=time(9, 30),
        regular_open_time=time(9, 30),
        regular_close_time=time(16, 0),
        afterhours_start_time=time(16, 0),
        afterhours_end_time=time(20, 0),
        is_active=True,
    ),
]


class YFinanceReferenceAdapter(ReferenceDataProvider):
    """Adapter for Yahoo Finance reference data.

    Implements ReferenceDataProvider protocol using yfinance library.

    Capabilities:
    - Ticker details and fundamentals via Ticker.info
    - Raw ticker data for bootstrap fundamentals

    Limitations:
    - Cannot list all tickers (no discovery endpoint)
    - Exchange list is hardcoded (NYSE/NASDAQ only)
    - fetch_all_tickers raises NotImplementedError
    """

    def fetch_ticker_details(
        self,
        symbol: str,
        market_code_to_id: Optional[Dict[str, int]] = None
    ) -> Optional[Asset]:
        """Fetch ticker details from Yahoo Finance.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            market_code_to_id: Mapping of market codes to database IDs

        Returns:
            Asset object or None if error
        """
        try:
            logger.debug(f"Fetching ticker details for {symbol} from yfinance")
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if not info or info.get("regularMarketPrice") is None:
                logger.warning(f"No data returned from yfinance for {symbol}")
                return None

            return self._transform_to_asset(symbol, info, market_code_to_id)

        except Exception as e:
            logger.error(f"Error fetching ticker details for {symbol}: {e}")
            return None

    def fetch_ticker_details_raw(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch raw ticker details from Yahoo Finance.

        Returns the full yfinance .info dict which includes fundamentals.

        Args:
            symbol: Stock symbol

        Returns:
            Raw ticker data dict or None if error
        """
        try:
            logger.debug(f"Fetching raw ticker details for {symbol} from yfinance")
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if not info:
                return None

            return info

        except Exception as e:
            logger.error(f"Error fetching raw ticker details for {symbol}: {e}")
            return None

    def fetch_all_tickers(
        self,
        market: str = "stocks",
        active: bool = True,
        limit: Optional[int] = None,
        market_code_to_id: Optional[Dict[str, int]] = None
    ) -> List[Asset]:
        """Not available via yfinance - no ticker discovery endpoint.

        The database should already be bootstrapped with tickers from initial setup.
        For re-bootstrapping, use FreeReferenceAdapter (NASDAQ Trader) which supports bulk listing.

        Raises:
            NotImplementedError: Always - yfinance cannot list all tickers
        """
        raise NotImplementedError(
            "yfinance does not support listing all tickers. "
            "Use FreeReferenceAdapter (NASDAQ Trader) for ticker bootstrap."
        )

    def fetch_all_exchanges(
        self,
        asset_class: str = "stocks",
        locale: str = "us"
    ) -> List[Market]:
        """Return hardcoded US exchanges.

        yfinance doesn't have an exchange listing endpoint.
        Returns NYSE and NASDAQ which cover the TradeScout use case.

        Args:
            asset_class: Asset class filter (ignored - always returns stock exchanges)
            locale: Locale filter (only 'us' supported)

        Returns:
            List of Market objects for NYSE and NASDAQ
        """
        if locale != "us":
            logger.warning(f"Only US exchanges supported, got locale={locale}")
            return []

        return US_EXCHANGES

    def _transform_to_asset(
        self,
        symbol: str,
        info: dict,
        market_code_to_id: Optional[Dict[str, int]] = None
    ) -> Optional[Asset]:
        """Transform yfinance info dict to Asset dataclass.

        Args:
            symbol: Stock symbol
            info: yfinance Ticker.info dictionary
            market_code_to_id: Mapping of market codes to database IDs

        Returns:
            Asset object or None if transformation fails
        """
        try:
            # Determine exchange/market
            exchange = info.get("exchange", "")
            mic_code = EXCHANGE_TO_MIC.get(exchange, "XNAS")

            # Resolve market_id
            market_id = 0
            if market_code_to_id:
                market_id = market_code_to_id.get(mic_code, 0)

            # Determine asset type
            quote_type = info.get("quoteType", "EQUITY")
            asset_type = QUOTE_TYPE_MAP.get(quote_type, AssetType.STOCK)

            name = info.get("longName") or info.get("shortName") or symbol

            return Asset(
                id=0,
                symbol=symbol.upper(),
                name=name,
                asset_type=asset_type,
                asset_class=AssetClass.EQUITY,
                market_id=market_id,
                currency=info.get("currency", "USD"),
                provider_id=0,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                is_active=True,
                is_delisted=False,
            )

        except Exception as e:
            logger.error(f"Error transforming yfinance data for {symbol}: {e}")
            return None

    def get_provider_name(self) -> str:
        return "yfinance"
