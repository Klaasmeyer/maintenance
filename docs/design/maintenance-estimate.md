# Maintenance Estimate Generator

## Overview

Automatically generates O&M (Operations & Maintenance) cost estimates from geocoded ticket data by analyzing ticket distribution across route legs/segments.

## Features

### Calculated Automatically:
- **Tickets per route leg** - Total tickets assigned to each route segment
- **Leg statistics** - Length, tickets/mile, emergency vs normal breakdown
- **Duration analysis** - Tickets by 1-3 day, 4-10 day, 11+ day durations
- **Work type breakdown** - Top work types per leg
- **Quality metrics** - Average confidence, assignment rates
- **Cost projections** - Annual and monthly ticket/cost estimates
- **Locate cost estimates** - Based on ticket counts and default rates

### User Inputs Required (Highlighted in Yellow):
- Average cost per strike repair
- Locate fee per ticket
- Expected strike rate
- NOC/monitoring costs
- Insurance costs
- Initial setup/activation costs

## Route Leg Detection

The generator analyzes the route KMZ file to identify route legs. For the Wink project:

1. **Pyote Build** - Main route to Pyote
2. **Pyote Build (Easement Option)** - Shorter alternative if easement obtained
3. **Andrews Build** - Route to Andrews
4. **Monahans Build** - Route to Monahans

Tickets are automatically assigned to the nearest leg within a 500m buffer.

## Output Format

### Excel Workbook with 5 Sheets:

#### 1. Maintenance Estimate (Summary)
- Project summary statistics
- Tickets per route leg
- Comprehensive input parameters (calculated + user input fields)
- Key metrics and totals

#### 2. Leg Details
- Detailed statistics per route leg
- Route leg name
- Leg length (miles)
- Total tickets and tickets/mile
- Emergency vs Normal breakdown
- Duration breakdowns (1-3, 4-10, 11+ days)
- Top work types
- Quality metrics

#### 3. Cost Projections
- Annual and monthly ticket projections per leg
- Locate cost estimates
- Default rates applied (can be updated)
- Notes on assumptions

#### 4. Ticket Breakdowns
- Detailed breakdowns by:
  - Ticket type (Emergency/Normal)
  - Duration categories
  - Top 5 work types per leg
- Percentages and counts

#### 5. Ticket Assignments
- Raw geocoded ticket data
- Route leg assignments
- Distance to nearest leg
- All ticket metadata

## Usage

### Command Line

```bash
# Generate estimate with pipeline run
python3 cli.py projects/wink/tickets \
  --generate-estimate projects/wink/route/wink.kmz \
  --output results.csv \
  --estimate-output wink_maintenance_estimate.xlsx

# With config file
python3 cli.py projects/wink/tickets \
  --config configs/wink_project_full.yaml \
  --generate-estimate projects/wink/route/wink.kmz

# The estimate will be saved as:
# maintenance_estimate_YYYYMMDD_HHMMSS.xlsx (if no --estimate-output specified)
```

### Programmatic Usage

```python
from pathlib import Path
import pandas as pd
from utils.maintenance_estimate import generate_maintenance_estimate

# Load geocoded tickets (from pipeline output or cache)
tickets_df = pd.read_csv('pipeline_results.csv')

# Filter to only geocoded tickets (exclude FAILED)
tickets_df = tickets_df[
    (tickets_df['latitude'].notna()) &
    (tickets_df['longitude'].notna())
]

# Generate estimate
generate_maintenance_estimate(
    tickets_df=tickets_df,
    kmz_path=Path('projects/wink/route/wink.kmz'),
    output_path=Path('wink_maintenance_estimate.xlsx'),
    project_name='Wink APN',
    buffer_distance_m=500.0  # Ticket assignment threshold
)
```

## Input Parameters Reference

### Automatically Calculated:

| Parameter | Source | Notes |
|-----------|--------|-------|
| Total Route Length | KMZ geometry | Sum of all leg lengths in miles |
| Total Annual Tickets | Pipeline data | All geocoded tickets |
| Average Tickets/Mile | Calculated | Total tickets / total length |
| Tickets per Leg | Spatial analysis | Assigned by proximity to leg |
| Emergency % | Ticket type field | Percentage of emergency tickets |
| Duration Breakdown | Duration field | 1-3 day, 4-10 day, 11+ day |
| Work Type Analysis | Work type field | Most common work types |
| Quality Metrics | Confidence scores | Average confidence per leg |

### User Input Required:

| Parameter | Unit | Purpose |
|-----------|------|---------|
| Locate Fee Per Ticket | $/ticket | Standard 811 locate fee |
| Average Cost Per Strike Repair | $ | Average cost to repair utility strike |
| Expected Strike Rate | strikes/year | Projected annual strike incidents |
| NOC Monitoring Cost | $/month | Network Operations Center monitoring |
| Insurance Cost | $/year | Annual insurance premium |
| Initial Setup/Activation | $ | One-time setup costs |

