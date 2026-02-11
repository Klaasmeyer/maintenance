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
mv -v geometric_results*.csv "$ARCHIVE_DIR/" 2>/dev/null || echo "  (no geometric_results files)"
mv -v proximity_results*.csv "$ARCHIVE_DIR/" 2>/dev/null || echo "  (no proximity_results files)"
mv -v review_queue_*.csv "$ARCHIVE_DIR/" 2>/dev/null || echo "  (no review_queue files)"
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
mv -v outputs/wink_full_results_fixed.csv "$ARCHIVE_DIR/" 2>/dev/null || echo "  (no fixed results)"
mv -v outputs/wink_maintenance_estimate_test.xlsx "$ARCHIVE_DIR/" 2>/dev/null || echo "  (no test estimate)"
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
if [ -f "../2026-02-09-floydada-results-144757.csv" ]; then
    ln -sf ../2026-02-09-floydada-results-144757.csv results.csv
fi
if [ -f "../2026-02-09-floydada-maintenance-estimate-144757.xlsx" ]; then
    ln -sf ../2026-02-09-floydada-maintenance-estimate-144757.xlsx estimate.xlsx
fi
cd ../../../..

echo "✓ Symlinks created"
echo

# Remove empty outputs/ directory if empty
if [ -d "outputs" ] && [ -z "$(ls -A outputs 2>/dev/null)" ]; then
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
echo "  projects/floydada/outputs/latest/ (pending completion)"
echo
echo "Archived files in: $ARCHIVE_DIR/"
echo
echo "To access latest files:"
echo "  cat projects/wink/outputs/latest/results.csv"
echo "  open projects/wink/outputs/latest/estimate.xlsx"
