#!/usr/bin/env python3
"""
analyze_geocode_failures.py

Analyze geocode_cache.json to understand failure patterns and calculate
success rates. This informs the strategy for improving geocoding.

Output:
    - Console report with statistics
    - failures_report.json with detailed breakdown
    - failures_by_type.csv for further analysis
"""

import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

CACHE_FILE = Path("geocode_cache.json")
OUTPUT_REPORT = Path("failures_report.json")
OUTPUT_CSV = Path("failures_by_type.csv")

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def is_geocode_ok(entry: dict[str, Any]) -> bool:
    """Check if geocode was successful."""
    geocode = entry.get("geocode", {})
    if not isinstance(geocode, dict):
        return False
    return geocode.get("status") == "OK" and geocode.get("lat") is not None


def extract_road_type(road_name: str) -> str:
    """Extract road type prefix from road name."""
    if not road_name:
        return "none"

    name_lower = road_name.lower().strip()

    # Check for common road type prefixes
    if name_lower.startswith(("fm ", "fm-")):
        return "FM"
    elif name_lower.startswith(("rm ", "rm-")):
        return "RM"
    elif name_lower.startswith(("cr ", "cr-", "county road")):
        return "CR"
    elif name_lower.startswith(("tx ", "tx-", "sh ", "state")):
        return "TX/SH"
    elif name_lower.startswith(("i-", "i ", "ih", "interstate")):
        return "Interstate"
    elif name_lower.startswith(("us ", "us-")):
        return "US Highway"
    elif name_lower.startswith(("loop", "spur", "bus")):
        return "Loop/Spur/Bus"
    else:
        return "Local/Other"


def analyze_cache(cache: dict[str, Any]) -> dict[str, Any]:
    """Perform comprehensive analysis of geocode cache."""

    total = len(cache)
    successes = sum(1 for entry in cache.values() if is_geocode_ok(entry))
    failures = total - successes

    # Status breakdown
    status_counter = Counter()

    # Failure analysis by various dimensions
    failure_by_county = Counter()
    failure_by_city = Counter()
    failure_by_type = Counter()  # intersection vs address
    failure_by_status = Counter()
    failure_by_road_type = Counter()

    # Success analysis
    success_by_county = Counter()
    success_by_type = Counter()

    # Detailed failure records for CSV export
    failure_records = []

    for geo_key, entry in cache.items():
        geocode = entry.get("geocode", {})
        status = geocode.get("status", "MISSING") if isinstance(geocode, dict) else "MISSING"
        status_counter[status] += 1

        county = entry.get("county", "UNKNOWN")
        city = entry.get("city", "UNKNOWN")
        is_intersection = entry.get("is_intersection", False)
        street = entry.get("street", "")
        intersection = entry.get("intersection", "")

        entry_type = "intersection" if is_intersection else "address"

        if is_geocode_ok(entry):
            success_by_county[county] += 1
            success_by_type[entry_type] += 1
        else:
            failure_by_county[county] += 1
            failure_by_city[city] += 1
            failure_by_type[entry_type] += 1
            failure_by_status[status] += 1

            # Determine road types involved
            road_type_street = extract_road_type(street)
            road_type_intersection = extract_road_type(intersection)

            if is_intersection and street and intersection:
                failure_by_road_type[f"{road_type_street} & {road_type_intersection}"] += 1
            elif street:
                failure_by_road_type[road_type_street] += 1
            elif intersection:
                failure_by_road_type[road_type_intersection] += 1

            # Record for CSV
            failure_records.append({
                "geo_key": geo_key,
                "county": county,
                "city": city,
                "type": entry_type,
                "status": status,
                "street": street,
                "intersection": intersection,
                "street_road_type": road_type_street,
                "intersection_road_type": road_type_intersection,
                "raw_line": entry.get("raw_line", ""),
                "normalized_line": entry.get("normalized_line", ""),
            })

    return {
        "summary": {
            "total_entries": total,
            "successful": successes,
            "failed": failures,
            "success_rate": round(successes / total * 100, 2) if total > 0 else 0,
        },
        "status_breakdown": dict(status_counter.most_common()),
        "failures": {
            "by_county": dict(failure_by_county.most_common()),
            "by_city": dict(failure_by_city.most_common(20)),  # top 20 cities
            "by_type": dict(failure_by_type.most_common()),
            "by_status": dict(failure_by_status.most_common()),
            "by_road_type": dict(failure_by_road_type.most_common()),
        },
        "successes": {
            "by_county": dict(success_by_county.most_common()),
            "by_type": dict(success_by_type.most_common()),
        },
        "failure_records": failure_records,
    }


