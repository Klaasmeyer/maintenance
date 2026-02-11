# Pipeline Stage Design

## Overview

The geocoding pipeline uses a 6-stage architecture to maximize quality while minimizing API costs. Each stage handles specific geocoding scenarios with appropriate optimization strategies.

## 6-Stage Architecture

### Stage 1: API Geocoding
**Module:** `src/kcci_maintenance/stages/stage_1_api.py`

**Purpose:** Geocode addresses via Google Maps API (premium tier)

**Optimization Strategy:**
- Intelligent caching to minimize API costs
- De-duplication by geocode key (street + city + county)
- Cache hits avoid repeated API calls

**Quality Characteristics:**
- Confidence: 0.9-1.0
- Accuracy: High (Google Maps premium)
- Coverage: Best for complete, well-formatted addresses

**When It Runs:**
- First attempt for all uncached tickets
- Skipped if geocode key exists in cache

**Cost Consideration:**
- $X per 1,000 requests (premium tier)
- Cache hit rate: ~60-80% on subsequent runs

---

### Stage 2: Geometric Geocoding
**Module:** `src/kcci_maintenance/stages/stage_2_geometric.py`

**Purpose:** Match addresses to road network geometry using local spatial joins

**Optimization Strategy:**
- No API calls - uses local road network (GPKG)
- Fast spatial indexing via GeoPandas
- Fuzzy name matching for road names

**Quality Characteristics:**
- Confidence: 0.7-0.9
- Accuracy: Good for structured addresses on known roads
- Coverage: Limited to roads in local network

**When It Runs:**
- After Stage 1 API geocoding
- Provides fallback for API failures
- Fills gaps in API coverage

**Performance:**
- ~100-200ms per ticket
- Zero API costs

---

### Stage 3: Proximity Geocoding
**Module:** `src/kcci_maintenance/stages/stage_3_proximity.py`

**Purpose:** Fuzzy matching with spatial proximity analysis

**Optimization Strategy:**
- **Pipeline proximity boost:** Increases confidence for tickets near known pipeline routes
- Handles misspellings and partial addresses
- Uses distance-based confidence scoring

**Quality Characteristics:**
- Base confidence: 0.5-0.8
- Boosted confidence: +0.1-0.2 if near pipeline (within 500m)
- Handles: Typos, abbreviations, incomplete addresses

**Pipeline Proximity Boost:**
```python
if distance_to_pipeline < 500m:
    confidence += 0.15  # Boost for pipeline proximity
```

**When It Runs:**
- After geometric geocoding
- Primary workhorse for fuzzy matches

**Use Cases:**
- "CR 1234" → County Road 1234
- "FM123" → Farm-to-Market Road 123
- Misspelled road names

---

### Stage 4: Fallback Geocoding
**Module:** `src/kcci_maintenance/stages/stage_4_fallback.py`

**Purpose:** Last-resort geocoding with relaxed matching criteria

**Optimization Strategy:**
- Very permissive matching rules
- City/county-level fallback
- Generates low-confidence results requiring review

**Quality Characteristics:**
- Confidence: 0.3-0.6
- Accuracy: Low to moderate
- Review: Always flagged for manual review

**When It Runs:**
- After all other stages fail
- Prevents total geocoding failure

---

### Stage 5: Validation
**Module:** `src/kcci_maintenance/stages/stage_5_validation.py`

**Purpose:** Quality assessment and validation rule application

**Validation Rules:**
1. **Confidence Threshold Rule** - Flags low-confidence geocodes
2. **Out-of-Corridor Rule** - Detects tickets outside route corridor
3. **Pipeline Mismatch Rule** - Validates pipeline proximity assumptions
4. **Duplicate Detection Rule** - Identifies duplicate geocodes
5. **Coordinate Bounds Rule** - Validates lat/lng within expected range

**Quality Tiers:**
- **GOLD** (90-100% confidence): Production ready
- **SILVER** (70-89% confidence): Good quality, minor review
- **BRONZE** (50-69% confidence): Acceptable, needs review
- **FAILED** (<50% confidence): Requires manual geocoding

**Review Priority:**
- **HIGH**: Failed geocodes, out of corridor, very low confidence
- **MEDIUM**: Moderate confidence, edge cases
- **LOW**: High confidence, validated locations

**Features:**
- Route corridor validation (KMZ buffer check)
- Metadata enrichment
- Review queue generation

---

### Stage 6: Enrichment
**Module:** `src/kcci_maintenance/stages/stage_6_enrichment.py`

**Purpose:** Add contextual metadata to geocoded locations

**Enrichment Sources:**
1. **Jurisdiction/Permitting Data:**
   - Authority name
   - Jurisdiction type
   - Permit requirements
   - Point-in-polygon spatial join

2. **Future Enrichment:**
   - Land ownership data
   - Environmental constraints
   - Crossing permits
   - Right-of-way information

**Optimization Strategy:**
- Spatial index for O(log n) polygon lookups
- GeoJSON caching
- Skip failed geocodes (no point enriching failures)

**Performance:**
- ~20ms per ticket with spatial index
- 38.5 MB GeoJSON loads once per pipeline run

---

## Stage Execution Flow

