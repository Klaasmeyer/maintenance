#!/usr/bin/env python3
"""
Regenerate maintenance estimates from cached geocoding results using project configurations.

Uses project YAML configs to determine paths, eliminating hard-coded values.
"""

import sys
from pathlib import Path
import pandas as pd

from kcci_maintenance.cache.cache_manager import CacheManager
from kcci_maintenance.config_manager import ConfigManager
from kcci_maintenance.utils.maintenance_estimate import generate_maintenance_estimate


def regenerate_estimate_from_config(config_path: Path) -> None:
    """Regenerate maintenance estimate from project configuration.

    Args:
        config_path: Path to project YAML configuration file
    """
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.load(config_path)

    print(f"\n{'='*70}")
    print(f"Regenerating Maintenance Estimate: {config.name}")
    print(f"{'='*70}\n")

    # Resolve paths from config
    cache_db = config.cache_db_path
    output_csv = config.output_dir / "results.csv"

    # Get route and estimate settings from raw config
    raw_config = config_manager._config
    route_config = raw_config.get("route", {})
    estimates_config = raw_config.get("estimates", {})

    # Resolve route KMZ path
    if "kmz_path" not in route_config:
        print(f"⚠️  Warning: No route.kmz_path in config, skipping estimate generation")
        return

    kmz_path = Path(route_config["kmz_path"])
    buffer_distance_m = route_config.get("buffer_distance_m", 500.0)

    # Resolve estimate output path
    if "estimate_xlsx" in estimates_config:
        estimate_output = Path(estimates_config["estimate_xlsx"])
    else:
        estimate_output = config.output_dir / "maintenance_estimate.xlsx"

    # Verify files exist
    if not cache_db.exists():
        print(f"❌ Error: Cache database not found: {cache_db}")
        return

    if not kmz_path.exists():
        print(f"❌ Error: Route KMZ file not found: {kmz_path}")
        return

    # Initialize cache manager
    cache_manager_obj = CacheManager(db_path=cache_db)

    # Export results with updated columns
    print(f"📤 Exporting cached results to {output_csv}...")
    from kcci_maintenance.cache.models import CacheQuery
    import csv

    records = cache_manager_obj.query(CacheQuery())

    # Ensure output directory exists
    output_csv.parent.mkdir(parents=True, exist_ok=True)

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
    print(f"   Exported {count:,} records\n")

    # Load results for estimate generation
    print(f"📊 Loading results for maintenance estimate...")
    results_df = pd.read_csv(output_csv)

    # Filter to only geocoded tickets
    results_df = results_df[
        (results_df['latitude'].notna()) &
        (results_df['longitude'].notna())
    ]
    print(f"   Found {len(results_df):,} geocoded tickets\n")

    # Ensure estimate output directory exists
    estimate_output.parent.mkdir(parents=True, exist_ok=True)

    # Generate maintenance estimate
    print(f"📊 Generating maintenance estimate...")
    generate_maintenance_estimate(
        tickets_df=results_df,
        kmz_path=kmz_path,
        output_path=estimate_output,
        project_name=config.name,
        buffer_distance_m=buffer_distance_m
    )

    print(f"\n✅ Maintenance estimate saved to {estimate_output}")
    print(f"{'='*70}\n")


def main():
    """Regenerate estimates for all configured projects."""
    # Get config directory
    config_dir = Path("config/projects")

    # Define project configs to process
    project_configs = [
        config_dir / "wink_project_full.yaml",
        config_dir / "floydada_project.yaml",
    ]

    # Process each project
    for config_path in project_configs:
        if not config_path.exists():
            print(f"⚠️  Warning: Config not found: {config_path}")
            continue

        try:
            regenerate_estimate_from_config(config_path)
        except Exception as e:
            print(f"❌ Error processing {config_path.name}: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
