"""Data update metadata model for TradeScout."""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class OperationStatus(Enum):
    """Operation status enumeration."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class DataUpdateMetadataType(Enum):
    """Data update metadata operation types."""
    FUNDAMENTALS = "fundamentals"
    TICKERS = "tickers"
    UNIVERSES = "universes"
    PROVIDERS = "providers"
    MARKETS = "markets"
    ASSET_PRICES = "asset_prices"
    TICKER_SNAPSHOTS = "ticker_snapshots"
    MARKET_SNAPSHOTS = "market_snapshots"
    MARKET_CONTEXT = "market_context"
    MARKET_HOLIDAYS = "market_holidays"


@dataclass
class DataUpdateMetadata:
    """Represents metadata for a data update operation."""

    # Operation identification
    operation_type: str  # 'fundamentals', 'tickers', 'snapshot', 'universe', 'market_context'
    operation_subtype: Optional[str] = None  # 'bootstrap', 'refresh', 'single_symbol', 'fetch'

    # Run metadata
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Status tracking
    status: OperationStatus = OperationStatus.RUNNING

    # Statistics
    stats: Optional[Dict[str, Any]] = None

    # Operation details
    total_items: Optional[int] = None
    processed_items: int = 0
    failed_items: int = 0
    api_calls_made: int = 0

    # Additional context
    operation_params: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    # Database ID (set after insert)
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'id': self.id,
            'operation_type': self.operation_type,
            'operation_subtype': self.operation_subtype,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status.value,
            'stats': json.dumps(self.stats) if self.stats else None,
            'total_items': self.total_items,
            'processed_items': self.processed_items,
            'failed_items': self.failed_items,
            'api_calls_made': self.api_calls_made,
            'operation_params': json.dumps(self.operation_params) if self.operation_params else None,
            'error_message': self.error_message
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataUpdateMetadata':
        """Create from dictionary (from database)."""
        return cls(
            id=data.get('id'),
            operation_type=data['operation_type'],
            operation_subtype=data.get('operation_subtype'),
            started_at=datetime.fromisoformat(data['started_at']) if data.get('started_at') else None,
            completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
            status=OperationStatus(data.get('status', 'running')),
            stats=json.loads(data['stats']) if data.get('stats') else None,
            total_items=data.get('total_items'),
            processed_items=data.get('processed_items', 0),
            failed_items=data.get('failed_items', 0),
            api_calls_made=data.get('api_calls_made', 0),
            operation_params=json.loads(data['operation_params']) if data.get('operation_params') else None,
            error_message=data.get('error_message')
        )

    def get_operation_name(self) -> str:
        """Get formatted operation name."""
        if self.operation_subtype:
            return f"{self.operation_type}.{self.operation_subtype}"
        return self.operation_type

    def get_duration_seconds(self) -> Optional[float]:
        """Get operation duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def get_formatted_duration(self) -> str:
        """Get formatted duration string."""
        duration = self.get_duration_seconds()
        if duration is None:
            return "N/A"
        return f"{duration:.1f}s"

    def is_complete(self) -> bool:
        """Check if operation is complete (success or failure)."""
        return self.status in [OperationStatus.COMPLETED, OperationStatus.FAILED, OperationStatus.PARTIAL]

    def is_running(self) -> bool:
        """Check if operation is still running."""
        return self.status == OperationStatus.RUNNING

    def mark_completed(self, final_stats: Dict[str, Any], status: OperationStatus = OperationStatus.COMPLETED):
        """Mark operation as completed with final stats."""
        self.completed_at = datetime.now()
        self.status = status
        self.stats = final_stats

    def mark_failed(self, error_message: str):
        """Mark operation as failed with error message."""
        self.completed_at = datetime.now()
        self.status = OperationStatus.FAILED
        self.error_message = error_message

    def update_progress(self, processed_items: Optional[int] = None,
                       api_calls_made: Optional[int] = None,
                       stats: Optional[Dict[str, Any]] = None):
        """Update operation progress."""
        if processed_items is not None:
            self.processed_items = processed_items
        if api_calls_made is not None:
            self.api_calls_made = api_calls_made
        if stats is not None:
            self.stats = stats