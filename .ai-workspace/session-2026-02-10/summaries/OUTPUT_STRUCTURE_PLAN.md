# Output Structure and Cleanup Plan

## Current Problems

### Inconsistent Locations
- ❌ Root directory: `geometric_results.csv`, `proximity_results.csv`, `review_queue_*.csv`
- ❌ `outputs/`: Mixed files with inconsistent naming
- ❌ `projects/[project]/outputs/`: Some project-specific files
- ❌ No standardized naming convention

### Naming Issues
- ❌ `wink_full_results.csv` vs `wink_full_results_fixed.csv`
- ❌ `floydada_results.csv` vs `floydada_results_v2.csv`
- ❌ Timestamps only on some files
- ❌ No date stamps
- ❌ Unclear which is latest/authoritative

---

## Proposed Standard Structure

```
maintenance/
├── projects/
│   ├── wink/
│   │   ├── outputs/
│   │   │   ├── 2026-02-09-wink-results-145235.csv
│   │   │   ├── 2026-02-09-wink-maintenance-estimate-145235.xlsx
│   │   │   ├── 2026-02-09-wink-review-queue-145235.csv
│   │   │   └── latest/  (symlinks to most recent)
│   │   │       ├── results.csv -> ../2026-02-09-wink-results-145235.csv
│   │   │       ├── estimate.xlsx -> ../2026-02-09-wink-maintenance-estimate-145235.xlsx
│   │   │       └── review-queue.csv -> ../2026-02-09-wink-review-queue-145235.csv
│   │   ├── cache/
│   │   ├── route/
│   │   ├── tickets/
│   │   └── permitting/
│   │
│   └── floydada/
│       ├── outputs/
│       │   ├── 2026-02-09-floydada-results-152230.csv
│       │   ├── 2026-02-09-floydada-maintenance-estimate-152230.xlsx
│       │   ├── 2026-02-09-floydada-review-queue-152230.csv
│       │   └── latest/
│       ├── cache/
│       ├── route/
│       └── tickets/
│
├── outputs/  (DEPRECATED - to be removed)
└── archive/  (OLD FILES - organized by date)
    ├── 2026-02-08/
    └── 2026-02-09/
```

---

## Naming Convention

### Format
```
[YYYY-MM-DD]-[project-name]-[output-type]-[HHMMSS].[ext]
```

### Components
- **Date**: `YYYY-MM-DD` (sortable, clear)
- **Project**: `wink`, `floydada`, etc. (lowercase, hyphenated)
- **Type**: `results`, `maintenance-estimate`, `review-queue`
- **Timestamp**: `HHMMSS` (optional, for multiple runs per day)
- **Extension**: `.csv`, `.xlsx`

### Examples
```bash
# Geocoded results
2026-02-09-wink-results-145235.csv

# Maintenance estimate
2026-02-09-wink-maintenance-estimate-145235.xlsx

# Review queue
2026-02-09-wink-review-queue-145235.csv

# With project variant
2026-02-09-floydada-klaasmeyer-results-152230.csv
```

---

## "latest" Symlink Strategy

Each project's `outputs/latest/` directory contains symlinks to the most recent outputs:

```bash
projects/wink/outputs/latest/
├── results.csv -> ../2026-02-09-wink-results-145235.csv
├── estimate.xlsx -> ../2026-02-09-wink-maintenance-estimate-145235.xlsx
└── review-queue.csv -> ../2026-02-09-wink-review-queue-145235.csv
```

**Benefits:**
- Easy reference: `projects/wink/outputs/latest/results.csv`
- Always points to most recent run
- Preserves full history
- Scripts can use stable paths

---

## File Inventory and Cleanup Actions

### Root Directory Files (TO ARCHIVE)
```
❌ geometric_results_merged.csv          → archive/2026-02-08/
❌ geometric_results.csv                 → archive/2026-02-08/
❌ proximity_results_baseline.csv        → archive/2026-02-08/
❌ proximity_results_before_phase1.csv   → archive/2026-02-08/
❌ proximity_results.csv                 → archive/2026-02-08/
❌ review_queue_20260209_144757.csv      → archive/2026-02-09/
❌ review_queue_20260209_145235.csv      → archive/2026-02-09/
```

