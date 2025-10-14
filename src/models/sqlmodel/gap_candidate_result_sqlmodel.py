"""GapCandidateResult SQLModel for database operations.

This model represents gap candidate results (performance outcomes) in the database using SQLModel ORM.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class GapCandidateResultSQLModel(SQLModel, table=True):
    """SQLModel for gap_candidate_result table.

    Tracks actual performance metrics for gap candidate opportunities.
    """

    __tablename__ = "gap_candidate_result"

    id: Optional[int] = Field(default=None, primary_key=True)
    gap_result_id: int = Field(unique=True, index=True)

    # Intraday performance (same day)
    entry_price: Optional[float] = None
    entry_timestamp: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_timestamp: Optional[datetime] = None
    max_intraday_price: Optional[float] = None
    min_intraday_price: Optional[float] = None

    # Performance metrics
    realized_return_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    max_upside_pct: Optional[float] = None
    gap_filled: Optional[bool] = None  # Did price return to reference price?
    gap_fill_timestamp: Optional[datetime] = None

    # Outcome classification
    outcome: Optional[str] = Field(default=None, index=True)  # 'winner', 'loser', 'breakeven', 'not_traded'
    trade_taken: bool = Field(default=False)

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
