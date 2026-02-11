#!/usr/bin/env python3
"""
Generate maintenance estimates by merging geocoded results with original ticket data.
"""

import sys
from pathlib import Path
import pandas as pd

from kcci_maintenance.utils.maintenance_estimate import generate_maintenance_estimate


def generate_estimate_with_merge(project_name, results_csv, original_tickets, kmz_path, estimate_output):
    """Generate maintenance estimate by merging results with original ticket data."""

    print(f"\n{'='*70}")
    print(f"Generating Maintenance Estimate: {project_name}")
    print(f"{'='*70}\n")

    # Load geocoded results
    print(f"📊 Loading geocoded results from {results_csv}...")
    results_df = pd.read_csv(results_csv)
    print(f"   Total records: {len(results_df)}")

    # Load original ticket data
    print(f"📊 Loading original ticket data from {original_tickets}...")
    if Path(original_tickets).is_dir():
        # Load from directory using TicketLoader
        from kcci_maintenance.utils.ticket_loader import TicketLoader
        loader = TicketLoader(normalize_columns=True)
        tickets_df = loader.load(original_tickets)
    else:
        # Load single file
        tickets_df = pd.read_csv(original_tickets)
        # Normalize column names
        tickets_df.columns = tickets_df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('-', '_')

    # Map column names
    column_mapping = {
        'nature_of_work': 'work_type',
        'number': 'ticket_number',
    }
    tickets_df.rename(columns=column_mapping, inplace=True)

    print(f"   Ticket records: {len(tickets_df)}")

    # Filter geocoded results to only successful geocodes
    results_df = results_df[
        (results_df['latitude'].notna()) &
        (results_df['longitude'].notna())
    ]
    print(f"   Geocoded tickets: {len(results_df)}\n")

    if len(results_df) == 0:
        print("⚠️  No geocoded tickets found, skipping estimate generation")
        return

    # Merge the dataframes on ticket_number
    print(f"🔀 Merging geocoded results with original ticket data...")

    # Determine which columns to merge
    merge_columns = ['ticket_number']
    optional_columns = ['duration', 'work_type', 'excavator', 'creation', 'Creation']

    for col in optional_columns:
        if col in tickets_df.columns and col not in results_df.columns:
            merge_columns.append(col)

    merged_df = results_df.merge(
        tickets_df[merge_columns],
        on='ticket_number',
        how='left'
    )

    # Standardize creation date column name if present
    if 'Creation' in merged_df.columns:
        merged_df.rename(columns={'Creation': 'creation'}, inplace=True)

    print(f"   Merged records: {len(merged_df)}")
    print(f"   Merged columns: {', '.join([c for c in merge_columns if c != 'ticket_number'])}\n")

    # Generate maintenance estimate
    print(f"📊 Generating maintenance estimate...")
    try:
        generate_maintenance_estimate(
            tickets_df=merged_df,
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
    generate_estimate_with_merge(
        project_name="Wink APN",
        results_csv="projects/wink/outputs/2026-02-10-wink-results-124346.csv",
        original_tickets="projects/wink/tickets/wink-intersection.csv",
        kmz_path="projects/wink/route/wink.kmz",
        estimate_output="projects/wink/outputs/2026-02-10-wink-maintenance-estimate-annualized.xlsx"
    )

    # Floydada Project
    generate_estimate_with_merge(
        project_name="Floydada - Klaasmeyer",
        results_csv="projects/floydada/outputs/2026-02-10-floydada-results-124336.csv",
        original_tickets="projects/floydada/tickets/",
        kmz_path="projects/floydada/route/Klaasmeyer - Floydada.kmz",
        estimate_output="projects/floydada/outputs/2026-02-10-floydada-maintenance-estimate-annualized.xlsx"
    )


if __name__ == "__main__":
    main()
