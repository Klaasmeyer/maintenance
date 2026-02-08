#!/usr/bin/env python3
"""
download_txdot_data.py

Download road data from TxDOT GIS portal for Ward, Andrews, and Winkler counties.

TxDOT ArcGIS REST API endpoints:
- County Roads: https://services.arcgis.com/KTcxiTD9dsQw4r7Z/arcgis/rest/services/
- State Highway System: https://gis-txdot.opendata.arcgis.com/

Usage:
    python download_txdot_data.py --counties Ward,Andrews,Winkler
    python download_txdot_data.py --all  # Download all available road types
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

# TxDOT ArcGIS REST API endpoints
ENDPOINTS = {
    "county_roads": {
        "url": "https://services.arcgis.com/KTcxiTD9dsQw4r7Z/arcgis/rest/services/TxDOT_County_Maintained_Roads/FeatureServer/0/query",
        "description": "County maintained roads",
    },
    "state_highways": {
        "url": "https://services.arcgis.com/KTcxiTD9dsQw4r7Z/arcgis/rest/services/TxDOT_Roadways/FeatureServer/0/query",
        "description": "State highways (FM, RM, TX, US)",
    },
}

OUTPUT_DIR = Path("txdot_data")


def query_arcgis_features(
    endpoint_url: str,
    where_clause: str = "1=1",
    out_fields: str = "*",
    timeout: int = 300,
) -> Optional[dict]:
    """Query ArcGIS REST API and return GeoJSON features."""

    params = {
        "where": where_clause,
        "outFields": out_fields,
        "f": "geojson",
        "returnGeometry": "true",
    }

    logging.info(f"Querying: {endpoint_url}")
    logging.info(f"Where: {where_clause}")

    try:
        response = requests.get(endpoint_url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {e}")
        return None


def download_county_roads(counties: list[str], output_file: Path) -> Optional[gpd.GeoDataFrame]:
    """Download county roads for specified counties."""

    # Build where clause for counties
    county_list = "','".join(counties)
    where_clause = f"COUNTY_NAME IN ('{county_list}')"

    logging.info(f"Downloading county roads for: {', '.join(counties)}")

    geojson_data = query_arcgis_features(
        ENDPOINTS["county_roads"]["url"],
        where_clause=where_clause,
    )

    if not geojson_data:
        logging.error("Failed to download county roads")
        return None

    # Convert to GeoDataFrame
    gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])

    if gdf.empty:
        logging.warning("No county roads found for specified counties")
        return None

    # Set CRS (TxDOT data is typically in WGS84)
    if gdf.crs is None:
        gdf.set_crs("EPSG:4326", inplace=True)

    logging.info(f"Downloaded {len(gdf)} county road segments")

    # Save to GeoPackage
    gdf.to_file(output_file, driver="GPKG", layer="county_roads")
    logging.info(f"Saved to {output_file}")

    return gdf


def download_state_highways(counties: list[str], output_file: Path) -> Optional[gpd.GeoDataFrame]:
    """Download state highways for specified counties."""

    # Build where clause for counties
    county_list = "','".join(counties)
    where_clause = f"COUNTY IN ('{county_list}')"

    logging.info(f"Downloading state highways for: {', '.join(counties)}")

    geojson_data = query_arcgis_features(
        ENDPOINTS["state_highways"]["url"],
        where_clause=where_clause,
    )

    if not geojson_data:
        logging.error("Failed to download state highways")
        return None

    # Convert to GeoDataFrame
    gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])

    if gdf.empty:
        logging.warning("No state highways found for specified counties")
        return None

    # Set CRS
    if gdf.crs is None:
        gdf.set_crs("EPSG:4326", inplace=True)

    logging.info(f"Downloaded {len(gdf)} state highway segments")

    # Save to GeoPackage
    gdf.to_file(output_file, driver="GPKG", layer="state_highways")
    logging.info(f"Saved to {output_file}")

    return gdf


def main():
    parser = argparse.ArgumentParser(
        description="Download TxDOT road data for specified counties"
    )
    parser.add_argument(
        "--counties",
        default="Ward,Andrews,Winkler",
        help="Comma-separated list of county names (default: Ward,Andrews,Winkler)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download all road types",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Output directory for downloaded data",
    )

    args = parser.parse_args()

    # Parse county list
    counties = [c.strip().upper() for c in args.counties.split(",")]

    # Create output directory
    args.output_dir.mkdir(exist_ok=True)

    print("\n" + "=" * 70)
    print("DOWNLOADING TXDOT ROAD DATA")
    print("=" * 70)
    print(f"\nCounties: {', '.join(counties)}")
    print(f"Output directory: {args.output_dir}")

    # Download county roads
    county_roads_file = args.output_dir / "txdot_county_roads.gpkg"
    county_gdf = download_county_roads(counties, county_roads_file)

    # Download state highways
    state_highways_file = args.output_dir / "txdot_state_highways.gpkg"
    state_gdf = download_state_highways(counties, state_highways_file)

    # Summary
    print("\n" + "=" * 70)
    print("DOWNLOAD COMPLETE")
    print("=" * 70)

    if county_gdf is not None:
        print(f"\n✅ County Roads: {len(county_gdf):,} segments")
        print(f"   File: {county_roads_file}")
    else:
        print("\n❌ County Roads: Download failed")

    if state_gdf is not None:
        print(f"\n✅ State Highways: {len(state_gdf):,} segments")
        print(f"   File: {state_highways_file}")
    else:
        print("\n❌ State Highways: Download failed")

    print("\n" + "=" * 70)
    print("\nNext steps:")
    print("1. Inspect downloaded data:")
    print(f"   python inspect_roads.py --roads {county_roads_file}")
    print("2. Merge with existing OSM data (script to be created)")
    print("3. Re-run geometric geocoding with merged data")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
