"""
Pipeline stages for geocoding.

Each stage implements the BaseStage abstract class and provides
a specific geocoding approach (API, proximity, geometric, etc.).

Implemented Stages:
- Stage3ProximityGeocoder: Proximity-based geocoding using road networks
- Stage5Validation: Validation and quality reassessment

Stub Stages (Not Yet Implemented):
- Stage1APIGeocoder: API-based geocoding (Google Maps, etc.)
- Stage2GeometricIntersection: Geometric intersection calculation
- Stage4Fallback: Fallback strategies for difficult cases
"""

from .base_stage import BaseStage, StageResult, StageStatistics
from .stage_1_api import Stage1APIGeocoder
from .stage_2_geometric import Stage2GeometricIntersection
from .stage_3_proximity import Stage3ProximityGeocoder
from .stage_4_fallback import Stage4Fallback
from .stage_5_validation import Stage5Validation

__all__ = [
    "BaseStage",
    "StageResult",
    "StageStatistics",
    "Stage1APIGeocoder",
    "Stage2GeometricIntersection",
    "Stage3ProximityGeocoder",
    "Stage4Fallback",
    "Stage5Validation",
]
