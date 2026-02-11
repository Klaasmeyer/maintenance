# Changelog

All notable changes to the KCCI Maintenance project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Major Reorganization (2026-02-10)

#### Added
- `.ai-workspace/` directory for AI-generated working files and session artifacts
- `docs/` reorganized with clear hierarchy (architecture, design, evolution, guides, specifications)
- `src/` layout following Python best practices
  - `src/kcci_maintenance/` - Main package (renamed from `geocoding_pipeline`)
  - `src/tools/` - Categorized utility scripts (data_acquisition, geocoding, analysis, maintenance, estimates)
  - `src/scripts/` - Application entry points
- `data/` directory for large data files (roads, cache, metadata)
- `config/` directory for centralized configuration
- Project output archiving with timestamped archives and "latest" symlinks
- Comprehensive documentation:
  - `docs/design/frequency-model.md` - Ticket frequency estimation model
  - `docs/architecture/stage-design.md` - 6-stage pipeline architecture
  - `docs/README.md` - Documentation index
- `CHANGELOG.md` - This file

#### Changed
- Reorganized all documentation by purpose instead of mixing in root directory
- Moved 24 Python scripts from root to categorized `src/tools/` subdirectories
- Moved large data files (1.2GB+ GPKG files) to `data/roads/`
- Moved cache files to `data/cache/`
- Renamed `geocoding_pipeline/` to `src/kcci_maintenance/` for proper package structure
- Project outputs now archived by date with symlinks to latest
- Configuration files centralized in `config/projects/`

#### Removed
- Root directory clutter (24 scripts, 14 markdown files, large data files)
- Inconsistent output file naming (old vs. new formats consolidated)
- Duplicate/test output files moved to `.ai-workspace/`

---

### Features (2026-02-10)

#### Quote Sheet Generation
- Added Quote sheet as first sheet in maintenance estimates
- Automatic calculation of Monthly O&M Fee (MRC) proportional to leg length
- Kilometer conversion for international compatibility
- Summary metrics (Cost Per Foot/Month, Cost Per Kilometer/Month, Annual Cost)
- Excel Table with professional formatting
- Dynamic formulas referencing Maintenance Estimate sheet

**Files:**
- `src/kcci_maintenance/utils/maintenance_estimate.py` - `_write_quote_sheet()` method
- See: `docs/design/quote-sheet-design.md`

#### Annualization of Multi-Year Ticket Data
- Automatic detection of data time span from ticket creation dates
- Conversion of multi-year ticket counts to annual rates
- Proper handling of multi-year datasets (e.g., 2022-2025 = 4 years)
- Timezone-aware date parsing to prevent errors
- Time span metadata included in output notes

**Impact:**
- Floydada: 788 tickets / 4 years = 197 annual tickets
- Wink: 1,293 tickets / 1 year = 1,293 annual tickets

**Files:**
- `src/kcci_maintenance/utils/maintenance_estimate.py` - `_calculate_time_span_years()`
- `src/tools/estimates/generate_estimates_merged.py` - Merges original ticket dates
- See: `docs/design/annualization-design.md`, `docs/design/frequency-model.md`

#### Excavation Ticket Filtering
- Classification of ticket types into excavation vs non-excavation
- Excludes Update, No Response, Cancellation, Recall, Survey/Design, Non-Compliant
- Focuses cost model on actual excavation risk
- Summary statistics show excavation breakdown

**Impact:**
- Wink: Excludes 44.5% of tickets (10,175 non-excavation)
- Floydada: Excludes ~17% of tickets

**Files:**
- `src/kcci_maintenance/utils/maintenance_estimate.py` - `_filter_excavation_tickets()`
- See: `docs/design/frequency-model.md`

#### Route Corridor Validation
- Out-of-corridor detection for geocoded tickets
- Configurable buffer distance (default: 500m)
- Validation flags in output
- Review queue generation for out-of-corridor tickets

**Files:**
- `src/kcci_maintenance/utils/route_corridor.py` - `RouteCorridorValidator`
- `src/kcci_maintenance/stages/stage_5_validation.py` - Integration
- `src/kcci_maintenance/core/validation_rules.py` - `OutOfCorridorRule`

---

### Fixes (2026-02-10)

#### Fixed Double Annualization Bug
**Issue:** Ticket counts were being divided by `years_span` twice - once in `_generate_leg_details()` and again in `_write_inputs_sheet()`.

**Impact:** Floydada showed 49 annual tickets instead of correct 197.

**Fix:** Removed second division since leg details already contain annualized counts.

**Files:** `src/kcci_maintenance/utils/maintenance_estimate.py`

#### Fixed Percentage Storage Format
**Issue:** Percentages stored as text strings ("5.3%") instead of numeric values with formatting.

**Impact:** Excel reported "number stored as text" warnings.

**Fix:** Changed to store numeric values (0.053) with `'0.0%'` number format.

**Affected Fields:**
- Emergency % in Leg Details
- Avg Confidence in Leg Details
- Assignment Rate in Summary
- Percentage column in Breakdowns

**Files:** `src/kcci_maintenance/utils/maintenance_estimate.py`

#### Fixed Timezone Handling in Date Parsing
**Issue:** "Mixed timezones detected" error when calculating time spans.

**Fix:** Added `utc=True` parameter to `pd.to_datetime()` to normalize all dates to UTC.

**Files:** `src/kcci_maintenance/utils/maintenance_estimate.py` - `_calculate_time_span_years()`

---

## [Phase 1] - 2026-02-09

### Added
- Initial 6-stage geocoding pipeline implementation
- Stage 1: API Geocoding (Google Maps)
- Stage 2: Geometric Geocoding (local road network)
- Stage 3: Proximity Geocoding (fuzzy matching)
- Stage 4: Fallback Geocoding
- Stage 5: Validation
- Stage 6: Enrichment (jurisdiction/permitting)
- Intelligent caching system
- Quality tier assessment (GOLD, SILVER, BRONZE, FAILED)
- Pipeline proximity confidence boost
- Review queue generation
- Maintenance estimate generation with Excel formulas
- Project-based directory structure (Floydada, Wink)

### Pipeline Results
- **Floydada:** 79.1% success rate (5,255 / 6,647 tickets)
- **Wink:** 74.7% success rate (17,080 / 22,855 tickets)
- Performance: ~130ms per ticket average

---

## Project Statistics

### Code Organization
- **Source Code:** `src/kcci_maintenance/` (main package)
- **Tools:** 24 utility scripts organized in `src/tools/`
- **Documentation:** 15+ markdown files in `docs/`
- **Tests:** Unit and integration tests in `tests/`

### Data Processing
- **Projects:** 2 (Floydada, Wink)
- **Total Tickets Processed:** 29,502 (6,647 + 22,855)
- **Success Rate:** ~76% average
- **Road Network:** 1.2GB Texas road data + project-specific networks

### Generated Outputs
- Geocoded results CSV (with lat/lng, confidence, quality tier)
- Maintenance estimates Excel (with Quote sheet, formulas, projections)
- Review queues for manual inspection
- Annualized cost projections

---

## Links

- [Project README](README.md)
- [Documentation Index](docs/README.md)
- [Frequency Model](docs/design/frequency-model.md)
- [Pipeline Architecture](docs/architecture/pipeline-architecture.md)
- [Stage Design](docs/architecture/stage-design.md)
