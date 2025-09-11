"""
Minimal Market Data Interface for TradeScout

This interface defines the contract for market-wide data operations.
All data providers must implement these methods for market analysis.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

from ..data_models.models_market import MarketMover


class MarketDataInterface(ABC):
    """Minimal interface for market-wide data operations"""

    @abstractmethod
    def get_market_gainers(
        self, 
        limit: int = 20,
        force_refresh: bool = False
    ) -> List[MarketMover]:
        """
        Get top market gainers for the current session.
        
        Args:
            limit: Maximum number of gainers to return
            force_refresh: Bypass cache and fetch fresh data
            
        Returns:
            List of top gaining stocks
        """
        pass

    @abstractmethod
    def get_market_losers(
        self,
        limit: int = 20,
        force_refresh: bool = False
    ) -> List[MarketMover]:
        """
        Get top market losers for the current session.
        
        Args:
            limit: Maximum number of losers to return
            force_refresh: Bypass cache and fetch fresh data
            
        Returns:
            List of top losing stocks
        """
        pass

    @abstractmethod
    def get_most_active(
        self,
        limit: int = 20,
        force_refresh: bool = False
    ) -> List[MarketMover]:
        """
        Get most actively traded stocks by volume.
        
        Args:
            limit: Maximum number of stocks to return
            force_refresh: Bypass cache and fetch fresh data
            
        Returns:
            List of most active stocks
        """
        pass

    @abstractmethod
    def get_market_snapshot(
        self,
        force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get complete market snapshot with all tickers.
        
        Args:
            force_refresh: Bypass cache and fetch fresh data
            
        Returns:
            Dictionary with full market data or None
        """
        pass