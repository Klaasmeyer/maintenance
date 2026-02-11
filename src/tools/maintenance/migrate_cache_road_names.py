#!/usr/bin/env python
"""
migrate_cache_road_names.py

Rekeys geocode_cache.json using the new normalize_road_name() function,
deduplicating entries whose raw road-name variants now collapse to the
same canonical key.

When multiple old entries map to a single new key, the entry with
geocode.status == "OK" is preferred (i.e. one that actually has lat/lng).

Usage:
    python migrate_cache_road_names.py --dry-run   # preview only
    python migrate_cache_road_names.py              # apply migration
"""

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

# geocode-routes.py isn't a package; import via importlib.
from importlib import import_module

geocode_routes = import_module("geocode-routes")
make_geo_key = geocode_routes.make_geo_key

CACHE_FILE = Path("geocode_cache.json")
BACKUP_FILE = Path("geocode_cache.pre_road_norm.backup.json")

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def is_geocode_ok(entry: dict) -> bool:
    geocode = entry.get("geocode", {})
    if not isinstance(geocode, dict):
        return False
    return geocode.get("status") == "OK" and geocode.get("lat") is not None


def rekey_cache(cache: dict) -> tuple[dict, int]:
    """Recompute cache keys and deduplicate.

    Returns (new_cache, duplicates_merged).
    """
    new_cache: dict = {}
    duplicates = 0

    for old_key, entry in cache.items():
        county = entry.get("county", "")
        city = entry.get("city", "")
        street = entry.get("street", "")
        intersection = entry.get("intersection", "")
        is_intersection = entry.get("is_intersection", False)

        new_key = make_geo_key(county, city, street, intersection, is_intersection)

        if new_key in new_cache:
            duplicates += 1
            existing = new_cache[new_key]
            # Keep the entry with a successful geocode result.
            if not is_geocode_ok(existing) and is_geocode_ok(entry):
                new_cache[new_key] = entry
            # Otherwise keep the existing (first-seen or already-OK) entry.
        else:
            new_cache[new_key] = entry

        # Update the stored geo_key to match the new canonical key.
        new_cache[new_key]["geo_key"] = new_key

    return new_cache, duplicates


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate geocode cache to use normalized road names."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration without writing changes.",
    )
    args = parser.parse_args()

    if not CACHE_FILE.exists():
        logging.error(f"Cache file not found: {CACHE_FILE}")
        sys.exit(1)

    logging.info(f"Loading cache from {CACHE_FILE}")
    with CACHE_FILE.open("r", encoding="utf-8") as f:
        cache = json.load(f)

    before_count = len(cache)
    logging.info(f"Entries before migration: {before_count}")

    new_cache, duplicates = rekey_cache(cache)
    after_count = len(new_cache)

    logging.info(f"Entries after migration:  {after_count}")
    logging.info(f"Duplicates merged:        {duplicates}")
    logging.info(f"Net reduction:            {before_count - after_count}")

    if args.dry_run:
        logging.info("Dry run — no changes written.")
        return

    # Backup original cache
    logging.info(f"Backing up to {BACKUP_FILE}")
    shutil.copy2(CACHE_FILE, BACKUP_FILE)

    # Write migrated cache
    with CACHE_FILE.open("w", encoding="utf-8") as f:
        json.dump(new_cache, f, ensure_ascii=False, indent=2)
    logging.info(f"Saved migrated cache to {CACHE_FILE}")


if __name__ == "__main__":
    main()
