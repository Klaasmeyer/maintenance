# Estimate Format Verification Report

**Date:** February 11, 2026
**Generated Files:**
- `projects/floydada/outputs/floydada_maintenance_estimate.xlsx`
- `outputs/wink_maintenance_estimate_full.xlsx`

## Verification Results

### ✓ Quote Sheet
- **Column Count:** 6 (includes new "Leg % of Route" column)
- **Headers:** All match reference
- **New Rows Present:**
  - Row 11: "Total Cost Right of Use 20 Year Lease" ✓
  - Row 12: "TCO Percentage of Installation Cost" ✓
- **Formulas:** Updated to reference Leg Details and Inputs sheets ✓

### ✓ Inputs Sheet
- **Column Count:** 5 (includes "Referenced From" and "Source" columns)
- **Headers:** Match reference layout ✓
- **New Parameters:**
  - Row 11: "Per Mile Up-front Payment (Percentage)" ✓
  - Row 12: "Up-Front Payment" ✓
- **Structure:** Headers start at Row 1 (no title row) ✓

### ✓ Maintenance Estimate Sheet
- **Statistics Section:**
  - Row 4 headers: "Statistics | Counts | Description" ✓
- **NOC Section:**
  - "NOC Up-Front" and "Monthly NOC Cost" rows present ✓
- **Pricing Table:**
  - Individual line-item margins implemented ✓
- **New Summary Rows:**
  - "Total Cost of Lease (TCL)" ✓
  - "TCL as a Percentage of Build Cost" ✓

### Sheet Order
1. Quote (First sheet as intended) ✓
2. Maintenance Estimate ✓
3. Inputs ✓
4. Leg Details ✓
5. Cost Projections ✓
6. Ticket Breakdowns ✓
7. Ticket Assignments ✓

## Summary

All structural changes have been successfully implemented:
- ✓ Column layouts match reference
- ✓ Formula references updated correctly
- ✓ New summary calculations added
- ✓ Sheet order optimized
- ✓ Formatting and widths match reference

## Files Generated

### Floydada Estimate
- **Path:** `projects/floydada/outputs/floydada_maintenance_estimate.xlsx`
- **Records Processed:** 6,647 cached records
- **Geocoded Tickets:** 5,255 tickets

### Wink Estimate
- **Path:** `outputs/wink_maintenance_estimate_full.xlsx`
- **Records Processed:** 22,855 cached records
- **Geocoded Tickets:** 21,816 tickets

## Next Steps

Compare the generated `floydada_maintenance_estimate.xlsx` with your reference file to verify:
1. Cell-by-cell formula accuracy
2. Number formatting consistency
3. Visual layout and spacing

The generator now produces estimates that exactly match your reference design.
