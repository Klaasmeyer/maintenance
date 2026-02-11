# Quote Sheet Feature - Implementation Summary

## Overview

Added a new "Quote" sheet to the maintenance estimate workbooks, providing a high-level pricing summary suitable for customer-facing quotes.

**Generated:** 2026-02-10
**Files Updated:**
- `geocoding_pipeline/utils/maintenance_estimate.py`
- All newly generated maintenance estimates

---

## Quote Sheet Structure

### Layout

The Quote sheet is positioned as the **first sheet** in the workbook (before Inputs and Maintenance Estimate), making it the default view when opening the file.

### Columns

| Column | Header | Description | Format |
|--------|--------|-------------|--------|
| A | Leg | Route leg name | Text |
| B | Length (miles) | Leg length in miles | Formula (references Maintenance Estimate) |
| C | Est. Distance (km) | Length converted to kilometers | Formula: `=B*1.60934` |
| D | Non-Recurring Charges (O&M NRC) | One-time setup costs | Currency `"$"#,##0.00` |
| E | Monthly O&M Fee (MRC) | Monthly maintenance cost | Formula (proportional to leg length) |

### Column Widths
- A (Leg): 16.57
- B (Length): 20.57
- C (Est. Distance): 28.14
- D (NRC): 43.0
- E (MRC): 34.43

### Row Heights
- All data rows: 22.5 points

---

## Formulas

### Length References
Each leg's length is dynamically referenced from the Maintenance Estimate sheet:

```excel
='Maintenance Estimate'!C{row}
```

Where `{row}` is the actual row number of that leg in the Maintenance Estimate sheet.

### Kilometer Conversion
```excel
=B2*1.60934
```

### Monthly O&M Fee (MRC)
Calculated as proportional share of total annual O&M cost:

```excel
='Maintenance Estimate'!$D${total_row}/12*(B{row}/$B${total_row})
```

Where:
- `$D${total_row}` = Total Annual O&M Cost from Maintenance Estimate
- `B{row}` = This leg's length
- `$B${total_row}` = Sum of all leg lengths
- `/12` = Convert annual to monthly cost

### Total Row Formulas
```excel
B{total}: =SUM(B2:B{last_data_row})
C{total}: =SUM(C2:C{last_data_row})
D{total}: $110,000.00  (placeholder - manually updated)
E{total}: =SUM(E2:E{last_data_row})
```

---

## Summary Calculations

Below the main table, additional metrics are calculated:

| Row | Label (Column D) | Formula (Column E) | Format |
|-----|------------------|-------------------|--------|
| +2 | Cost Per Foot/Month | `=E{total}/B{total}` | Currency |
| +3 | Cost Per Kilometer/Month | `=E{total}/C{total}` | Currency |
| +4 | Annual Cost | `=12*E{total}` | Currency (bold) |

---

## Excel Table

The Quote sheet includes an Excel Table with:
- **Name:** Project name with underscores (e.g., `Wink_APN`, `Floydada___Klaasmeyer`)
- **Range:** `A1:E{total_row}`
- **Style:** `Quote-style` (falls back to `TableStyleMedium2`)
- **Features:** Row striping enabled, first/last column highlighting disabled

---

## Example: Wink APN Quote Sheet

```
| Leg                           | Length (miles) | Est. Distance (km) | NRC          | MRC        |
|-------------------------------|----------------|--------------------|--------------|-----------|
| Andrews Build                 | 68.71          | 110.58             | $0.00        | $10,586.17 |
| Monahans Build                | 16.89          | 27.18              | $0.00        | $2,602.25  |
| Pyote Build                   | 23.93          | 38.52              | $0.00        | $3,686.26  |
| Pyote Build (Easement Option) | 15.58          | 25.08              | $0.00        | $2,401.06  |
| Total                         | 125.11         | 201.33             | $110,000.00  | $19,275.73 |

Summary:
Cost Per Foot/Month:        $154.08
Cost Per Kilometer/Month:   $95.74
Annual Cost:                $231,308.76
```

---

## Implementation Details

### Method: `_write_quote_sheet()`

**Location:** `geocoding_pipeline/utils/maintenance_estimate.py`

