#!/usr/bin/env python3
"""
frequency.py

Tag 811 tickets as in/out of the Wink APN corridor using our new
geocoding persistence structure, and analytically correct the
corridor ticket count for geocoding failures.

Pipeline:

1) Load the original 811 dataset (CSV or XLSX).
2) Recompute _geo_key for each row using the same definition as
   geocode-intersect-routes.py.
3) Load geocode_cache.json and attach:
      - lat, lng
      - geocode_status
      - geocode_ok (status == "OK" and lat/lng present)
4) Load Wink APN route from KMZ (without fastkml), project to a metric CRS,
   and buffer by ROUTE_BUFFER_METERS to form the corridor polygon.
5) For each ticket with geocode_ok == 1, test whether it falls inside
   the buffered corridor; set in_corridor = True/False.
6) Summarize:
      - total_rows (N_total)
      - geocoded_rows (N_good)
      - failed_rows (N_failed)
      - corridor_geocoded_rows (N_corr_good)
7) Analytically estimate total corridor tickets, correcting for
   geocoding failures under a missing-at-random assumption:
      p_hat = N_corr_good / N_good
      N_corr_est = p_hat * N_total
      lower_bound = N_corr_good
      upper_bound = N_corr_good + N_failed
8) Write an updated CSV with lat, lng, geocode_ok, in_corridor.

Requirements:
    - geocode_cache.json (created by geocode-intersect-routes.py)
    - Wink APN.kmz (route geometry)
    - GeoCallSearchResult_geocoded_with_corridor_all.csv (or similar 811 data)
    - shapely, pyproj, pandas installed

Adjust PATH / filenames in CONFIG as needed.
"""

from pathlib import Path
import zipfile
import logging
from typing import Any, Dict, Optional, List

import pandas as pd
from shapely.geometry import Point, LineString, MultiLineString
from shapely.ops import transform, unary_union
from pyproj import CRS, Transformer
import xml.etree.ElementTree as ET
import json

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

# Original 811 dataset
INPUT_811_FILE = "GeoCallSearchResult_geocoded_with_corridor_all.csv"
INPUT_811_TYPE = "csv"  # "csv" or "xlsx"

# New geocoding persistence cache
GEOCODE_CACHE_FILE = Path("geocode_cache.json")

# Wink route & buffer configuration
ROUTE_KMZ = Path("Wink APN.kmz")
ROUTE_BUFFER_METERS = 200.0  # adjust as needed

# CRS definitions
WGS84 = CRS.from_epsg(4326)
PROJECTED_CRS = CRS.from_epsg(3857)  # good enough for local distances

# Column candidates in the 811 dataset
COUNTY_COL_CANDIDATES = ["County", "COUNTY"]
CITY_COL_CANDIDATES = ["City", "CITY", "Place", "PLACE"]
STREET_COL_CANDIDATES = ["Street", "STREET", "Address", "ADDRESS", "LOCATE_STREET"]
INTERSECTION_COL_CANDIDATES = ["Intersection", "INTERSECTION", "CrossStreet", "CROSS_STREET"]
STATE_COL_CANDIDATES = ["State", "STATE"]

# Output CSV with corridor tagging
OUTPUT_CSV = "GeoCallSearchResult_corridor_tagged.csv"

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)


# ---------------------------------------------------------------------------
# Helpers: data loading, column resolution
# ---------------------------------------------------------------------------

def find_column(df: pd.DataFrame, candidates, logical_name: str) -> str:
    """
    Find the first existing column in df from a list of candidate names.
    Raise a clear error if none are found.
    """
    for c in candidates:
        if c in df.columns:
            logging.info(f"Using column '{c}' for {logical_name}")
            return c
    raise RuntimeError(f"Could not find a column for {logical_name} among: {candidates}")


def load_811_dataframe() -> pd.DataFrame:
    """
    Load the 811 locate dataset, either CSV or XLSX.
    """
    if INPUT_811_TYPE == "csv":
        logging.info(f"Loading CSV: {INPUT_811_FILE}")
        df = pd.read_csv(INPUT_811_FILE)
    elif INPUT_811_TYPE == "xlsx":
        logging.info(f"Loading Excel: {INPUT_811_FILE}")
        df = pd.read_excel(INPUT_811_FILE)
    else:
        raise ValueError(f"Unsupported INPUT_811_TYPE: {INPUT_811_TYPE}")

    logging.info(f"Loaded {len(df)} rows from {INPUT_811_FILE}")
    return df


