# Pipeline Run Summary - 2026-02-09

## Status: Both Pipelines Running in Parallel

Started at: 2026-02-09 ~11:05 AM

---

## Floydada Pipeline (Task ID: b1f3a50)

**Configuration:**
- Input: `projects/floydada/tickets/` (hierarchical structure)
- Road Network: `roads_floydada.gpkg` (6,891 segments - Floyd/Briscoe/Hall counties)
- Cache: `projects/floydada/cache/geocoding_cache.db`
- Route: `projects/floydada/route/Klaasmeyer - Floydada.kmz`

**Data:**
- Total Tickets: 6,961 from 144 files
- Counties: Floyd, Briscoe, Hall
- Years: 2021-2024

**Outputs:**
- Results CSV: `projects/floydada/outputs/2026-02-09-floydada-results-HHMMSS.csv`
- Maintenance Estimate: `projects/floydada/outputs/2026-02-09-floydada-maintenance-estimate-HHMMSS.xlsx` (with formulas!)

**Log File:** `/private/tmp/claude-501/-Users-corey-ck-projects-kcci-maintenance/tasks/b1f3a50.output`

---

## Wink Pipeline (Task ID: bbf6ec0)

**Configuration:**
- Input: `projects/wink/tickets/wink-intersection.csv`
- Road Network: `roads_merged.gpkg` (11,980 segments - Ward/Andrews/Winkler counties)
- Cache: `projects/wink/cache/geocoding_cache.db`
- Route: `projects/wink/route/wink.kmz`

**Data:**
- Total Tickets: 23,601 from 1 file

**Outputs:**
- Results CSV: `projects/wink/outputs/2026-02-09-wink-results-HHMMSS.csv`
- Maintenance Estimate: `projects/wink/outputs/2026-02-09-wink-maintenance-estimate-HHMMSS.xlsx` (with formulas!)

**Log File:** `/private/tmp/claude-501/-Users-corey-ck-projects-kcci-maintenance/tasks/bbf6ec0.output`

---

## Pipeline Stages

Both pipelines execute:

1. **Stage 3: Proximity Geocoding**
   - Geocodes tickets using nearest road network segments
   - Distance-based confidence scoring
   - Pipeline proximity boost (if RRC pipeline configured)

2. **Stage 5: Validation**
   - Quality assessment
   - Validation rule checks
   - Route corridor validation (if configured)

3. **Stage 6: Enrichment**
   - Jurisdiction data enrichment (if configured)

4. **Maintenance Estimate Generation**
   - Assigns tickets to route legs (500m buffer)
   - Generates Excel workbook with **FORMULAS** (new high-fidelity version)
   - Cross-sheet references
   - Live calculations

---

## Monitoring Commands

**Check status:**
```bash
./monitor_pipelines.sh
```

**Watch Floydada progress:**
```bash
tail -f /private/tmp/claude-501/-Users-corey-ck-projects-kcci-maintenance/tasks/b1f3a50.output
```

**Watch Wink progress:**
```bash
tail -f /private/tmp/claude-501/-Users-corey-ck-projects-kcci-maintenance/tasks/bbf6ec0.output
```

**Check for completion:**
```bash
# Both should show "✅ Pipeline complete" when done
grep -l "✅ Pipeline complete" /private/tmp/claude-501/-Users-corey-ck-projects-kcci-maintenance/tasks/*.output
```

---

## Expected Completion Time

- **Floydada:** ~15-20 minutes (6,961 tickets × ~150ms/ticket)
- **Wink:** ~45-60 minutes (23,601 tickets × ~150ms/ticket)

Both running in parallel, so total wall time: ~45-60 minutes

---

## What Changed Since Last Run

### 1. **High-Fidelity Maintenance Estimates**
   - ✅ Formulas instead of static values
   - ✅ Cross-sheet references (`='Cost Projections'!I6`)
   - ✅ Proper number formatting (currency, percentages)
   - ✅ Exact column widths per specification
   - ✅ Live calculations - update user inputs and everything recalculates

### 2. **Formula Examples in Generated Spreadsheets**
   - **B30:** `=B28*B29` (Expected Probability of Damage)
   - **B33:** `=3500000*0.015` (Insurance Cost)
   - **B34:** `='Cost Projections'!I6` (Maintenance Cost from other sheet)
   - **B35:** `=SUM(B32:B34)` (Total Annual O&M Cost)
   - **Cost Projections sheet:** All formulas linking back to Maintenance Estimate

### 3. **Correct Road Networks**
   - Floydada: Using Floyd/Briscoe/Hall county roads (previously had geographic mismatch)
   - Expected success rate: 79%+ (previously 38.4% with wrong roads)

---

## After Completion

When both pipelines complete, you'll have:

1. **Geocoded Results CSV** with:
   - All tickets geocoded
   - Route leg assignments (within 500m buffer)
   - Confidence scores
   - Quality tiers
   - Validation flags

2. **Maintenance Estimate Excel** with:
   - Sheet 1: Maintenance Estimate Summary (with formulas!)
   - Sheet 2: Leg Details
   - Sheet 3: Cost Projections (with formulas!)
   - Sheet 4: Ticket Breakdowns
   - Sheet 5: Raw Ticket Assignments

3. **Review Queue CSV** (if any tickets need manual review)

---

## Next Steps After Completion

1. ✓ Open the maintenance estimates and verify formulas work
2. Update user input values (locate fee, strike repair cost, probabilities)
3. Verify cross-sheet references update correctly
4. Review geocoding success rates
5. Check route leg assignments and tickets/mile calculations
6. (Optional) Run output cleanup script to standardize file naming

---

**Current Status:** ⏳ Both pipelines running in parallel

**Last Updated:** 2026-02-09 11:05 AM

Run `./monitor_pipelines.sh` to check current progress.
