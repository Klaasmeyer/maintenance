# Maintenance Project Documentation

## Quick Links

- [Pipeline Architecture](architecture/pipeline-architecture.md) - System design overview
- [Frequency Model](design/frequency-model.md) - Ticket frequency estimation model
- [Maintenance Estimates](design/maintenance-estimate.md) - Estimate generation design
- [Stage Design](architecture/stage-design.md) - 6-stage pipeline architecture

## Directory Structure

### Architecture (`architecture/`)
High-level system design and architectural decisions for the geocoding pipeline.

**Files:**
- `pipeline-architecture.md` - Overall system architecture
- `stage-design.md` - 6-stage pipeline design, optimization, and quality assessment
- `quality-optimization.md` - Quality scoring and validation strategies

### Design (`design/`)
Feature designs and technical specifications for major components.

**Files:**
- `frequency-model.md` - Ticket frequency estimation and annualization
- `maintenance-estimate.md` - Cost estimation methodology
- `annualization-design.md` - Multi-year data handling and annualization
- `quote-sheet-design.md` - Customer-facing quote generation

### Evolution (`evolution/`)
Historical context and evolution of the project through development phases.

**Files:**
- `phase-1-summary.md` - Phase 1 development summary
- `phase-1-progress.md` - Detailed progress tracking
- `tasks-9-12-completion.md` - Tasks 9-12 implementation details
- `ticket-structure-refactor.md` - Ticket data structure reorganization

### Guides (`guides/`)
How-to guides and operational procedures.

**Files:**
- `road-data-acquisition.md` - Guide for acquiring and processing road network data
- `geocoding-improvement-plan.md` - Plan for improving geocoding accuracy

### Specifications (`specifications/`)
Detailed technical specifications and test results.

**Files:**
- `maintenance-estimate-template.md` - Excel template specification
- `maintenance-estimate-tests.md` - Test results and validation

## Getting Started

1. **Understanding the System**: Start with [Pipeline Architecture](architecture/pipeline-architecture.md)
2. **Core Features**: Review [Frequency Model](design/frequency-model.md) and [Maintenance Estimates](design/maintenance-estimate.md)
3. **Development History**: See [Phase 1 Summary](evolution/phase-1-summary.md) for context

## Contributing

When adding new documentation:
- Place architectural decisions in `architecture/`
- Place feature designs in `design/`
- Document major changes in `evolution/`
- Create how-to guides in `guides/`
- Add technical specs in `specifications/`