# ---------------------------------------------------------------------------
# Geo-key and normalization utilities
# (must match geocode-intersect-routes.py semantics)
# ---------------------------------------------------------------------------

def normalize_text(s: Any) -> str:
    if pd.isna(s):
        return ""
    return str(s).strip()


def make_geo_key(
    county: str,
    city: str,
    street: str,
    intersection: str,
    is_intersection: bool,
) -> str:
    """
    Construct the same geo_key used in geocode-intersect-routes.py so that we
    can join tickets to geocode_cache.json. This is critical for consistency.
    """
    parts = [
        normalize_text(county).lower(),
        normalize_text(city).lower(),
        ("intersection" if is_intersection else "address"),
        normalize_text(street).lower(),
        normalize_text(intersection).lower(),
    ]
    return "|".join(parts)


# ---------------------------------------------------------------------------
# Route loading & buffering (no fastkml)
# ---------------------------------------------------------------------------

def load_route_from_kmz(kmz_path: Path):
    """
    Load the Wink APN route geometry from a KMZ file using zipfile + XML
    (no fastkml dependency). Returns a unified LineString/MultiLineString
    in WGS84 coordinates.

    We search for all <LineString> elements in the KML and parse their
    <coordinates> content into shapely LineStrings, then unary_union them.
    """
    if not kmz_path.exists():
        raise FileNotFoundError(f"Route KMZ not found: {kmz_path}")

    logging.info(f"Loading route from KMZ: {kmz_path}")

    # 1. Extract KML from KMZ
    with zipfile.ZipFile(kmz_path, "r") as zf:
        kml_name = None
        for name in zf.namelist():
            if name.lower().endswith(".kml"):
                kml_name = name
                break
        if not kml_name:
            raise RuntimeError(f"No .kml file found inside {kmz_path}")
        kml_data = zf.read(kml_name)

    # 2. Parse KML XML
    root = ET.fromstring(kml_data)
    ns = {"kml": "http://www.opengis.net/kml/2.2"}

    line_elems = root.findall(".//kml:LineString", ns)
    if not line_elems:
        raise RuntimeError(f"No LineString geometries found in {kmz_path}")

    geoms: List[LineString] = []

    for le in line_elems:
        coords_elem = le.find("kml:coordinates", ns)
        if coords_elem is None or not coords_elem.text:
            continue

        coords: List[tuple] = []
        # coordinates text is usually "lon,lat,alt lon,lat,alt ..."
        for token in coords_elem.text.strip().split():
            parts = token.split(",")
            if len(parts) >= 2:
                try:
                    lon = float(parts[0])
                    lat = float(parts[1])
                except ValueError:
                    continue
                coords.append((lon, lat))

        if len(coords) >= 2:
            geoms.append(LineString(coords))

    if not geoms:
        raise RuntimeError(f"Could not parse any valid LineString coordinates from {kmz_path}")

    route = unary_union(geoms)
    if not isinstance(route, (LineString, MultiLineString)):
        raise RuntimeError("Route union did not produce a LineString/MultiLineString.")

    logging.info("Route geometry loaded from KMZ (via XML parsing).")
    return route  # WGS84


def project_geometry(geom, src_crs: CRS, dst_crs: CRS):
    """
    Project a shapely geometry from src_crs to dst_crs using pyproj Transformer.
    """
    transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    return transform(transformer.transform, geom)


# ---------------------------------------------------------------------------
# Geocode cache loading / join
# ---------------------------------------------------------------------------

def load_geocode_cache(cache_file: Path) -> Dict[str, Dict[str, Any]]:
    if not cache_file.exists():
        raise FileNotFoundError(f"Geocode cache not found: {cache_file}")
    with cache_file.open("r", encoding="utf-8") as f:
        cache = json.load(f)
    logging.info(f"Loaded geocode cache: {cache_file} ({len(cache)} geo_keys)")
    return cache