### outputs/ Directory (TO REORGANIZE)
```
❌ outputs/wink_full_results.csv         → projects/wink/outputs/2026-02-09-wink-results-145235.csv
❌ outputs/wink_full_results_fixed.csv   → DELETE (superseded)
❌ outputs/wink_maintenance_estimate_full.xlsx → projects/wink/outputs/2026-02-09-wink-maintenance-estimate-145235.xlsx
❌ outputs/wink_maintenance_estimate_test.xlsx → archive/2026-02-09/
❌ outputs/pipeline_cache.db             → DELETE (cache file in wrong place)
```

### projects/floydada/outputs/ (TO RENAME)
```
❌ floydada_results.csv                  → 2026-02-09-floydada-results-144757.csv
❌ floydada_maintenance_estimate.xlsx    → 2026-02-09-floydada-maintenance-estimate-144757.xlsx
```

---

## Cleanup Script

**File:** `cleanup_outputs.sh`

```bash
#!/bin/bash
# Output structure cleanup and reorganization

set -e

DATE=$(date +%Y-%m-%d)
ARCHIVE_DIR="archive/$DATE"

echo "🧹 Output Structure Cleanup"
echo "=========================="
echo

# Create directories
echo "Creating directory structure..."
mkdir -p "$ARCHIVE_DIR"
mkdir -p projects/wink/outputs/latest
mkdir -p projects/floydada/outputs/latest
echo "✓ Directories created"
echo

# Archive old root files
echo "Archiving old files from root..."
mv -v geometric_results*.csv "$ARCHIVE_DIR/" 2>/dev/null || true
mv -v proximity_results*.csv "$ARCHIVE_DIR/" 2>/dev/null || true
mv -v review_queue_*.csv "$ARCHIVE_DIR/" 2>/dev/null || true
echo "✓ Root files archived"
echo

# Reorganize outputs/ directory
echo "Reorganizing outputs/ directory..."
if [ -f "outputs/wink_full_results.csv" ]; then
    mv -v outputs/wink_full_results.csv projects/wink/outputs/2026-02-09-wink-results-145235.csv
fi

if [ -f "outputs/wink_maintenance_estimate_full.xlsx" ]; then
    mv -v outputs/wink_maintenance_estimate_full.xlsx projects/wink/outputs/2026-02-09-wink-maintenance-estimate-145235.xlsx
fi

# Archive superseded files
mv -v outputs/wink_full_results_fixed.csv "$ARCHIVE_DIR/" 2>/dev/null || true
mv -v outputs/wink_maintenance_estimate_test.xlsx "$ARCHIVE_DIR/" 2>/dev/null || true
rm -f outputs/pipeline_cache.db
echo "✓ outputs/ reorganized"
echo

# Rename Floydada files
echo "Renaming Floydada files..."
cd projects/floydada/outputs
if [ -f "floydada_results.csv" ]; then
    mv -v floydada_results.csv 2026-02-09-floydada-results-144757.csv
fi
if [ -f "floydada_maintenance_estimate.xlsx" ]; then
    mv -v floydada_maintenance_estimate.xlsx 2026-02-09-floydada-maintenance-estimate-144757.xlsx
fi
cd ../../..
echo "✓ Floydada files renamed"
echo

# Create symlinks for latest
echo "Creating 'latest' symlinks..."

# Wink latest
cd projects/wink/outputs/latest
ln -sf ../2026-02-09-wink-results-145235.csv results.csv
ln -sf ../2026-02-09-wink-maintenance-estimate-145235.xlsx estimate.xlsx
cd ../../../..

# Floydada latest (will update when new run completes)
cd projects/floydada/outputs/latest
ln -sf ../2026-02-09-floydada-results-144757.csv results.csv
ln -sf ../2026-02-09-floydada-maintenance-estimate-144757.xlsx estimate.xlsx
cd ../../../..

echo "✓ Symlinks created"
echo

# Remove empty outputs/ directory if empty
if [ -d "outputs" ] && [ -z "$(ls -A outputs)" ]; then
    rmdir outputs
    echo "✓ Removed empty outputs/ directory"
fi

echo
echo "=========================="
echo "✅ Cleanup complete!"
echo
echo "New structure:"
echo "  projects/wink/outputs/latest/results.csv"
echo "  projects/wink/outputs/latest/estimate.xlsx"
echo "  projects/floydada/outputs/latest/results.csv"
echo "  projects/floydada/outputs/latest/estimate.xlsx"
echo
echo "Archived files in: $ARCHIVE_DIR/"
```

