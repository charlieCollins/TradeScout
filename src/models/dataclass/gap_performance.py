"""Gap candidate result model objects.

Model objects for tracking actual intraday performance of gap candidates:
- Performance metrics (entry/exit, high/low, returns)
- Gap fill detection
- Outcome classification
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from enum import Enum


class PerformanceOutcome(Enum):
    """Performance outcome classification."""
    WINNER = "winner"      # ≥2% return
    LOSER = "loser"        # ≤-1% return
    BREAKEVEN = "breakeven"  # Between -1% and +2%


@dataclass
class GapCandidateResult:
    """Performance tracking for a gap candidate result.

    Tracks actual intraday performance during regular trading hours
    (9:30 AM - 4:00 PM) on the appropriate trading day.

    Trading day determination:
    - Premarket gap: Same day's regular hours
    - Afterhours gap: Next trading day's regular hours
    """

    # Link to gap candidate
    gap_result_id: int

    # Entry/Exit prices (regular hours)
    entry_price: float  # Open at 9:30 AM
    exit_price: float   # Close at 4:00 PM

    # Intraday range
    max_intraday_price: float  # High during 9:30-4:00
    min_intraday_price: float  # Low during 9:30-4:00

    # Gap fill tracking
    gap_filled: bool  # Did price touch reference_price?
    gap_fill_timestamp: Optional[datetime] = None  # When gap filled (NULL if didn't fill)

    # Calculated performance metrics
    realized_return_pct: float = 0.0  # (exit - entry) / entry * 100
    max_upside_pct: float = 0.0       # (high - entry) / entry * 100
    max_drawdown_pct: float = 0.0     # (low - entry) / entry * 100

    # Outcome classification
    outcome: Optional[PerformanceOutcome] = None

    # Database fields
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        """Calculate derived metrics after initialization."""
        if self.entry_price and self.exit_price:
            self.realized_return_pct = self._calculate_return(self.entry_price, self.exit_price)

        if self.entry_price and self.max_intraday_price:
            self.max_upside_pct = self._calculate_return(self.entry_price, self.max_intraday_price)

        if self.entry_price and self.min_intraday_price:
            self.max_drawdown_pct = self._calculate_return(self.entry_price, self.min_intraday_price)

        # Classify outcome
        if self.realized_return_pct >= 2.0:
            self.outcome = PerformanceOutcome.WINNER
        elif self.realized_return_pct <= -1.0:
            self.outcome = PerformanceOutcome.LOSER
        else:
            self.outcome = PerformanceOutcome.BREAKEVEN

    @staticmethod
    def _calculate_return(entry: float, exit: float) -> float:
        """Calculate percentage return."""
        if entry == 0:
            return 0.0
        return ((exit - entry) / entry) * 100

    @property
    def is_winner(self) -> bool:
        """Check if outcome is winner."""
        return self.outcome == PerformanceOutcome.WINNER

    @property
    def is_loser(self) -> bool:
        """Check if outcome is loser."""
        return self.outcome == PerformanceOutcome.LOSER

    @property
    def is_breakeven(self) -> bool:
        """Check if outcome is breakeven."""
        return self.outcome == PerformanceOutcome.BREAKEVEN
