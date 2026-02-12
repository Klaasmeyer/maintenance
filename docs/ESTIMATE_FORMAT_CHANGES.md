# Maintenance Estimate Generator - Format Changes

This document summarizes the changes made to match the reference Excel layout exactly.

## Date
February 11, 2026

## Reference File
`Estimate_ Floydada Operations and Maintenance.xlsx`

## Changes Made

### 1. Quote Sheet (`_write_quote_sheet`)

**Column Changes:**
- Added Column F: "Leg % of Route"
- Updated column widths to match reference:
  - A: 26.71 (was 16.57)
  - B: 20.43 (was 20.57)
  - F: 14.43 (new)
  - G: 8.86 (new)

**Formula Changes:**
- Length formulas now reference `'Leg Details'!B{row}` instead of `'Maintenance Estimate'!C{row}`
- NRC formula changed to: `=Inputs!$B$12*Quote!$F{row}`
- MRC formula changed to: `='Maintenance Estimate'!$D${total_cost_row}/12*Quote!$F{row}`
- Added Leg % formula: `=Quote!$B{row}/$B$6`

**New Summary Rows:**
- Row 11: "Total Cost Right of Use 20 Year Lease"
  - Formula: `=Quote!$D$6+'Maintenance Estimate'!D{total_cost_lease_row}`
- Row 12: "TCO Percentage of Installation Cost"
  - Formula: `=E11/Inputs!B10`

**Row Height:**
- Rows 1-7 set to 22.5 (was only 1-6)

### 2. Inputs Sheet (`_write_inputs_sheet`)

**Column Changes:**
- Added Column D: "Referenced From"
- Added Column E: "Source"
- Updated column widths to match reference:
  - A: 39.57 (was 26.83)
  - B: 16.43 (was 10.66)
  - D: 24.86 (new)
  - E: 33.14 (new)
  - F: 8.86 (new)

**Structure Changes:**
- Removed "MAINTENANCE ESTIMATE INPUTS" header row
- Headers now start at Row 1 (not Row 2)
- Reordered parameters to match reference

**Parameter Changes:**
- Removed: "Total Route Length (Miles)", "Total Annual Tickets", "Average (Tickets/Mile/Year)"
- Changed Row 7: "Margin" format from 0.01 to 0.01 (value remains 1%)
- Added Row 11: "Per Mile Up-front Payment (Percentage)" = 0.05 (5%)
- Added Row 12: "Up-Front Payment" = `=B10*B11`
- Updated descriptions to match reference wording

### 3. Maintenance Estimate Sheet (`_write_summary_sheet`)

**Header Changes:**
- Row 4: Changed from "SUMMARY STATISTICS" to "Statistics"
- Added Column B header: "Counts"
- Added Column C header: "Description"

**Structure Changes:**
- Route Leg section header changed from "TICKETS PER ROUTE LEG" to just "Route Leg" (bold)
- Added blank row at Row 10 in statistics section

**New NOC Section (Rows 21-23):**
- Row 21: Headers "Item", "Cost", "Type" (all bold)
- Row 22: "NOC Up-Front" = `=120*150`, "Non-recurring"
- Row 23: "Monthly NOC Cost" = 3000.00, "Monthly recurring"

**Pricing Table Changes:**
- NOC Monitoring Cost formula changed to: `=B{noc_monthly_row}*12`
- Insurance formula changed to reference: `=Inputs!B10*Inputs!B9` (was B16*B15)
- Individual margins now hardcoded per line item:
  - NOC: 15% (0.15)
  - Insurance: 50% (0.50)
  - Maintenance: 40% (0.40)
- Margin column header changed from "Margin" to "Margin"
- Total row Column C changed from "Total Price" to "Total Price (Annual)"

**New Summary Rows:**
- Row after Total: "Total Cost of Lease (TCL)"
  - Formula: `=20*D{total_row}`
- Row after TCL: "TCL as a Percentage of Build Cost"
  - Formula: `=D{total_cost_lease_row}/Inputs!B10`
  - Format: 0.0%

**Column Widths:**
- A: 33.57 (was 29.7)
- B: 20.14 (was 11.2)
- C: 38.14 (was 43.0)
- D: 19.43 (was 11.0)
- E: 8.86 (new)

### 4. Method Signature Updates

**`_write_quote_sheet`:**
- Added parameter: `total_cost_lease_row: int`
- Updated to accept 6 parameters total

**`_write_summary_sheet`:**
- Return dictionary now includes: `'total_cost_lease_row'`

**`generate_estimate`:**
- Updated to pass `total_cost_lease_row` to `_write_quote_sheet`
- Quote sheet now written after Leg Details sheet (for reference integrity)

## Testing

To test the changes:

```bash
# Navigate to project root
cd /Users/corey/ck/projects/kcci/maintenance

# Run the regenerate script
./venv/bin/python src/tools/estimates/regenerate_estimates.py
```

Or for just Floydada:

```bash
# Use the test script
./venv/bin/python test_new_format.py
```

## Files Modified

- `src/kcci_maintenance/utils/maintenance_estimate.py`
  - `_write_quote_sheet()` method
  - `_write_inputs_sheet()` method
  - `_write_summary_sheet()` method
  - `generate_estimate()` method

## Backward Compatibility

These changes maintain the same core functionality but update the Excel output format. The generated estimates will now exactly match the reference layout provided.

## Verification

Run syntax check:
```bash
./venv/bin/python -m py_compile src/kcci_maintenance/utils/maintenance_estimate.py
```

Compare output with reference file after generation.
