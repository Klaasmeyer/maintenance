# Maintenance Estimate Spreadsheet Template Specification

## Based on User-Modified Floydada Spreadsheet

This document specifies the exact structure, formulas, and formatting for the maintenance estimate Excel output.

---

## Sheet 1: Maintenance Estimate (Summary)

### Structure

**Dimensions**: 37 rows x 4 columns (A-D)

**Column Widths**:
- Column A: 29.7
- Column B: 11.2
- Column C: 43.0
- Column D: 11.0

### Content Layout

```
Row 1:  [Project Name] - O&M Maintenance Estimate
Row 2:  Generated: [timestamp]
Row 3:  [blank]
Row 4:  SUMMARY STATISTICS
Row 5:  Total Tickets | [value] | All geocoded tickets
Row 6:  Assigned to Route Legs | [value] | Within 500m of route legs
Row 7:  Unassigned (>500m from route) | [value] | Outside buffer zone
Row 8:  Assignment Rate | [%] | Percentage of tickets assigned to legs
Row 9:  [blank]
Row 10: [blank]
Row 11: TICKETS PER ROUTE LEG
Row 12: Route Leg | Total Tickets | Leg Length (Miles) | Tickets/Mile
Row 13-16: [Data rows for each route leg]
Row 17: [blank]
Row 18: [blank]
Row 19: MAINTENANCE ESTIMATE INPUTS
Row 20: Input Parameter | Value | Source/Notes
Row 21: Total Route Length (Miles) | [calculated] | Calculated from KMZ route legs
Row 22: Total Annual Tickets | [calculated] | Based on geocoded ticket data
Row 23: Average (Tickets/Mile/Year) | [calculated] | Calculated average across all legs
Row 24: Buffer Distance (Meters) | 500 | Ticket assignment threshold
Row 25: [blank]
Row 26: Locate Fee Per Ticket | [USER INPUT] | [blank or note]
Row 27: Average Cost Per Strike Repair | [USER INPUT] | [source note]
Row 28: Probability of Damage | [USER INPUT] | This is a national average per ticket
Row 29: Probability of Damage Telcom | [USER INPUT] | Of those that result in damage, half are telecom strikes
Row 30: Expected Probability of Damage | =B28*B29 | Probability given the two statistics above
Row 31: [blank]
Row 32: NOC Monitoring Cost | [USER INPUT] | [blank or note]
Row 33: Insurance Cost | =3500000*0.015 | [calculation note]
Row 34: Maintenance Cost | ='Cost Projections'!I6 | [reference note]
Row 35: Total Annual O&M Cost | =SUM(B32:B34) | [blank]
Row 36: [blank]
Row 37: [blank]
```

### Cell Formatting

**Bold cells**:
- A1, A4, A11, A19, A20, B20, C20

**Number Formats**:
- B8: Percentage (0.0%)
- B26: Currency ("$"#,##0.00)
- B27: Currency ("$"#,##0.00)
- B28: Percentage (0.00%)
- B29: Percentage (0%)
- B30: Percentage (0.00%)
- B32: Currency ("$"#,##0.00)
- B33: Currency ("$"#,##0.00)
- B34: Currency ("$"#,##0.00)
- B35: Currency ("$"#,##0.00)

**Formulas**:
- B30: `=B28*B29`
- B33: `=3500000*0.015`
- B34: `='Cost Projections'!I6`
- B35: `=SUM(B32:B34)`

---

## Sheet 3: Cost Projections

### Structure

**Dimensions**: 6 rows x 9 columns (A-I)

### Column Headers (Row 1)

1. Route Leg
2. Annual Tickets
3. Monthly Avg Tickets
4. Locate Fee ($/ticket)
5. Annual Locate Cost
6. Annual Adjusted Ticket Count: Probability of Damage
7. Annual Estimated Maintenance Cost
8. Annual Estimated Locate Cost
9. Annual Total Maintenance Cost

### Formulas

**Row 2-5**: Data rows for each route leg with calculations:
- Column C: `=B2/12` (Monthly average)
- Column D: Reference to locate fee (from Maintenance Estimate sheet or value)
- Column E: `=B2*D2` (Annual locate cost)
- Column F: `=B2*'Maintenance Estimate'!$B$30` (Adjusted ticket count with probability)
- Column G: `=F2*'Maintenance Estimate'!$B$27` (Estimated maintenance cost)
- Column H: `=E2` (Copy of annual locate cost)
- Column I: `=G2+H2` (Total maintenance cost)

**Row 6**: Totals row
- Column B: `=SUM(B2:B5)`
- Column C: `=SUM(C2:C5)`
- Column E: `=SUM(E2:E5)`
- Column F: `=SUM(F2:F5)`
- Column G: `=SUM(G2:G5)`
- Column H: `=SUM(H2:H5)`
- Column I: `=SUM(I2:I5)` ← **This is referenced in Maintenance Estimate B34**

### Number Formats

- Column B, C, F: Number (0.00)
- Column D, E, G, H, I: Currency ("$"#,##0.00)

---

## Key Design Principles

### 1. Use Formulas, Not Static Values

**Bad (current)**:
```python
writer.writerow({'Total Annual O&M Cost': 49610.87})
```

**Good (target)**:
```python
ws['B35'] = '=SUM(B32:B34)'
ws['B35'].number_format = '"$"#,##0.00'
```

### 2. Cross-Sheet References

Link sheets together so updates propagate:
```python
ws['B34'] = "='Cost Projections'!I6"
```

### 3. User Input Fields

Some cells are meant for user input (B26, B27, B28, B29, B32):
- Leave with default/example values
- Can add yellow highlighting if desired
- Include guidance in column C

### 4. Currency and Percentage Formatting

```python
from openpyxl.styles import numbers

ws['B26'].number_format = '"$"#,##0.00'  # Currency
ws['B28'].number_format = '0.00%'        # Percentage
```

### 5. Column Widths

```python
from openpyxl.utils import get_column_letter

ws.column_dimensions['A'].width = 29.7
ws.column_dimensions['B'].width = 11.2
ws.column_dimensions['C'].width = 43.0
ws.column_dimensions['D'].width = 11.0
```

---

## Implementation Priority

### Phase 1: Core Formulas
- [ ] Implement all formulas in Maintenance Estimate sheet
- [ ] Implement all formulas in Cost Projections sheet
- [ ] Ensure cross-sheet references work

### Phase 2: Formatting
- [ ] Apply currency/percentage number formats
- [ ] Set column widths
- [ ] Apply bold to headers

### Phase 3: Calculations
- [ ] Proper calculation flow (Cost Projections → Maintenance Estimate)
- [ ] Validate all formula references
- [ ] Test with different datasets

---

## Example User Inputs

From the modified Floydada spreadsheet:

```
Locate Fee Per Ticket: $25.00
Average Cost Per Strike Repair: $11,728.00
Probability of Damage: 0.56%
Probability of Damage Telcom: 47%
NOC Monitoring Cost: $3,000.00
Insurance Cost: =3500000*0.015 (formula: $52,500.00)
```

These drive the calculations that propagate through the Cost Projections sheet and back to the Total Annual O&M Cost.

---

*This specification is based on the user-modified spreadsheet at:*
`/Users/corey/ck/projects/kcci/maintenance/projects/floydada/outputs/floydada_maintenance_estimate_correct.xlsx`
