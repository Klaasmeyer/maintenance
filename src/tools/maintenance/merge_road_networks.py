#!/usr/bin/env python3
"""
merge_road_networks.py

Merge TxDOT and OSM road networks into a single unified dataset.
Handles deduplication and field normalization.
"""

import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

OSM_FILE = Path("roads.gpkg")
TXDOT_FILE = Path("txdot_data/txdot_state_highways.gpkg")
OUTPUT_FILE = Path("roads_merged.gpkg")


def normalize_osm_roads(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Normalize OSM road data to unified schema."""
    normalized = gdf.copy()

    normalized["source"] = "OSM"
    normalized["road_name"] = normalized["name"].fillna(normalized["ref"])
    normalized["road_ref"] = normalized["ref"]

    # Keep only essential columns
    keep_cols = ["road_name", "road_ref", "road_type", "source", "geometry"]
    return normalized[keep_cols]


def normalize_txdot_roads(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Normalize TxDOT road data to unified schema."""
    normalized = gdf.copy()

    normalized["source"] = "TxDOT"

    # Build road name from prefix + number
    normalized["road_ref"] = (
        normalized["RTE_PRFX"].fillna("") + " " +
        normalized["RTE_NBR"].astype(str)
    ).str.strip()

    # Use MAP_LBL as primary name, fall back to constructed ref
    normalized["road_name"] = normalized["MAP_LBL"].fillna(normalized["road_ref"])

    # Classify road type
    normalized["road_type"] = normalized["RTE_PRFX"].map({
        "CR": "CR",
        "FM": "FM",
        "RM": "RM",
        "US": "US",
        "SH": "TX_SH",
        "IH": "Interstate",
    }).fillna("OTHER")

    # Keep only essential columns
    keep_cols = ["road_name", "road_ref", "road_type", "source", "geometry"]
    return normalized[keep_cols]


def deduplicate_roads(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Remove duplicate road segments based on geometry similarity."""
    # For now, simple deduplication by exact geometry match
    # In production, might want spatial tolerance-based deduplication

    before = len(gdf)
    gdf = gdf.drop_duplicates(subset=["geometry"])
    after = len(gdf)

    if before > after:
        logging.info(f"Removed {before - after} exact duplicate geometries")

    return gdf


def main():
    print("\n" + "=" * 70)
    print("MERGING ROAD NETWORKS")
    print("=" * 70)

    # Load OSM data
    if not OSM_FILE.exists():
        logging.error(f"OSM road file not found: {OSM_FILE}")
        return

    logging.info(f"Loading OSM roads from {OSM_FILE}")
    osm_gdf = gpd.read_file(OSM_FILE, layer="roads")
    logging.info(f"Loaded {len(osm_gdf)} OSM road segments")

    # Load TxDOT data
    if not TXDOT_FILE.exists():
        logging.error(f"TxDOT road file not found: {TXDOT_FILE}")
        return

    logging.info(f"Loading TxDOT roads from {TXDOT_FILE}")
    txdot_gdf = gpd.read_file(TXDOT_FILE)
    logging.info(f"Loaded {len(txdot_gdf)} TxDOT road segments")

    # Normalize both datasets
    logging.info("Normalizing OSM data...")
    osm_normalized = normalize_osm_roads(osm_gdf)

    logging.info("Normalizing TxDOT data...")
    txdot_normalized = normalize_txdot_roads(txdot_gdf)

    # Merge
    logging.info("Merging datasets...")
    merged = pd.concat([osm_normalized, txdot_normalized], ignore_index=True)

    # Ensure CRS consistency
    if merged.crs is None:
        merged.set_crs("EPSG:4326", inplace=True)

    logging.info(f"Merged total: {len(merged)} segments")

    # Deduplicate
    logging.info("Deduplicating...")
    merged = deduplicate_roads(merged)
    logging.info(f"After deduplication: {len(merged)} segments")

    # Create spatial index
    logging.info("Creating spatial index...")
    merged.sindex

    # Save
    logging.info(f"Saving to {OUTPUT_FILE}")
    merged.to_file(OUTPUT_FILE, driver="GPKG", layer="roads")

    # Summary
    print("\n" + "=" * 70)
    print("MERGE COMPLETE")
    print("=" * 70)
    print(f"\nInput:")
    print(f"  OSM:    {len(osm_gdf):,} segments")
    print(f"  TxDOT:  {len(txdot_gdf):,} segments")
    print(f"\nOutput:")
    print(f"  Merged: {len(merged):,} segments")
    print(f"  File:   {OUTPUT_FILE}")

    print(f"\nRoad type distribution:")
    type_counts = merged["road_type"].value_counts()
    for road_type, count in type_counts.items():
        print(f"  {road_type:20s} {count:4,}")

    print(f"\nSource distribution:")
    source_counts = merged["source"].value_counts()
    for source, count in source_counts.items():
        print(f"  {source:20s} {count:4,}")

    print("\n" + "=" * 70)
    print("\nNext: Re-run geometric geocoding with merged data")
    print(f"  python apply_geometric_geocoding.py")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
