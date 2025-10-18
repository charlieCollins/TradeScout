"""Result models for fed command outputs."""

from dataclasses import dataclass
from typing import List, Dict, Optional

from models.dataclass.fed_data import FedData


@dataclass
class FedUpdateResult:
    """Result for fed update command."""
    data_by_type: Dict[str, int]  # data_type -> observations_stored
    total_stored: int
    elapsed_seconds: float


@dataclass
class FedInfoSection:
    """Fed data for one section (inflation, expectations, yields)."""
    data_type_key: str
    display_name: str
    latest: Optional[FedData]  # Compose existing FedData model
    recent: List[FedData]  # Compose existing FedData model


@dataclass
class FedInfoResult:
    """Result for fed info command."""
    sections: List[FedInfoSection]