def print_report(analysis: dict[str, Any]) -> None:
    """Print human-readable analysis report."""

    summary = analysis["summary"]
    failures = analysis["failures"]
    successes = analysis["successes"]

    print("\n" + "=" * 70)
    print("GEOCODE CACHE ANALYSIS REPORT")
    print("=" * 70)

    print("\n📊 OVERALL SUMMARY")
    print("-" * 70)
    print(f"  Total entries:        {summary['total_entries']:,}")
    print(f"  Successful geocodes:  {summary['successful']:,}")
    print(f"  Failed geocodes:      {summary['failed']:,}")
    print(f"  Success rate:         {summary['success_rate']:.2f}%")

    print("\n🔍 STATUS BREAKDOWN")
    print("-" * 70)
    for status, count in analysis["status_breakdown"].items():
        pct = count / summary['total_entries'] * 100
        print(f"  {status:20s} {count:5,} ({pct:5.2f}%)")

    print("\n❌ FAILURES BY TYPE")
    print("-" * 70)
    for fail_type, count in failures["by_type"].items():
        print(f"  {fail_type:20s} {count:5,}")

    print("\n❌ FAILURES BY STATUS")
    print("-" * 70)
    for status, count in failures["by_status"].items():
        pct = count / summary['failed'] * 100 if summary['failed'] > 0 else 0
        print(f"  {status:20s} {count:5,} ({pct:5.2f}% of failures)")

    print("\n❌ FAILURES BY COUNTY")
    print("-" * 70)
    for county, count in failures["by_county"].items():
        print(f"  {county:20s} {count:5,}")

    print("\n❌ FAILURES BY ROAD TYPE")
    print("-" * 70)
    for road_type, count in list(failures["by_road_type"].items())[:15]:
        print(f"  {road_type:30s} {count:5,}")

    print("\n✅ SUCCESSES BY TYPE")
    print("-" * 70)
    for success_type, count in successes["by_type"].items():
        print(f"  {success_type:20s} {count:5,}")

    print("\n✅ SUCCESSES BY COUNTY")
    print("-" * 70)
    for county, count in successes["by_county"].items():
        print(f"  {county:20s} {count:5,}")

    print("\n" + "=" * 70)

    # Key insights
    print("\n💡 KEY INSIGHTS")
    print("-" * 70)

    if summary['failed'] > 0:
        top_failure_status = list(failures["by_status"].items())[0]
        print(f"  • Most common failure: {top_failure_status[0]} ({top_failure_status[1]:,} cases)")

        if failures["by_type"].get("intersection", 0) > failures["by_type"].get("address", 0):
            print(f"  • Intersections fail more often than addresses")
        else:
            print(f"  • Addresses fail more often than intersections")

        if failures["by_road_type"]:
            top_road_failure = list(failures["by_road_type"].items())[0]
            print(f"  • Most problematic road type: {top_road_failure[0]} ({top_road_failure[1]:,} failures)")

    print("=" * 70 + "\n")


def main() -> None:
    if not CACHE_FILE.exists():
        logging.error(f"Cache file not found: {CACHE_FILE}")
        return

    logging.info(f"Loading cache from {CACHE_FILE}")
    with CACHE_FILE.open("r", encoding="utf-8") as f:
        cache = json.load(f)

    logging.info(f"Analyzing {len(cache):,} cache entries...")
    analysis = analyze_cache(cache)

    # Print report to console
    print_report(analysis)

    # Save JSON report
    report_data = {
        "summary": analysis["summary"],
        "status_breakdown": analysis["status_breakdown"],
        "failures": analysis["failures"],
        "successes": analysis["successes"],
    }

    with OUTPUT_REPORT.open("w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    logging.info(f"Saved detailed report to {OUTPUT_REPORT}")

    # Save failure records to CSV
    if analysis["failure_records"]:
        df = pd.DataFrame(analysis["failure_records"])
        df.to_csv(OUTPUT_CSV, index=False)
        logging.info(f"Saved {len(df):,} failure records to {OUTPUT_CSV}")
    else:
        logging.info("No failures to export to CSV")


if __name__ == "__main__":
    main()
