#!/usr/bin/env python3
"""
Run the geocoding pipeline end-to-end on 811 ticket data.

This script demonstrates the complete pipeline workflow:
1. Load ticket data
2. Initialize cache and pipeline
3. Add geocoding stages
4. Run pipeline
5. Generate outputs and reports
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

# Add geocoding_pipeline to path
sys.path.insert(0, str(Path(__file__).parent / "geocoding_pipeline"))

from pipeline import Pipeline
from cache.cache_manager import CacheManager
from stages.stage_3_proximity import Stage3ProximityGeocoder
from stages.stage_5_validation import Stage5Validation
from stages.stage_6_enrichment import Stage6Enrichment

def main():
    print("="*80)
    print("🚀 Geocoding Pipeline - End-to-End Integration Test")
    print("="*80)
    print()

    # Configuration
    input_csv = Path("ticket_failures.csv")
    cache_db = Path("geocoding_pipeline/outputs/pipeline_cache.db")
    output_dir = Path("geocoding_pipeline/outputs")
    roads_file = Path("roads_merged.gpkg")

    # Validate inputs
    if not input_csv.exists():
        print(f"❌ Error: Input file not found: {input_csv}")
        return 1

    if not roads_file.exists():
        print(f"❌ Error: Road network file not found: {roads_file}")
        return 1

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"📁 Input: {input_csv}")
    print(f"📁 Cache: {cache_db}")
    print(f"📁 Roads: {roads_file}")
    print(f"📁 Output: {output_dir}")
    print()

    # Load ticket data
    print("📊 Loading ticket data...")
    df = pd.read_csv(input_csv)
    print(f"   Loaded {len(df)} tickets")
    print()

    # Prepare ticket data
    tickets = []
    for _, row in df.iterrows():
        tickets.append({
            "ticket_number": str(row["Number"]),
            "county": row.get("County", ""),
            "city": row.get("City", ""),
            "street": row.get("Street", ""),
            "intersection": row.get("Intersection", ""),
        })

    print(f"   Prepared {len(tickets)} tickets for processing")
    print()

    # Initialize cache
    print("💾 Initializing cache...")
    cache_manager = CacheManager(str(cache_db))
    print(f"   Cache ready at {cache_db}")
    print()

    # Create pipeline
    print("🔧 Configuring pipeline...")
    pipeline_config = {
        "name": "811_geocoding_pipeline",
        "fail_fast": False,
        "save_intermediate": True,
    }
    pipeline = Pipeline(cache_manager, pipeline_config)

    # Add Stage 3: Proximity Geocoding
    stage3_config = {
        "road_network_path": str(roads_file),
        "skip_rules": {
            "skip_if_quality": ["EXCELLENT", "GOOD"],
            "skip_if_locked": True,
        }
    }
    stage3 = Stage3ProximityGeocoder(cache_manager, stage3_config)
    pipeline.add_stage(stage3)
    print("   ✅ Added Stage 3: Proximity Geocoding")

    # Add Stage 5: Validation
    stage5_config = {
        "validation_rules": [
            "low_confidence",
            "emergency_low_confidence",
            "city_distance",
            "fallback_geocode",
            "missing_road",
        ],
        "skip_rules": {
            "skip_if_locked": True,
        }
    }
    stage5 = Stage5Validation(cache_manager, stage5_config)
    pipeline.add_stage(stage5)
    print("   ✅ Added Stage 5: Validation")

    # Add Stage 6: Enrichment (optional - only if config available)
    # Note: Stage 6 requires jurisdiction data, so it's typically configured via config file
    # For basic usage without enrichment, this stage can be skipped
    # Example config would go here if needed
    print()

    # Run pipeline
    print("🚀 Running pipeline...")
    print()

    start_time = datetime.now()
    result = pipeline.run(tickets)
    end_time = datetime.now()

    duration = (end_time - start_time).total_seconds()

    print()
    print("="*80)
    print("📊 Pipeline Results Summary")
    print("="*80)
    print(f"Total Tickets:     {result.total_tickets}")
    print(f"Succeeded:         {result.total_succeeded} ({result.total_succeeded/result.total_tickets*100:.1f}%)")
    print(f"Failed:            {result.total_failed} ({result.total_failed/result.total_tickets*100:.1f}%)")
    print(f"Total Time:        {duration:.1f}s ({duration/result.total_tickets*1000:.1f}ms per ticket)")
    print()

    # Stage-by-stage breakdown
    print("📋 Stage Performance:")
    print("-"*80)
    for stats in result.stage_statistics:
        print(f"\n{stats.stage_name}:")
        print(f"  Processed:  {stats.processed}/{stats.total_tickets}")
        print(f"  Succeeded:  {stats.succeeded}")
        print(f"  Failed:     {stats.failed}")
        print(f"  Skipped:    {stats.skipped}")
        print(f"  Avg Time:   {stats.to_dict()['avg_time_ms']:.1f}ms")

    print()
    print("="*80)

    # Export results
    print()
    print("💾 Exporting results...")

    # Export all results
    results_csv = output_dir / f"pipeline_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    count = pipeline.export_results(results_csv)
    print(f"   ✅ Exported {count} results to {results_csv}")

    # Export review queue
    review_csv = output_dir / f"review_queue_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    review_count = pipeline.generate_review_queue(
        review_csv,
        priority_filter=["CRITICAL", "HIGH", "MEDIUM"]
    )
    print(f"   ✅ Generated review queue with {review_count} tickets at {review_csv}")

    # Cache statistics
    print()
    print("📊 Cache Statistics:")
    print("-"*80)
    stats = cache_manager.get_statistics()
    print(f"Total Records:     {stats['total_records']}")
    print(f"Total Versions:    {stats['total_versions']}")
    print(f"Locked Records:    {stats['locked_count']}")
    print()
    print("Quality Distribution:")
    for tier, count in stats['quality_tiers'].items():
        percentage = count / stats['total_records'] * 100
        print(f"  {tier:20s}: {count:4d} ({percentage:5.1f}%)")

    if 'avg_confidence_by_tier' in stats:
        print()
        print("Average Confidence by Tier:")
        for tier, conf in stats['avg_confidence_by_tier'].items():
            print(f"  {tier:20s}: {conf:.1%}")

    print()
    print("="*80)
    print("✅ Pipeline execution complete!")
    print("="*80)
    print()
    print(f"📁 Results: {results_csv}")
    print(f"📁 Review Queue: {review_csv}")
    print(f"📁 Cache: {cache_db}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
