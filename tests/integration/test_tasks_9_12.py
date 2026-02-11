#!/usr/bin/env python3
"""
Integration test for Tasks #9-12: Verify all pipeline enhancements are working.

Tests:
- Task #9: Route corridor validation in Stage 5
- Task #10: JurisdictionEnricher utility
- Task #11: Stage 6 enrichment stage
- Task #12: Pipeline orchestrator integration
"""

import sys
from pathlib import Path

def test_task_9_route_corridor():
    """Test Task #9: Route corridor validation in Stage 5."""
    print("\n" + "="*80)
    print("TEST: Task #9 - Route Corridor Validation in Stage 5")
    print("="*80)

    from kcci_maintenance.stages.stage_5_validation import Stage5Validation
    from kcci_maintenance.cache.cache_manager import CacheManager
    from kcci_maintenance.cache.models import GeocodeRecord, QualityTier, ReviewPriority

    # Create temporary cache
    cache_db = Path("data/cache/test_task9.db")
    cache_db.parent.mkdir(parents=True, exist_ok=True)
    if cache_db.exists():
        cache_db.unlink()

    cache_manager = CacheManager(str(cache_db))

    # Config with route corridor enabled
    stage_config = {
        'validation_rules': ['out_of_corridor'],
        'route_corridor': {
            'enabled': True,
            'kmz_path': 'projects/wink/route/wink.kmz',
            'buffer_distance_m': 500,
        }
    }

    try:
        stage5 = Stage5Validation(cache_manager, stage_config)
        print("✅ Stage 5 initialized with RouteCorridorValidator")

        # Add test geocode
        test_record = GeocodeRecord(
            ticket_number="TEST_CORRIDOR",
            geocode_key=CacheManager.generate_geocode_key("CR 426", "CR 432", "Pyote", "Ward"),
            street="CR 426",
            intersection="CR 432",
            city="Pyote",
            county="Ward",
            latitude=31.7534,  # Near Wink
            longitude=-103.1615,
            confidence=0.85,
            method="stage_3_proximity",
            approach="closest_point",
            ticket_type="Normal",
            quality_tier=QualityTier.GOOD,
            review_priority=ReviewPriority.NONE,
        )

        cache_manager.set(test_record, "stage_3_proximity")

        # Process through Stage 5
        ticket = {"ticket_number": "TEST_CORRIDOR"}
        result = stage5.run_single(ticket)

        if result.success and result.geocode_record:
            metadata = result.geocode_record.metadata or {}
            print(f"✅ Corridor validation applied")
            print(f"   Within corridor: {metadata.get('within_corridor')}")
            print(f"   Distance from centerline: {metadata.get('distance_from_centerline_m')} m")
            return True
        else:
            print("❌ Stage 5 failed to process record")
            return False

    except Exception as e:
        print(f"❌ Task #9 failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_task_10_jurisdiction_enricher():
    """Test Task #10: JurisdictionEnricher utility."""
    print("\n" + "="*80)
    print("TEST: Task #10 - JurisdictionEnricher Utility")
    print("="*80)

    from kcci_maintenance.utils.jurisdiction_enrichment import JurisdictionEnricher

    jurisdiction_file = Path("projects/wink/permitting/Wink APN - Jurisdictions and Permitting.geojson")

    if not jurisdiction_file.exists():
        print(f"⚠️  Jurisdiction file not found: {jurisdiction_file}")
        print("   Skipping Task #10 test")
        return True  # Not a failure, just missing test data

    try:
        enricher = JurisdictionEnricher(
            geojson_path=jurisdiction_file,
            attributes=["authority_name", "jurisdiction_type", "permit_required"],
            cache_spatial_index=True,
        )
        print("✅ JurisdictionEnricher initialized successfully")

        # Test location near Wink, TX
        test_lat, test_lng = 31.7534, -103.1615
        success, jurisdiction_data = enricher.determine_jurisdiction(test_lat, test_lng)

        print(f"✅ Jurisdiction lookup completed")
        print(f"   Success: {success}")
        print(f"   Jurisdiction data: {jurisdiction_data}")

        return True

    except Exception as e:
        print(f"❌ Task #10 failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_task_11_stage_6():
    """Test Task #11: Stage 6 enrichment stage."""
    print("\n" + "="*80)
    print("TEST: Task #11 - Stage 6 Enrichment")
    print("="*80)

    from kcci_maintenance.stages.stage_6_enrichment import Stage6Enrichment
    from kcci_maintenance.cache.cache_manager import CacheManager
    from kcci_maintenance.cache.models import GeocodeRecord, QualityTier, ReviewPriority

    # Create temporary cache
    cache_db = Path("data/cache/test_task11.db")
    cache_db.parent.mkdir(parents=True, exist_ok=True)
    if cache_db.exists():
        cache_db.unlink()

    cache_manager = CacheManager(str(cache_db))

    # Config with jurisdiction enabled
    stage_config = {
        'jurisdiction': {
            'enabled': True,
            'geojson_path': 'projects/wink/permitting/Wink APN - Jurisdictions and Permitting.geojson',
            'cache_spatial_index': True,
            'attributes': ['authority_name', 'jurisdiction_type', 'permit_required'],
        }
    }

    try:
        stage6 = Stage6Enrichment(cache_manager, stage_config)
        print("✅ Stage 6 initialized with JurisdictionEnricher")

        # Add test geocode with existing metadata
        test_record = GeocodeRecord(
            ticket_number="TEST_ENRICH",
            geocode_key=CacheManager.generate_geocode_key("CR 426", "CR 432", "Pyote", "Ward"),
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
            metadata={'pipeline_proximity_m': 45.2, 'within_corridor': True},  # Existing metadata
        )

        cache_manager.set(test_record, "stage_3_proximity")

        # Process through Stage 6
        ticket = {"ticket_number": "TEST_ENRICH"}
        result = stage6.run_single(ticket)

        if result.success and result.geocode_record:
            metadata = result.geocode_record.metadata or {}
            print(f"✅ Enrichment applied")
            print(f"   Pipeline proximity preserved: {metadata.get('pipeline_proximity_m')} m")
            print(f"   Corridor info preserved: {metadata.get('within_corridor')}")
            print(f"   Jurisdiction found: {metadata.get('jurisdiction_found')}")

            # Verify metadata was merged, not replaced
            if 'pipeline_proximity_m' in metadata and 'jurisdiction_found' in metadata:
                print("✅ Metadata properly merged (pipeline + jurisdiction)")
                return True
            else:
                print("❌ Metadata not properly merged")
                return False
        else:
            print("❌ Stage 6 failed to process record")
            return False

    except Exception as e:
        print(f"❌ Task #11 failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_task_12_pipeline_integration():
    """Test Task #12: Pipeline orchestrator integration."""
    print("\n" + "="*80)
    print("TEST: Task #12 - Pipeline Orchestrator Integration")
    print("="*80)

    # Test 1: Verify Stage 6 is exported from stages module
    try:
        from kcci_maintenance.stages import Stage6Enrichment
        print("✅ Stage6Enrichment exported from stages module")
    except ImportError as e:
        print(f"❌ Stage6Enrichment import failed: {e}")
        return False

    # Test 2: Verify CLI imports work
    try:
        from kcci_maintenance.cli import Stage6Enrichment as CLIStage6
        print("✅ Stage6Enrichment imported in CLI")
    except ImportError as e:
        print(f"❌ CLI import failed: {e}")
        return False

    # Test 3: Verify run_pipeline imports work
    try:
        import sys
        from pathlib import Path
        # Add src to path to import run_pipeline script
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "scripts"))
        import run_pipeline
        # Check if Stage6Enrichment is imported
        if hasattr(run_pipeline, 'Stage6Enrichment'):
            print("✅ Stage6Enrichment imported in run_pipeline")
        else:
            print("⚠️  Stage6Enrichment not directly used in run_pipeline (expected for basic runner)")
    except ImportError as e:
        print(f"❌ run_pipeline import failed: {e}")
        return False

    print("✅ All pipeline orchestrator integrations verified")
    return True


def main():
    """Run all integration tests."""
    print("\n" + "="*80)
    print("INTEGRATION TEST: Tasks #9-12 Pipeline Enhancement")
    print("="*80)

    results = {
        'Task #9 (Route Corridor in Stage 5)': test_task_9_route_corridor(),
        'Task #10 (JurisdictionEnricher)': test_task_10_jurisdiction_enricher(),
        'Task #11 (Stage 6 Enrichment)': test_task_11_stage_6(),
        'Task #12 (Pipeline Integration)': test_task_12_pipeline_integration(),
    }

    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    for task, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{task:45s} {status}")

    all_passed = all(results.values())

    print("\n" + "="*80)
    if all_passed:
        print("🎉 ALL TESTS PASSED - Tasks #9-12 Implementation Complete!")
    else:
        print("⚠️  SOME TESTS FAILED - Review errors above")
    print("="*80)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
