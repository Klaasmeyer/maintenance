#!/usr/bin/env python3
"""
download_road_network.py

Download road network geometry from OpenStreetMap for Ward, Andrews, and
Winkler counties in Texas. Focuses on road types involved in geocoding failures:
- County Roads (CR)
- Farm to Market roads (FM)
- Ranch to Market roads (RM)
- State Highways (TX/SH)
- Interstate highways
- US Highways

Uses Overpass API to query OSM data and stores in GeoPackage format with
spatial index for fast geometric intersection queries.

Output: roads.gpkg (GeoPackage with road geometries)
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import LineString, MultiLineString, shape

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

# Output files
OUTPUT_GPKG = Path("roads.gpkg")
OUTPUT_METADATA = Path("roads_metadata.json")

# County bounding boxes (roughly - covers the area of interest)
# Format: (min_lon, min_lat, max_lon, max_lat)
COUNTIES = {
    "Andrews": (-103.0, 32.0, -102.0, 32.6),
    "Ward": (-103.5, 31.4, -102.7, 32.0),
    "Winkler": (-103.5, 31.7, -102.8, 32.1),
}

# Expand to cover all three counties with some buffer
BBOX = (
    min(box[0] for box in COUNTIES.values()) - 0.05,  # min_lon with buffer
    min(box[1] for box in COUNTIES.values()) - 0.05,  # min_lat with buffer
    max(box[2] for box in COUNTIES.values()) + 0.05,  # max_lon with buffer
    max(box[3] for box in COUNTIES.values()) + 0.05,  # max_lat with buffer
)

# Overpass API endpoint
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Road type mappings for classification
ROAD_TYPE_TAGS = {
    "FM": ["ref~'^FM [0-9]'", "name~'Farm[- ]to[- ]Market'", "name~'^FM [0-9]'"],
    "RM": ["ref~'^RM [0-9]'", "name~'Ranch[- ]to[- ]Market'", "name~'^RM [0-9]'"],
    "CR": ["ref~'^CR [0-9]'", "name~'County Road'", "name~'^CR [0-9]'"],
    "TX_SH": ["ref~'^TX [0-9]'", "ref~'^SH [0-9]'", "name~'State Highway'"],
    "Interstate": ["highway=motorway", "ref~'^I-'", "name~'Interstate'"],
    "US": ["ref~'^US [0-9]'", "name~'^US Highway'"],
}


def build_overpass_query(bbox: tuple[float, float, float, float]) -> str:
    """Build Overpass QL query for road network."""
    min_lon, min_lat, max_lon, max_lat = bbox

    # Query for all road types we care about
    # Using highway tags that typically contain our target roads
    query = f"""
[out:json][timeout:300][bbox:{min_lat},{min_lon},{max_lat},{max_lon}];
(
  // Major highways - Interstate, US, State
  way["highway"~"^(motorway|trunk|primary)$"];

  // Secondary roads - likely FM, RM
  way["highway"="secondary"]["ref"];

  // Tertiary roads - likely CR
  way["highway"="tertiary"]["ref"];

  // Unclassified roads with ref tags - likely CR
  way["highway"="unclassified"]["ref"];

  // Service roads with names - numbered county roads
  way["highway"="service"]["name"~"[0-9]"];
  way["highway"="service"]["ref"];

  // Residential roads with ref - numbered roads
  way["highway"="residential"]["ref"~"[0-9]"];
);
out geom;
"""
    return query


def query_overpass(query: str, max_retries: int = 3) -> dict[str, Any]:
    """Query Overpass API with retry logic."""
    for attempt in range(max_retries):
        try:
            logging.info(f"Querying Overpass API (attempt {attempt + 1}/{max_retries})...")
            response = requests.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=600,  # 10 minute timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logging.warning(f"Query timed out on attempt {attempt + 1}")
            if attempt < max_retries - 1:
                wait_time = 30 * (attempt + 1)
                logging.info(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(30)
            else:
                raise

    raise RuntimeError("Failed to query Overpass API after all retries")


def classify_road_type(tags: dict[str, str]) -> str:
    """Classify road based on OSM tags."""
    ref = tags.get("ref", "").upper()
    name = tags.get("name", "").upper()
    highway = tags.get("highway", "")

    # Check ref first (most reliable)
    if ref:
        if ref.startswith("I-") or ref.startswith("I "):
            return "Interstate"
        elif ref.startswith("US ") or ref.startswith("US-"):
            return "US"
        elif ref.startswith(("FM ", "FM-")):
            return "FM"
        elif ref.startswith(("RM ", "RM-")):
            return "RM"
        elif ref.startswith(("CR ", "CR-")):
            return "CR"
        elif ref.startswith(("TX ", "TX-", "SH ", "SH-")):
            return "TX_SH"
        # Numbered roads (e.g., "1234" or "NE 8000")
        elif any(char.isdigit() for char in ref):
            if any(d in ref for d in ["NE", "NW", "SE", "SW", "N", "S", "E", "W"]):
                return "CR_NUMBERED"
            return "OTHER_NUMBERED"

    # Check name
    if name:
        if "INTERSTATE" in name or name.startswith("I-"):
            return "Interstate"
        elif "FARM TO MARKET" in name or "FARM-TO-MARKET" in name:
            return "FM"
        elif "RANCH TO MARKET" in name or "RANCH-TO-MARKET" in name:
            return "RM"
        elif "COUNTY ROAD" in name or name.startswith("CR "):
            return "CR"
        elif "STATE HIGHWAY" in name or name.startswith(("SH ", "TX ")):
            return "TX_SH"
        elif name.startswith("US "):
            return "US"
        # Numbered roads by pattern
        elif any(d in name for d in ["NE ", "NW ", "SE ", "SW "]) and any(c.isdigit() for c in name):
            return "CR_NUMBERED"

    # Fallback to highway classification
    if highway in ["motorway", "motorway_link"]:
        return "Interstate"
    elif highway in ["trunk", "trunk_link"]:
        return "US"
    elif highway == "primary":
        return "TX_SH"
    elif highway in ["secondary", "tertiary"]:
        return "FM_RM_CR"

    return "OTHER"


def extract_road_name(tags: dict[str, str]) -> str:
    """Extract normalized road name from OSM tags."""
    ref = tags.get("ref", "")
    name = tags.get("name", "")

    # Prefer ref if available
    if ref:
        return ref.strip()
    elif name:
        return name.strip()
    else:
        return ""


def process_osm_data(osm_data: dict[str, Any]) -> gpd.GeoDataFrame:
    """Convert OSM JSON to GeoDataFrame with road classifications."""
    roads = []

    for element in osm_data.get("elements", []):
        if element.get("type") != "way":
            continue

        tags = element.get("tags", {})
        geometry_coords = element.get("geometry", [])

        if not geometry_coords:
            continue

        # Build LineString from coordinates
        coords = [(node["lon"], node["lat"]) for node in geometry_coords]
        if len(coords) < 2:
            continue

        geom = LineString(coords)
        road_type = classify_road_type(tags)
        road_name = extract_road_name(tags)

        roads.append({
            "osm_id": element.get("id"),
            "name": road_name,
            "ref": tags.get("ref", ""),
            "road_type": road_type,
            "highway": tags.get("highway", ""),
            "surface": tags.get("surface", ""),
            "geometry": geom,
        })

    if not roads:
        logging.warning("No roads extracted from OSM data")
        return gpd.GeoDataFrame()

    gdf = gpd.GeoDataFrame(roads, crs="EPSG:4326")
    logging.info(f"Extracted {len(gdf)} road segments")

    # Log road type distribution
    type_counts = gdf["road_type"].value_counts()
    logging.info("Road type distribution:")
    for road_type, count in type_counts.items():
        logging.info(f"  {road_type}: {count}")

    return gdf


def create_spatial_index(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Create spatial index for fast geometric queries."""
    logging.info("Creating spatial index...")
    gdf.sindex  # This creates the spatial index
    logging.info("Spatial index created")
    return gdf


