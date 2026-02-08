# Geocoding Pipeline

Intelligent geocoding pipeline with caching, quality assessment, and progressive fallback strategies.

## Features

- **Smart Caching**: Version-controlled cache prevents unnecessary reprocessing
- **Quality Tiers**: Automatic assessment of geocode confidence (EXCELLENT → FAILED)
- **Progressive Fallback**: Multiple geocoding strategies with intelligent selection
- **Human-in-the-Loop**: Automated review queue generation for low-confidence results
- **Performance Tracking**: Monitor improvements across pipeline runs

## Installation

```bash
# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .

# Install with dev dependencies
uv pip install -e ".[dev]"
```

## Quick Start

```bash
# Run full pipeline
python run_pipeline.py --input ticket_failures.csv

# Run specific stage
python run_pipeline.py --input tickets.csv --stage 3

# Query cache
python query_cache.py stats

# View ticket history
python query_cache.py history 2560764644

# Export results
python export_results.py --quality REVIEW_NEEDED --output review.csv
```

## Architecture

```
Input Tickets → Cache Check → Stage Processing → Quality Assessment → Review Queue
                     ↓              ↓                    ↓
                 [Skip if          [Stage 1: API]    [Validation]
                  cached]          [Stage 2: Geometric]
                                  [Stage 3: Proximity]
                                  [Stage 4: Metadata]
                                  [Stage 5: Validation]
                                  [Stage 6: Review Queue]
```

## Configuration

Edit `config/pipeline_config.yaml` to customize:
- Quality tier thresholds
- Stage skip rules
- Validation checks
- Output paths

## Quality Tiers

| Tier | Confidence | Description |
|------|------------|-------------|
| **EXCELLENT** | ≥90% | High-confidence, no review needed |
| **GOOD** | 80-90% | Reliable, reprocess only with major improvements |
| **ACCEPTABLE** | 65-80% | Usable, reprocess with any improvement |
| **REVIEW_NEEDED** | 40-65% | Low confidence, human review recommended |
| **FAILED** | <40% | Geocoding failed, manual intervention required |

## Development

```bash
# Run tests
pytest

# Format code
black geocoding_pipeline/

# Type check
mypy geocoding_pipeline/

# Lint
ruff check geocoding_pipeline/
```

## Phase 1 Status

✅ Cache system with versioning
✅ Quality assessment framework
✅ Pipeline orchestration
✅ Stage 3 (Proximity) integrated
✅ Stage 5 (Validation) integrated
⏳ Stage 1 (API) - Phase 2
⏳ Stage 2 (Geometric) - Phase 2
⏳ Stage 4 (Metadata) - Phase 2
⏳ Stage 6 (Review Queue) - Phase 2

## Documentation

- [Architecture](docs/architecture.md)
- [Cache Schema](docs/cache_schema.md)
- [Quality Tiers](docs/quality_tiers.md)
- [API Reference](docs/api/)

## License

Internal use only.
