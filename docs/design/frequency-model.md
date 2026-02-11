# Ticket Frequency Estimation Model

## Overview

The frequency model estimates annual maintenance locate ticket volumes based on historical data, enabling accurate cost projections for pipeline maintenance operations.

## Key Components

### 1. Time Span Detection

Automatically detects the time range covered by ticket data using original creation dates from source tickets.

**Implementation:**
```python
def _calculate_time_span_years(self, tickets_df: pd.DataFrame) -> tuple[float, dict]:
    # Look for creation date columns
    date_col = None
    for col in ['Creation', 'creation', 'created_at', 'date', 'Date']:
        if col in tickets_df.columns:
            date_col = col
            break

    # Parse dates with UTC timezone handling
    dates = pd.to_datetime(tickets_df[date_col], errors='coerce', utc=True)
    valid_dates = dates.dropna()

    min_date = valid_dates.min()
    max_date = valid_dates.max()

    # Calculate years span
    days_span = (max_date - min_date).days
    years_span = max(1.0, days_span / 365.25)

    return years_span, time_info
```

**Key Features:**
- Searches multiple column name variants
- Handles timezone-aware dates (UTC conversion)
- Returns detailed time span metadata
- Minimum 1.0 year for single-year datasets

### 2. Annualization

Converts multi-year ticket counts to annual rates using the detected time span.

**Formula:**
```
annual_tickets = total_tickets / years_span
years_span = (max_date - min_date).days / 365.25
```

**Example:**
- Floydada: 788 tickets over 4.0 years (2022-2025) → **197 annual tickets**
- Wink: 1,293 tickets over 1.0 years (2025) → **1,293 annual tickets**

**Implementation:**
```python
def _generate_leg_details(self, tickets_df: pd.DataFrame, years_span: float = 1.0):
    # Basic counts (total in dataset)
    total_tickets_dataset = len(group)

    # Annualized count
    total_tickets = round(total_tickets_dataset / years_span)

    # Annualize ticket type breakdowns
    emergency_tickets_dataset = len(group[group['ticket_type'] == 'Emergency'])
    normal_tickets_dataset = len(group[group['ticket_type'] != 'Emergency'])
    emergency_tickets = round(emergency_tickets_dataset / years_span)
    normal_tickets = round(normal_tickets_dataset / years_span)
```

### 3. Ticket Type Filtering

Classifies tickets into excavation vs non-excavation types to accurately model excavation risk.

**Excavation Types (counted):**
- **Normal** - Standard excavation work
- **Emergency** - Emergency excavation (requires immediate response)
- **DigUp** - Dig-up work

**Non-Excavation Types (excluded):**
- **Update** - Re-marks only (no new excavation)
- **No Response** - No locator response
- **Cancellation** - Cancelled tickets
- **Recall** - Recalled tickets
- **Survey/Design** - Planning/survey work only (no excavation)
- **Non-Compliant** - Non-compliant tickets

**Rationale:**
The model focuses on tickets that represent actual excavation risk. Update tickets are re-marks of existing excavations and don't represent new risk. Survey/design tickets don't involve excavation. This filtering provides more accurate cost modeling.

**Implementation:**
```python
EXCAVATION_TICKET_TYPES = {'Normal', 'Emergency', 'DigUp'}
NON_EXCAVATION_TICKET_TYPES = {
    'Update', 'No Response', 'Cancellation',
    'Recall', 'Survey/Design', 'Non-Compliant'
}

def _filter_excavation_tickets(self, tickets_df: pd.DataFrame):
    excavation_mask = tickets_df['ticket_type'].isin(EXCAVATION_TICKET_TYPES)
    excavation_tickets = tickets_df[excavation_mask].copy()
    excluded_tickets = tickets_df[~excavation_mask].copy()

    filter_stats = {
        'total_tickets': len(tickets_df),
        'excavation_tickets': len(excavation_tickets),
        'excluded_tickets': len(excluded_tickets),
        'excluded_by_type': excluded_tickets['ticket_type'].value_counts().to_dict()
    }

    return excavation_tickets, filter_stats
```

