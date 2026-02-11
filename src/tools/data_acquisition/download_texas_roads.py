#!/usr/bin/env python3
"""
Download comprehensive Texas road data from Geofabrik (OpenStreetMap).

This provides the most detailed and comprehensive road network for Texas,
including all highway types, county roads, farm-to-market roads, and local streets.
"""

import logging
import subprocess
import tempfile
from pathlib import Path
import geopandas as gpd
import pandas as pd

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

# Geofabrik Texas OSM extract
GEOFABRIK_URL = "https://download.geofabrik.de/north-america/us/texas-latest-free.shp.zip"
OUTPUT_FILE = Path("roads_texas_complete.gpkg")

def download_texas_osm():
    """Download Texas OSM shapefile from Geofabrik."""

    print("\n" + "=" * 70)
    print("DOWNLOADING COMPREHENSIVE TEXAS ROAD DATA")
    print("=" * 70)
    print(f"\nSource: Geofabrik OpenStreetMap")
    print(f"URL: {GEOFABRIK_URL}")
    print(f"Coverage: All Texas roads (highways, county roads, streets)")
    print()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        zip_path = temp_path / "texas-roads.zip"

        # Download
        logging.info("Downloading Texas OSM data (~250 MB)...")
        logging.info("This may take 2-5 minutes depending on connection speed...")

        try:
            result = subprocess.run(
                ["curl", "-L", "-o", str(zip_path), GEOFABRIK_URL, "--progress-bar"],
                check=True,
            )
            logging.info(f"Downloaded {zip_path.stat().st_size / 1024 / 1024:.1f} MB")
        except subprocess.CalledProcessError as e:
            logging.error(f"Download failed: {e}")
            logging.info("\nAlternative: Download manually from:")
            logging.info(f"  {GEOFABRIK_URL}")
            logging.info(f"Then extract and process with: ogr2ogr")
            return None

        # Extract
        logging.info("Extracting shapefile...")
        extract_dir = temp_path / "extracted"
        extract_dir.mkdir(exist_ok=True)

        subprocess.run(
            ["unzip", "-q", str(zip_path), "-d", str(extract_dir)],
            check=True,
        )

        # Find roads shapefile
        shp_files = list(extract_dir.glob("**/gis_osm_roads*.shp"))

        if not shp_files:
            logging.error("No roads shapefile found in download")
            return None

        # Load roads
        roads_shp = shp_files[0]
        logging.info(f"Loading roads from {roads_shp.name}...")
        gdf = gpd.read_file(roads_shp)
        logging.info(f"Loaded {len(gdf):,} road segments")

        # Normalize schema
        logging.info("Normalizing road data...")
        normalized = normalize_osm_roads(gdf)

        # Filter to Texas only (in case extract includes border areas)
        logging.info("Filtering to Texas boundaries...")
        # OSM data should already be filtered, but verify CRS
        if normalized.crs != "EPSG:4326":
            logging.info(f"Reprojecting from {normalized.crs} to EPSG:4326")
            normalized = normalized.to_crs("EPSG:4326")

        # Remove duplicates
        before = len(normalized)
        normalized = normalized.drop_duplicates(subset=["geometry"])
        after = len(normalized)
        if before > after:
            logging.info(f"Removed {before - after:,} duplicate geometries")

        # Create spatial index
        logging.info("Creating spatial index...")
        normalized.sindex  # Trigger index creation

        # Save
        logging.info(f"Saving to {OUTPUT_FILE}...")
        normalized.to_file(OUTPUT_FILE, driver="GPKG", layer="roads")

        # Summary
        print("\n" + "=" * 70)
        print("TEXAS ROAD NETWORK COMPLETE")
        print("=" * 70)
        print(f"\nFile: {OUTPUT_FILE}")
        print(f"Size: {OUTPUT_FILE.stat().st_size / 1024 / 1024:.1f} MB")
        print(f"Segments: {len(normalized):,}")
        print()

        print("Road type distribution:")
        type_counts = normalized["road_type"].value_counts()
        for road_type, count in type_counts.head(15).items():
            print(f"  {road_type:25s} {count:8,}")

        if len(type_counts) > 15:
            other_count = type_counts.iloc[15:].sum()
            print(f"  {'(Other types)':25s} {other_count:8,}")

        print("\n" + "=" * 70)
        print("\n✅ Complete Texas road network ready!")
        print("\nUsage:")
        print(f"  python geocoding_pipeline/cli.py --roads {OUTPUT_FILE} <tickets>")
        print()
        print("This will provide:")
        print("  • Highways (Interstate, US, State)")
        print("  • Farm-to-Market roads")
        print("  • County roads")
        print("  • City streets")
        print("  • Rural roads")
        print("  • Complete coverage for all Texas projects")
        print("=" * 70 + "\n")

        return normalized


