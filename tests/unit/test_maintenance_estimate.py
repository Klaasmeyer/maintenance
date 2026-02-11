#!/usr/bin/env python3
"""
Quick test of maintenance estimate generator with Wink data.
"""

import sys
from pathlib import Path
import pandas as pd

from kcci_maintenance.utils.maintenance_estimate import generate_maintenance_estimate

def main():
    # Load ticket data
    tickets_path = Path("projects/wink/tickets/wink-intersection.csv")
    print(f"Loading tickets from {tickets_path}...")
    tickets_df = pd.read_csv(tickets_path)

    # Normalize column names (spaces to underscores, lowercase)
    tickets_df.columns = tickets_df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('-', '_')

    # Map CSV columns to expected names
    column_mapping = {
        'nature_of_work': 'work_type',
        'number': 'ticket_number',
    }
    tickets_df.rename(columns=column_mapping, inplace=True)

    print(f"Total tickets loaded: {len(tickets_df)}")
    print(f"Columns (normalized): {list(tickets_df.columns)[:12]}...")

    # Filter to only tickets with coordinates
    tickets_with_coords = tickets_df[
        (tickets_df['latitude'].notna()) &
        (tickets_df['longitude'].notna())
    ]
    print(f"Tickets with coordinates: {len(tickets_with_coords)}")

    # Generate maintenance estimate
    kmz_path = Path("projects/wink/route/wink.kmz")
    output_path = Path("outputs/wink_maintenance_estimate_test.xlsx")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\nGenerating maintenance estimate...")
    print(f"  KMZ: {kmz_path}")
    print(f"  Output: {output_path}")

    generate_maintenance_estimate(
        tickets_df=tickets_with_coords,
        kmz_path=kmz_path,
        output_path=output_path,
        project_name="Wink APN",
        buffer_distance_m=500.0
    )

    print(f"\n✅ Maintenance estimate generated: {output_path}")
    print("\nReview the Excel file to verify:")
    print("  - Sheet 1: Maintenance Estimate (summary)")
    print("  - Sheet 2: Leg Details")
    print("  - Sheet 3: Cost Projections")
    print("  - Sheet 4: Ticket Breakdowns")
    print("  - Sheet 5: Ticket Assignments")

if __name__ == "__main__":
    main()
