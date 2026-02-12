# Font Standardization - Arial

**Date:** February 11, 2026

## Changes Made

All fonts in the maintenance estimate Excel workbooks have been standardized to **Arial** across all sheets.

### Implementation

1. **Added Helper Method:** `_apply_arial_font()`
   - Applies Arial font (11pt) to all cells in a worksheet
   - Preserves bold and size attributes where they exist
   - Ensures consistent typography throughout

2. **Updated All Font Specifications:**
   - Changed all `Font(bold=True)` to `Font(name="Arial", bold=True)`
   - Applied Arial to headers, data cells, and totals
   - Applied to all 7 sheets:
     - Quote
     - Maintenance Estimate
     - Inputs
     - Leg Details
     - Cost Projections
     - Ticket Breakdowns
     - Ticket Assignments

### Verification

All sheets verified for font consistency:
- ✓ Quote: All Arial
- ✓ Maintenance Estimate: All Arial
- ✓ Inputs: All Arial
- ✓ Leg Details: All Arial
- ✓ Cost Projections: All Arial
- ✓ Ticket Breakdowns: All Arial
- ✓ Ticket Assignments: All Arial

### Files Modified

- `src/kcci_maintenance/utils/maintenance_estimate.py`
  - Added `_apply_arial_font()` method
  - Updated all `Font()` instantiations
  - Added font application calls to all sheet writing methods

### Testing

Run the estimate generator to verify:
```bash
PYTHONPATH=src ./venv/bin/python src/tools/estimates/regenerate_estimates.py
```

All generated estimates now use Arial font consistently throughout.