## Ticket Assignment Logic

Tickets are assigned to route legs using spatial proximity:

1. **Calculate distance** from each ticket to each route leg
2. **Find nearest leg** for each ticket
3. **Apply buffer threshold** (default 500m)
   - Within 500m: Assigned to nearest leg
   - Beyond 500m: Marked as "Unassigned"
4. **Track distance** for analysis

### Assignment Metrics:
- **Assignment Rate**: % of tickets assigned to legs
- **Unassigned Tickets**: Tickets >500m from any leg
- **Distance Statistics**: Min/max/avg distance per leg

## Cost Calculation Defaults

The generator includes default cost assumptions that can be updated:

- **Locate Fee**: $3.50 per ticket (standard rate)
- **Emergency Multiplier**: 2.0x (emergency tickets cost more)
- **Annual Projection**: Based on full dataset
- **Monthly Average**: Annual / 12

**Note**: These are placeholder values. Update the Excel output with actual rates for your project.

## Example Output

### Maintenance Estimate Sheet:

```
Wink APN - O&M Maintenance Estimate
Generated: 2026-02-09 15:30:00

SUMMARY STATISTICS
Total Tickets:                    23,601
Assigned to Route Legs:           22,847 (96.8%)
Unassigned (>500m from route):    754 (3.2%)

TICKETS PER ROUTE LEG
Route Leg                 | Total Tickets | Leg Length (mi) | Tickets/Mile
Pyote Build              | 8,234         | 42.5           | 193.7
Pyote Build (Easement)   | 1,523         | 18.2           | 83.7
Andrews Build            | 9,876         | 67.3           | 146.8
Monahans Build           | 3,214         | 38.9           | 82.6

MAINTENANCE ESTIMATE INPUTS
Input Parameter                    | Value    | Unit        | Source/Notes
Total Route Length                 | 166.9    | miles       | Calculated from KMZ
Total Annual Tickets               | 22,847   | tickets/yr  | Based on geocoded data
Average Tickets/Mile               | 136.9    | tickets/mi  | Calculated average
Locate Fee Per Ticket             |          | $/ticket    | USER INPUT REQUIRED
Average Cost Per Strike Repair    |          | $           | USER INPUT REQUIRED
Expected Strike Rate              |          | strikes/yr  | USER INPUT REQUIRED
NOC Monitoring Cost               |          | $/month     | USER INPUT REQUIRED
Insurance Cost                    |          | $/year      | USER INPUT REQUIRED
```

## Integration with Pipeline

The maintenance estimate generator is fully integrated with the pipeline:

### CLI Integration:
- `--generate-estimate <kmz_file>` - Enable estimate generation
- `--estimate-output <path>` - Specify output path
- Automatically uses pipeline results
- Runs after all stages complete

### Workflow:
1. Pipeline geocodes tickets
2. Tickets enriched with jurisdiction/corridor data
3. Results exported to CSV
4. Maintenance estimate generated from CSV + KMZ
5. Excel workbook created with all analyses

## Files

### Created:
- `geocoding_pipeline/utils/maintenance_estimate.py` - Generator implementation
- `MAINTENANCE_ESTIMATE.md` - This documentation

### Modified:
- `geocoding_pipeline/cli.py` - Added CLI integration

## Requirements

- **pandas** - Data manipulation
- **geopandas** - Spatial analysis
- **shapely** - Geometry operations
- **openpyxl** - Excel output

All included in project dependencies.

## Troubleshooting

### "No tickets assigned to legs"
- Check buffer_distance_m parameter (default 500m)
- Verify KMZ file has correct coordinate system (EPSG:4326)
- Check ticket latitude/longitude are valid

### "KMZ file not found"
- Verify path to KMZ file
- Use relative path from working directory
- Example: `projects/wink/route/wink.kmz`

### "No successful geocodes"
- Pipeline must complete successfully first
- Check that tickets have valid lat/lng
- Review pipeline logs for geocoding errors

## Future Enhancements

Potential additions:
- Historical trend analysis (if multi-year data available)
- Seasonal patterns (by month/quarter)
- Strike prediction modeling
- Cost optimization recommendations
- Comparison with industry benchmarks
- GIS visualization of ticket distribution

## Summary

The Maintenance Estimate Generator provides comprehensive O&M cost analysis by:
- ✅ Automatically analyzing ticket distribution across route legs
- ✅ Calculating key metrics (tickets/mile, costs, etc.)
- ✅ Generating professional Excel reports
- ✅ Highlighting user input requirements
- ✅ Integrating seamlessly with pipeline workflow

Simply add `--generate-estimate` flag to pipeline runs to get instant maintenance cost estimates!
