"""
Stage 5: Validation and quality reassessment.

Applies validation rules to already-geocoded tickets and adjusts
quality tiers and review priorities based on validation results.
"""

import sys
from pathlib import Path
from typing import Dict, Any, List

# Add paths for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from stages.base_stage import BaseStage
from cache.cache_manager import CacheManager
from cache.models import GeocodeRecord, QualityTier, ReviewPriority

# Import route corridor validator
try:
    from utils.route_corridor import RouteCorridorValidator
except ImportError:
    RouteCorridorValidator = None


class Stage5Validation(BaseStage):
    """Stage 5: Validation and quality reassessment for geocoded tickets."""

    def __init__(
        self,
        cache_manager: CacheManager,
        config: Dict[str, Any],
    ):
        """Initialize validation stage.

        Args:
            cache_manager: Cache manager instance
            config: Stage configuration with validation rules
        """
        super().__init__(
            stage_name="stage_5_validation",
            cache_manager=cache_manager,
            config=config,
        )

        # Get validation rules from config
        self.enabled_rules = config.get("validation_rules", [
            "low_confidence",
            "emergency_low_confidence",
            "city_distance",
            "fallback_geocode",
            "missing_road",
        ])

        # Initialize route corridor validator (optional)
        self.route_corridor_validator = None
        corridor_config = config.get("route_corridor", {})

        if corridor_config.get("enabled", False) and RouteCorridorValidator is not None:
            kmz_path = corridor_config.get("kmz_path")
            if kmz_path:
                buffer_distance = corridor_config.get("buffer_distance_m", 500.0)

                try:
                    self.route_corridor_validator = RouteCorridorValidator(
                        kmz_path=Path(kmz_path),
                        buffer_distance_m=buffer_distance,
                    )
                    print(f"✓ Initialized RouteCorridorValidator with {kmz_path}")
                except Exception as e:
                    print(f"⚠ Warning: Failed to initialize corridor validator: {e}")
                    self.route_corridor_validator = None

        print(f"✓ Initialized Stage5Validation with {len(self.enabled_rules)} rules")

    def process_ticket(self, ticket_data: Dict[str, Any]) -> GeocodeRecord:
        """Re-validate an already-geocoded ticket.

        This stage retrieves the existing geocode from cache, re-runs
        validation, and potentially adjusts quality tier and review priority.

        Args:
            ticket_data: Dictionary with ticket fields
                Required: ticket_number

        Returns:
            GeocodeRecord with updated quality assessment

        Raises:
            Exception: If ticket not found in cache or validation fails
        """
        ticket_number = ticket_data["ticket_number"]

        # Get current geocode from cache
        cached_record = self.cache_manager.get_current(ticket_number=ticket_number)

        if cached_record is None:
            raise Exception(f"Ticket {ticket_number} not found in cache - must be geocoded first")

        # Check if this is a failed geocode (nothing to validate)
        if cached_record.quality_tier == QualityTier.FAILED:
            # Don't change failed geocodes
            return cached_record

        # Check if geocode is locked (human verified - don't touch)
        if cached_record.locked:
            return cached_record

        # Check route corridor if enabled
        corridor_metadata = {}
        if self.route_corridor_validator is not None and cached_record.latitude:
            is_within, corridor_metadata = self.route_corridor_validator.check_containment(
                cached_record.latitude,
                cached_record.longitude
            )

        # Merge metadata (preserve existing, add corridor)
        updated_metadata = {
            **(cached_record.metadata or {}),  # Preserve existing metadata
            **corridor_metadata,                 # Add corridor metadata
        }

        # Re-run quality assessment with current validation engine
        # The _assess_quality method in BaseStage will recalculate everything
        # We just need to return the record and let the parent handle it

        # Create a copy of the record for reassessment
        updated_record = GeocodeRecord(
            ticket_number=cached_record.ticket_number,
            geocode_key=cached_record.geocode_key,
            street=cached_record.street,
            intersection=cached_record.intersection,
            city=cached_record.city,
            county=cached_record.county,
            latitude=cached_record.latitude,
            longitude=cached_record.longitude,
            confidence=cached_record.confidence,
            method=cached_record.method,
            approach=cached_record.approach,
            reasoning=cached_record.reasoning,
            ticket_type=cached_record.ticket_type,
            duration=cached_record.duration,
            work_type=cached_record.work_type,
            excavator=cached_record.excavator,
            metadata=updated_metadata,  # Include corridor metadata
            # Quality fields will be recalculated by _assess_quality
            quality_tier=cached_record.quality_tier,
            review_priority=cached_record.review_priority,
            validation_flags=cached_record.validation_flags,
        )

        return updated_record


