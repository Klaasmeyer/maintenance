# Annualization Fix Summary

## Problem Identified

Multi-year ticket datasets were being treated as single-year data, resulting in significantly overestimated annual ticket counts and maintenance costs.

**Example:** Floydada project has 788 excavation tickets across 4 years (2022-2025), but was showing as 788 annual tickets instead of 197 annual tickets.

---

## Root Cause

The maintenance estimate generator was reading geocoded results CSVs which contain:
- `created_at` column: Timestamp when geocoding was performed (e.g., 2026-02-10)
- **Missing:** `Creation` column: Original ticket creation date (e.g., 2022-03-15)

This caused the time span detection to see all tickets as created on the geocoding date, resulting in "2026-2026 (1.0 years)" instead of the correct "2022-2025 (4.0 years)".

---

## Solution Implemented

### 1. Enhanced Data Merging
**File:** `generate_estimates_merged.py`

**Changes:**
- Modified merge logic to include `Creation`/`creation` date column from original ticket files
- Added automatic column name standardization (`Creation` → `creation`)
- Updated paths to use latest geocoded results

```python
# Now merges date columns along with other ticket metadata
merge_columns = ['ticket_number', 'duration', 'work_type', 'excavator', 'creation', 'Creation']
```

### 2. Timezone-Aware Date Parsing
**File:** `geocoding_pipeline/utils/maintenance_estimate.py`

**Method:** `_calculate_time_span_years()`

**Changes:**
- Added `utc=True` parameter to handle mixed timezone data
- Prevents "Mixed timezones detected" errors

```python
# Before: dates = pd.to_datetime(tickets_df[date_col], errors='coerce')
# After:  dates = pd.to_datetime(tickets_df[date_col], errors='coerce', utc=True)
```

### 3. Fixed Double Annualization Bug
**File:** `geocoding_pipeline/utils/maintenance_estimate.py`

**Method:** `_write_inputs_sheet()`

**Issue:** Ticket counts were being annualized twice:
1. First in `_generate_leg_details()`: `total_tickets = round(total_tickets_dataset / years_span)`
2. Then again in `_write_inputs_sheet()`: `annual_tickets_assigned = round(total_tickets_assigned / years_span)`

**Fix:** Removed second division since `leg_details_df['Total Tickets']` already contains annualized values

```python
# Before: annual_tickets_assigned = round(total_tickets_assigned / years_span)
# After:  annual_tickets_assigned = round(total_tickets_assigned)
```

### 4. Annualized Emergency/Normal Ticket Counts
**File:** `geocoding_pipeline/utils/maintenance_estimate.py`

**Method:** `_generate_leg_details()`

**Changes:**
- Emergency and Normal ticket counts now properly annualized
- Ensures Total = Emergency + Normal (within rounding tolerance)

```python
emergency_tickets_dataset = len(group[group['ticket_type'] == 'Emergency'])
normal_tickets_dataset = len(group[group['ticket_type'] != 'Emergency'])
emergency_tickets = round(emergency_tickets_dataset / years_span)
normal_tickets = round(normal_tickets_dataset / years_span)
```

---

## Results

### Floydada Project
**Before Fix:**
- Detected time span: "2026-2026 (1.0 years)" ❌
- Total Annual Tickets: 788 (4x overestimate) ❌

**After Fix:**
- Detected time span: "2022-2025 (4.0 years)" ✓
- Total Annual Tickets: 197 (correctly annualized) ✓
- Emergency + Normal counts match Total ✓

**Breakdown by Leg:**
- Floydada Eastern Lateral: 4 annual tickets
- Floydada Northern Lateral: 1 annual ticket
- Floydada Western Lateral: 1 annual ticket
- Floydada to Esteline: 191 annual tickets

### Wink Project
**Before Fix:**
- Detected time span: "2025-2025 (1.0 years)" ✓ (already correct)
- Total Annual Tickets: 1,293 ✓

**After Fix:**
- No change needed (data already spans only 1 year)
- Total Annual Tickets: 1,293 ✓

---

## Generated Files

### Annualized Estimates
```
projects/floydada/outputs/2026-02-10-floydada-maintenance-estimate-annualized.xlsx
projects/wink/outputs/2026-02-10-wink-maintenance-estimate-annualized.xlsx
```

These files contain:
- ✅ Correctly annualized ticket counts
- ✅ Proper time span detection from original ticket dates
- ✅ Emergency/Normal breakdowns that sum to Total
- ✅ All formulas and formatting from previous template updates

---

## Verification

To regenerate annualized estimates in the future:

```bash
source venv/bin/activate
python3 generate_estimates_merged.py
```

This script:
1. Loads geocoded results from the pipeline
2. Merges with original ticket data (preserving Creation dates)
3. Detects multi-year time spans automatically
4. Generates properly annualized maintenance estimates

---

## Technical Notes

### Date Column Priority
The `_calculate_time_span_years()` method searches for date columns in this order:
1. `Creation` (original ticket creation date - preferred)
2. `creation` (normalized column name)
3. `created_at` (geocoding timestamp - fallback)
4. `date`, `Date` (generic fallbacks)

### Annualization Formula
```python
annual_tickets = total_tickets_in_dataset / years_span
years_span = (max_date - min_date).days / 365.25
```

### Rounding Tolerance
Emergency + Normal may differ from Total by ±1 ticket due to independent rounding.
This is acceptable and reflects the mathematical reality of rounding fractional annual counts.

---

**Status:** ✅ Complete
**Date:** 2026-02-10
**Impact:** Maintenance cost estimates now accurately reflect annual rates instead of multi-year totals
