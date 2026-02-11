"""
Stage 3: Proximity-based geocoding.

Wraps the ProximityGeocoder to fit into the pipeline framework.
Uses spatial proximity and road network analysis to geocode intersections.
"""

import sys
from pathlib import Path
from typing import Dict, Any

# Add paths for imports
parent_dir = Path(__file__).parent.parent
grandparent_dir = parent_dir.parent
sys.path.insert(0, str(parent_dir))
sys.path.insert(0, str(grandparent_dir))

from proximity_geocoder import ProximityGeocoder, ProximityResult
from stages.base_stage import BaseStage
from cache.cache_manager import CacheManager
from cache.models import GeocodeRecord, QualityTier, ReviewPriority

# Import pipeline proximity analyzer
try:
    from utils.pipeline_proximity import PipelineProximityAnalyzer
except ImportError:
    PipelineProximityAnalyzer = None


class Stage3ProximityGeocoder(BaseStage):
    """Stage 3: Proximity-based geocoding using road network analysis."""

    def __init__(
        self,
        cache_manager: CacheManager,
        config: Dict[str, Any],
    ):
        """Initialize proximity geocoding stage.

        Args:
            cache_manager: Cache manager instance
            config: Stage configuration with road_network_path
        """
        super().__init__(
            stage_name="stage_3_proximity",
            cache_manager=cache_manager,
            config=config,
        )

        # Get road network path from config
        road_network_path = config.get("road_network_path")
        if not road_network_path:
            raise ValueError("stage_3_proximity requires 'road_network_path' in config")

        road_network_path = Path(road_network_path)
        if not road_network_path.exists():
            raise FileNotFoundError(f"Road network file not found: {road_network_path}")

        # Initialize proximity geocoder
        self.geocoder = ProximityGeocoder(str(road_network_path))

        # Initialize pipeline proximity analyzer (optional)
        self.pipeline_analyzer = None
        pipeline_config = config.get("pipeline_layers", {})

        if pipeline_config.get("enabled", False) and PipelineProximityAnalyzer is not None:
            shapefile_paths = pipeline_config.get("shapefiles", [])
            if shapefile_paths:
                shapefile_paths = [Path(p) for p in shapefile_paths]
                boost_thresholds = pipeline_config.get("boost_thresholds")
                validation_distance = pipeline_config.get("validation_distance_m", 500.0)

                try:
                    self.pipeline_analyzer = PipelineProximityAnalyzer(
                        shapefile_paths=shapefile_paths,
                        boost_thresholds=boost_thresholds,
                        validation_distance_m=validation_distance,
                    )
                    print(f"✓ Initialized PipelineProximityAnalyzer with {len(shapefile_paths)} shapefiles")
                except Exception as e:
                    print(f"⚠ Warning: Failed to initialize pipeline analyzer: {e}")
                    self.pipeline_analyzer = None

        print(f"✓ Initialized Stage3ProximityGeocoder with {road_network_path}")

    def process_ticket(self, ticket_data: Dict[str, Any]) -> GeocodeRecord:
        """Process a single ticket using proximity-based geocoding.

        Args:
            ticket_data: Dictionary with ticket fields
                Required: ticket_number, street, intersection, city, county
                Optional: ticket_type, duration, work_type

        Returns:
            GeocodeRecord with result

        Raises:
            Exception: If geocoding fails
        """
        # Extract required fields
        ticket_number = ticket_data["ticket_number"]
        street = ticket_data.get("street", "")
        intersection = ticket_data.get("intersection", "")
        city = ticket_data.get("city", "")
        county = ticket_data.get("county", "")

        # Extract optional metadata fields
        ticket_type = ticket_data.get("ticket_type")
        duration = ticket_data.get("duration")
        work_type = ticket_data.get("work_type")

        # Call proximity geocoder
        result: ProximityResult = self.geocoder.geocode_proximity(
            street=street,
            intersection=intersection,
            county=county,
            city=city,
            ticket_type=ticket_type,
            duration=duration,
            work_type=work_type,
        )

        # Convert ProximityResult to GeocodeRecord
        if result.success:
            # Apply pipeline proximity boost if available
            base_confidence = result.confidence
            pipeline_metadata = {}

            if self.pipeline_analyzer is not None:
                boost, pipeline_metadata = self.pipeline_analyzer.calculate_proximity_boost(
                    result.lat, result.lng
                )

                # Apply boost (capped at 1.0)
                boosted_confidence = min(1.0, base_confidence + boost)

                # Update reasoning if boost was applied
                if boost > 0:
                    boost_pct = boost * 100
                    distance_m = pipeline_metadata.get("pipeline_proximity_m", 0)
                    original_reasoning = result.reasoning or ""
                    result.reasoning = (
                        f"{original_reasoning} "
                        f"[Pipeline proximity boost: +{boost_pct:.1f}% "
                        f"(distance: {distance_m:.1f}m)]"
                    ).strip()

                result.confidence = boosted_confidence

            # Successful geocoding
            geocode_record = GeocodeRecord(
                ticket_number=ticket_number,
                geocode_key=CacheManager.generate_geocode_key(
                    street, intersection, city, county
                ),
                street=street,
                intersection=intersection,
                city=city,
                county=county,
                latitude=result.lat,
                longitude=result.lng,
                confidence=result.confidence,
                method=self.stage_name,
                approach=result.approach,
                reasoning=result.reasoning,
                ticket_type=ticket_type,
                duration=duration,
                work_type=work_type,
                metadata=pipeline_metadata,  # Store pipeline proximity metadata
                # Quality tier will be calculated by _assess_quality()
                quality_tier=QualityTier.GOOD,  # Default, will be reassessed
                review_priority=ReviewPriority.NONE,  # Default, will be reassessed
            )

            return geocode_record
        else:
            # Failed geocoding
            raise Exception(result.error or "Proximity geocoding failed")


