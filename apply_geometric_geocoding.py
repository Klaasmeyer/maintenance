#!/usr/bin/env python3
"""
apply_geometric_geocoding.py

Apply geometric geocoding to all failed intersections and measure improvement.

Reads ticket_failures.csv (728 failed tickets) and attempts to geocode each
using the geometric geocoder. Reports success rate and saves results.

Output:
    - geometric_results.csv - All attempts with results
    - geometric_summary.json - Statistics on success/failure
    - Console report with improvement metrics
"""

import json
import logging
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from geometric_geocoder import GeometricGeocoder

logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")

FAILURES_FILE = Path("ticket_failures.csv")
ROADS_FILE = Path("roads.gpkg")
OUTPUT_RESULTS = Path("geometric_results.csv")
OUTPUT_SUMMARY = Path("geometric_summary.json")


def main():
    print("\n" + "=" * 70)
    print("APPLYING GEOMETRIC GEOCODING TO FAILURES")
    print("=" * 70)

    # Load failures
    if not FAILURES_FILE.exists():
        print(f"❌ Failures file not found: {FAILURES_FILE}")
        print("Please run analyze_ticket_geocoding.py first")
        return

    df = pd.read_csv(FAILURES_FILE)
    print(f"\n📋 Loaded {len(df)} failed tickets")

    # Initialize geocoder
    if not ROADS_FILE.exists():
        print(f"❌ Road network file not found: {ROADS_FILE}")
        print("Please run download_road_network.py first")
        return

    geocoder = GeometricGeocoder(ROADS_FILE)
    print(f"✅ Loaded road network")

    # Process each failure
    print(f"\n🔄 Processing failures...")

    results = []
    successes = 0
    failures_no_roads = 0
    failures_no_intersection = 0

    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Geocoding"):
        ticket_number = row["Number"]
        county = row["County"]
        city = row["City"]
        street = row["Street"]
        intersection = row["Intersection"]
        original_status = row.get("geocode_status", "ZERO_RESULTS")

        # Attempt geometric geocoding
        result = geocoder.geocode_intersection(street, intersection, county, city)

        # Record result
        result_row = {
            "ticket_number": ticket_number,
            "county": county,
            "city": city,
            "street": street,
            "intersection": intersection,
            "original_status": original_status,
            "geometric_success": result.success,
            "geometric_lat": result.lat,
            "geometric_lng": result.lng,
            "geometric_confidence": result.confidence,
            "geometric_error": result.error,
        }
        results.append(result_row)

        if result.success:
            successes += 1
        elif "not found" in (result.error or "").lower():
            failures_no_roads += 1
        elif "do not intersect" in (result.error or "").lower():
            failures_no_intersection += 1

    # Create results DataFrame
    results_df = pd.DataFrame(results)

    # Save results
    results_df.to_csv(OUTPUT_RESULTS, index=False)
    print(f"\n💾 Saved detailed results to {OUTPUT_RESULTS}")

    # Calculate statistics
    total = len(df)
    success_rate = (successes / total * 100) if total > 0 else 0
    original_success_rate = 96.92  # From analysis
    new_success_rate = original_success_rate + (successes / 23601 * 100)

    # Group by error type
    error_types = results_df[~results_df["geometric_success"]].groupby(
        results_df["geometric_error"].fillna("unknown")
    ).size().to_dict()

    # Summary statistics
    summary = {
        "total_failed_tickets": total,
        "geometric_successes": successes,
        "geometric_failures": total - successes,
        "success_rate": round(success_rate, 2),
        "failures_no_roads": failures_no_roads,
        "failures_no_intersection": failures_no_intersection,
        "original_geocoding_success_rate": original_success_rate,
        "new_overall_success_rate": round(new_success_rate, 2),
        "improvement": round(new_success_rate - original_success_rate, 2),
        "error_breakdown": error_types,
    }

    # Save summary
    with OUTPUT_SUMMARY.open("w") as f:
        json.dump(summary, f, indent=2)
    print(f"💾 Saved summary to {OUTPUT_SUMMARY}")

    # Print report
    print("\n" + "=" * 70)
    print("GEOMETRIC GEOCODING RESULTS")
    print("=" * 70)

    print(f"\n📊 OVERALL RESULTS")
    print("-" * 70)
    print(f"  Total failed tickets:          {total:,}")
    print(f"  Geometric successes:           {successes:,} ({success_rate:.2f}%)")
    print(f"  Geometric failures:            {total - successes:,} ({100 - success_rate:.2f}%)")

    print(f"\n📈 IMPROVEMENT ANALYSIS")
    print("-" * 70)
    print(f"  Original success rate:         {original_success_rate:.2f}%")
    print(f"  New overall success rate:      {new_success_rate:.2f}%")
    print(f"  Improvement:                   +{summary['improvement']:.2f} percentage points")
    print(f"  Additional tickets geocoded:   {successes:,}")

    print(f"\n❌ FAILURE BREAKDOWN")
    print("-" * 70)
    print(f"  Road(s) not in network:        {failures_no_roads:,}")
    print(f"  Roads don't intersect:         {failures_no_intersection:,}")
    print(f"  Other errors:                  {total - successes - failures_no_roads - failures_no_intersection:,}")

    if error_types:
        print(f"\n🔍 ERROR TYPES (Top 10)")
        print("-" * 70)
        for error, count in sorted(error_types.items(), key=lambda x: -x[1])[:10]:
            error_short = (error[:60] + "...") if len(error) > 60 else error
            print(f"  {error_short:63s} {count:4,}")

    # Success by county
    success_by_county = results_df[results_df["geometric_success"]].groupby("county").size()
    if len(success_by_county) > 0:
        print(f"\n✅ SUCCESSES BY COUNTY")
        print("-" * 70)
        for county, count in success_by_county.items():
            print(f"  {county:20s} {count:4,}")

    # Confidence distribution for successes
    if successes > 0:
        success_df = results_df[results_df["geometric_success"]]
        avg_confidence = success_df["geometric_confidence"].mean()
        min_confidence = success_df["geometric_confidence"].min()
        max_confidence = success_df["geometric_confidence"].max()

        print(f"\n🎯 CONFIDENCE SCORES (for successes)")
        print("-" * 70)
        print(f"  Average confidence:            {avg_confidence:.2%}")
        print(f"  Min confidence:                {min_confidence:.2%}")
        print(f"  Max confidence:                {max_confidence:.2%}")

    print("\n" + "=" * 70)

    # Recommendations
    print(f"\n💡 NEXT STEPS")
    print("-" * 70)

    if failures_no_roads > total * 0.5:
        print(f"  • {failures_no_roads} failures due to missing roads in network")
        print(f"    → Consider acquiring TxDOT county road data")
        print(f"    → Or implement grid-based estimation for numbered roads")

    if failures_no_intersection > 100:
        print(f"  • {failures_no_intersection} failures where roads don't intersect")
        print(f"    → May indicate data quality issues in tickets")
        print(f"    → Or roads are parallel/don't actually cross")

    if successes > 0:
        print(f"  • ✅ Successfully geocoded {successes} tickets geometrically!")
        print(f"    → Integrate these results into geocode_cache.json")
        print(f"    → Re-run frequency analysis with improved data")

    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
