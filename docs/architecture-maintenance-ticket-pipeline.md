# Wink APN 811 Ticket Geocoding & Frequency/Severity Architecture

## 1. Overview

This document describes the architecture of the **Wink APN 811 ticket geocoding and frequency/severity pipeline**.

The goal of the pipeline is to:

- Ingest Texas 811 locate ticket data for Winkler and surrounding counties.
- Normalize and geocode ticket locations with high fidelity.
- Constrain those locations to a **corridor** around the planned Wink APN fiber route.
- Use those geocoded tickets to estimate **ticket and damage frequency per mile per year**.
- Feed an **O&M cost model** and 20-year IRU pricing for the AWS Metro Fiber / Wink APN build.

Core scripts:

- `geocode-intersect-routes.py` — new, restart-safe, JSON/JSONL-based geocoding pipeline.
- `migrate.py` — one-time migration script from legacy CSV to the new cache/JSON format.
- `frequency.py` — corridor intersection & frequency/severity modeling (uses geocoded output).

---

## 2. Inputs & Outputs

### 2.1 Inputs

- **Texas 811 Excel Exports**

  - Files matching `GeoCallSearchResult*.xlsx`.
  - Key columns:
    - `Street` — primary road/address.
    - `Intersection` — cross street (often with abbreviations: CR, FM, HWY, TX-).
    - `City`, `County`.
    - Ticket ID, dates, and other metadata.

- **Wink APN Route**

  - `Wink APN.kmz` — KML/KMZ containing route geometries (~125 route miles total).
  - Used to derive a 2D bounding box and later a corridor buffer.

- **Environment / Config**

  - `GOOGLE_MAPS_API_KEY` — for:
    - Google **Address Validation API**.
    - Google **Geocoding API**.

---

## 3. Directory Layout

Working directory: `operations/maintenance`

Key files and directories:

```text
operations/maintenance/
  geocode-intersect-routes.py
  migrate.py
  frequency.py
  Wink APN.kmz
  GeoCallSearchResult_geocoded_with_corridor_all.csv   (legacy)
  GeoCallSearchResult_geocoded_with_corridor_buffered.csv (legacy)

  counties/
    winkler/
      winkler-normalized.jsonl
      winkler-validated.jsonl
      winkler-geocoded.jsonl
    ward/
      ward-normalized.jsonl
      ...

  routes/
    wink_apn/
      route_bounds.json

  geocode_cache.json
  prompts/
    ticket-pipeline.md
    ticket-analysis-pipeline.md
    ...