def normalize_osm_roads(gdf):
    """Normalize OSM road data to unified schema."""

    normalized = gdf.copy()

    # OSM fields: name, ref, fclass (road functional class)
    normalized["road_name"] = normalized.get("name", "")
    normalized["road_ref"] = normalized.get("ref", "")

    # Map OSM fclass to our road types
    fclass_mapping = {
        "motorway": "Interstate",
        "motorway_link": "Interstate",
        "trunk": "US",
        "trunk_link": "US",
        "primary": "TX_SH",
        "primary_link": "TX_SH",
        "secondary": "FM",
        "secondary_link": "FM",
        "tertiary": "CR",
        "tertiary_link": "CR",
        "residential": "Residential",
        "living_street": "Residential",
        "unclassified": "LOCAL",
        "service": "SERVICE",
        "track": "TRACK",
    }

    if "fclass" in normalized.columns:
        normalized["road_type"] = normalized["fclass"].map(fclass_mapping).fillna("OTHER")
    elif "highway" in normalized.columns:
        normalized["road_type"] = normalized["highway"].map(fclass_mapping).fillna("OTHER")
    else:
        normalized["road_type"] = "OTHER"

    # Refine road_type based on ref patterns
    def refine_road_type(row):
        ref = str(row.get("road_ref", "")).upper()
        name = str(row.get("road_name", "")).upper()
        current_type = row.get("road_type", "OTHER")

        # Check ref for specific patterns
        if "I-" in ref or "IH " in ref:
            return "Interstate"
        elif "US " in ref or "US-" in ref:
            return "US"
        elif "TX-" in ref or "SH " in ref:
            return "TX_SH"
        elif "FM " in ref or "FM-" in ref:
            return "FM"
        elif "RM " in ref or "RM-" in ref:
            return "RM"
        elif "CR " in ref or "CR-" in ref or "CO RD" in ref:
            return "CR"

        # Check name for patterns
        if "INTERSTATE" in name or "I-" in name:
            return "Interstate"
        elif "US HIGHWAY" in name or "US HWY" in name:
            return "US"
        elif "FM " in name or "FARM" in name:
            return "FM"
        elif "RANCH" in name or "RM " in name:
            return "RM"
        elif "COUNTY ROAD" in name or "CR " in name:
            return "CR"

        return current_type

    normalized["road_type"] = normalized.apply(refine_road_type, axis=1)

    normalized["source"] = "OpenStreetMap (Geofabrik)"

    # Keep essential columns
    keep_cols = ["road_name", "road_ref", "road_type", "source", "geometry"]
    return normalized[keep_cols].copy()


def main():
    """Download and process Texas road data."""

    result = download_texas_osm()

    if result is None:
        print("\n⚠️  Download failed or was interrupted")
        print("\nManual alternative:")
        print(f"1. Download from: {GEOFABRIK_URL}")
        print("2. Extract the shapefile")
        print("3. Convert to GeoPackage:")
        print(f"   ogr2ogr -f GPKG {OUTPUT_FILE} gis_osm_roads_free_1.shp")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
