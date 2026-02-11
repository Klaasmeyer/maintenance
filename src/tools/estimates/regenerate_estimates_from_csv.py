#!/usr/bin/env python3
"""
Regenerate maintenance estimates from existing CSV results.
"""

import sys
from pathlib import Path
import pandas as pd

from kcci_maintenance.utils.maintenance_estimate import generate_maintenance_estimate


def regenerate_estimate(project_name, input_csv, kmz_path, estimate_output):
    """Regenerate maintenance estimate from CSV results."""

    print(f"\n{'='*70}")
    print(f"Regenerating Maintenance Estimate: {project_name}")
    print(f"{'='*70}\n")

    # Load results
    print(f"📊 Loading results from {input_csv}...")
    results_df = pd.read_csv(input_csv)
    print(f"   Total records: {len(results_df)}")

    # Filter to only geocoded tickets
    results_df = results_df[
        (results_df['latitude'].notna()) &
        (results_df['longitude'].notna())
    ]
    print(f"   Geocoded tickets: {len(results_df)}\n")

    if len(results_df) == 0:
        print("⚠️  No geocoded tickets found, skipping estimate generation")
        return

    # Generate maintenance estimate
    print(f"📊 Generating maintenance estimate...")
    try:
        generate_maintenance_estimate(
            tickets_df=results_df,
            kmz_path=Path(kmz_path),
            output_path=Path(estimate_output),
            project_name=project_name,
            buffer_distance_m=500.0
        )
        print(f"\n✅ Maintenance estimate saved to {estimate_output}")
    except Exception as e:
        print(f"\n❌ Error generating estimate: {e}")
        import traceback
        traceback.print_exc()

    print(f"{'='*70}\n")


def main():
    # Wink Project
    regenerate_estimate(
        project_name="Wink APN",
        input_csv="outputs/wink_full_results.csv",
        kmz_path="projects/wink/route/wink.kmz",
        estimate_output="outputs/wink_maintenance_estimate_full.xlsx"
    )

    # Floydada Project
    regenerate_estimate(
        project_name="Floydada - Klaasmeyer",
        input_csv="projects/floydada/outputs/floydada_results.csv",
        kmz_path="projects/floydada/route/Klaasmeyer - Floydada.kmz",
        estimate_output="projects/floydada/outputs/floydada_maintenance_estimate.xlsx"
    )


if __name__ == "__main__":
    main()
