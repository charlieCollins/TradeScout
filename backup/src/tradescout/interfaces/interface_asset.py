"""
Minimal Asset Data Interface for TradeScout

This interface defines the contract for asset-specific data operations.
All data providers must implement these methods for individual asset queries.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any

from ..data_models.models_asset import Asset, PriceData


class AssetDataInterface(ABC):
    """Minimal interface for asset-specific data operations"""

    @abstractmethod
    def get_current_quote(self, symbol: str) -> Optional[PriceData]:
        """
        Get current price data for a single asset.
        Returns the most recent price available, including extended hours.

        Args:
            symbol: Stock ticker symbol (e.g., 'AAPL')

        Returns:
            Current price data with latest available price or None if unavailable
        """
        pass

    @abstractmethod
    def get_fundamentals(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get fundamental data for a single asset.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with fundamental metrics or None
        """
        pass

    @abstractmethod
    def get_ohlc(
        self, symbol: str, date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get OHLC (Open, High, Low, Close) data for a specific date.

        Args:
            symbol: Stock ticker symbol
            date: Date string (defaults to today if None)

        Returns:
            Dictionary with OHLC data or None
        """
        pass
