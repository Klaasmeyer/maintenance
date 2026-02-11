#!/usr/bin/env python3
"""
analyze_ticket_geocoding.py

Analyze the actual 811 ticket dataset to understand geocoding success/failure
patterns. This examines tickets that haven't been geocoded yet or failed.

Input: projects/{project}/tickets/*.csv (or similar)
Output: Comprehensive failure analysis report
"""

import argparse
import json
import logging
from collections import Counter
from pathlib import Path

import pandas as pd

# Import project path utilities
try:
    from kcci_maintenance.utils.project_paths import resolve_project_file
    from kcci_maintenance.utils.ticket_loader import TicketLoader
except ImportError:
    # Fallback if utils not available
    def resolve_project_file(project_name, resource_type, filename, base_dir=Path("projects")):
        return base_dir / project_name / resource_type / filename
    TicketLoader = None

# Default paths (can be overridden by CLI args)
INPUT_FILE = Path("projects/wink/tickets")  # Now supports directory structures
OUTPUT_REPORT = Path("ticket_analysis_report.json")
OUTPUT_CSV = Path("ticket_failures.csv")

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def extract_road_type(road_name: str) -> str:
    """Extract road type prefix from road name."""
    if pd.isna(road_name) or not road_name:
        return "none"

    name_lower = str(road_name).lower().strip()

    # Check for common road type prefixes
    if any(name_lower.startswith(p) for p in ["fm ", "fm-", "f.m."]):
        return "FM"
    elif any(name_lower.startswith(p) for p in ["rm ", "rm-", "r.m."]):
        return "RM"
    elif any(name_lower.startswith(p) for p in ["cr ", "cr-", "county road", "co rd"]):
        return "CR"
    elif any(name_lower.startswith(p) for p in ["tx ", "tx-", "sh ", "state highway", "state hwy", "st hwy"]):
        return "TX/SH"
    elif any(name_lower.startswith(p) for p in ["i-", "i ", "ih", "interstate"]):
        return "Interstate"
    elif any(name_lower.startswith(p) for p in ["us ", "us-", "u.s."]):
        return "US Highway"
    elif any(name_lower.startswith(p) for p in ["loop", "spur", "bus"]):
        return "Loop/Spur/Bus"
    elif name_lower.startswith(("ne ", "nw ", "se ", "sw ", "n ", "s ", "e ", "w ")):
        return "Numbered (directional)"
    else:
        return "Local/Other"


def analyze_tickets(df: pd.DataFrame) -> dict:
    """Perform comprehensive analysis of ticket geocoding."""

    total = len(df)

    # Determine success criteria - check multiple possible columns
    if "geocode_ok" in df.columns:
        successes = df[df["geocode_ok"] == 1]
        failures = df[df["geocode_ok"] != 1]
    elif "lat" in df.columns and "lng" in df.columns:
        successes = df[(df["lat"].notna()) & (df["lng"].notna())]
        failures = df[(df["lat"].isna()) | (df["lng"].isna())]
    else:
        logging.error("Cannot determine success/failure - missing expected columns")
        return {}

    n_success = len(successes)
    n_failure = len(failures)

    # Status breakdown
    status_col = "geocode_status" if "geocode_status" in df.columns else None
    status_counter = Counter(df[status_col].fillna("MISSING")) if status_col else {}

    # Failure analysis
    failure_by_county = Counter(failures["County"].fillna("UNKNOWN"))
    failure_by_city = Counter(failures["City"].fillna("UNKNOWN"))

    # Determine if intersection or address
    has_intersection_col = "Intersection" in failures.columns
    if has_intersection_col:
        is_intersection = failures["Intersection"].notna() & (failures["Intersection"] != "")
        failure_by_type = {
            "intersection": int(is_intersection.sum()),
            "address": int((~is_intersection).sum()),
        }
    else:
        failure_by_type = {"unknown": n_failure}

    # Failure by status
    failure_by_status = Counter()
    if status_col:
        failure_by_status = Counter(failures[status_col].fillna("MISSING"))

    # Road type analysis for failures
    failure_by_road_type = Counter()
    if "Street" in failures.columns and "Intersection" in failures.columns:
        for _, row in failures.iterrows():
            street = row.get("Street", "")
            intersection = row.get("Intersection", "")

            street_type = extract_road_type(street)
            intersection_type = extract_road_type(intersection)

            if pd.notna(intersection) and str(intersection).strip():
                # It's an intersection
                failure_by_road_type[f"{street_type} & {intersection_type}"] += 1
            elif pd.notna(street) and str(street).strip():
                # It's an address
                failure_by_road_type[street_type] += 1
            else:
                failure_by_road_type["none"] += 1

    # Success analysis
    success_by_county = Counter(successes["County"].fillna("UNKNOWN"))
    if has_intersection_col:
        is_intersection_success = successes["Intersection"].notna() & (successes["Intersection"] != "")
        success_by_type = {
            "intersection": int(is_intersection_success.sum()),
            "address": int((~is_intersection_success).sum()),
        }
    else:
        success_by_type = {"unknown": n_success}

    # Sample failures for inspection
    sample_failures = []
    for _, row in failures.head(20).iterrows():
        sample_failures.append({
            "number": str(row.get("Number", "")),
            "county": str(row.get("County", "")),
            "city": str(row.get("City", "")),
            "street": str(row.get("Street", "")),
            "intersection": str(row.get("Intersection", "")),
            "status": str(row.get(status_col, "")) if status_col else "UNKNOWN",
        })

    return {
        "summary": {
            "total_tickets": total,
            "successful": n_success,
            "failed": n_failure,
            "success_rate": round(n_success / total * 100, 2) if total > 0 else 0,
        },
        "status_breakdown": dict(status_counter.most_common()),
        "failures": {
            "by_county": dict(failure_by_county.most_common()),
            "by_city": dict(failure_by_city.most_common(20)),
            "by_type": failure_by_type,
            "by_status": dict(failure_by_status.most_common()),
            "by_road_type": dict(failure_by_road_type.most_common(20)),
            "sample_records": sample_failures,
        },
        "successes": {
            "by_county": dict(success_by_county.most_common()),
            "by_type": success_by_type,
        },
    }