```
Input Tickets (CSV/XLSX)
    ↓
┌─────────────────────────────────┐
│  Cache Check                     │
│  - Check geocode key exists      │
│  - Return cached if found        │
└─────────────────────────────────┘
    ↓ (cache miss)
┌─────────────────────────────────┐
│  Stage 1: API Geocoding          │
│  - Google Maps API               │
│  - High quality, high cost       │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│  Stage 2: Geometric Geocoding    │
│  - Local road network match      │
│  - Zero API cost                 │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│  Stage 3: Proximity Geocoding    │
│  - Fuzzy match + pipeline boost  │
│  - Handles typos/abbreviations   │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│  Stage 4: Fallback               │
│  - Last resort                   │
│  - Low confidence                │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│  Stage 5: Validation             │
│  - Quality assessment            │
│  - Corridor check                │
│  - Review queue generation       │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│  Stage 6: Enrichment             │
│  - Jurisdiction data             │
│  - Permitting info               │
└─────────────────────────────────┘
    ↓
Output Results (CSV + Review Queue)
```

## Quality Optimization

### Confidence Scoring System

**API Geocodes (Stage 1):**
- Base: 0.95
- Adjustments: ±0.05 based on address match quality

**Geometric Geocodes (Stage 2):**
- Exact match: 0.85
- Partial match: 0.70-0.80
- Adjustments: Based on name similarity

**Proximity Geocodes (Stage 3):**
- Base: 0.50-0.80 (distance-based)
- Pipeline boost: +0.15 if within 500m of pipeline
- Name similarity: ±0.10

**Fallback Geocodes (Stage 4):**
- Base: 0.30-0.60
- Always flagged for review

### Pipeline Proximity Optimization

**Concept:**
Tickets near the known pipeline route are more likely to be correctly geocoded, even with fuzzy matching.

**Implementation:**
```python
class PipelineProximityAnalyzer:
    def __init__(self, kmz_path: Path, buffer_distance_m: float = 500.0):
        self.pipeline_corridor = self._load_pipeline_corridor(kmz_path)
        self.buffer_distance_m = buffer_distance_m

    def analyze_proximity(self, lat: float, lng: float) -> dict:
        point = Point(lng, lat)
        distance = self.pipeline_corridor.distance(point).min()

        if distance <= self.buffer_distance_m:
            return {
                'near_pipeline': True,
                'distance_m': distance,
                'confidence_boost': 0.15
            }
```

**Benefits:**
- Reduces false negatives for misspelled addresses
- Improves geocoding success rate by 10-15%
- Maintains high quality near critical infrastructure

### Route Corridor Validation

**Concept:**
Validates that geocoded tickets fall within expected route corridor (pipeline + buffer).

**Implementation:**
```python
class RouteCorridorValidator:
    def check_containment(self, lat: float, lng: float):
        point = Point(lng, lat)
        within_corridor = self.corridor_buffer.contains(point)

        return within_corridor, {
            'within_corridor': within_corridor,
            'distance_to_corridor_m': distance_m
        }
```

**Validation Logic:**
- GOLD tier must be within corridor (or flagged)
- SILVER tier: warning if outside corridor
- BRONZE/FAILED: expected to have corridor issues

---

## Performance Characteristics

### Speed (per ticket)
- Stage 1 (API): ~200-500ms (network dependent)
- Stage 2 (Geometric): ~100-200ms
- Stage 3 (Proximity): ~100ms
- Stage 4 (Fallback): ~50ms
- Stage 5 (Validation): ~10ms
- Stage 6 (Enrichment): ~20ms

**Total Pipeline:** ~130ms average (with caching)

### Success Rates
- Floydada: 79.1% geocoding success rate
- Wink: 74.7% geocoding success rate
- Assignment rate: 85%+ (tickets assigned to route)

### Cost Optimization
- Cache hit rate: 60-80% (avoids API calls)
- Local geocoding (Stages 2-4): Zero API cost
- API calls only for new/uncached tickets

---

## Cache Strategy

### Cache Key
```
geocode_key = f"{street}|{city}|{county}"
```

### Cache Invalidation
- Reprocessing rules trigger re-geocoding
- Manual purge via `src/tools/maintenance/cache_maintenance.py`
- Version-based invalidation for stage updates

### Cache Versioning
Each stage maintains its own version:
```python
stage_version = "stage_3_v1.2.0"
```

Changes to geocoding logic increment version, triggering re-processing.

---

## Extension Points

### Adding New Stages
1. Inherit from `BaseStage`
2. Implement `process_ticket(ticket_data) -> GeocodeRecord`
3. Register in `src/kcci_maintenance/stages/__init__.py`
4. Add to pipeline orchestrator

### Adding New Validation Rules
1. Inherit from `BaseValidationRule`
2. Implement `validate(record, **kwargs) -> RuleResult`
3. Register in `ValidationEngine`

### Adding New Enrichment Sources
1. Create enricher class (e.g., `LandOwnershipEnricher`)
2. Add to Stage 6 configuration
3. Merge metadata into `GeocodeRecord`

---

## References

- [Pipeline Architecture](pipeline-architecture.md) - Overall system design
- [Quality Optimization](quality-optimization.md) - Detailed quality strategies
- [Frequency Model](../design/frequency-model.md) - Ticket frequency estimation

## Related Files

- `src/kcci_maintenance/stages/` - Stage implementations
- `src/kcci_maintenance/core/quality_assessment.py` - Quality tier logic
- `src/kcci_maintenance/core/validation_rules.py` - Validation rules
- `src/kcci_maintenance/utils/pipeline_proximity.py` - Pipeline boost logic
- `src/kcci_maintenance/utils/route_corridor.py` - Corridor validation
