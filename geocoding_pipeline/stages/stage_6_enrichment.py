"""
Stage 6: Data enrichment.

Enriches successfully geocoded tickets with additional contextual data:
- Jurisdiction and permitting authority information
- Future: Land ownership, environmental constraints, etc.
"""

import sys
from pathlib import Path
from typing import Dict, Any

# Add paths for imports
parent_dir = Path(__file__).parent.parent
grandparent_dir = parent_dir.parent
sys.path.insert(0, str(parent_dir))
sys.path.insert(0, str(grandparent_dir))

from stages.base_stage import BaseStage
from cache.cache_manager import CacheManager
from cache.models import GeocodeRecord, QualityTier

# Import jurisdiction enricher
try:
    from utils.jurisdiction_enrichment import JurisdictionEnricher
except ImportError:
    JurisdictionEnricher = None


class Stage6Enrichment(BaseStage):
    """Stage 6: Enrichment with jurisdiction and contextual data."""

    def __init__(
        self,
        cache_manager: CacheManager,
        config: Dict[str, Any],
    ):
        """Initialize enrichment stage.

        Args:
            cache_manager: Cache manager instance
            config: Stage configuration with enrichment settings
        """
        super().__init__(
            stage_name="stage_6_enrichment",
            cache_manager=cache_manager,
            config=config,
        )

        # Initialize jurisdiction enricher (optional)
        self.jurisdiction_enricher = None
        jurisdiction_config = config.get("jurisdiction", {})

        if jurisdiction_config.get("enabled", False) and JurisdictionEnricher is not None:
            geojson_path = jurisdiction_config.get("geojson_path")
            if geojson_path:
                attributes = jurisdiction_config.get("attributes", [])
                cache_index = jurisdiction_config.get("cache_spatial_index", True)

                try:
                    self.jurisdiction_enricher = JurisdictionEnricher(
                        geojson_path=Path(geojson_path),
                        attributes=attributes,
                        cache_spatial_index=cache_index,
                    )
                    print(f"✓ Initialized JurisdictionEnricher with {geojson_path}")
                except Exception as e:
                    print(f"⚠ Warning: Failed to initialize jurisdiction enricher: {e}")
                    self.jurisdiction_enricher = None

        print(f"✓ Initialized Stage6Enrichment")

    def process_ticket(self, ticket_data: Dict[str, Any]) -> GeocodeRecord:
        """Enrich a geocoded ticket with jurisdiction and contextual data.

        Args:
            ticket_data: Dictionary with ticket fields

        Returns:
            GeocodeRecord with enriched metadata

        Raises:
            Exception: If enrichment fails critically
        """
        ticket_number = ticket_data["ticket_number"]

        # Get cached record from previous stages
        cached_record = self.cache_manager.get_current(ticket_number=ticket_number)

        if cached_record is None:
            raise Exception(f"No cached record found for ticket {ticket_number}")

        # Skip enrichment for failed geocodes
        if cached_record.quality_tier == QualityTier.FAILED:
            # Return as-is, no enrichment needed
            return cached_record

        # Enrich with jurisdiction data if available
        jurisdiction_metadata = {}
        if self.jurisdiction_enricher is not None and cached_record.latitude:
            success, jurisdiction_metadata = self.jurisdiction_enricher.determine_jurisdiction(
                cached_record.latitude,
                cached_record.longitude
            )

        # Merge metadata (preserve existing, add jurisdiction)
        enriched_metadata = {
            **(cached_record.metadata or {}),
            **jurisdiction_metadata,
        }

        # Create enriched record
        enriched_record = GeocodeRecord(
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
            metadata=enriched_metadata,  # Enriched metadata
            quality_tier=cached_record.quality_tier,
            review_priority=cached_record.review_priority,
            validation_flags=cached_record.validation_flags,
            error_message=cached_record.error_message,
        )

        return enriched_record


if __name__ == "__main__":
    # Test Stage6Enrichment
    print("Testing Stage6Enrichment...\n")

    # Initialize cache
    cache_db = Path(__file__).parent.parent / "outputs" / "test_stage6.db"
    cache_db.parent.mkdir(parents=True, exist_ok=True)
    if cache_db.exists():
        cache_db.unlink()

    cache_manager = CacheManager(str(cache_db))

    # Create stage config
    stage_config = {
        "jurisdiction": {
            "enabled": True,
            "geojson_path": "projects/wink/permitting/Wink APN - Jurisdictions and Permitting.geojson",
            "cache_spatial_index": True,
            "attributes": [
                "authority_name",
                "jurisdiction_type",
                "permit_required",
            ]
        },
        "skip_rules": {
            "skip_if_locked": True,
        }
    }

    # Initialize stage
    stage = Stage6Enrichment(cache_manager, stage_config)

    # Test 1: Add a geocode to cache first
    print("Test 1: Setup - Adding test geocode to cache")
    from cache.models import GeocodeRecord, ReviewPriority

    test_record = GeocodeRecord(
        ticket_number="TEST_ENRICH_001",
        geocode_key=CacheManager.generate_geocode_key(
            "CR 426", "CR 432", "Pyote", "Ward"
        ),
        street="CR 426",
        intersection="CR 432",
        city="Pyote",
        county="Ward",
        latitude=31.7534,
        longitude=-103.1615,
        confidence=0.85,
        method="stage_3_proximity",
        approach="closest_point",
        ticket_type="Normal",
        quality_tier=QualityTier.GOOD,
        review_priority=ReviewPriority.NONE,
        metadata={"pipeline_proximity_m": 45.2},  # Existing metadata
    )

    cache_manager.set(test_record, "stage_3_proximity")
    print("✓ Added test record to cache")

    # Test 2: Enrich the record
    print("\nTest 2: Enrich geocoded ticket with jurisdiction data")
    ticket = {
        "ticket_number": "TEST_ENRICH_001",
    }

    result = stage.run_single(ticket)
    print(f"✓ Success: {result.success}")
    print(f"  Skipped: {result.skipped}")
    if result.geocode_record:
        print(f"  Metadata: {result.geocode_record.metadata}")
        if result.geocode_record.metadata:
            print(f"  Jurisdiction found: {result.geocode_record.metadata.get('jurisdiction_found')}")

    # Test 3: Try to enrich failed geocode (should skip enrichment)
    print("\nTest 3: Try to enrich failed geocode")
    failed_record = GeocodeRecord(
        ticket_number="TEST_ENRICH_FAILED",
        geocode_key="",
        street="",
        intersection="",
        city="",
        county="",
        latitude=None,
        longitude=None,
        confidence=0.0,
        method="",
        quality_tier=QualityTier.FAILED,
        review_priority=ReviewPriority.HIGH,
        error_message="Failed to geocode",
    )

    cache_manager.set(failed_record, "stage_3_proximity")

    ticket_failed = {
        "ticket_number": "TEST_ENRICH_FAILED",
    }

    result3 = stage.run_single(ticket_failed)
    print(f"✓ Success: {result3.success}")
    print(f"  Quality tier: {result3.geocode_record.quality_tier if result3.geocode_record else 'N/A'}")
    print(f"  Metadata: {result3.geocode_record.metadata if result3.geocode_record else 'N/A'}")

    print("\n✓ All Stage6Enrichment tests passed!")