def attach_geocodes(
    df: pd.DataFrame,
    cache: Dict[str, Dict[str, Any]],
    county_col: str,
    city_col: str,
    street_col: Optional[str],
    intersection_col: Optional[str],
    state_col: Optional[str],
) -> pd.DataFrame:
    """
    For each row in df, reconstruct the geo_key and attach geocode info
    from geocode_cache.json. Adds:

        _geo_key
        geocode_status
        geocode_ok (1/0)
        lat
        lng

    geocode_ok == 1 iff geocode.status == "OK" and lat/lng are present.
    """

    # Ensure we have a state value; default to TX if missing
    if state_col:
        df["_state"] = df[state_col].fillna("TX")
    else:
        logging.info("[INFO] No State column found; defaulting to 'TX' for all rows.")
        df["_state"] = "TX"

    geo_keys: List[str] = []
    lat_list: List[Optional[float]] = []
    lng_list: List[Optional[float]] = []
    status_list: List[str] = []
    ok_list: List[int] = []

    for _, row in df.iterrows():
        county = row[county_col]
        city = row[city_col]
        street = row[street_col] if street_col else ""
        intersection = row[intersection_col] if intersection_col else ""
        is_intersection = bool(normalize_text(intersection))

        gk = make_geo_key(county, city, street, intersection, is_intersection)
        geo_keys.append(gk)

        info = cache.get(gk, {})
        geocode = info.get("geocode", {})
        status = geocode.get("status")
        lat = geocode.get("lat")
        lng = geocode.get("lng")
        ok = status == "OK" and lat is not None and lng is not None

        status_list.append(status or "")
        ok_list.append(1 if ok else 0)
        lat_list.append(lat)
        lng_list.append(lng)

    df["_geo_key"] = geo_keys
    df["geocode_status"] = status_list
    df["geocode_ok"] = ok_list
    df["lat"] = lat_list
    df["lng"] = lng_list

    return df


# ---------------------------------------------------------------------------
# Corridor tagging and analytical correction
# ---------------------------------------------------------------------------

def tag_corridor(df: pd.DataFrame, route_buffer_proj) -> pd.DataFrame:
    """
    For rows with geocode_ok == 1, compute whether they fall inside the
    projected corridor buffer and set in_corridor True/False.
    For rows without valid geocode, in_corridor is set to False.
    """

    in_corridor_flags: List[bool] = []
    transformer = Transformer.from_crs(WGS84, PROJECTED_CRS, always_xy=True)

    for _, row in df.iterrows():
        if not row.get("geocode_ok", 0):
            in_corridor_flags.append(False)
            continue

        lat = row["lat"]
        lng = row["lng"]
        if lat is None or pd.isna(lat) or lng is None or pd.isna(lng):
            in_corridor_flags.append(False)
            continue

        # (x, y) = (lon, lat)
        x, y = transformer.transform(lng, lat)
        pt = Point(x, y)
        in_corridor_flags.append(route_buffer_proj.contains(pt))

    df["in_corridor"] = in_corridor_flags
    return df