**Parameters:**
- `writer`: Excel writer instance
- `leg_details_df`: DataFrame with leg statistics
- `leg_row_mapping`: Dict mapping leg names to Maintenance Estimate row numbers
- `total_cost_row`: Row number of "Total Annual O&M Cost" in Maintenance Estimate
- `project_name`: Used for table naming

**Flow:**
1. Create sheet as first sheet (index 0)
2. Set column widths and row heights
3. Write headers
4. For each route leg (excluding "Unassigned"):
   - Write leg name
   - Add formula referencing Maintenance Estimate length
   - Calculate km conversion
   - Add placeholder NRC ($0.00)
5. After all data rows, add MRC formulas (requires knowing total row)
6. Add total row with SUM formulas
7. Create Excel Table
8. Add summary calculations below table

### Integration with `generate_estimate()`

**Execution Order:**
1. Write **Maintenance Estimate** sheet first (to establish row mappings)
2. Extract `leg_row_mapping` and `total_cost_row` from Maintenance Estimate
3. Write **Quote** sheet using those references
4. Write remaining sheets (Inputs, Leg Details, etc.)

**Code:**
```python
# First write Maintenance Estimate to get the row mappings
sheet_refs = self._write_summary_sheet(writer, summary_df, leg_details_df, project_name)

# Now write Quote sheet using the references
self._write_quote_sheet(
    writer,
    leg_details_df,
    sheet_refs['leg_row_mapping'],
    sheet_refs['total_cost_row'],
    project_name
)
```

---

## Key Features

### ✅ Dynamic References
- All leg lengths reference the Maintenance Estimate sheet
- Changes to the Maintenance Estimate automatically update the Quote sheet
- No hardcoded values (except placeholder NRC)

### ✅ Proportional Cost Allocation
- Monthly O&M fees are automatically distributed based on leg length
- Longer legs receive proportionally higher monthly fees
- Total MRC always sums to Total Annual O&M Cost / 12

### ✅ Professional Formatting
- Excel Table with built-in filtering and sorting
- Currency formatting throughout
- Bold totals row
- Consistent column widths and row heights

### ✅ Customer-Friendly
- Simple, clean layout suitable for quotes
- Metric conversions (miles ↔ kilometers)
- Monthly costs instead of annual (easier to understand)
- Summary metrics for quick analysis

---

## Placeholder Values

### Non-Recurring Charges (NRC)
- **Current:** $0.00 for all legs
- **Update:** Manually enter actual NRC values per leg
- **Total NRC:** Currently set to $110,000.00 (placeholder)

These placeholders allow the template to be customized for specific quotes while maintaining all formula relationships.

---

## Usage in Quotes

1. **Open the estimate file** - Quote sheet appears first
2. **Verify leg lengths** - Auto-calculated from route KMZ
3. **Update NRC values** - Enter actual one-time costs per leg
4. **Update Total NRC** - Enter total non-recurring charges
5. **Review MRC calculations** - Auto-calculated based on annual O&M cost
6. **Check summary metrics** - Cost per foot/km, annual cost
7. **Export or share** - Quote sheet ready for customer presentation

---

## Files Generated

All new maintenance estimates include the Quote sheet:

```
projects/wink/outputs/
├── 2026-02-10-wink-maintenance-estimate-annualized.xlsx  ← Includes Quote sheet

projects/floydada/outputs/
├── 2026-02-10-floydada-maintenance-estimate-annualized.xlsx  ← Includes Quote sheet
```

---

## Testing

Verified on:
- ✅ Wink APN (4 route legs)
- ✅ Floydada (4 route legs)

Tests confirmed:
- ✅ Quote sheet created as first sheet
- ✅ Excel Table with correct name and range
- ✅ All formulas reference correct cells
- ✅ Length formulas pull from Maintenance Estimate
- ✅ MRC formulas calculate proportional costs
- ✅ Summary calculations work correctly
- ✅ Formatting applied (currency, bold totals)

---

**Status:** ✅ Complete
**Next Steps:**
- Manually update NRC values for actual quotes
- Consider adding conditional formatting for highlighting
- Optional: Add chart visualizations of cost distribution