def save_to_geopackage(gdf: gpd.GeoDataFrame, output_path: Path) -> None:
    """Save GeoDataFrame to GeoPackage format."""
    logging.info(f"Saving to {output_path}...")

    # Save with spatial index
    gdf.to_file(output_path, driver="GPKG", layer="roads", index=True)

    logging.info(f"Saved {len(gdf)} road segments to {output_path}")


def save_metadata(gdf: gpd.GeoDataFrame, bbox: tuple) -> None:
    """Save metadata about the road network."""
    metadata = {
        "total_roads": len(gdf),
        "bbox": {
            "min_lon": bbox[0],
            "min_lat": bbox[1],
            "max_lon": bbox[2],
            "max_lat": bbox[3],
        },
        "counties": list(COUNTIES.keys()),
        "road_type_counts": gdf["road_type"].value_counts().to_dict(),
        "crs": str(gdf.crs),
        "date_downloaded": pd.Timestamp.now().isoformat(),
    }

    with OUTPUT_METADATA.open("w") as f:
        json.dump(metadata, f, indent=2)

    logging.info(f"Saved metadata to {OUTPUT_METADATA}")


def main() -> None:
    logging.info("=" * 70)
    logging.info("DOWNLOADING ROAD NETWORK DATA FROM OPENSTREETMAP")
    logging.info("=" * 70)

    logging.info(f"Target counties: {', '.join(COUNTIES.keys())}")
    logging.info(f"Bounding box: {BBOX}")

    # Build and execute query
    query = build_overpass_query(BBOX)
    logging.info("Overpass query built")

    osm_data = query_overpass(query)
    logging.info(f"Received {len(osm_data.get('elements', []))} OSM elements")

    # Process data
    gdf = process_osm_data(osm_data)

    if gdf.empty:
        logging.error("No road data extracted. Exiting.")
        return

    # Filter out roads with no useful name/ref
    before_filter = len(gdf)
    gdf = gdf[gdf["name"] != ""].copy()
    logging.info(f"Filtered {before_filter - len(gdf)} roads without names")

    # Create spatial index
    gdf = create_spatial_index(gdf)

    # Save results
    save_to_geopackage(gdf, OUTPUT_GPKG)
    save_metadata(gdf, BBOX)

    # Summary
    logging.info("=" * 70)
    logging.info("DOWNLOAD COMPLETE")
    logging.info("=" * 70)
    logging.info(f"Total roads: {len(gdf)}")
    logging.info(f"Output file: {OUTPUT_GPKG}")
    logging.info(f"File size: {OUTPUT_GPKG.stat().st_size / 1024 / 1024:.2f} MB")
    logging.info("=" * 70)


if __name__ == "__main__":
    main()
