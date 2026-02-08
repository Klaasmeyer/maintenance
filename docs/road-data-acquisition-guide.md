# Road Data Acquisition Guide

**Goal:** Acquire road geometry data for CR 426, CR 516, CR 432, and other missing roads in Ward, Andrews, and Winkler counties.

**Target:** Solve 512+ of the remaining 721 failures to achieve 98%+ geocoding success rate.

---

## Priority Roads Needed

Based on failure analysis, these roads would have the highest impact:

| Road | Failures | County | Priority |
|------|----------|--------|----------|
| CR 426 | 377 | Ward | 🔴 Critical |
| CR 516 | 76 | Ward | 🔴 Critical |
| CR 432 | 59 | Ward | 🔴 Critical |
| SE 8000, NE 7501, etc. | 40+ | Andrews | 🟡 High |
| FM 432 | 8 | Ward | 🟢 Medium |
| Local roads | 109 | Various | 🟢 Medium |

**Total potential impact:** 512+ tickets (70% of remaining failures)

---

## Data Sources

### 1. TxDOT (Texas Department of Transportation) 🎯 RECOMMENDED

**TxDOT GIS Data Portal**
- URL: https://gis-txdot.opendata.arcgis.com/
- Data: Official state-maintained road inventory
- Coverage: All Texas roads including county roads
- Format: Shapefiles, GeoJSON, File Geodatabase

**Specific Datasets to Download:**
1. **Texas County Roads**
   - Dataset: "County Maintained Roads"
   - URL: https://gis-txdot.opendata.arcgis.com/datasets/txdot-county-maintained-roads
   - Filter for: Ward, Andrews, Winkler counties

2. **Farm-to-Market Roads**
   - Dataset: "State Highway System"
   - URL: https://gis-txdot.opendata.arcgis.com/datasets/txdot-roadways
   - Includes: FM, RM, SH, US highways

3. **Texas Road Inventory**
   - Comprehensive dataset with all road types
   - URL: https://www.txdot.gov/data-maps/gis-data.html

**Download Steps:**
```bash
# Via ArcGIS REST API
curl "https://services.arcgis.com/KTcxiTD9dsQw4r7Z/arcgis/rest/services/\
TxDOT_County_Maintained_Roads/FeatureServer/0/query?\
where=COUNTY_NAME+IN+%28%27WARD%27%2C%27ANDREWS%27%2C%27WINKLER%27%29\
&outFields=*&f=geojson" -o txdot_county_roads.geojson
```

---

### 2. County GIS Portals

**Ward County**
- GIS Portal: Check county website or Texas GIS portals
- May have higher resolution local road data
- Contact: Ward County Appraisal District or County Engineer

**Andrews County**
- GIS Portal: Similar to Ward
- Numbered roads (SE 8000, etc.) may be in county data

**Winkler County**
- GIS Portal: Check for local road inventory

**Texas County GIS Hub:**
- URL: https://tnris.org/ (Texas Natural Resources Information System)
- Centralized access to county-level data

---

### 3. TIGER/Line (U.S. Census Bureau)

**Census Road Data**
- URL: https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html
- Coverage: All U.S. roads including county roads
- Format: Shapefiles
- Quality: Good for major roads, variable for local roads

**Download:**
```bash
# 2024 TIGER/Line Roads for Texas counties
# Ward County FIPS: 48475
# Andrews County FIPS: 48003
# Winkler County FIPS: 48495

wget https://www2.census.gov/geo/tiger/TIGER2024/ROADS/tl_2024_48475_roads.zip
wget https://www2.census.gov/geo/tiger/TIGER2024/ROADS/tl_2024_48003_roads.zip
wget https://www2.census.gov/geo/tiger/TIGER2024/ROADS/tl_2024_48495_roads.zip
```

---

### 4. OpenStreetMap (Enhanced Extract)

**Overpass Turbo** (Already tried, limited success)
- URL: https://overpass-turbo.eu/
- Good for major roads, poor for local county roads

