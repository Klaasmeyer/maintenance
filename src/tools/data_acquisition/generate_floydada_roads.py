#!/usr/bin/env python3
"""
Generate road network for Floydada project (Floyd, Briscoe, Hall counties).
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile

import geopandas as gpd
import pandas as pd

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

# Texas counties for Floydada project
COUNTIES = {
    "Floyd": "48153",
    "Briscoe": "48045",
    "Hall": "48191",
}

TIGER_YEAR = "2024"
OUTPUT_FILE = Path("roads_floydada.gpkg")


def download_tiger_roads(county_name: str, fips_code: str, temp_dir: Path) -> Path:
    """Download TIGER/Line roads for a county."""
    url = f"https://www2.census.gov/geo/tiger/TIGER{TIGER_YEAR}/ROADS/tl_{TIGER_YEAR}_{fips_code}_roads.zip"
    zip_path = temp_dir / f"{county_name}_roads.zip"

    logging.info(f"Downloading {county_name} County roads...")

    result = subprocess.run(
        ["curl", "-L", "-o", str(zip_path), url],
        capture_output=True,
        check=True,
    )
    logging.info(f"  Downloaded {zip_path.stat().st_size / 1024 / 1024:.1f} MB")
    return zip_path


def extract_shapefile(zip_path: Path, temp_dir: Path) -> Path:
    """Extract shapefile from zip."""
    with ZipFile(zip_path, 'r') as zf:
        zf.extractall(temp_dir)
    shp_files = list(temp_dir.glob("*.shp"))
    return shp_files[0]


def load_and_normalize_roads(shp_path: Path, county_name: str) -> gpd.GeoDataFrame:
    """Load and normalize road data."""
    gdf = gpd.read_file(shp_path)
    logging.info(f"  Loaded {len(gdf):,} road segments")

    normalized = gdf.copy()
    normalized["road_name"] = normalized.get("FULLNAME", normalized.get("NAME", ""))
    normalized["road_ref"] = normalized["road_name"]

    def classify_road_type(name):
        if pd.isna(name):
            return "OTHER"
        name = str(name).upper()
        if "CR " in name or "COUNTY ROAD" in name or "CO RD" in name:
            return "CR"
        elif "FM " in name or "FARM" in name:
            return "FM"
        elif "RM " in name or "RANCH" in name:
            return "RM"
        elif "US " in name or "US HWY" in name:
            return "US"
        elif "SH " in name or "STATE HWY" in name or "TX-" in name:
            return "TX_SH"
        elif "I-" in name or "IH " in name:
            return "Interstate"
        else:
            return "OTHER"

    normalized["road_type"] = normalized["road_name"].apply(classify_road_type)
    normalized["source"] = f"TIGER/Line ({county_name})"
    normalized["county"] = county_name

    keep_cols = ["road_name", "road_ref", "road_type", "source", "county", "geometry"]
    result = normalized[keep_cols].copy()

    if result.crs != "EPSG:4326":
        result = result.to_crs("EPSG:4326")

    return result


def main():
    print("\n" + "=" * 70)
    print("GENERATING ROAD NETWORK FOR FLOYDADA PROJECT")
    print("=" * 70)
    print(f"\nCounties: Floyd, Briscoe, Hall (Texas Panhandle)")
    print(f"Source: TIGER/Line {TIGER_YEAR}\n")

    all_roads = []

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        for county_name, fips_code in COUNTIES.items():
            try:
                zip_path = download_tiger_roads(county_name, fips_code, temp_path)
                county_temp = temp_path / county_name
                county_temp.mkdir(exist_ok=True)
                shp_path = extract_shapefile(zip_path, county_temp)
                county_roads = load_and_normalize_roads(shp_path, county_name)
                all_roads.append(county_roads)
                logging.info(f"✓ {county_name} County: {len(county_roads):,} segments\n")
            except Exception as e:
                logging.error(f"✗ Failed {county_name}: {e}")
                continue

    if not all_roads:
        logging.error("No road data downloaded")
        return

    # Merge
    merged = pd.concat(all_roads, ignore_index=True)
    logging.info(f"Total: {len(merged):,} segments")

    # Deduplicate
    before = len(merged)
    merged = merged.drop_duplicates(subset=["geometry"])
    after = len(merged)
    if before > after:
        logging.info(f"Removed {before - after:,} duplicates")

    # Spatial index
    logging.info("Creating spatial index...")
    merged.sindex

    # Save
    logging.info(f"Saving to {OUTPUT_FILE}...")
    merged.to_file(OUTPUT_FILE, driver="GPKG", layer="roads")

    print("\n" + "=" * 70)
    print("FLOYDADA ROAD NETWORK COMPLETE")
    print("=" * 70)
    print(f"\nFile: {OUTPUT_FILE}")
    print(f"Size: {OUTPUT_FILE.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"Segments: {len(merged):,}\n")

    print("Road types:")
    for road_type, count in merged["road_type"].value_counts().items():
        print(f"  {road_type:20s} {count:6,}")

    print("\n" + "=" * 70)
    print("\n✅ Ready to run Floydada pipeline!")
    print("\nNext command:")
    print("  python geocoding_pipeline/cli.py \\")
    print("    --roads roads_floydada.gpkg \\")
    print("    --generate-estimate projects/floydada/route/Klaasmeyer\\ -\\ Floydada.kmz \\")
    print("    projects/floydada/tickets/")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
