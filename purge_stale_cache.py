#!/usr/bin/env python
"""
purge_stale_cache.py

Removes stale/failed entries from geocode_cache.json so they can be
re-geocoded on the next run of geocode-routes.py.

Entries removed:
  - Old-format (flat dict without nested 'geocode' key)
  - New-format with non-OK geocode status (ZERO_RESULTS, exception, etc.)

A backup is saved to geocode_cache.backup.json before any changes.
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Any

CACHE_FILE = Path("geocode_cache.json")
BACKUP_FILE = Path("geocode_cache.backup.json")

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def is_new_format(entry: dict[str, Any]) -> bool:
    """Return True if the entry uses the new nested geocode/validation format."""
    return "geocode" in entry and isinstance(entry["geocode"], dict)


def is_geocode_ok(entry: dict[str, Any]) -> bool:
    """Return True if the entry has a successful geocode result."""
    if not is_new_format(entry):
        return False
    return entry["geocode"].get("status") == "OK"


def classify_cache(cache: dict[str, Any]) -> dict[str, int]:
    """Return a breakdown of cache entry categories."""
    stats: dict[str, int] = {
        "total": 0,
        "new_format": 0,
        "new_ok": 0,
        "new_failed": 0,
        "old_format": 0,
    }
    status_counts: dict[str, int] = {}

    for entry in cache.values():
        stats["total"] += 1
        if is_new_format(entry):
            stats["new_format"] += 1
            status = entry["geocode"].get("status", "MISSING")
            if status == "OK":
                stats["new_ok"] += 1
            else:
                stats["new_failed"] += 1
        else:
            stats["old_format"] += 1
            status = entry.get("status", "MISSING")

        status_counts[status] = status_counts.get(status, 0) + 1

    return stats, status_counts


def purge_cache(cache: dict[str, Any]) -> dict[str, Any]:
    """Return a new cache containing only new-format entries with OK status."""
    return {k: v for k, v in cache.items() if is_geocode_ok(v)}


def report(label: str, stats: dict[str, int], status_counts: dict[str, int]) -> None:
    """Log a summary of cache statistics."""
    logging.info(f"=== {label} ===")
    logging.info(f"  Total entries:      {stats['total']}")
    logging.info(f"  New format:         {stats['new_format']}")
    logging.info(f"    OK:               {stats['new_ok']}")
    logging.info(f"    Failed:           {stats['new_failed']}")
    logging.info(f"  Old format:         {stats['old_format']}")
    logging.info(f"  Status breakdown:")
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        logging.info(f"    {status}: {count}")


def main() -> None:
    if not CACHE_FILE.exists():
        logging.error(f"Cache file not found: {CACHE_FILE}")
        return

    logging.info(f"Loading cache from {CACHE_FILE}")
    with CACHE_FILE.open("r", encoding="utf-8") as f:
        cache = json.load(f)

    before_stats, before_status = classify_cache(cache)
    report("BEFORE PURGE", before_stats, before_status)

    # Backup
    logging.info(f"Backing up to {BACKUP_FILE}")
    shutil.copy2(CACHE_FILE, BACKUP_FILE)

    # Purge
    cleaned = purge_cache(cache)
    removed = before_stats["total"] - len(cleaned)

    after_stats, after_status = classify_cache(cleaned)
    report("AFTER PURGE", after_stats, after_status)

    logging.info(f"Removed {removed} entries")
    logging.info(f"Retained {len(cleaned)} entries")

    # Save
    with CACHE_FILE.open("w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
    logging.info(f"Saved cleaned cache to {CACHE_FILE}")


if __name__ == "__main__":
    main()