**Geofabrik Texas Extract**
- URL: https://download.geofabrik.de/north-america/us/texas.html
- Full Texas OSM data
- May have more roads than our targeted Overpass query

---

## Acquisition Strategy

### Phase 1: TxDOT Data (Highest Priority)
1. Download TxDOT County Maintained Roads for 3 counties
2. Download TxDOT State Highway System (for FM/RM roads)
3. Merge with existing OSM data (roads.gpkg)
4. Re-run geometric geocoding

**Expected Impact:** Solve 450-500 additional tickets

### Phase 2: TIGER/Line Data (Supplement)
1. Download TIGER roads for 3 counties
2. Filter for roads not in TxDOT dataset
3. Add to combined road network

**Expected Impact:** Solve 20-50 additional tickets

### Phase 3: Manual Enhancement (If Needed)
1. For remaining high-value failures, manually digitize roads
2. Use Google Maps/satellite imagery to trace roads
3. Focus on roads with 5+ failures

**Expected Impact:** Solve 10-20 additional tickets

---

## Data Processing Workflow

### Step 1: Download TxDOT Data
```bash
# Script: download_txdot_data.py (to be created)
python download_txdot_data.py --counties Ward,Andrews,Winkler --output txdot_roads.gpkg
```

### Step 2: Merge with Existing OSM Data
```bash
# Script: merge_road_networks.py (to be created)
python merge_road_networks.py \
  --input roads.gpkg,txdot_roads.gpkg \
  --output roads_merged.gpkg \
  --deduplicate
```

### Step 3: Re-run Geometric Geocoding
```bash
# Use merged road network
python apply_geometric_geocoding.py --roads roads_merged.gpkg
```

### Step 4: Validate and Measure Improvement
```bash
# Compare results
python compare_geocoding_results.py \
  --before geometric_results.csv \
  --after geometric_results_merged.csv
```

---

## Data Quality Checks

After acquiring new data:

1. **Coverage check:**
   ```python
   # Check if priority roads are now present
   python inspect_roads.py --roads roads_merged.gpkg --search "CR 426,CR 516,CR 432"
   ```

2. **Intersection validation:**
   ```python
   # Test geometric geocoding on sample failures
   python test_geocoding_samples.py --count 50
   ```

3. **Visual inspection:**
   - Load roads_merged.gpkg in QGIS
   - Verify road connectivity and completeness
   - Check for duplicate or overlapping segments

---

## Contact Information

**TxDOT GIS Support:**
- Email: gis@txdot.gov
- Phone: (512) 416-2900
- They can help with data access questions

**Ward County:**
- Ward County Courthouse: (432) 943-3294
- May have local road data not in state databases

**Andrews County:**
- Andrews County Courthouse: (432) 524-1417

**Winkler County:**
- Winkler County Courthouse: (432) 586-3401

---

## Estimated Timeline

- **TxDOT download:** 1-2 hours
- **Data processing/merging:** 2-4 hours
- **Re-run geocoding:** 10-15 minutes
- **Validation:** 1-2 hours

**Total:** ~1 day of work

---

## Expected Final Results

**Current State:**
- Success rate: 96.95%
- Failed: 721 tickets

**After TxDOT Data:**
- Success rate: 98.5-99.0%
- Failed: ~200-300 tickets

**After TIGER/Line Supplement:**
- Success rate: 99.0-99.5%
- Failed: ~100-150 tickets

**Final with Manual Enhancement:**
- Success rate: 99.5%+
- Failed: <100 tickets (likely data quality issues in original tickets)

---

## Scripts to Create

1. `download_txdot_data.py` - Automated TxDOT data download
2. `download_tiger_data.py` - Automated TIGER/Line download
3. `merge_road_networks.py` - Merge multiple road datasets
4. `compare_geocoding_results.py` - Before/after analysis

**Status:** To be implemented based on acquired data

---

*Last Updated: 2026-02-08*
*Next: Download TxDOT data and test on sample*