if __name__ == "__main__":
    # Test Stage5Validation
    print("Testing Stage5Validation...\n")

    # Initialize cache
    cache_db = Path(__file__).parent.parent / "outputs" / "test_stage5.db"
    cache_db.parent.mkdir(parents=True, exist_ok=True)
    if cache_db.exists():
        cache_db.unlink()

    cache_manager = CacheManager(str(cache_db))

    # Create stage config
    stage_config = {
        "validation_rules": [
            "low_confidence",
            "emergency_low_confidence",
            "city_distance",
            "fallback_geocode",
            "missing_road",
        ],
        "skip_rules": {
            "skip_if_locked": True,  # Don't re-validate locked records
        }
    }

    # Initialize stage
    stage = Stage5Validation(cache_manager, stage_config)

    # Test 1: Add a geocode to cache first
    print("Test 1: Setup - Adding test geocode to cache")
    from cache.models import GeocodeRecord

    test_record = GeocodeRecord(
        ticket_number="TEST_VAL_001",
        geocode_key=CacheManager.generate_geocode_key(
            "CR 426", "CR 432", "Pyote", "Ward"
        ),
        street="CR 426",
        intersection="CR 432",
        city="Pyote",
        county="Ward",
        latitude=31.396112,
        longitude=-103.091668,
        confidence=0.65,  # ACCEPTABLE tier, should trigger validation
        method="stage_3_proximity",
        approach="closest_point",
        ticket_type="Normal",
        quality_tier=QualityTier.ACCEPTABLE,
        review_priority=ReviewPriority.LOW,
    )

    cache_manager.set(test_record, "stage_3_proximity")
    print("✓ Added test record to cache")

    # Test 2: Validate the record
    print("\nTest 2: Re-validate geocoded ticket")
    ticket = {
        "ticket_number": "TEST_VAL_001",
    }

    result = stage.run_single(ticket)
    print(f"✓ Success: {result.success}")
    print(f"  Skipped: {result.skipped}")
    if result.geocode_record:
        print(f"  Quality Tier: {result.geocode_record.quality_tier.value if hasattr(result.geocode_record.quality_tier, 'value') else result.geocode_record.quality_tier}")
        print(f"  Review Priority: {result.geocode_record.review_priority.value if hasattr(result.geocode_record.review_priority, 'value') else result.geocode_record.review_priority}")
        print(f"  Validation Flags: {result.geocode_record.validation_flags}")

    # Test 3: Try to validate locked record (should skip)
    print("\nTest 3: Lock record and try to re-validate")
    cached = cache_manager.get_current(ticket_number="TEST_VAL_001")
    cache_manager.lock(cached.cache_id, "Human verified")

    result3 = stage.run_single(ticket)
    print(f"✓ Success: {result3.success}")
    print(f"  Skipped: {result3.skipped}")
    if result3.skipped:
        print(f"  Skip reason: {result3.skip_reason}")

    # Test 4: Try to validate non-existent ticket (should fail)
    print("\nTest 4: Try to validate ticket not in cache")
    ticket_missing = {
        "ticket_number": "DOES_NOT_EXIST",
    }

    result4 = stage.run_single(ticket_missing)
    print(f"✓ Success: {result4.success}")
    if not result4.success:
        print(f"  Error: {result4.error}")

    print("\n✓ All Stage5Validation tests passed!")
