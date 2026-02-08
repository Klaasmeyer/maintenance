---

## `README.md` (for `operations/maintenance` or a subdir repo)

```markdown
# Wink APN – 811 Ticket Geocoding & Frequency/Severity Pipeline

This directory contains the scripts and artifacts used to:

- Geocode Texas 811 locate ticket data for **Winkler and nearby counties**.
- Constrain ticket locations to a **corridor around the Wink APN fiber route**.
- Estimate **ticket frequency per route-mile per year**.
- Feed a **20-year O&M and IRU pricing model** for the AWS Metro Fiber / Wink APN build.

## Contents

Key files:

- `geocode-intersect-routes.py`  
  Main geocoding pipeline:
  - Reads `GeoCallSearchResult*.xlsx` exports.
  - Normalizes roads (`CR`, `FM`, `HWY`, `TX-`, etc.).
  - Optionally uses **libpostal** for better address normalization.
  - Uses **Google Address Validation** + **Geocoding** (with corridor bounds).
  - Writes per-county JSONL files (`normalized`, `validated`, `geocoded`).
  - Maintains a restart-safe `geocode_cache.json`.

- `migrate.py`  
  One-time migration tool:
  - Reads legacy `GeoCallSearchResult_geocoded_with_corridor_all.csv`.
  - Rebuilds normalization fields and `geo_key`.
  - Creates an initial `geocode_cache.json`.
  - Writes per-county JSONL files in the new format.

- `frequency.py`  
  Frequency & severity modeling:
  - Uses geocoded tickets to estimate tickets/mile/year inside a corridor buffer.
  - Produces summaries that feed the O&M pricing workbook.

- `Wink APN.kmz`  
  KMZ/KML route file for the Wink APN fiber route.  
  Used to create `routes/wink_apn/route_bounds.json` and corridor buffers.

Generated directories & files:

- `counties/`  
  Per-county pipeline snapshots:
  - `<slug>-normalized.jsonl`
  - `<slug>-validated.jsonl`
  - `<slug>-geocoded.jsonl`

- `routes/wink_apn/route_bounds.json`  
  Route bounding box for Geocoding `bounds` parameter.

- `geocode_cache.json`  
  Restart-safe cache keyed by `geo_key`.

- `prompts/`  
  Markdown prompts and design docs for AI-assisted development:
  - `ticket-pipeline.md`
  - `ticket-analysis-pipeline.md`
  - etc.

---

## Setup

### 1. Python Environment

Create and activate a virtualenv (example):

```bash
cd /Users/corey/ck/projects/kcci/operations/maintenance

python3 -m venv .venv
source .venv/bin/activate
