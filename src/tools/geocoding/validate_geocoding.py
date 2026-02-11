#!/usr/bin/env python3
"""
validate_geocoding.py

Validate proximity geocoding results and flag suspicious entries for manual review.

Checks:
1. Low confidence scores (< 65%)
2. Emergency tickets with low confidence (< 75%)
3. Locations far from city center (> 50km)
4. Fallback geocodes (city centroid)
5. Unusual approach selections
"""

import json
from pathlib import Path

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

# City centroids for distance validation (same as ProximityGeocoder)
CITY_CENTROIDS = {
    ("KERMIT", "WINKLER"): (31.8576, -103.0930),
    ("PYOTE", "WARD"): (31.5401, -103.1293),
    ("BARSTOW", "WARD"): (31.4596, -103.3954),
    ("MONAHANS", "WARD"): (31.5943, -102.8929),
    ("ANDREWS", "ANDREWS"): (32.3185, -102.5457),
    ("GARDENDALE", "ANDREWS"): (32.0165, -102.3779),
    ("COYANOSA", "WARD"): (31.2693, -103.0324),
    ("WICKETT", "WARD"): (31.5768, -103.0010),
    ("THORNTONVILLE", "WARD"): (31.4446, -103.1079),
}

RESULTS_FILE = Path("proximity_results.csv")
OUTPUT_VALIDATION = Path("geocoding_validation_report.csv")
OUTPUT_SUMMARY = Path("validation_summary.json")


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in km between two lat/lng points."""
    from math import radians, sin, cos, sqrt, atan2

    R = 6371  # Earth radius in km

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


def validate_results(df: pd.DataFrame) -> pd.DataFrame:
    """Validate geocoding results and flag issues.

    Returns DataFrame with validation flags and reasons.
    """
    validation_flags = []

    for idx, row in df.iterrows():
        if not row["proximity_success"]:
            validation_flags.append(
                {
                    "ticket_number": row["ticket_number"],
                    "flag": "FAILURE",
                    "severity": "HIGH",
                    "reason": f"Geocoding failed: {row['proximity_error']}",
                    "confidence": None,
                    "distance_from_city_km": None,
                    "action": "Manual geocoding required",
                }
            )
            continue

        flags = []
        severity = "OK"
        actions = []

        confidence = row["proximity_confidence"]
        approach = row["proximity_approach"]
        city = row["city"]
        county = row["county"]
        lat = row["proximity_lat"]
        lng = row["proximity_lng"]

        # Get ticket metadata
        ticket_type = row.get("ticket_type", None)
        work_type = row.get("work_type", None)

        # Check 1: Low confidence
        if confidence < 0.65:
            flags.append(f"Low confidence: {confidence:.1%}")
            severity = "MEDIUM" if severity == "OK" else severity
            actions.append("Review location accuracy")

        # Check 2: Emergency ticket with low confidence
        if pd.notna(ticket_type) and ticket_type == "Emergency" and confidence < 0.75:
            flags.append(f"Emergency ticket with {confidence:.1%} confidence")
            severity = "HIGH"
            actions.append("High priority review - emergency response location")

        # Check 3: City centroid fallback
        if approach == "city_centroid_fallback":
            flags.append("City centroid fallback used (both roads missing)")
            severity = "HIGH"
            actions.append("Locate actual work area - city centroid is approximate")

        # Check 4: Distance from city center
        city_key = (city.upper(), county.upper())
        if city_key in CITY_CENTROIDS:
            city_lat, city_lng = CITY_CENTROIDS[city_key]
            distance = haversine_distance(lat, lng, city_lat, city_lng)

            if distance > 50:
                flags.append(f"Location {distance:.1f}km from {city} center")
                severity = "MEDIUM" if severity == "OK" else severity
                actions.append("Verify location is correct for city")
        else:
            distance = None

        # Check 5: Very low confidence approach 4 (one road missing)
        if approach == "city_primary" and confidence < 0.55:
            flags.append(f"One road missing, low confidence: {confidence:.1%}")
            severity = "MEDIUM" if severity == "OK" else severity
            actions.append("Consider finding missing road or more precise location")

        # Create validation entry
        if flags:
            validation_flags.append(
                {
                    "ticket_number": row["ticket_number"],
                    "flag": "; ".join(flags),
                    "severity": severity,
                    "reason": f"{approach} approach, " + ", ".join(flags),
                    "confidence": confidence,
                    "distance_from_city_km": distance,
                    "action": "; ".join(actions),
                    "city": city,
                    "county": county,
                    "street": row["street"],
                    "intersection": row["intersection"],
                    "ticket_type": ticket_type,
                    "work_type": work_type,
                }
            )

    return pd.DataFrame(validation_flags)


def main():
    print("\n" + "=" * 80)
    print("GEOCODING VALIDATION REPORT")
    print("=" * 80)

    # Load results
    if not RESULTS_FILE.exists():
        print(f"❌ Results file not found: {RESULTS_FILE}")
        return

    df = pd.read_csv(RESULTS_FILE)
    print(f"\n📋 Loaded {len(df)} geocoding results")

    # Run validation
    print("\n🔍 Running validation checks...")
    validation_df = validate_results(df)

    if len(validation_df) == 0:
        print("\n✅ All geocoding results passed validation!")
        print("   No issues found.")
        return

    # Save validation report
    validation_df.to_csv(OUTPUT_VALIDATION, index=False)
    print(f"\n💾 Saved validation report to {OUTPUT_VALIDATION}")

    # Generate summary statistics
    total_flagged = len(validation_df)
    severity_counts = validation_df["severity"].value_counts().to_dict()

    # Top issues
    flag_counts = validation_df["flag"].value_counts().head(10).to_dict()

    # Confidence distribution of flagged tickets
    flagged_with_conf = validation_df[validation_df["confidence"].notna()]
    if len(flagged_with_conf) > 0:
        avg_confidence = flagged_with_conf["confidence"].mean()
        min_confidence = flagged_with_conf["confidence"].min()
        max_confidence = flagged_with_conf["confidence"].max()
    else:
        avg_confidence = min_confidence = max_confidence = None

    summary = {
        "total_geocoded": len(df),
        "total_flagged": total_flagged,
        "flagged_percentage": round(total_flagged / len(df) * 100, 2),
        "severity_breakdown": severity_counts,
        "top_issues": flag_counts,
        "flagged_confidence_stats": {
            "average": round(avg_confidence, 4) if avg_confidence else None,
            "min": round(min_confidence, 4) if min_confidence else None,
            "max": round(max_confidence, 4) if max_confidence else None,
        },
    }

    # Save summary
    with OUTPUT_SUMMARY.open("w") as f:
        json.dump(summary, f, indent=2)
    print(f"💾 Saved summary to {OUTPUT_SUMMARY}")

    # Print report
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)

    print(f"\n📊 OVERALL STATISTICS")
    print("-" * 80)
    print(f"  Total geocoded tickets:       {len(df):,}")
    print(f"  Flagged for review:           {total_flagged:,} ({summary['flagged_percentage']:.1f}%)")
    print(f"  Passed validation:            {len(df) - total_flagged:,}")

    print(f"\n⚠️  SEVERITY BREAKDOWN")
    print("-" * 80)
    for severity in ["HIGH", "MEDIUM", "OK"]:
        count = severity_counts.get(severity, 0)
        pct = count / total_flagged * 100 if total_flagged > 0 else 0
        icon = "🔴" if severity == "HIGH" else "🟡" if severity == "MEDIUM" else "🟢"
        print(f"  {icon} {severity:10s} {count:4,} ({pct:5.1f}%)")

    print(f"\n🔍 TOP ISSUES")
    print("-" * 80)
    for issue, count in list(flag_counts.items())[:5]:
        issue_short = (issue[:70] + "...") if len(issue) > 70 else issue
        print(f"  {issue_short:73s} {count:4,}")

    if avg_confidence:
        print(f"\n📉 FLAGGED TICKETS CONFIDENCE")
        print("-" * 80)
        print(f"  Average confidence:           {avg_confidence:.2%}")
        print(f"  Min confidence:               {min_confidence:.2%}")
        print(f"  Max confidence:               {max_confidence:.2%}")

    # Priority actions
    high_priority = validation_df[validation_df["severity"] == "HIGH"]
    if len(high_priority) > 0:
        print(f"\n🚨 HIGH PRIORITY ACTIONS ({len(high_priority)} tickets)")
        print("-" * 80)
        for _, row in high_priority.head(10).iterrows():
            print(f"  Ticket {row['ticket_number']}: {row['flag']}")
            print(f"    Action: {row['action']}")

    print("\n" + "=" * 80)
    print(f"\n📝 Review flagged tickets in: {OUTPUT_VALIDATION}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
