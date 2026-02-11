#!/usr/bin/env python3
"""
Regenerate maintenance estimates from cached geocoding results.
"""

import sys
from pathlib import Path
import pandas as pd

from kcci_maintenance.cache.cache_manager import CacheManager
from kcci_maintenance.utils.maintenance_estimate import generate_maintenance_estimate

def regenerate_estimate(project_name, cache_db, output_csv, kmz_path, estimate_output):
    """Regenerate maintenance estimate from cached results."""

    print(f"\n{'='*70}")
    print(f"Regenerating Maintenance Estimate: {project_name}")
    print(f"{'='*70}\n")

    # Initialize cache manager
    cache_manager = CacheManager(db_path=cache_db)

    # Export results with updated columns
    print(f"📤 Exporting cached results to {output_csv}...")
    from kcci_maintenance.cache.models import CacheQuery
    import csv

    records = cache_manager.query(CacheQuery())

    with open(output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            "ticket_number", "geocode_key", "latitude", "longitude",
            "confidence", "method", "approach", "quality_tier",
            "review_priority", "validation_flags", "street", "intersection",
            "city", "county", "ticket_type", "duration", "work_type",
            "excavator", "created_at", "created_by_stage"
        ])
        writer.writeheader()

        for record in records:
            writer.writerow({
                "ticket_number": record.ticket_number,
                "geocode_key": record.geocode_key,
                "latitude": record.latitude,
                "longitude": record.longitude,
                "confidence": record.confidence,
                "method": record.method,
                "approach": record.approach,
                "quality_tier": record.quality_tier.value if hasattr(record.quality_tier, 'value') else record.quality_tier,
                "review_priority": record.review_priority.value if hasattr(record.review_priority, 'value') else record.review_priority,
                "validation_flags": ",".join(record.validation_flags) if record.validation_flags else "",
                "street": record.street,
                "intersection": record.intersection,
                "city": record.city,
                "county": record.county,
                "ticket_type": record.ticket_type,
                "duration": record.duration,
                "work_type": record.work_type,
                "excavator": record.excavator,
                "created_at": record.created_at,
                "created_by_stage": record.created_by_stage,
            })

    count = len(records)
    print(f"   Exported {count} records\n")

    # Load results for estimate generation
    print(f"📊 Loading results for maintenance estimate...")
    results_df = pd.read_csv(output_csv)

    # Filter to only geocoded tickets
    results_df = results_df[
        (results_df['latitude'].notna()) &
        (results_df['longitude'].notna())
    ]
    print(f"   Found {len(results_df)} geocoded tickets\n")

    # Generate maintenance estimate
    print(f"📊 Generating maintenance estimate...")
    generate_maintenance_estimate(
        tickets_df=results_df,
        kmz_path=Path(kmz_path),
        output_path=Path(estimate_output),
        project_name=project_name,
        buffer_distance_m=500.0
    )

    print(f"\n✅ Maintenance estimate saved to {estimate_output}")
    print(f"{'='*70}\n")


def main():
    # Wink Project
    regenerate_estimate(
        project_name="Wink APN",
        cache_db="projects/wink/cache/geocoding_cache.db",
        output_csv="outputs/wink_full_results_fixed.csv",
        kmz_path="projects/wink/route/wink.kmz",
        estimate_output="outputs/wink_maintenance_estimate_full.xlsx"
    )

    # Floydada Project
    regenerate_estimate(
        project_name="Floydada - Klaasmeyer",
        cache_db="projects/floydada/cache/geocoding_cache.db",
        output_csv="projects/floydada/outputs/floydada_results_fixed.csv",
        kmz_path="projects/floydada/route/Klaasmeyer - Floydada.kmz",
        estimate_output="projects/floydada/outputs/floydada_maintenance_estimate.xlsx"
    )


if __name__ == "__main__":
    main()