---

## Updated CLI Integration

### Changes to `geocoding_pipeline/cli.py`

**Current:**
```python
output_path = args.output or Path(f'pipeline_results_{timestamp}.csv')
```

**New:**
```python
from datetime import datetime

# Extract project name from config or path
project_name = "pipeline"
if args.config:
    project_name = args.config.stem.replace('_project_full', '').replace('_', '-')

# Generate standardized filename
date_str = datetime.now().strftime('%Y-%m-%d')
time_str = timestamp.split('_')[1]  # Extract HHMMSS from existing timestamp
output_path = args.output or Path(f'projects/{project_name}/outputs/{date_str}-{project_name}-results-{time_str}.csv')

# Ensure output directory exists
output_path.parent.mkdir(parents=True, exist_ok=True)
```

**For review queue:**
```python
review_queue_path = Path(f'projects/{project_name}/outputs/{date_str}-{project_name}-review-queue-{time_str}.csv')
```

**For maintenance estimate:**
```python
estimate_path = args.estimate_output or Path(f'projects/{project_name}/outputs/{date_str}-{project_name}-maintenance-estimate-{time_str}.xlsx')
```

**Update latest symlinks:**
```python
def update_latest_symlinks(project_name, output_files):
    """Update 'latest' symlinks to point to newest outputs."""
    latest_dir = Path(f'projects/{project_name}/outputs/latest')
    latest_dir.mkdir(parents=True, exist_ok=True)

    for output_type, file_path in output_files.items():
        symlink_name = latest_dir / f"{output_type}.{file_path.suffix[1:]}"
        if symlink_name.exists() or symlink_name.is_symlink():
            symlink_name.unlink()
        symlink_name.symlink_to(f"../{file_path.name}")
```

---

## Migration Checklist

### Phase 1: Archive Old Files (Safe)
- [ ] Run cleanup script to archive root directory files
- [ ] Move outputs/ files to project directories
- [ ] Rename project files to new convention
- [ ] Verify archived files are accessible

### Phase 2: Update CLI (Code Changes)
- [ ] Implement standardized naming in cli.py
- [ ] Add project directory resolution
- [ ] Implement latest symlink creation
- [ ] Test with sample run

### Phase 3: Documentation
- [ ] Update README with new output structure
- [ ] Update USAGE.md examples
- [ ] Add OUTPUT_STRUCTURE.md guide

### Phase 4: Ongoing Maintenance
- [ ] Archive files older than 30 days (manual or cron)
- [ ] Monitor disk usage
- [ ] Clean cache directories periodically

---

## Benefits of New Structure

✅ **Clear organization**: All project outputs in one place
✅ **Easy to find latest**: Symlinks in `latest/` directory
✅ **Chronological history**: Date-sorted filenames
✅ **No confusion**: Standardized naming eliminates ambiguity
✅ **Simple cleanup**: Old files easy to identify and archive
✅ **Script-friendly**: Stable paths for automation

---

## Example Usage After Cleanup

```bash
# Access latest Wink results
cat projects/wink/outputs/latest/results.csv

# Access latest Wink estimate
open projects/wink/outputs/latest/estimate.xlsx

# List all Wink runs
ls -lt projects/wink/outputs/*.csv

# Archive old runs (older than 30 days)
find projects/wink/outputs -name "*.csv" -mtime +30 -exec mv {} archive/ \;

# Run pipeline with auto-naming
python cli.py --config configs/wink_project_full.yaml projects/wink/tickets/
# Outputs to: projects/wink/outputs/YYYY-MM-DD-wink-results-HHMMSS.csv
```

---

## Next Steps

1. **Review this plan** and provide feedback
2. **Run cleanup script** to reorganize existing files
3. **Update CLI code** to implement new naming
4. **Test** with new Floydada run (currently in progress)
5. **Document** new structure for team

---

*Last Updated: 2026-02-09*
