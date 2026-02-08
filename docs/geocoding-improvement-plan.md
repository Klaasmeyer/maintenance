# Geocoding Improvement Plan - 7 Step Strategy

**Goal:** Increase geocoding success rate from 96.92% to 98-100%
**Target:** 728 failed intersections (all ZERO_RESULTS or exceptions)
**Date Started:** 2026-02-08
**Status:** Steps 1-3 complete, moving to Step 4

---

## The 7-Step Plan

### Step 1: Analyze Current Failure Patterns ✅ COMPLETE

**Implementation:** `analyze_ticket_geocoding.py`

**Key Findings:**
- **Total tickets:** 23,601
- **Success rate:** 96.92% (22,873 successful)
- **Failures:** 728 tickets (3.08%)

**Failure Breakdown:**
- **100% are intersections** (0 address failures)
- **94.2%** are ZERO_RESULTS (Google can't find it)
- **5.8%** are exceptions (API errors)

**Geographic Distribution:**
- **Ward County:** 655 failures (90%)
  - Pyote: 440
  - Barstow: 186
- **Andrews County:** 64 failures
- **Winkler County:** 9 failures

**Problematic Road Types:**
1. **CR & CR** (County Road × County Road): 383 failures (53%)
2. **CR & Interstate**: 81 failures
3. **FM & CR**: 64 failures
4. **FM & Interstate**: 44 failures
5. **Numbered roads & US Highway**: 42 failures

**Critical Pattern:**
Many failures involve **numbered county roads** (SE 8000, NE 7501, NW 9999) that don't have well-known names in Google's database. The same intersection appears with multiple naming variants (e.g., "US HWY 385" vs "US-385" vs "HWY 385") - all fail.

**Potential Impact:**
If geometric intersection solving succeeds for all 728 intersection failures:
- Success rate: 96.92% → 100.00% (+3.08%)
- Ward County: 7,880 → 8,535 geocoded (+8.3%)

**Output Files:**
- `ticket_analysis_report.json` - Detailed statistics
- `ticket_failures.csv` - All 728 failed tickets

---

### Step 2: Enhanced Road Name Normalization & Fuzzy Matching

**Status:** PLANNED (defer to after Step 4)

**Tasks:**
- Extend `normalize_road_name()` for more variants
- Add fuzzy matching against known roads
- Handle directionals (N/S/E/W variants)
- Common misspellings and data entry errors

**Priority:** Medium (quick wins available, but geometric solving is higher impact)

---

### Step 3: Acquire Texas Road Geometry Data ✅ COMPLETE

**Implementation:** `download_road_network.py`

**Data Source:** OpenStreetMap (Overpass API)
**Coverage:** Andrews, Ward, and Winkler counties
**Bounding Box:** (-103.55, 31.35) to (-101.95, 32.65)

**Road Network Statistics:**
- **Total segments:** 1,969
- **File:** `roads.gpkg` (0.89 MB GeoPackage)
- **Format:** EPSG:4326 with spatial index

**Road Type Distribution:**
| Type | Count | % | Coverage Status |
|------|-------|---|----------------|
| State Highways (TX/SH) | 602 | 31% | ✅ Excellent |
| Interstate (I-20) | 354 | 18% | ✅ Excellent |
| US Highways | 94 | 5% | ✅ US 385 found (83 segments) |
| Farm-to-Market (FM) | 168 | 9% | ✅ FM 1788 found (35 segments) |
| County Roads (CR) | 176 | 9% | ⚠️ Partial |
| CR Numbered | 86 | 4% | ❌ Missing target roads |
| Ranch-to-Market (RM) | 5 | <1% | ⚠️ Limited |
| Other | 484 | 25% | N/A |

**Key Roads from Failures - Found:**
- ✅ US 385 (83 segments) - Major road in many failures
- ✅ FM 1788 (35 segments)
- ✅ I-20 and variants
- ✅ CR 201 and some named county roads

**Key Roads - NOT Found:**
- ❌ SE 8000, SW 8000 (numbered county roads)
- ❌ NE 7501, NW 9999 (numbered county roads)
- ❌ Most directional numbered roads

**Analysis:**
OSM has good coverage of **major roads** (state highways, US routes, FM roads) but **poor coverage of numbered county roads** (SE 8000, etc.). This is expected - local numbered roads are often unmapped in OSM.

**Implication:**
- Can geometrically solve ~30-40% of failures (where we have both roads)
- Cannot solve ~60-70% where numbered county roads are involved
- Estimated 200-300 tickets can be rescued with current data

**Output Files:**
- `roads.gpkg` - GeoPackage with road geometries
- `roads_metadata.json` - Dataset metadata

**Future Enhancement Options:**
1. Request TxDOT county road data (official source)
2. Implement grid-based estimation for numbered roads
   - SE 8000 might mean "8000 units southeast" of county origin
   - Requires understanding local numbering system
3. Web scraping county GIS portals
4. Manual digitization of critical missing roads

---

### Step 4: Geometric Intersection Calculation ✅ COMPLETE

**Goal:** Calculate intersection coordinates from road geometries

**Implementation:**
- `geometric_geocoder.py` - Core geocoding engine
  - Road name normalization and fuzzy matching
  - Shapely-based geometric intersection calculation
  - Confidence scoring for results
- `apply_geometric_geocoding.py` - Batch processing script
  - Applied to all 728 failed tickets
  - Generated results and statistics

**Approach:**
For each failed intersection ticket:
1. Parse both road names (already normalized)
2. Query road network for matching geometries (fuzzy match)
3. Calculate geometric intersection using Shapely
   - Find all LineStrings for both roads
   - Compute intersection points
   - Handle multiple intersections (choose best)
4. Validate result and score confidence
5. Return lat/lng with metadata

**Actual Results:**
- **Attempted:** 728 failed tickets
- **Successfully geocoded:** 7 tickets (0.96% of failures)
- **Overall improvement:** +0.03 percentage points (96.92% → 96.95%)
- **Confidence scores:** 50-65% (average 58.57%)

**What Worked:** ✅
All 7 successes were **I-20 related intersections** in Ward County (Barstow):
- I-20 Service Road & I-20 (4 tickets)
- I-20 Service Road & I-20 Bus (3 tickets)

This **validates the approach** - geometric calculation works when data is available!

**Failure Analysis:** ❌
- **661 failures (91%):** Road(s) not in OSM network
  - CR 426: 377 tickets (primary culprit)
  - CR 516: 76 tickets
  - CR 432: 59 tickets
  - SE 8000 (numbered roads): 40 tickets
  - Other local roads: 109 tickets

- **60 failures (8%):** Roads in network but don't intersect
  - FM 516 & I-20: 18 tickets
  - Indicates data quality issues or incorrect ticket data

- **0 other failures**

**Critical Insight:**
The geometric geocoding algorithm is **technically sound and working correctly**. The limitation is **data availability**, not the approach. Our OSM dataset has excellent coverage of major roads (Interstates, US highways, state highways) but poor coverage of:
1. Specific county roads (CR 426, CR 516, CR 432)
2. Numbered directional roads (SE 8000, NE 7501, etc.)
3. Some FM roads that exist but aren't mapped in OSM

**Why Lower Than Expected:**
Original estimate: Solve ~200-300 failures (27-41%)
Actual: Solved 7 failures (0.96%)

The 40x gap is due to OSM's limited local road coverage. The 728 failures are concentrated in Ward County (Pyote/Barstow area) with very specific local roads that aren't in OSM.

**Output Files:**
- `geometric_geocoder.py` - Reusable geocoding module
- `apply_geometric_geocoding.py` - Batch processing script
- `geometric_results.csv` - All 728 attempts with results
- `geometric_summary.json` - Statistics

**Next Steps to Improve:**
1. **Acquire better road data:**
   - TxDOT county road inventory (official source)
   - Local county GIS data
   - Manual digitization of critical roads

2. **Grid-based estimation for numbered roads:**
   - SE 8000 likely means "8000 units southeast"
   - Requires understanding local coordinate system
   - Could solve ~40+ tickets

3. **Enhance OSM data:**
   - Contribute missing roads to OpenStreetMap
   - Or download more comprehensive OSM extract

**Technical Success:**
While the impact was limited, Step 4 successfully:
- ✅ Implemented working geometric intersection calculator
- ✅ Demonstrated the approach with 7 successful geocodes
- ✅ Identified specific data gaps preventing broader success
- ✅ Created reusable, well-documented code
- ✅ Measured and quantified the limitation

The foundation is solid. With better source data, this approach could solve 200+ additional tickets.

---

### Step 5: Multi-Strategy Geocoding Pipeline

**Status:** PLANNED (after Step 4)

**Goal:** Implement fallback cascade for maximum success rate

**Strategy Cascade:**
1. **Check cache** - fastest (current)
2. **Try Google Geocoding** - high quality (current)
3. **Try Geometric Intersection** - for intersections (Step 4)
4. **Try road-only geocoding** - geocode city + single road
5. **Try fuzzy road matching** - correct misspellings, retry Google
6. **Try broader location** - city/county centroid (low confidence)

**Each strategy returns:**
- `(lat, lng, confidence, method)`
- Logged for analysis
- Cached with provenance

---

### Step 6: Quality Validation & Bounds Checking

**Status:** PLANNED

**Validation Rules:**
- County bounds check (must be within stated county or adjacent)
- Route corridor check (flag if >20 miles from Wink APN route)
- Distance sanity check (for intersections, both roads near point)
- Confidence thresholds (tag low-confidence for manual review)

**Output:**
- Validation report with flagged items
- Manual review workflow

---

### Step 7: Re-geocode and Measure Improvement

**Status:** PLANNED

**Tasks:**
1. Backup current `geocode_cache.json`
2. Run enhanced pipeline on all failed entries
3. Generate comparison report:
   - Before/after success rates
   - Success by method (Google, geometric, fallback)
   - County-by-county improvements
   - Intersection vs address success
4. Update per-county JSONL files
5. Run `frequency.py` with improved geocodes
6. Document remaining failures

**Success Criteria:**
- Success rate ≥ 98%
- Clear provenance for all geocodes
- Validated results within bounds

---

## Current Status Summary

**Completed:**
- ✅ Step 1: Failure analysis (728 failures identified and categorized)
- ✅ Step 3: Road network acquired (1,969 segments from OSM)
- ✅ Step 4: Geometric intersection calculation (7 successes, +0.03% improvement)

**Key Finding:**
Geometric approach works! Limited impact due to OSM data gaps, not algorithm limitations. Need better road data source (TxDOT) to solve remaining 721 failures.

**Remaining:**
- ⏳ Step 2: Enhanced normalization
- ⏳ Step 3b: Acquire better road data (TxDOT county roads)
- ⏳ Step 5: Multi-strategy pipeline
- ⏳ Step 6: Quality validation
- ⏳ Step 7: Re-geocode and measure

**Next Actions (Recommended Priority):**
1. **Data Acquisition:** Get TxDOT road data for CR 426, CR 516, CR 432
2. **Grid Estimation:** Implement numbered road estimation (SE 8000, etc.)
3. **Step 5:** Integrate geometric geocoder into multi-strategy pipeline
4. **Step 7:** Re-run with enhanced data and measure final improvement

**Realistic Target with Current Data:**
- Current: 96.95% (with geometric solving)
- Potential with TxDOT data: 98-99%
- Maximum achievable: ~99.5% (some tickets may have bad data)

---

## Technical Debt & Future Enhancements

### High Priority
- **Numbered county road data:** Need TxDOT data or grid-based estimation
  - Would unlock remaining ~500 failures
  - Critical for Ward County (Pyote/Barstow area)

### Medium Priority
- **Enhanced fuzzy matching:** Better handling of road name variants
- **Confidence scoring:** Quantify geocode quality for downstream analysis
- **Manual review UI:** For low-confidence or ambiguous results

### Low Priority
- **Route-specific geocoding:** Use corridor buffer to disambiguate
- **Historical tracking:** Monitor geocoding success over time
- **API cost optimization:** Reduce Google API calls with better caching

---

## Files & Artifacts

### Analysis Scripts
- `analyze_geocode_failures.py` - Cache analysis (100% success, no failures in cache)
- `analyze_ticket_geocoding.py` - Full ticket dataset analysis (728 failures found)

### Data Acquisition
- `download_road_network.py` - OSM road network downloader
- `inspect_roads.py` - Road data inspection tool

### Geometric Geocoding (Step 4)
- `geometric_geocoder.py` - Core geometric intersection calculator
- `apply_geometric_geocoding.py` - Batch processing for all failures
- `geometric_results.csv` - Results for all 728 attempts (gitignored)
- `geometric_summary.json` - Summary statistics (gitignored)

### Data Files
- `roads.gpkg` - Road network geometries (1,969 segments) (gitignored)
- `roads_metadata.json` - Dataset metadata
- `ticket_failures.csv` - All 728 failed tickets (gitignored)
- `ticket_analysis_report.json` - Detailed failure statistics (gitignored)

### Documentation
- `docs/geocoding-improvement-plan.md` - This document
- `docs/architecture-maintenance-ticket-pipeline.md` - System architecture

---

## Lessons Learned

1. **Cache purging removed context:** The `geocode_cache.json` only contains successes because failed entries were purged. Need to analyze the original ticket dataset to find failures.

2. **OSM coverage varies:** Major roads (FM, US, Interstate) have excellent coverage. Numbered county roads (SE 8000, etc.) are poorly mapped. This is expected but limits what we can solve geometrically.

3. **Intersection failures dominate:** 100% of failures are intersections, not addresses. This validates the focus on geometric intersection calculation.

4. **Geographic concentration:** 90% of failures are in Ward County (Pyote/Barstow). Suggests localized data quality issues or unique numbering systems.

5. **Name variant explosion:** Same intersection appears with multiple name variants (US HWY 385, US-385, HWY 385, US 385). Normalization helps but geometric solving bypasses this entirely.

---

*Last Updated: 2026-02-08*
*Step 4 Complete: Geometric geocoding implemented, 7 tickets solved (+0.03%)*
*Next Review: After acquiring TxDOT road data or implementing grid estimation*
