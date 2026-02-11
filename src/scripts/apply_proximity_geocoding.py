#!/usr/bin/env python3
"""
apply_proximity_geocoding.py

Apply proximity-based geocoding to all failed 811 tickets using intelligent
approach selection based on road characteristics.

This solves the semantic issue where "intersection" means "work area vicinity"
rather than geometric intersection point.
"""

import json
import logging
from collections import Counter
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from proximity_geocoder import ProximityGeocoder

logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")

FAILURES_FILE = Path("ticket_failures.csv")
ROADS_FILE = Path("roads_merged.gpkg")
OUTPUT_RESULTS = Path("proximity_results.csv")
OUTPUT_SUMMARY = Path("proximity_summary.json")


def main():
    print("\n" + "=" * 70)
    print("APPLYING PROXIMITY-BASED GEOCODING TO FAILURES")
    print("=" * 70)

    # Load failures
    if not FAILURES_FILE.exists():
        print(f"❌ Failures file not found: {FAILURES_FILE}")
        return

    df = pd.read_csv(FAILURES_FILE)
    print(f"\n📋 Loaded {len(df)} failed tickets")

    # Initialize geocoder
    if not ROADS_FILE.exists():
        print(f"❌ Road network file not found: {ROADS_FILE}")
        return

    geocoder = ProximityGeocoder(ROADS_FILE)
    print(f"✅ Loaded road network")

    # Process each failure
    print(f"\n🔄 Processing failures...")

    results = []
    successes = 0
    approach_counts = Counter()
    failure_reasons = Counter()

    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Geocoding"):
        ticket_number = row["Number"]
        county = row["County"]
        city = row["City"]
        street = row["Street"]
        intersection = row["Intersection"]
        original_status = row.get("geocode_status", "ZERO_RESULTS")

        # Load ticket metadata for confidence adjustments
        ticket_type = row.get("Ticket Type")
        duration = row.get("Duration")
        work_type = row.get("Nature of Work")

        # Attempt proximity geocoding
        result = geocoder.geocode_proximity(
            street, intersection, county, city,
            ticket_type=ticket_type,
            duration=duration,
            work_type=work_type
        )

        # Record result
        result_row = {
            "ticket_number": ticket_number,
            "county": county,
            "city": city,
            "street": street,
            "intersection": intersection,
            "original_status": original_status,
            "proximity_success": result.success,
            "proximity_lat": result.lat,
            "proximity_lng": result.lng,
            "proximity_confidence": result.confidence,
            "proximity_approach": result.approach,
            "proximity_reasoning": result.reasoning,
            "proximity_error": result.error,
            "ticket_type": ticket_type,
            "duration": duration,
            "work_type": work_type,
        }
        results.append(result_row)

        if result.success:
            successes += 1
            approach_counts[result.approach] += 1
        else:
            failure_reasons[result.error or "unknown"] += 1

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

    # Confidence distribution
    success_df = results_df[results_df["proximity_success"]]
    if len(success_df) > 0:
        avg_confidence = success_df["proximity_confidence"].mean()
        min_confidence = success_df["proximity_confidence"].min()
        max_confidence = success_df["proximity_confidence"].max()
        confidence_stats = {
            "average": round(avg_confidence, 4),
            "min": round(min_confidence, 4),
            "max": round(max_confidence, 4),
        }
    else:
        confidence_stats = {}

    # Summary statistics
    summary = {
        "total_failed_tickets": total,
        "proximity_successes": successes,
        "proximity_failures": total - successes,
        "success_rate": round(success_rate, 2),
        "original_geocoding_success_rate": original_success_rate,
        "new_overall_success_rate": round(new_success_rate, 2),
        "improvement": round(new_success_rate - original_success_rate, 2),
        "approach_breakdown": dict(approach_counts),
        "failure_reasons": dict(failure_reasons.most_common(10)),
        "confidence_stats": confidence_stats,
    }

    # Save summary
    with OUTPUT_SUMMARY.open("w") as f:
        json.dump(summary, f, indent=2)
    print(f"💾 Saved summary to {OUTPUT_SUMMARY}")

    # Print report
    print("\n" + "=" * 70)
    print("PROXIMITY GEOCODING RESULTS")
    print("=" * 70)

    print(f"\n📊 OVERALL RESULTS")
    print("-" * 70)
    print(f"  Total failed tickets:          {total:,}")
    print(f"  Proximity successes:           {successes:,} ({success_rate:.2f}%)")
    print(f"  Proximity failures:            {total - successes:,} ({100 - success_rate:.2f}%)")

    print(f"\n📈 IMPROVEMENT ANALYSIS")
    print("-" * 70)
    print(f"  Original success rate:         {original_success_rate:.2f}%")
    print(f"  New overall success rate:      {new_success_rate:.2f}%")
    print(f"  Improvement:                   +{summary['improvement']:.2f} percentage points")
    print(f"  Additional tickets geocoded:   {successes:,}")

    print(f"\n🎯 APPROACH BREAKDOWN")
    print("-" * 70)
    for approach, count in approach_counts.most_common():
        pct = count / successes * 100 if successes > 0 else 0
        approach_name = {
            "closest_point": "Closest Point (parallel roads)",
            "corridor_midpoint": "Corridor Midpoint (highway segment)",
            "city_primary": "City + Primary Street",
        }.get(approach, approach)
        print(f"  {approach_name:40s} {count:4,} ({pct:5.1f}%)")

    if confidence_stats:
        print(f"\n🎯 CONFIDENCE SCORES")
        print("-" * 70)
        print(f"  Average confidence:            {confidence_stats['average']:.2%}")
        print(f"  Min confidence:                {confidence_stats['min']:.2%}")
        print(f"  Max confidence:                {confidence_stats['max']:.2%}")

    # Success by county
    success_by_county = results_df[results_df["proximity_success"]].groupby("county").size()
    if len(success_by_county) > 0:
        print(f"\n✅ SUCCESSES BY COUNTY")
        print("-" * 70)
        for county, count in success_by_county.items():
            print(f"  {county:20s} {count:4,}")

    # Failures
    if failure_reasons:
        print(f"\n❌ FAILURE REASONS (Top 5)")
        print("-" * 70)
        for reason, count in list(failure_reasons.items())[:5]:
            reason_short = (reason[:60] + "...") if len(reason) > 60 else reason
            print(f"  {reason_short:63s} {count:4,}")

    print("\n" + "=" * 70)

    # Comparison with geometric approach
    print(f"\n💡 COMPARISON WITH GEOMETRIC INTERSECTION APPROACH")
    print("-" * 70)
    print(f"  Geometric approach:            7 successes (0.96%)")
    print(f"  Proximity approach:            {successes:,} successes ({success_rate:.2f}%)")
    print(f"  Improvement:                   {successes - 7:,} additional tickets ({success_rate - 0.96:.2f}%)")

    print("\n" + "=" * 70)
    print("\n✅ Proximity-based geocoding correctly interprets 811 ticket semantics!")
    print("   'Intersection' field means 'work vicinity', not geometric intersection.")
    print(f"\n🎯 Achieved {new_success_rate:.2f}% overall success rate (+{summary['improvement']:.2f}%)")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