def analytical_correction(df: pd.DataFrame) -> None:
    """
    Print an analytical estimate of total corridor tickets, correcting
    for geocoding failures under a missing-at-random assumption.

    Notation:
        N_total         = total number of tickets
        N_good          = tickets with geocode_ok == 1
        N_failed        = tickets with geocode_ok == 0
        N_corr_good     = tickets with geocode_ok == 1 and in_corridor == True

    We estimate:
        p_hat           = N_corr_good / N_good
        N_corr_est      = p_hat * N_total

    Bounds:
        lower_bound     = N_corr_good              (assume all failures outside)
        upper_bound     = N_corr_good + N_failed   (assume all failures inside)
    """

    total_rows = len(df)
    good_rows = int(df["geocode_ok"].sum())
    failed_rows = total_rows - good_rows
    corr_good = int(df[(df["geocode_ok"] == 1) & (df["in_corridor"])].shape[0])

    logging.info("\n=== Analytical Corridor Ticket Estimate (geocode failure correction) ===")
    logging.info(f"Total tickets (N_total):                  {total_rows}")
    logging.info(f"Tickets with geocode_ok == 1 (N_good):    {good_rows}")
    logging.info(f"Tickets with geocode_ok == 0 (N_failed):  {failed_rows}")
    logging.info(f"Geocoded corridor tickets (N_corr_good):  {corr_good}")

    if good_rows == 0:
        logging.warning("No tickets with geocode_ok == 1; cannot form an analytical estimate.")
        return

    p_hat = corr_good / good_rows
    corr_est = p_hat * total_rows
    lower_bound = corr_good
    upper_bound = corr_good + failed_rows

    logging.info(f"\nObserved corridor fraction among geocoded: p_hat = {p_hat:.4f}")
    logging.info(
        f"Bias-corrected total corridor estimate:    N_corr_est ≈ {corr_est:.1f}"
    )
    logging.info(f"Lower bound (all failures outside):        {lower_bound}")
    logging.info(f"Upper bound (all failures inside):         {upper_bound}")

    factor = total_rows / good_rows
    logging.info(f"Implied correction factor (N_total / N_good): {factor:.3f}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # 1) Load the original 811 data
    df = load_811_dataframe()

    # 2) Resolve columns for geo_key construction
    county_col = find_column(df, COUNTY_COL_CANDIDATES, "County")
    city_col = find_column(df, CITY_COL_CANDIDATES, "City/Place")
    street_col = None
    intersection_col = None

    try:
        street_col = find_column(df, STREET_COL_CANDIDATES, "Street/Address")
    except RuntimeError:
        logging.info("[INFO] No explicit Street column found; will rely on Intersection.")
    try:
        intersection_col = find_column(df, INTERSECTION_COL_CANDIDATES, "Intersection/CrossStreet")
    except RuntimeError:
        logging.info("[INFO] No explicit Intersection column found; will rely on Street.")

    if not street_col and not intersection_col:
        raise RuntimeError("Need at least one of Street or Intersection columns to build geo_key.")

    # State is optional; default TX if missing
    state_col = None
    for c in STATE_COL_CANDIDATES:
        if c in df.columns:
            state_col = c
            logging.info(f"Using column '{c}' for State")
            break

    # 3) Load geocode cache and attach lat/lng + geocode_ok to each row
    cache = load_geocode_cache(GEOCODE_CACHE_FILE)
    df = attach_geocodes(
        df,
        cache,
        county_col=county_col,
        city_col=city_col,
        street_col=street_col,
        intersection_col=intersection_col,
        state_col=state_col,
    )

    # Quick geocode summary
    total_rows = len(df)
    geocoded_rows = int(df["geocode_ok"].sum())
    logging.info("\n=== Geocoding Coverage Summary (from cache) ===")
    logging.info(f"Total rows:        {total_rows}")
    logging.info(f"Rows geocode_ok=1: {geocoded_rows}")
    logging.info(f"Rows geocode_ok=0: {total_rows - geocoded_rows}")

    # 4) Load and buffer the Wink APN route
    route_wgs84 = load_route_from_kmz(ROUTE_KMZ)
    logging.info("Projecting route to projected CRS for buffering...")
    route_proj = project_geometry(route_wgs84, WGS84, PROJECTED_CRS)

    logging.info(f"Buffering route by {ROUTE_BUFFER_METERS} meters...")
    route_buffer_proj = route_proj.buffer(ROUTE_BUFFER_METERS)
    logging.info("Route buffer (corridor polygon) ready.")

    # 5) Corridor tagging
    df = tag_corridor(df, route_buffer_proj)

    in_corridor_rows = int(df["in_corridor"].sum())
    logging.info("\n=== Corridor Tagging Summary ===")
    logging.info(f"Total rows:                      {total_rows}")
    logging.info(f"Rows with geocode_ok == 1:       {geocoded_rows}")
    logging.info(f"Rows inside corridor buffer:     {in_corridor_rows}")

    # 6) Analytical correction for geocoding failures
    analytical_correction(df)

    # 7) Write updated CSV
    logging.info(f"\nWriting updated CSV with lat/lng, geocode_ok, in_corridor to: {OUTPUT_CSV}")
    df.to_csv(OUTPUT_CSV, index=False)
    logging.info("Done.")


if __name__ == "__main__":
    main()
