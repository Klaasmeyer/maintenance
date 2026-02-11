# Geocoding Pipeline - Usage Guide

## Overview

The Geocoding Pipeline is an intelligent, multi-stage system for geocoding 811 ticket data with automatic quality assessment, caching, and human review queue generation.

## Quick Start

### 1. Installation

```bash
# Install dependencies
uv pip install -r requirements.txt

# Or using pip
pip install pandas geopandas shapely pyyaml pydantic
```

### 2. Basic Usage

```python
from pathlib import Path
from geocoding_pipeline.pipeline import Pipeline
from geocoding_pipeline.cache.cache_manager import CacheManager
from geocoding_pipeline.config_manager import ConfigManager
from geocoding_pipeline.stages import Stage3ProximityGeocoder

# Load configuration
config_manager = ConfigManager()
config = config_manager.load(Path("config/pipeline_config.yaml"))

# Initialize cache
cache_manager = CacheManager(config.cache_db_path)

# Create pipeline
pipeline = Pipeline(cache_manager, config.to_dict())

# Add stages
stage3 = Stage3ProximityGeocoder(
    cache_manager,
    config.stages["stage_3_proximity"]
)
pipeline.add_stage(stage3)

# Load tickets
import pandas as pd
df = pd.read_csv("tickets.csv")
tickets = df.to_dict("records")

# Run pipeline
result = pipeline.run(tickets)

# Export results
pipeline.export_results(Path("output/results.csv"))
pipeline.generate_review_queue(Path("output/review_queue.csv"))
```

## Configuration

### Pipeline Configuration (YAML)

Create a `pipeline_config.yaml` file:

```yaml
name: geocoding_pipeline
cache:
  db_path: ${HOME}/geocoding_cache.db
output_dir: outputs
fail_fast: false
save_intermediate: true

stages:
  stage_3_proximity:
    enabled: true
    skip_rules:
      skip_if_quality: ["EXCELLENT", "GOOD"]
      skip_if_locked: true
    road_network_path: roads_merged.gpkg
    max_distance_km: 50

  stage_5_validation:
    enabled: true
    skip_rules:
      skip_if_locked: true
    validation_rules:
      - low_confidence
      - emergency_low_confidence
      - city_distance
      - fallback_geocode
      - missing_road
```

### Environment Variables

Use `${VAR_NAME}` or `${VAR_NAME:default}` syntax for environment variables:

```yaml
cache:
  db_path: ${GEOCODING_CACHE:/tmp/geocoding_cache.db}

stages:
  stage_1_api:
    api_key: ${GEOCODING_API_KEY}
```

## Pipeline Stages

### Stage 1: API Geocoding (STUB)
*Not yet implemented*
- High-quality API-based geocoding
- Google Maps Geocoding API or similar
- Target confidence: 90%+

### Stage 2: Geometric Intersection (STUB)
*Not yet implemented*
- Calculate true geometric intersection of roads
- Uses road network shapefile/geopackage
- Target confidence: 85-95%

### Stage 3: Proximity Geocoding (IMPLEMENTED)
**Status**: ✅ Implemented and tested

Uses spatial proximity analysis to geocode intersections:

- **Approach 2 (Closest Point)**: For parallel/nearby roads in rural areas
- **Approach 3 (Corridor Midpoint)**: For major highway + minor road reference
- **Approach 4 (City + Primary Street)**: When one road is missing
- **Fallback (City Centroid)**: Last resort for missing roads

**Confidence adjustments** based on:
- Ticket type (Emergency: +5%)
- Work duration (1 DAY: +10%, 2 MONTHS: -5%)
- Work type (Hydro-excavation: +10%, Pipeline: -5%)

**Success rate**: 99.94% (23,585/23,601 tickets)
**Average confidence**: 84.95%

### Stage 4: Fallback Strategies (STUB)
*Not yet implemented*
- Fuzzy road name matching
- Partial address geocoding
- Historical pattern learning

### Stage 5: Validation (IMPLEMENTED)
**Status**: ✅ Implemented and tested

Re-validates already-geocoded tickets and updates quality assessments:

- Runs validation rules on existing geocodes
- Updates quality tier and review priority
- Respects locked records (human-verified)
- Generates actionable validation flags

## Quality Tiers

The pipeline assigns quality tiers based on confidence and validation:

| Tier | Confidence Range | Description |
|------|-----------------|-------------|
| **EXCELLENT** | ≥90% | High confidence, no issues |
| **GOOD** | 80-90% | Good confidence, minor issues |
| **ACCEPTABLE** | 65-80% | Acceptable, may need review |
| **REVIEW_NEEDED** | 40-65% | Low confidence, review recommended |
| **FAILED** | <40% | Failed geocoding |

## Review Priorities

Human review queue is prioritized:

| Priority | Description |
|----------|-------------|
| **CRITICAL** | Failed geocodes, must review |
| **HIGH** | Emergency tickets <75% confidence, city centroid fallback |
| **MEDIUM** | Review needed tier with validation flags |
| **LOW** | Acceptable tier with minor issues |
| **NONE** | Excellent/Good quality, no review needed |

## Caching & Versioning

The pipeline maintains a versioned cache of all geocoding results:

- **Automatic versioning**: Every update creates a new version
- **Current record tracking**: Always retrieves latest version
- **Version history**: Track improvements over time
- **Locking**: Prevent reprocessing of human-verified geocodes

### Cache Operations

