"""
Markets Configuration Manager

Manages supported markets and exchanges configuration for TradeScout.
Currently focused on US markets (NASDAQ and NYSE).
"""

import logging
import yaml
from datetime import datetime, time
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TradingSession(Enum):
    """Trading session types"""

    PREMARKET = "premarket"
    REGULAR = "regular"
    AFTERHOURS = "afterhours"
    CLOSED = "closed"


@dataclass
class MarketHours:
    """Market trading hours configuration"""

    regular_open: time
    regular_close: time
    premarket_start: time
    premarket_end: time
    afterhours_start: time
    afterhours_end: time
    timezone: str


@dataclass
class ExchangeConfig:
    """Configuration for a specific exchange"""

    name: str
    market_id: str
    country: str
    currency: str
    timezone: str
    market_hours: MarketHours
    trading_days: Set[str]
    tick_size: float
    lot_size: int
    supported_assets: List[str]
    priority: int
    enabled: bool


class MarketsManager:
    """
    Manages markets configuration and provides market-related utilities
    """

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize markets manager

        Args:
            config_file: Path to markets config file (optional)
        """
        if config_file is None:
            config_file = Path(__file__).parent / "markets_config.yaml"

        self.config_file = Path(config_file)
        self.config = self._load_config()
        self.exchanges = self._parse_exchanges()

    def _load_config(self) -> Dict:
        """Load markets configuration from YAML file"""
        try:
            with open(self.config_file, "r") as f:
                config = yaml.safe_load(f)
            logger.debug(f"Loaded markets config from {self.config_file}")
            return config
        except Exception as e:
            logger.error(f"Failed to load markets config: {e}")
            return {}

    def _parse_exchanges(self) -> Dict[str, ExchangeConfig]:
        """Parse exchange configurations"""
        exchanges = {}

        if "supported_exchanges" not in self.config:
            logger.warning("No supported exchanges found in config")
            return exchanges

        for exchange_id, exchange_data in self.config["supported_exchanges"].items():
            try:
                # Parse market hours
                regular_hours = exchange_data["regular_hours"]
                extended_hours = exchange_data["extended_hours"]

                market_hours = MarketHours(
                    regular_open=self._parse_time(regular_hours["open"]),
                    regular_close=self._parse_time(regular_hours["close"]),
                    premarket_start=self._parse_time(extended_hours["premarket_start"]),
                    premarket_end=self._parse_time(extended_hours["premarket_end"]),
                    afterhours_start=self._parse_time(
                        extended_hours["afterhours_start"]
                    ),
                    afterhours_end=self._parse_time(extended_hours["afterhours_end"]),
                    timezone=exchange_data["timezone"],
                )

                # Create exchange config
                exchange_config = ExchangeConfig(
                    name=exchange_data["name"],
                    market_id=exchange_data["market_id"],
                    country=exchange_data["country"],
                    currency=exchange_data["currency"],
                    timezone=exchange_data["timezone"],
                    market_hours=market_hours,
                    trading_days=set(exchange_data["trading_days"]),
                    tick_size=exchange_data["tick_size"],
                    lot_size=exchange_data["lot_size"],
                    supported_assets=exchange_data["supported_assets"],
                    priority=exchange_data["priority"],
                    enabled=exchange_data["enabled"],
                )

                exchanges[exchange_id] = exchange_config
                logger.debug(f"Configured exchange: {exchange_id}")

            except Exception as e:
                logger.error(f"Failed to parse exchange config for {exchange_id}: {e}")

        return exchanges

    def _parse_time(self, time_str: str) -> time:
        """Parse time string (HH:MM) to time object"""
        hour, minute = map(int, time_str.split(":"))
        return time(hour, minute)

    def get_supported_exchanges(self) -> List[str]:
        """Get list of supported exchange IDs"""
        return [eid for eid, config in self.exchanges.items() if config.enabled]

    def get_exchange_config(self, exchange_id: str) -> Optional[ExchangeConfig]:
        """Get configuration for specific exchange"""
        return self.exchanges.get(exchange_id)

    def is_supported_exchange(self, exchange_id: str) -> bool:
        """Check if exchange is supported and enabled"""
        config = self.get_exchange_config(exchange_id)
        return config is not None and config.enabled

    def get_primary_exchanges(self) -> List[str]:
        """Get primary focus exchanges (NASDAQ, NYSE)"""
        primary = self.config.get("market_categories", {}).get("primary_focus", [])
        return [eid for eid in primary if self.is_supported_exchange(eid)]

    def get_candidate_identification_markets(self) -> List[str]:
        """Get markets where we identify trading candidates (NASDAQ, NYSE only)"""
        candidate_config = self.config.get("market_categories", {}).get(
            "candidate_identification", {}
        )
        candidate_markets = candidate_config.get("markets", [])
        return [eid for eid in candidate_markets if self.is_supported_exchange(eid)]

    def is_candidate_market(self, exchange_id: str) -> bool:
        """Check if exchange is used for candidate identification"""
        return exchange_id in self.get_candidate_identification_markets()

    def get_current_trading_session(
        self, exchange_id: str = "nasdaq"
    ) -> TradingSession:
        """
        Get current trading session for an exchange

        Args:
            exchange_id: Exchange ID (defaults to NASDAQ)

        Returns:
            Current trading session
        """
        config = self.get_exchange_config(exchange_id)
        if not config:
            return TradingSession.CLOSED

        now = datetime.now()
        current_time = now.time()
        current_weekday = now.strftime("%A").lower()

        # Check if it's a trading day
        if current_weekday not in config.trading_days:
            return TradingSession.CLOSED

        hours = config.market_hours

        # Check trading sessions
        if hours.premarket_start <= current_time < hours.premarket_end:
            return TradingSession.PREMARKET
        elif hours.regular_open <= current_time < hours.regular_close:
            return TradingSession.REGULAR
        elif hours.afterhours_start <= current_time < hours.afterhours_end:
            return TradingSession.AFTERHOURS
        else:
            return TradingSession.CLOSED

    def is_market_open(self, exchange_id: str = "nasdaq") -> bool:
        """Check if market is currently open (regular hours)"""
        return self.get_current_trading_session(exchange_id) == TradingSession.REGULAR

    def is_extended_hours_active(self, exchange_id: str = "nasdaq") -> bool:
        """Check if extended hours trading is active"""
        session = self.get_current_trading_session(exchange_id)
        return session in [TradingSession.PREMARKET, TradingSession.AFTERHOURS]

    def is_after_hours_active(self, exchange_id: str = "nasdaq") -> bool:
        """Check if after-hours trading is active"""
        return (
            self.get_current_trading_session(exchange_id) == TradingSession.AFTERHOURS
        )

    def is_premarket_active(self, exchange_id: str = "nasdaq") -> bool:
        """Check if pre-market trading is active"""
        return self.get_current_trading_session(exchange_id) == TradingSession.PREMARKET

    def get_supported_asset_types(self, exchange_id: str) -> List[str]:
        """Get supported asset types for an exchange"""
        config = self.get_exchange_config(exchange_id)
        return config.supported_assets if config else []

    def get_data_requirements(self) -> Dict:
        """Get data requirements for analysis"""
        return self.config.get("data_requirements", {})

    def get_analysis_focus(self) -> Dict:
        """Get analysis focus configuration"""
        return self.config.get("analysis_focus", {})

    def meets_minimum_requirements(
        self, volume: int, price: float, market_cap: Optional[int] = None
    ) -> bool:
        """
        Check if a security meets minimum requirements for analysis

        Args:
            volume: Daily trading volume
            price: Current stock price
            market_cap: Market capitalization (optional)

        Returns:
            True if meets requirements, False otherwise
        """
        requirements = self.get_data_requirements()

        if volume < requirements.get("minimum_volume", 0):
            return False

        if price < requirements.get("minimum_price", 0):
            return False

        if market_cap is not None:
            min_market_cap = requirements.get("minimum_market_cap", 0)
            if market_cap < min_market_cap:
                return False

        return True


# Global instance for easy access
_markets_manager = None


def get_markets_manager() -> MarketsManager:
    """Get global markets manager instance"""
    global _markets_manager
    if _markets_manager is None:
        _markets_manager = MarketsManager()
    return _markets_manager
