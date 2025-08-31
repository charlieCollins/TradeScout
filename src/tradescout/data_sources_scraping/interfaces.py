"""
TradeScout Web Scraping Interfaces

Interfaces for scraping extended hours market movers from web sources.
Includes both after-hours (4 PM - 8 PM ET) and pre-market (4 AM - 9:30 AM ET) data.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional


class AfterHoursWebScraper(ABC):
    """
    Abstract interface for scraping after-hours gainers and losers from web sources

    Specifically designed to capture extended-hours trading data (4 PM - 8 PM ET)
    for gap trading candidate identification.
    """

    @abstractmethod
    def get_after_hours_gainers(self, limit: int = 10) -> List[Dict[str, any]]:
        """
        Get top after-hours gaining stocks from the web source

        Args:
            limit: Number of top after-hours gainers to return (default: 10)

        Returns:
            List of dictionaries with after-hours gainer data:
            [
                {
                    "symbol": "AAPL",
                    "regular_close": 214.51,
                    "after_hours_price": 217.23,
                    "after_hours_change": 2.72,
                    "after_hours_change_percent": 1.27,
                    "after_hours_volume": 1250000,
                    "source": "yahoo_finance_after_hours",
                    "timestamp": datetime.now(),
                    "session": "after_hours"
                },
                ...
            ]
        """
        pass

    @abstractmethod
    def get_after_hours_losers(self, limit: int = 10) -> List[Dict[str, any]]:
        """
        Get top after-hours losing stocks from the web source

        Args:
            limit: Number of top after-hours losers to return (default: 10)

        Returns:
            List of dictionaries with after-hours loser data (same format as gainers)
        """
        pass

    @abstractmethod
    def is_after_hours_session(self) -> bool:
        """
        Check if we're currently in after-hours trading session (4 PM - 8 PM ET)

        Returns:
            True if currently in after-hours trading period
        """
        pass

    @abstractmethod
    def get_session_info(self) -> Dict[str, any]:
        """
        Get information about the current trading session and data source

        Returns:
            Dictionary with session and source metadata:
            {
                "current_session": "after_hours",  # or "regular", "premarket", "closed"
                "session_start": "4:00 PM ET",
                "session_end": "8:00 PM ET",
                "source_name": "Yahoo Finance After Hours",
                "data_delay": "real_time",
                "last_updated": datetime.now()
            }
        """
        pass


class PreMarketWebScraper(ABC):
    """
    Abstract interface for scraping pre-market gainers and losers from web sources

    Specifically designed to capture pre-market trading data (4 AM - 9:30 AM ET)
    for gap trading candidate identification.
    """

    @abstractmethod
    def get_premarket_gainers(self, limit: int = 10) -> List[Dict[str, any]]:
        """
        Get top pre-market gaining stocks from the web source

        Args:
            limit: Number of top pre-market gainers to return (default: 10)

        Returns:
            List of dictionaries with pre-market gainer data:
            [
                {
                    "symbol": "AAPL",
                    "previous_close": 214.51,
                    "premarket_price": 217.23,
                    "premarket_change": 2.72,
                    "premarket_change_percent": 1.27,
                    "premarket_volume": 850000,
                    "source": "marketwatch_premarket",
                    "timestamp": datetime.now(),
                    "session": "premarket"
                },
                ...
            ]
        """
        pass

    @abstractmethod
    def get_premarket_losers(self, limit: int = 10) -> List[Dict[str, any]]:
        """
        Get top pre-market losing stocks from the web source

        Args:
            limit: Number of top pre-market losers to return (default: 10)

        Returns:
            List of dictionaries with pre-market loser data (same format as gainers)
        """
        pass

    @abstractmethod
    def is_premarket_session(self) -> bool:
        """
        Check if we're currently in pre-market trading session (4 AM - 9:30 AM ET)

        Returns:
            True if currently in pre-market trading period
        """
        pass

    @abstractmethod
    def get_premarket_session_info(self) -> Dict[str, any]:
        """
        Get information about the current pre-market session and data source

        Returns:
            Dictionary with session and source metadata:
            {
                "current_session": "premarket",  # or "regular", "after_hours", "closed"
                "session_start": "4:00 AM ET",
                "session_end": "9:30 AM ET",
                "source_name": "MarketWatch Pre-Market",
                "data_delay": "real_time",
                "last_updated": datetime.now()
            }
        """
        pass
