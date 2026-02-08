"""
Stage 1: API-based geocoding (STUB - Not Yet Implemented).

Will use external geocoding API (e.g., Google Maps Geocoding API)
for high-quality geocoding of intersections.
"""

import sys
from pathlib import Path
from typing import Dict, Any

# Add paths for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from stages.base_stage import BaseStage
from cache.cache_manager import CacheManager
from cache.models import GeocodeRecord


class Stage1APIGeocoder(BaseStage):
    """Stage 1: API-based geocoding using external services (STUB)."""

    def __init__(
        self,
        cache_manager: CacheManager,
        config: Dict[str, Any],
    ):
        """Initialize API geocoding stage.

        Args:
            cache_manager: Cache manager instance
            config: Stage configuration with API credentials
        """
        super().__init__(
            stage_name="stage_1_api",
            cache_manager=cache_manager,
            config=config,
        )

        print("⚠️  Stage1APIGeocoder is a STUB - not yet implemented")
        print("    Will be implemented with Google Maps Geocoding API or similar")

    def process_ticket(self, ticket_data: Dict[str, Any]) -> GeocodeRecord:
        """Process a single ticket using API-based geocoding.

        Args:
            ticket_data: Dictionary with ticket fields

        Returns:
            GeocodeRecord with result

        Raises:
            NotImplementedError: This stage is not yet implemented
        """
        raise NotImplementedError(
            "Stage1APIGeocoder is not yet implemented. "
            "Future implementation will use Google Maps Geocoding API or similar service."
        )


if __name__ == "__main__":
    print("Stage1APIGeocoder is a STUB implementation.")
    print("\nPlanned features:")
    print("  - Google Maps Geocoding API integration")
    print("  - Intersection geocoding (e.g., 'CR 426 & CR 432')")
    print("  - High-quality results with 90%+ confidence")
    print("  - API key management and rate limiting")
    print("  - Error handling for API failures")
    print("\nStatus: Not yet implemented")
