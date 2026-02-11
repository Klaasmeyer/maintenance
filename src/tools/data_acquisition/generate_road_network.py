#!/usr/bin/env python3
"""
Generate roads_merged.gpkg from TIGER/Line Census data.

Downloads road data for Ward, Andrews, and Winkler counties in Texas
and merges them into a single GeoPackage file for the geocoding pipeline.
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile

import geopandas as gpd
import pandas as pd

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

# Texas counties for Wink project
COUNTIES = {
    "Ward": "48475",
    "Andrews": "48003",
    "Winkler": "48495",
}

TIGER_YEAR = "2024"
OUTPUT_FILE = Path("roads_merged.gpkg")


def download_tiger_roads(county_name: str, fips_code: str, temp_dir: Path) -> Path:
    """Download TIGER/Line roads for a county."""
    url = f"https://www2.census.gov/geo/tiger/TIGER{TIGER_YEAR}/ROADS/tl_{TIGER_YEAR}_{fips_code}_roads.zip"
    zip_path = temp_dir / f"{county_name}_roads.zip"

    logging.info(f"Downloading {county_name} County roads from TIGER/Line...")

    try:
        result = subprocess.run(
            ["curl", "-L", "-o", str(zip_path), url],
            capture_output=True,
            text=True,
            check=True,
        )
        logging.info(f"  Downloaded {zip_path.stat().st_size / 1024 / 1024:.1f} MB")
        return zip_path
    except subprocess.CalledProcessError as e:
        logging.error(f"  Failed to download: {e}")
        raise


def extract_shapefile(zip_path: Path, temp_dir: Path) -> Path:
    """Extract shapefile from zip archive."""
    logging.info(f"Extracting {zip_path.name}...")

    with ZipFile(zip_path, 'r') as zf:
        zf.extractall(temp_dir)

    # Find the .shp file
    shp_files = list(temp_dir.glob("*.shp"))
    if not shp_files:
        raise FileNotFoundError(f"No shapefile found in {zip_path}")

    return shp_files[0]


def load_and_normalize_roads(shp_path: Path, county_name: str) -> gpd.GeoDataFrame:
    """Load shapefile and normalize to unified schema."""
    logging.info(f"Loading {county_name} County roads...")

    gdf = gpd.read_file(shp_path)
    logging.info(f"  Loaded {len(gdf):,} road segments")

    # Normalize to unified schema
    normalized = gdf.copy()

    # Build road name from FULLNAME field
    normalized["road_name"] = normalized.get("FULLNAME", normalized.get("NAME", ""))

    # Extract road ref (e.g., "CR 426", "FM 1788")
    normalized["road_ref"] = normalized["road_name"]

    # Classify road type based on road name
    def classify_road_type(name):
        if pd.isna(name):
            return "OTHER"
        name = str(name).upper()
        if "CR " in name or "COUNTY ROAD" in name:
            return "CR"
        elif "FM " in name or "FARM" in name:
            return "FM"
        elif "RM " in name or "RANCH" in name:
            return "RM"
        elif "US " in name or "US HWY" in name:
            return "US"
        elif "SH " in name or "STATE HWY" in name:
            return "TX_SH"
        elif "I-" in name or "IH " in name or "INTERSTATE" in name:
            return "Interstate"
        else:
            return "OTHER"

    normalized["road_type"] = normalized["road_name"].apply(classify_road_type)
    normalized["source"] = f"TIGER/Line ({county_name})"
    normalized["county"] = county_name

    # Keep only essential columns
    keep_cols = ["road_name", "road_ref", "road_type", "source", "county", "geometry"]
    result = normalized[keep_cols].copy()

    # Ensure CRS is EPSG:4326 (WGS84)
    if result.crs != "EPSG:4326":
        logging.info(f"  Reprojecting from {result.crs} to EPSG:4326")
        result = result.to_crs("EPSG:4326")

    return result


def deduplicate_roads(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Remove duplicate road segments."""
    before = len(gdf)

    # Remove exact duplicates based on geometry
    gdf = gdf.drop_duplicates(subset=["geometry"])

    after = len(gdf)
    if before > after:
        logging.info(f"Removed {before - after:,} duplicate geometries")

    return gdf


def main():
    print("\n" + "=" * 70)
    print("GENERATING ROAD NETWORK FOR WINK PROJECT")
    print("=" * 70)
    print(f"\nCounties: Ward, Andrews, Winkler")
    print(f"Source: TIGER/Line {TIGER_YEAR} (US Census Bureau)")
    print()

    all_roads = []

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Download and process each county
        for county_name, fips_code in COUNTIES.items():
            try:
                # Download
                zip_path = download_tiger_roads(county_name, fips_code, temp_path)

                # Extract
                county_temp = temp_path / county_name
                county_temp.mkdir(exist_ok=True)
                shp_path = extract_shapefile(zip_path, county_temp)

                # Load and normalize
                county_roads = load_and_normalize_roads(shp_path, county_name)
                all_roads.append(county_roads)

                logging.info(f"✓ {county_name} County: {len(county_roads):,} segments")
                print()

            except Exception as e:
                logging.error(f"✗ Failed to process {county_name} County: {e}")
                continue

    if not all_roads:
        logging.error("No road data was successfully downloaded")
        return

    # Merge all counties
    logging.info("Merging counties...")
    merged = pd.concat(all_roads, ignore_index=True)
    logging.info(f"  Total: {len(merged):,} segments")

    # Deduplicate
    logging.info("Deduplicating...")
    merged = deduplicate_roads(merged)
    logging.info(f"  After deduplication: {len(merged):,} segments")

    # Create spatial index for performance
    logging.info("Creating spatial index...")
    merged.sindex  # Trigger index creation

    # Save to GeoPackage
    logging.info(f"Saving to {OUTPUT_FILE}...")
    merged.to_file(OUTPUT_FILE, driver="GPKG", layer="roads")

    # Summary
    print("\n" + "=" * 70)
    print("ROAD NETWORK GENERATION COMPLETE")
    print("=" * 70)
    print(f"\nOutput file: {OUTPUT_FILE}")
    print(f"File size: {OUTPUT_FILE.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"Total segments: {len(merged):,}")
    print()

    print("Road type distribution:")
    type_counts = merged["road_type"].value_counts()
    for road_type, count in type_counts.items():
        print(f"  {road_type:20s} {count:6,}")
    print()

    print("County distribution:")
    county_counts = merged["county"].value_counts()
    for county, count in county_counts.items():
        print(f"  {county:20s} {count:6,}")

    print("\n" + "=" * 70)
    print("\n✅ Ready to run pipeline with road network!")
    print("\nNext steps:")
    print("  1. Test with sample tickets:")
    print("     python geocoding_pipeline/cli.py --roads roads_merged.gpkg <tickets.csv>")
    print()
    print("  2. Run full pipeline:")
    print("     python geocoding_pipeline/cli.py --config configs/wink_project_full.yaml <tickets.csv>")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
