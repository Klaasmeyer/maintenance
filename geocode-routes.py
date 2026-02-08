#!/usr/bin/env python
"""
geocode-routes.py

Restart-safe geocoding pipeline with:
- Optional Google Address Validation (errors, including 403, are non-fatal)
- Google Geocoding API for lat/lng
- libpostal-based normalization (if installed)
- Per-county JSONL output for validation and geocoding
- Shared geocode_cache.json keyed by normalized geo_key

Environment:
    export GOOGLE_MAPS_API_KEY="YOUR_KEY"

Dependencies (typical):
    pip install pandas requests shapely pyproj postal

Note:
    If the project's billing account is closed, Google APIs (Validation + Geocoding)
    will likely return 403 / billing-related errors. This script will *not* crash
    in that case, but geocode_ok will stay False for those keys.
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import pandas as pd
import requests

# Optional: libpostal
try:
    from postal.expand import expand_address  # type: ignore
    LIBPOSTAL_AVAILABLE = True
except Exception:
    LIBPOSTAL_AVAILABLE = False

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

# Adjust these to match your actual input
INPUT_FILE = "GeoCallSearchResult_geocoded_with_corridor_all.csv"
INPUT_FILE_TYPE = "csv"  # "csv" or "xlsx"

COUNTY_COL_CANDIDATES = ["County", "COUNTY"]
CITY_COL_CANDIDATES = ["City", "CITY", "Place", "PLACE"]
STREET_COL_CANDIDATES = ["Street", "STREET", "Address", "ADDRESS", "LOCATE_STREET"]
INTERSECTION_COL_CANDIDATES = ["Intersection", "INTERSECTION", "CrossStreet", "CROSS_STREET"]
STATE_COL_CANDIDATES = ["State", "STATE"]

CACHE_FILE = Path("geocode_cache.json")
COUNTIES_DIR = Path("counties")

GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
GOOGLE_ADDRESS_VALIDATION_URL = "https://addressvalidation.googleapis.com/v1:validateAddress"

BATCH_SIZE = 40
BATCH_SLEEP_SECONDS = 0.2  # simple rate smoothing

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)


# ---------------------------------------------------------------------------
# Helpers: load data, pick columns
# ---------------------------------------------------------------------------

def pick_column(df: pd.DataFrame, candidates) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def load_input_dataframe() -> pd.DataFrame:
    if INPUT_FILE_TYPE == "csv":
        logging.info(f"Loading CSV: {INPUT_FILE}")
        df = pd.read_csv(INPUT_FILE)
    elif INPUT_FILE_TYPE == "xlsx":
        logging.info(f"Loading Excel: {INPUT_FILE}")
        df = pd.read_excel(INPUT_FILE)
    else:
        raise ValueError(f"Unsupported INPUT_FILE_TYPE: {INPUT_FILE_TYPE}")

    logging.info(f"Loaded {len(df)} rows from {INPUT_FILE}")
    return df


# ---------------------------------------------------------------------------
# Normalization & keying
# ---------------------------------------------------------------------------

def normalize_text(s: Any) -> str:
    if pd.isna(s):
        return ""
    return str(s).strip()


def libpostal_normalize_address(line: str) -> str:
    line = normalize_text(line)
    if not line:
        return line
    if not LIBPOSTAL_AVAILABLE:
        return line
    try:
        expansions = expand_address(line)
        if expansions:
            # pick first expansion for simplicity
            return expansions[0]
        return line
    except Exception as e:
        logging.warning(f"[WARN] libpostal failed for '{line}': {e}")
        return line


def make_geo_key(
    county: str,
    city: str,
    street: str,
    intersection: str,
    is_intersection: bool,
) -> str:
    # A stable key that groups equivalent address/intersection locates
    parts = [
        normalize_text(county).lower(),
        normalize_text(city).lower(),
        ("intersection" if is_intersection else "address"),
        normalize_text(street).lower(),
        normalize_text(intersection).lower(),
    ]
    return "|".join(parts)


# ---------------------------------------------------------------------------
# Google Address Validation (optional) & Geocoding
# ---------------------------------------------------------------------------

def get_api_key() -> str:
    key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY not set in environment.")
    return key


def call_google_address_validation(
    key: str,
    address_line: str,
    locality: str,
    admin_area: str,
    region_code: str = "US",
) -> Dict[str, Any]:
    """
    Call Google's Address Validation API in a NON-FATAL way.

    Any HTTPError (including 403) is caught, logged, and returns a
    pseudo-result with status "forbidden" or "error", so the rest of
    the pipeline can proceed using unvalidated/normalized strings.
    """
    if not address_line:
        return {
            "status": "skipped",
            "raw_address": "",
            "validated_address": "",
            "error": "no_address_line",
        }

    payload = {
        "address": {
            "regionCode": region_code,
            "administrativeArea": admin_area,
            "locality": locality,
            "addressLines": [address_line],
        }
    }
    params = {"key": key}

    try:
        r = requests.post(
            GOOGLE_ADDRESS_VALIDATION_URL,
            params=params,
            json=payload,
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        # Extract something simple as "validated line" if present
        validated_line = None
        try:
            result = data.get("result", {})
            address = result.get("address", {})
            address_lines = address.get("addressLines", []) or []
            if address_lines:
                validated_line = address_lines[0]
        except Exception:
            validated_line = None

        return {
            "status": "ok",
            "raw_address": address_line,
            "validated_address": validated_line or address_line,
            "full_response": data,
        }
    except requests.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else None
        logging.warning(
            f"[WARN] Address Validation failed for '{address_line}': "
            f"{status_code} {e}"
        )
        if status_code == 403:
            return {
                "status": "forbidden",
                "raw_address": address_line,
                "validated_address": address_line,
                "error": f"http_403_forbidden: {e}",
            }
        else:
            return {
                "status": "error",
                "raw_address": address_line,
                "validated_address": address_line,
                "error": f"http_error_{status_code}: {e}",
            }
    except Exception as e:
        logging.warning(
            f"[WARN] Address Validation failed for '{address_line}': {e}"
        )
        return {
            "status": "error",
            "raw_address": address_line,
            "validated_address": address_line,
            "error": f"exception: {e}",
        }


def call_google_geocode(
    key: str,
    address_line: str,
    city: str,
    county: str,
    state: str,
    region_code: str = "US",
) -> Dict[str, Any]:
    """
    Call Google Geocoding API. Any HTTP error is handled gracefully.
    Returns a dict describing geocode status & geometry.
    """
    if not address_line and not city:
        return {
            "status": "skipped",
            "lat": None,
            "lng": None,
            "formatted_address": "",
            "place_id": "",
            "raw_error": "no_address",
        }

    params = {
        "key": key,
        "region": region_code,
    }

    # Structured query: prefer components over free-form when we can
    address = address_line
    components = []

    if county:
        components.append(f"administrative_area:{state}")  # TX etc.
        components.append(f"country:{region_code}")
    else:
        components.append(f"country:{region_code}")

    # city as locality
    if city:
        # we keep city primarily in free-form; structured locality is optional
        pass

    params["address"] = ", ".join(
        part for part in [address_line, city, state] if part
    )
    params["components"] = "|".join(components)

    try:
        r = requests.get(GOOGLE_GEOCODE_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        status = data.get("status", "UNKNOWN")

        if status != "OK":
            return {
                "status": status,
                "lat": None,
                "lng": None,
                "formatted_address": "",
                "place_id": "",
                "raw_response": data,
            }

        results = data.get("results", [])
        if not results:
            return {
                "status": "ZERO_RESULTS",
                "lat": None,
                "lng": None,
                "formatted_address": "",
                "place_id": "",
                "raw_response": data,
            }

        best = results[0]
        loc = best["geometry"]["location"]
        return {
            "status": "OK",
            "lat": float(loc["lat"]),
            "lng": float(loc["lng"]),
            "formatted_address": best.get("formatted_address", ""),
            "place_id": best.get("place_id", ""),
            "raw_response": data,
        }
    except requests.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else None
        logging.warning(
            f"[WARN] Geocoding HTTP error for '{address_line}': {status_code} {e}"
        )
        return {
            "status": f"http_error_{status_code}",
            "lat": None,
            "lng": None,
            "formatted_address": "",
            "place_id": "",
            "raw_error": str(e),
        }
    except Exception as e:
        logging.warning(
            f"[WARN] Geocoding exception for '{address_line}': {e}"
        )
        return {
            "status": "exception",
            "lat": None,
            "lng": None,
            "formatted_address": "",
            "place_id": "",
            "raw_error": str(e),
        }


# ---------------------------------------------------------------------------
# Cache I/O
# ---------------------------------------------------------------------------

def load_cache() -> Dict[str, Any]:
    if CACHE_FILE.exists():
        with CACHE_FILE.open("r", encoding="utf-8") as f:
            cache = json.load(f)
        logging.info(
            f"[INFO] Loaded existing geocode cache: {CACHE_FILE} "
            f"({len(cache)} keys)."
        )
        return cache
    logging.info("[INFO] No existing cache, starting fresh.")
    return {}


def save_cache(cache: Dict[str, Any]) -> None:
    with CACHE_FILE.open("w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    logging.info(
        f"[INFO] Cache flushed to {CACHE_FILE} ({len(cache)} keys)."
    )


# ---------------------------------------------------------------------------
# Per-county JSONL writing
# ---------------------------------------------------------------------------

def ensure_county_dir(county_slug: str) -> Path:
    path = COUNTIES_DIR / county_slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def county_slugify(county_name: str) -> str:
    return normalize_text(county_name).lower().replace(" ", "_")


def write_county_jsonl(
    county_name: str,
    validated_rows,
    geocoded_rows,
) -> None:
    slug = county_slugify(county_name or "unknown")
    county_dir = ensure_county_dir(slug)

    val_path = county_dir / f"{slug}-validated.jsonl"
    geo_path = county_dir / f"{slug}-geocoded.jsonl"

    with val_path.open("w", encoding="utf-8") as f:
        for row in validated_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    with geo_path.open("w", encoding="utf-8") as f:
        for row in geocoded_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    logging.info(
        f"[INFO] Wrote validated JSONL for county '{county_name}' to {val_path}"
    )
    logging.info(
        f"[INFO] Wrote geocoded JSONL for county '{county_name}' to {geo_path}"
    )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    key = get_api_key()
    df = load_input_dataframe()

    # Resolve columns
    county_col = pick_column(df, COUNTY_COL_CANDIDATES)
    city_col = pick_column(df, CITY_COL_CANDIDATES)
    street_col = pick_column(df, STREET_COL_CANDIDATES)
    intersection_col = pick_column(df, INTERSECTION_COL_CANDIDATES)
    state_col = pick_column(df, STATE_COL_CANDIDATES)

    if not county_col:
        raise RuntimeError("Could not find a County column.")
    if not city_col:
        raise RuntimeError("Could not find a City/Place column.")
    if not street_col and not intersection_col:
        raise RuntimeError("Need at least Street or Intersection column.")
    if not state_col:
        logging.info("[INFO] No State column found; defaulting to 'TX' for all rows.")

    # Derive state per-row (default TX)
    df["_state"] = "TX"
    if state_col:
        df["_state"] = df[state_col].fillna("TX")

    # Build geo_key for each row
    geo_keys = []
    for idx, row in df.iterrows():
        county = row[county_col]
        city = row[city_col]
        street = row[street_col] if street_col else ""
        intersection = row[intersection_col] if intersection_col else ""
        is_intersection = bool(normalize_text(intersection))

        gk = make_geo_key(county, city, street, intersection, is_intersection)
        geo_keys.append(gk)

    df["_geo_key"] = geo_keys

    unique_geo_keys = sorted(set(g for g in geo_keys if g))
    logging.info(
        f"[INFO] Total rows: {len(df)} | Unique geo_keys: {len(unique_geo_keys)}"
    )

    cache = load_cache()

    # Determine which keys need geocoding
    keys_to_geocode = [g for g in unique_geo_keys if g not in cache]
    logging.info(
        f"[INFO] Keys in cache: {len(cache)} | Keys to geocode this run: {len(keys_to_geocode)}"
    )

    # Prebuild a lookup from geo_key -> representative address components
    # We just pick the first row for each geo_key
    rep_by_geo_key: Dict[str, Tuple[str, str, str, str, bool]] = {}
    for gk, row in df.groupby("_geo_key").first().iterrows():
        county = row[county_col]
        city = row[city_col]
        street = row[street_col] if street_col else ""
        intersection = row[intersection_col] if intersection_col else ""
        is_intersection = bool(normalize_text(intersection))
        state = row["_state"]
        rep_by_geo_key[gk] = (
            normalize_text(county),
            normalize_text(city),
            normalize_text(street),
            normalize_text(intersection),
            is_intersection,
        )

    # Geocode missing keys in batches
    start_time = time.time()
    for i in range(0, len(keys_to_geocode), BATCH_SIZE):
        batch = keys_to_geocode[i:i + BATCH_SIZE]
        logging.info(
            f"[INFO] Geocoding batch {i//BATCH_SIZE + 1} "
            f"({len(batch)} keys: {i+1}–{i+len(batch)})"
        )

        for gk in batch:
            county, city, street, intersection, is_intersection = rep_by_geo_key[gk]

            # Build raw "line" to be validated / normalized
            # For intersections, we pass intersection name; for addresses, street.
            raw_line = intersection if is_intersection else street

            # libpostal normalize first
            normalized_line = libpostal_normalize_address(raw_line)

            # Call Google Address Validation (optional; non-fatal)
            validation_result = call_google_address_validation(
                key=key,
                address_line=normalized_line,
                locality=city,
                admin_area="TX",  # you can refine by row-specific state if needed
                region_code="US",
            )

            # Choose address to geocode: prefer validated_address if status=ok
            if validation_result["status"] == "ok":
                line_for_geocode = validation_result["validated_address"]
            else:
                line_for_geocode = normalized_line

            # Geocode
            state = "TX"  # or row-specific if different states appear
            geocode_result = call_google_geocode(
                key=key,
                address_line=line_for_geocode,
                city=city,
                county=county,
                state=state,
                region_code="US",
            )

            cache[gk] = {
                "geo_key": gk,
                "county": county,
                "city": city,
                "street": street,
                "intersection": intersection,
                "is_intersection": is_intersection,
                "raw_line": raw_line,
                "normalized_line": normalized_line,
                "validation": validation_result,
                "geocode": geocode_result,
            }

        # Save cache after each batch
        save_cache(cache)
        time.sleep(BATCH_SLEEP_SECONDS)

    total_time = time.time() - start_time
    logging.info(
        f"[INFO] Geocoding complete for this run. Total runtime: {total_time:.1f} seconds"
    )

    # Attach geocode_ok to each row by joining on _geo_key
    def is_geocode_ok(geo_info: Dict[str, Any]) -> bool:
        if not geo_info:
            return False
        geocode = geo_info.get("geocode", {})
        return geocode.get("status") == "OK" and geocode.get("lat") is not None

    # Build per-row geocode_ok + lat/lng
    geocode_ok_list = []
    lat_list = []
    lng_list = []

    for _, row in df.iterrows():
        gk = row["_geo_key"]
        info = cache.get(gk, {})
        if info:
            ok = is_geocode_ok(info)
            geocode_ok_list.append(1 if ok else 0)
            geo = info.get("geocode", {})
            lat_list.append(geo.get("lat"))
            lng_list.append(geo.get("lng"))
        else:
            geocode_ok_list.append(0)
            lat_list.append(None)
            lng_list.append(None)

    df["geocode_ok"] = geocode_ok_list
    df["lat"] = lat_list
    df["lng"] = lng_list

    # Summary
    total_rows = len(df)
    ok_rows = int(df["geocode_ok"].sum())
    logging.info("=== Geocoding Summary (Google) ===")
    logging.info(f"Total rows:        {total_rows}")
    logging.info(f"Rows geocode_ok=1: {ok_rows}")
    logging.info(f"Rows geocode_ok=0: {total_rows - ok_rows}")
    logging.info(f"Total unique keys: {len(unique_geo_keys)}")
    logging.info(f"Total keys in cache: {len(cache)}")

    # Write per-county JSONL from cache
    # We group by county, but use cache objects so that each geo_key is written once.
    county_to_validated = {}
    county_to_geocoded = {}

    for gk, info in cache.items():
        county = info.get("county", "") or ""
        if not county:
            county = "UNKNOWN"

        v_list = county_to_validated.setdefault(county, [])
        g_list = county_to_geocoded.setdefault(county, [])

        validation = info.get("validation", {})
        geocode = info.get("geocode", {})

        v_list.append(
            {
                "geo_key": gk,
                "county": info.get("county"),
                "city": info.get("city"),
                "street": info.get("street"),
                "intersection": info.get("intersection"),
                "is_intersection": info.get("is_intersection"),
                "raw_line": info.get("raw_line"),
                "normalized_line": info.get("normalized_line"),
                "validation_status": validation.get("status"),
                "validated_address": validation.get("validated_address"),
                "validation_error": validation.get("error"),
            }
        )

        g_list.append(
            {
                "geo_key": gk,
                "county": info.get("county"),
                "city": info.get("city"),
                "street": info.get("street"),
                "intersection": info.get("intersection"),
                "is_intersection": info.get("is_intersection"),
                "line_for_geocode": info.get("normalized_line"),
                "geocode_status": geocode.get("status"),
                "lat": geocode.get("lat"),
                "lng": geocode.get("lng"),
                "formatted_address": geocode.get("formatted_address"),
                "place_id": geocode.get("place_id"),
            }
        )

    for county_name, v_rows in county_to_validated.items():
        g_rows = county_to_geocoded.get(county_name, [])
        write_county_jsonl(county_name, v_rows, g_rows)


if __name__ == "__main__":
    main()
