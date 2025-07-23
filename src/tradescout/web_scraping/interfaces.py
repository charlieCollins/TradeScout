"""
TradeScout Web Scraping Interfaces

Focused interface for scraping after-hours market movers from web sources.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from decimal import Decimal
from datetime import datetime


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