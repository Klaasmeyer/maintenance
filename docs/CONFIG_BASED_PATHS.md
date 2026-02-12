# Configuration-Based Path Management

**Date:** February 11, 2026

## Overview

All project paths are now managed through YAML configuration files, eliminating hard-coded paths and enabling flexible project organization.

## Configuration System

### Location
All project configurations are stored in: `config/projects/`

### Structure

Each project has a YAML configuration file with the following structure:

```yaml
name: "Project Name"
config_version: 2
project_root: "projects/project_name"

cache:
  db_path: "${project_root}/cache/geocoding_cache.db"

output_dir: "${project_root}/outputs"

# Route configuration for estimates
route:
  kmz_path: "${project_root}/route/route_file.kmz"
  buffer_distance_m: 500

# Estimate output settings
estimates:
  results_csv: "${project_root}/outputs/results.csv"
  estimate_xlsx: "${project_root}/outputs/maintenance_estimate.xlsx"
```

## Template Variables

The config system supports template variable substitution:

- `${project_root}` - Resolves to the project's root directory
- `${HOME}` - Resolves to user's home directory
- `${ENV_VAR}` - Any environment variable

## Project Configurations

### Wink Project
**Config:** `config/projects/wink_project_full.yaml`
- **Project Root:** `projects/wink`
- **Cache:** `projects/wink/cache/geocoding_cache.db`
- **Outputs:** `projects/wink/outputs/`
- **Route:** `projects/wink/route/wink.kmz`

### Floydada Project
**Config:** `config/projects/floydada_project.yaml`
- **Project Root:** `projects/floydada`
- **Cache:** `projects/floydada/cache/geocoding_cache.db`
- **Outputs:** `projects/floydada/outputs/`
- **Route:** `projects/floydada/route/Klaasmeyer - Floydada.kmz`

## Usage

### Regenerating Estimates

The estimate regeneration script now reads all paths from project configs:

```bash
# Regenerate all projects
PYTHONPATH=src ./venv/bin/python src/tools/estimates/regenerate_estimates.py

# Or regenerate a specific project
PYTHONPATH=src ./venv/bin/python -c "
from pathlib import Path
from tools.estimates.regenerate_estimates import regenerate_estimate_from_config
regenerate_estimate_from_config(Path('config/projects/wink_project_full.yaml'))
"
```

### Adding a New Project

1. Create a new config file in `config/projects/`:

```yaml
name: "New Project Name"
config_version: 2
project_root: "projects/new_project"

cache:
  db_path: "${project_root}/cache/geocoding_cache.db"

output_dir: "${project_root}/outputs"

route:
  kmz_path: "${project_root}/route/route.kmz"
  buffer_distance_m: 500

estimates:
  results_csv: "${project_root}/outputs/results.csv"
  estimate_xlsx: "${project_root}/outputs/maintenance_estimate.xlsx"
```

2. Add the config to `regenerate_estimates.py`:

```python
project_configs = [
    config_dir / "wink_project_full.yaml",
    config_dir / "floydada_project.yaml",
    config_dir / "new_project.yaml",  # Add here
]
```

## Benefits

✓ **No Hard-Coded Paths** - All paths configured centrally
✓ **Flexible Organization** - Projects can be organized anywhere
✓ **Easy Maintenance** - Update paths in one place
✓ **Environment Agnostic** - Works across different systems
✓ **Template Variables** - Dynamic path resolution
✓ **Consistent Structure** - All projects follow same pattern

## Migration

All estimate generation scripts have been refactored:
- ❌ **Before:** Hard-coded paths like `"projects/wink/outputs/..."`
- ✅ **After:** Config-based paths from YAML files

## Files Modified

- `config/projects/wink_project_full.yaml` - Added route and estimates sections
- `config/projects/floydada_project.yaml` - Created new config file
- `src/tools/estimates/regenerate_estimates.py` - Refactored to use configs
- `src/kcci_maintenance/config_manager.py` - Already supports this pattern

## Configuration Manager

The `ConfigManager` class handles:
- YAML loading and validation
- Template variable substitution (`${var}` syntax)
- Path resolution relative to project roots
- Environment variable expansion

See `src/kcci_maintenance/config_manager.py` for implementation details.
