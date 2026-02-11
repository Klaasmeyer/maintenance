#!/usr/bin/env python3
"""
inspect_roads.py

Quick inspection of the downloaded road network data.
Shows sample roads by type to verify data quality.
"""

import geopandas as gpd
from pathlib import Path

ROADS_FILE = Path("roads.gpkg")


def main():
    print("\n" + "=" * 70)
    print("ROAD NETWORK INSPECTION")
    print("=" * 70)

    gdf = gpd.read_file(ROADS_FILE, layer="roads")

    print(f"\n📊 Total roads: {len(gdf):,}")
    print(f"CRS: {gdf.crs}")
    print(f"Bounds: {gdf.total_bounds}")

    print("\n🛣️  ROAD TYPE COUNTS")
    print("-" * 70)
    for road_type, count in gdf["road_type"].value_counts().items():
        pct = count / len(gdf) * 100
        print(f"  {road_type:20s} {count:4,} ({pct:5.1f}%)")

    # Show samples of key road types
    key_types = ["CR", "CR_NUMBERED", "FM", "RM", "Interstate", "US"]

    for road_type in key_types:
        roads = gdf[gdf["road_type"] == road_type]
        if len(roads) == 0:
            continue

        print(f"\n📍 SAMPLE {road_type} ROADS (first 10)")
        print("-" * 70)
        for idx, row in roads.head(10).iterrows():
            name = row["name"] or row["ref"] or "unnamed"
            highway = row["highway"]
            print(f"  {name:30s} (highway={highway})")

    # Check for specific roads mentioned in failures
    print("\n🔍 CHECKING FOR SPECIFIC ROADS FROM FAILURES")
    print("-" * 70)

    test_roads = [
        "US 385",
        "US-385",
        "FM 1788",
        "TX-115",
        "TX-176",
        "I-20",
        "SE 8000",
        "NE 7501",
        "CR 201",
    ]

    for test_road in test_roads:
        # Try multiple matching strategies
        matches = gdf[
            (gdf["name"].str.contains(test_road, case=False, na=False)) |
            (gdf["ref"].str.contains(test_road, case=False, na=False))
        ]
        if len(matches) > 0:
            print(f"  ✓ {test_road:20s} - Found {len(matches)} segment(s)")
        else:
            print(f"  ✗ {test_road:20s} - NOT FOUND")

    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