def print_report(analysis: dict) -> None:
    """Print human-readable analysis report."""

    summary = analysis["summary"]
    failures = analysis["failures"]
    successes = analysis["successes"]

    print("\n" + "=" * 70)
    print("811 TICKET GEOCODING ANALYSIS REPORT")
    print("=" * 70)

    print("\n📊 OVERALL SUMMARY")
    print("-" * 70)
    print(f"  Total tickets:        {summary['total_tickets']:,}")
    print(f"  Successfully geocoded:{summary['successful']:,}")
    print(f"  Failed/missing:       {summary['failed']:,}")
    print(f"  Success rate:         {summary['success_rate']:.2f}%")

    if summary['failed'] > 0:
        print(f"\n  ⚠️  {summary['failed']:,} tickets need geocoding!")

    if analysis["status_breakdown"]:
        print("\n🔍 GEOCODE STATUS BREAKDOWN")
        print("-" * 70)
        for status, count in analysis["status_breakdown"].items():
            pct = count / summary['total_tickets'] * 100
            print(f"  {status:20s} {count:5,} ({pct:5.2f}%)")

    print("\n❌ FAILURES BY TYPE")
    print("-" * 70)
    for fail_type, count in failures["by_type"].items():
        pct = count / summary['failed'] * 100 if summary['failed'] > 0 else 0
        print(f"  {fail_type:20s} {count:5,} ({pct:5.2f}%)")

    if failures["by_status"]:
        print("\n❌ FAILURES BY STATUS")
        print("-" * 70)
        for status, count in failures["by_status"].items():
            pct = count / summary['failed'] * 100 if summary['failed'] > 0 else 0
            print(f"  {status:20s} {count:5,} ({pct:5.2f}%)")

    print("\n❌ FAILURES BY COUNTY")
    print("-" * 70)
    for county, count in failures["by_county"].items():
        total_county = failures["by_county"][county]
        print(f"  {county:20s} {count:5,}")

    print("\n❌ FAILURES BY CITY (Top 10)")
    print("-" * 70)
    for city, count in list(failures["by_city"].items())[:10]:
        print(f"  {city:20s} {count:5,}")

    print("\n❌ FAILURES BY ROAD TYPE (Top 15)")
    print("-" * 70)
    for road_type, count in list(failures["by_road_type"].items())[:15]:
        print(f"  {road_type:40s} {count:5,}")

    print("\n✅ SUCCESSES BY TYPE")
    print("-" * 70)
    for success_type, count in successes["by_type"].items():
        pct = count / summary['successful'] * 100 if summary['successful'] > 0 else 0
        print(f"  {success_type:20s} {count:5,} ({pct:5.2f}%)")

    print("\n✅ SUCCESSES BY COUNTY")
    print("-" * 70)
    for county, count in successes["by_county"].items():
        print(f"  {county:20s} {count:5,}")

    if failures["sample_records"]:
        print("\n📋 SAMPLE FAILED TICKETS (First 20)")
        print("-" * 70)
        for i, record in enumerate(failures["sample_records"], 1):
            print(f"\n  {i}. Ticket {record['number']}")
            print(f"     County: {record['county']}, City: {record['city']}")
            print(f"     Street: {record['street']}")
            print(f"     Intersection: {record['intersection']}")
            print(f"     Status: {record['status']}")

    print("\n" + "=" * 70)

    # Key insights
    print("\n💡 KEY INSIGHTS & RECOMMENDATIONS")
    print("-" * 70)

    if summary['failed'] > 0:
        if failures["by_status"]:
            top_failure_status = list(failures["by_status"].items())[0]
            print(f"  • Most common failure: {top_failure_status[0]} ({top_failure_status[1]:,} cases)")

        int_failures = failures["by_type"].get("intersection", 0)
        addr_failures = failures["by_type"].get("address", 0)
        if int_failures > addr_failures:
            print(f"  • Intersections fail more often ({int_failures:,} vs {addr_failures:,})")
            print(f"    → Geometric intersection calculation could help significantly")
        elif addr_failures > int_failures:
            print(f"  • Addresses fail more often ({addr_failures:,} vs {int_failures:,})")
            print(f"    → Focus on address normalization and fuzzy matching")

        if failures["by_road_type"]:
            top_road_failure = list(failures["by_road_type"].items())[0]
            print(f"  • Most problematic road type: {top_road_failure[0]}")
            print(f"    → {top_road_failure[1]:,} failures involve this type")

        # Calculate potential improvement
        if int_failures > 0:
            potential = int_failures
            new_rate = ((summary['successful'] + potential) / summary['total_tickets']) * 100
            print(f"\n  🎯 POTENTIAL IMPROVEMENT:")
            print(f"     If geometric intersection solving succeeds for all intersection failures:")
            print(f"     Success rate could increase: {summary['success_rate']:.2f}% → {new_rate:.2f}%")
            print(f"     That's {potential:,} additional geocoded tickets!")

    print("=" * 70 + "\n")


