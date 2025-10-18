"""Result models for database command outputs."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional


@dataclass(frozen=True)
class DatabaseStats:
    """Database statistics and health information."""

    database_path: str
    status: str
    table_counts: Dict[str, int]
    total_records: int
    last_updated: Optional[datetime] = None
    error_message: Optional[str] = None

    @property
    def is_healthy(self) -> bool:
        """Check if database is in healthy state."""
        return self.status == "healthy" and self.error_message is None