```python
from geocoding_pipeline.cache.cache_manager import CacheManager

cache = CacheManager("cache.db")

# Get current geocode
record = cache.get_current(ticket_number="TEST001")

# Get version history
history = cache.get_version_history(ticket_number="TEST001")

# Lock a record (human verified)
cache.lock("TEST001", "Human verified")

# Query by quality tier
from geocoding_pipeline.cache.models import CacheQuery, QualityTier

query = CacheQuery(quality_tier=[QualityTier.REVIEW_NEEDED])
records = cache.query(query)

# Get statistics
stats = cache.get_statistics()
print(f"Total records: {stats['total_records']}")
print(f"Quality distribution: {stats['quality_tiers']}")
```

## Reprocessing Logic

The pipeline intelligently skips already-processed tickets based on rules:

```python
skip_rules = {
    "skip_if_quality": ["EXCELLENT", "GOOD"],  # Skip high-quality geocodes
    "skip_if_locked": True,                     # Never reprocess locked
    "skip_if_confidence": 0.90,                 # Skip if confidence ≥ 90%
    "skip_if_method": ["stage_1_api"],          # Skip specific methods
}
```

This prevents:
- Wasting resources on already-good geocodes
- Overwriting human-verified locations
- Infinite loops (same stage won't reprocess its own results)

## Outputs

### Results CSV

All geocoding results with full metadata:

```csv
ticket_number,latitude,longitude,confidence,quality_tier,review_priority,method,approach,...
TEST001,31.5401,-103.1293,0.95,EXCELLENT,NONE,stage_3_proximity,closest_point,...
```

### Review Queue CSV

Prioritized list for human review:

```csv
ticket_number,review_priority,quality_tier,confidence,validation_flags,lat,lng,...
TEST123,CRITICAL,FAILED,0.35,"low_confidence,city_distance",31.5,-103.1,...
```

### Pipeline Statistics

JSON summary of pipeline run:

```json
{
  "pipeline_id": "pipeline_20260208_150000",
  "total_tickets": 728,
  "total_succeeded": 727,
  "total_failed": 1,
  "total_time_ms": 45000,
  "stages": [
    {
      "stage_name": "stage_3_proximity",
      "total_tickets": 728,
      "succeeded": 727,
      "failed": 1,
      "skipped": 0,
      "avg_time_ms": 61.8
    }
  ]
}
```

## Advanced Usage

### Custom Stages

Create custom stages by inheriting from `BaseStage`:

```python
from geocoding_pipeline.stages.base_stage import BaseStage
from geocoding_pipeline.cache.models import GeocodeRecord, QualityTier

class MyCustomStage(BaseStage):
    def process_ticket(self, ticket_data):
        # Your custom geocoding logic here
        lat, lng, confidence = my_geocoder(ticket_data)

        return GeocodeRecord(
            ticket_number=ticket_data["ticket_number"],
            geocode_key=CacheManager.generate_geocode_key(...),
            latitude=lat,
            longitude=lng,
            confidence=confidence,
            method=self.stage_name,
            quality_tier=QualityTier.GOOD,
            # ...
        )
```

### Batch Processing

Process large datasets efficiently:

```python
import pandas as pd

# Load in chunks
chunksize = 1000
for chunk in pd.read_csv("large_tickets.csv", chunksize=chunksize):
    tickets = chunk.to_dict("records")
    result = pipeline.run(tickets)
    print(f"Processed {len(tickets)} tickets: {result.total_succeeded} succeeded")
```

### Pipeline History

Track all pipeline runs:

```sql
-- Query pipeline_history table
SELECT pipeline_id, start_time, status, ticket_count
FROM pipeline_history
ORDER BY start_time DESC;
```

## Testing

Run the test suite:

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_cache.py -v

# Run with coverage
pytest tests/ --cov=geocoding_pipeline --cov-report=html
```

## Troubleshooting

### Common Issues

**Issue**: Pipeline runs slow
- **Solution**: Enable skip rules to avoid reprocessing good geocodes
- **Solution**: Use batch processing for large datasets

**Issue**: Too many tickets in review queue
- **Solution**: Adjust quality tier thresholds in configuration
- **Solution**: Run Stage 1 (API) or Stage 2 (Geometric) for better results

**Issue**: Cache database locked
- **Solution**: Close all connections before running pipeline
- **Solution**: Use `cache_manager._get_connection()` context manager

**Issue**: Import errors
- **Solution**: Ensure all dependencies are installed: `uv pip install -r requirements.txt`
- **Solution**: Check PYTHONPATH includes geocoding_pipeline directory

## Next Steps

### Phase 2 Enhancements

1. **Implement Stage 1 (API Geocoding)**
   - Google Maps Geocoding API integration
   - Rate limiting and API key management
   - High-quality results for complex intersections

2. **Implement Stage 2 (Geometric Intersection)**
   - True geometric intersection calculation
   - Handle multiple intersection points
   - High confidence for actual intersections

3. **Implement Stage 4 (Fallback Strategies)**
   - Fuzzy road name matching (typos, abbreviations)
   - Historical ticket location analysis
   - Excavator/utility company pattern learning

4. **Infrastructure Owner Mapping**
   - Acquire PLAINS, OXY, ONCOR ROW maps
   - Snap to known pipeline/power line geometries
   - Expected: +10-15% confidence improvement

## Support

For issues or questions:
- Check the test suite for usage examples
- Review the PHASE1_PROGRESS.md for implementation details
- See the individual stage files for specific functionality

---

**Version**: 1.0.0 (Phase 1 Complete)
**Last Updated**: 2026-02-08