def main() -> None:
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Analyze 811 ticket geocoding success/failure patterns"
    )
    parser.add_argument(
        "--project",
        type=str,
        help="Project name (e.g., 'wink', 'floydada'). Will auto-resolve to projects/{project}/tickets/",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Input CSV/Excel file or directory with tickets (overrides --project)",
    )
    parser.add_argument(
        "--output-report",
        type=Path,
        default=OUTPUT_REPORT,
        help=f"Output JSON report path (default: {OUTPUT_REPORT})",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=OUTPUT_CSV,
        help=f"Output failures CSV path (default: {OUTPUT_CSV})",
    )

    args = parser.parse_args()

    # Determine input path (file or directory)
    if args.input:
        input_path = args.input
    elif args.project:
        # Auto-resolve project path - use tickets directory
        input_path = Path("projects") / args.project / "tickets"
    else:
        input_path = INPUT_FILE

    if not input_path.exists():
        logging.error(f"Input path not found: {input_path}")
        logging.info("Please ensure the ticket dataset is at the expected location.")
        logging.info("Use --project <name> or --input <path> to specify input.")
        return

    # Load tickets using TicketLoader if available (supports directory structures)
    if TicketLoader is not None and input_path.is_dir():
        logging.info(f"Loading tickets from directory: {input_path}")
        try:
            loader = TicketLoader(normalize_columns=True)
            df = loader.load(input_path)
            if '_source_file' in df.columns:
                num_files = df['_source_file'].nunique()
                logging.info(f"Loaded {len(df):,} tickets from {num_files} file(s)")
        except Exception as e:
            logging.error(f"Failed to load tickets: {e}")
            return
    else:
        # Single file loading (legacy)
        logging.info(f"Loading tickets from {input_path}")
        df = pd.read_csv(input_path, low_memory=False)

    logging.info(f"Analyzing {len(df):,} tickets...")
    analysis = analyze_tickets(df)

    if not analysis:
        return

    # Print report to console
    print_report(analysis)

    # Save JSON report
    report_data = {
        "summary": analysis["summary"],
        "status_breakdown": analysis["status_breakdown"],
        "failures": {
            "by_county": analysis["failures"]["by_county"],
            "by_city": analysis["failures"]["by_city"],
            "by_type": analysis["failures"]["by_type"],
            "by_status": analysis["failures"]["by_status"],
            "by_road_type": analysis["failures"]["by_road_type"],
        },
        "successes": analysis["successes"],
    }

    output_report = args.output_report
    with output_report.open("w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    logging.info(f"Saved detailed report to {output_report}")

    # Export failure records to CSV for further analysis
    if analysis["summary"]["failed"] > 0:
        # Reload and filter for failures
        if "geocode_ok" in df.columns:
            failures_df = df[df["geocode_ok"] != 1].copy()
        else:
            failures_df = df[(df["lat"].isna()) | (df["lng"].isna())].copy()

        # Select key columns
        key_cols = ["Number", "County", "City", "Street", "Intersection"]
        if "geocode_status" in failures_df.columns:
            key_cols.append("geocode_status")
        if "_geo_key" in failures_df.columns:
            key_cols.append("_geo_key")

        export_cols = [col for col in key_cols if col in failures_df.columns]
        output_csv = args.output_csv
        failures_df[export_cols].to_csv(output_csv, index=False)
        logging.info(f"Saved {len(failures_df):,} failure records to {output_csv}")


if __name__ == "__main__":
    main()
