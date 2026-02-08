# Wink APN 811 Ticket Geocoding & Frequency/Severity Pipeline  
**(libpostal + Google + Parallel + Restart-Safe + Per-County JSON)**

You are helping build a geocoding and frequency/severity modeling pipeline for the **Wink APN** fiber build in West Texas. The goal is to:

- Use **Texas 811 locate ticket data** for Winkler and surrounding counties,
- Geocode ticket locations as accurately as possible,
- Determine which tickets lie within a **corridor around the planned Wink APN fiber route**,
- Use that to estimate **ticket and damage frequency per mile per year**, and
- Support an **O&M pricing model** (including expected damage repair and locate costs) for a **20-year IRU/lease-style agreement** with AWS.

The main Python script for this is:

> `geocode-intersect-routes.py`

---

## Data & Context

- Multiple Texas 811 Excel exports with columns such as:
  - `Street` (primary road or address)
  - `Intersection` (cross-street, often with rural abbreviations: CR, FM, HWY, TX-)
  - `City`
  - `County`
  - Ticket ID and other metadata

- Fiber route geometry is in:

  - `Wink APN.kmz`  
    ~125 route miles across several legs.

- A previous Nominatim-based run produced:
  - 23,601 total tickets across three counties,
  - 4,577 geocoded successfully,
  - 1,379 tickets within a 250 m corridor around the route,
  - implying roughly **11 tickets/mile/year** as a conservative data-backed lower bound.

- These results feed into:
  - An **O&M cost model** and **maintenance workbook**, including:
    - Locate costs (e.g., 15 vs 40 tickets/mile/year at ~$25/locate),
    - Damage frequencies/severity,
    - Long-term 20-year IRU pricing.

---

## Directory Layout & File Organization

Assume the working directory is:

> `operations/maintenance`

The script should maintain the following structure:

### Top-Level

- `counties/` — per-county pipeline snapshots (JSONL).
- `routes/` — route metadata, especially bounds for corridor bias.
- `geocode_cache.json` — restart-safe address geocode cache (keyed by `geo_key`).

### Under `counties/`

- One directory **per county**, using a slugified county name:

  - `counties/winkler/`
  - `counties/ward/`
  - `counties/reeves/`
  - etc.

- In each county directory, maintain **one JSONL file per pipeline stage**:

  - `<county-slug>-normalized.jsonl`
  - `<county-slug>-validated.jsonl`
  - `<county-slug>-geocoded.jsonl`

  Where each JSONL is **newline-delimited JSON** (one JSON object per line).

### Under `routes/`

- `routes/wink_apn/`  
  At minimum:

  - `route_bounds.json` — contains bounding box derived from `Wink APN.kmz`:
    ```json
    {
      "south": ...,
      "west": ...,
      "north": ...,
      "east": ...
    }
    ```

- Optionally, other route metadata as needed later.

---

## Script to Build: `geocode-intersect-routes.py`

The script should:

1. **Load & Normalize Ticket Data (with libpostal)**
2. **Compute Corridor Bounds from `Wink APN.kmz`**
3. **Load & Apply a Restart-Safe Geocode Cache (JSON)**
4. **Use libpostal + Google Address Validation + Google Geocoding**
5. **Geocode in Parallel Across Unique Address Keys**
6. **Write Per-County JSONL Progress Files (normalized / validated / geocoded)**
7. **Persist Everything in a Restart-Safe Way**

Each of these is detailed below.

---

## 1. Load & Normalize Ticket Data (with libpostal)

### 1.1 Input Files

- Read all Excel files matching a glob like:

  ```text
  GeoCallSearchResult*.xlsx