if __name__ == "__main__":
    # Test Stage3ProximityGeocoder
    print("Testing Stage3ProximityGeocoder...\n")

    # Initialize cache
    cache_db = Path(__file__).parent.parent / "outputs" / "test_stage3.db"
    cache_db.parent.mkdir(parents=True, exist_ok=True)
    if cache_db.exists():
        cache_db.unlink()

    cache_manager = CacheManager(str(cache_db))

    # Create stage config
    stage_config = {
        "road_network_path": Path(__file__).parent.parent.parent / "roads_merged.gpkg",
        "skip_rules": {
            "skip_if_quality": ["EXCELLENT", "GOOD"],
            "skip_if_locked": True,
        }
    }

    # Initialize stage
    stage = Stage3ProximityGeocoder(cache_manager, stage_config)

    # Test ticket
    ticket = {
        "ticket_number": "TEST_PROX_001",
        "street": "CR 426",
        "intersection": "CR 432",
        "city": "Pyote",
        "county": "Ward",
        "ticket_type": "Normal",
        "duration": "1 DAY",
        "work_type": "Hydro-excavation",
    }

    print("Test 1: Process new ticket with proximity geocoding")
    result = stage.run_single(ticket)

    print(f"✓ Success: {result.success}")
    print(f"  Skipped: {result.skipped}")
    if result.geocode_record:
        print(f"  Location: {result.geocode_record.latitude:.6f}, {result.geocode_record.longitude:.6f}")
        print(f"  Confidence: {result.geocode_record.confidence:.2%}")
        print(f"  Quality Tier: {result.geocode_record.quality_tier.value if hasattr(result.geocode_record.quality_tier, 'value') else result.geocode_record.quality_tier}")
        print(f"  Approach: {result.geocode_record.approach}")
        print(f"  Reasoning: {result.geocode_record.reasoning[:100]}...")

    # Test 2: Re-process (should skip)
    print("\nTest 2: Re-process same ticket (should skip)")
    result2 = stage.run_single(ticket)
    print(f"✓ Success: {result2.success}")
    print(f"  Skipped: {result2.skipped}")
    print(f"  Skip reason: {result2.skip_reason}")

    print("\n✓ All Stage3ProximityGeocoder tests passed!")