**Impact:**
- Wink: Excludes 44.5% of tickets (10,175 of 22,855)
- Floydada: Excludes ~17% of tickets

### 4. Route Assignment

Assigns tickets to route legs based on proximity for proportional cost allocation.

**Parameters:**
- **Buffer distance**: 500m default (configurable)
- **Assignment method**: Nearest route leg within buffer
- **Unassigned handling**: Tickets beyond buffer are marked as "Unassigned"

**Cost Allocation:**
Monthly O&M fees are distributed proportionally by leg length:
```
MRC_per_leg = (Total Annual O&M / 12) × (Leg Length / Total Length)
```

**Example (Wink):**
- Andrews Build: 68.71 mi (54.9% of total) → $10,586/month
- Monahans Build: 16.89 mi (13.5% of total) → $2,602/month
- Pyote Build: 23.93 mi (19.1% of total) → $3,686/month

### 5. Quality Metrics

Tracks data quality and coverage throughout the estimation process.

**Metrics Captured:**
- Total tickets in dataset
- Excavation vs non-excavation breakdown
- Assignment rate (% of tickets assigned to route)
- Tickets per mile per leg
- Emergency vs normal ticket distribution
- Average geocoding confidence per leg

## Data Flow

```
Source Tickets (CSV/XLSX)
    ↓
Time Span Detection → Years: 4.0 (2022-2025)
    ↓
Ticket Type Filtering → Excavation Only
    ↓
Route Assignment → Assign to Legs
    ↓
Annualization → Divide by Years Span
    ↓
Cost Allocation → Proportional by Length
    ↓
Maintenance Estimate (Excel)
```

## Implementation Files

### Core Module
`src/kcci_maintenance/utils/maintenance_estimate.py`

**Key Methods:**
- `_calculate_time_span_years()` - Time span detection
- `_filter_excavation_tickets()` - Ticket classification
- `_generate_leg_details()` - Annualization and leg assignment
- `assign_tickets_to_legs()` - Proximity-based route assignment

### Integration Point
`src/tools/estimates/generate_estimates_merged.py`

Merges geocoded results with original ticket data to preserve creation dates for accurate time span calculation.

## Validation

### Test Cases
- Single-year dataset (Wink): Should return years_span = 1.0
- Multi-year dataset (Floydada): Should detect actual span (4.0 years)
- Missing dates: Should default to 1.0 year with warning
- Timezone issues: Should handle mixed timezones via UTC conversion

### Verification
```python
# Check annualization
assert total_tickets == round(dataset_tickets / years_span)

# Check ticket type filtering
assert excavation_tickets.ticket_type.isin(EXCAVATION_TICKET_TYPES).all()

# Check leg assignment
assert (assigned_tickets / total_excavation_tickets) > 0.7  # 70%+ assignment rate
```

## Edge Cases

**Missing Creation Dates:**
- Falls back to 1.0 year assumption
- Logs warning message
- Documents assumption in output metadata

**Single-Day Datasets:**
- Minimum years_span = 1.0
- Prevents division by zero
- Assumes annual volume equals total tickets

**Timezone Handling:**
- Converts all dates to UTC
- Prevents "Mixed timezones" errors
- Ensures consistent date comparisons

## References

- [Annualization Design](annualization-design.md) - Detailed annualization implementation
- [Maintenance Estimate Design](maintenance-estimate.md) - Overall estimate generation
- [ANNUALIZATION_FIX.md](../../.ai-workspace/session-2026-02-10/summaries/ANNUALIZATION_FIX.md) - Fix history

## Change History

- **2026-02-10**: Implemented annualization with time span detection
- **2026-02-10**: Added ticket type filtering (excavation vs non-excavation)
- **2026-02-10**: Fixed double annualization bug
- **2026-02-10**: Added timezone-aware date parsing
