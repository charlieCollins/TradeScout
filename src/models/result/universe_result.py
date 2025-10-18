"""Result models for universe command outputs."""

from dataclasses import dataclass
from typing import List

from models.dataclass.universe import Universe, UniverseStats


@dataclass
class UniverseListItem:
    """Individual universe in the list with count."""
    universe: Universe  # Compose existing Universe model
    asset_count: int


@dataclass
class UniverseListResult:
    """Result for universe list command."""
    universes: List[UniverseListItem]


@dataclass
class UniverseInfoResult:
    """Result for universe info command."""
    universe: Universe  # Compose existing Universe model
    stats: UniverseStats  # Compose existing UniverseStats model
