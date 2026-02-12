# Export System Quick Start Guide

**Date:** February 11, 2026

## Overview

The export system makes ticket data modular and consumable by downstream systems including web maps, Osprey Strike, and real-time 811 monitoring.

## Quick Export

Export a complete map data bundle for a project:

```bash
# Export Floydada map bundle
PYTHONPATH=src python src/tools/export/export_map_bundle.py \
  --config config/projects/floydada_project.yaml \
  --output exports/floydada_map

# Export Wink map bundle
PYTHONPATH=src python src/tools/export/export_map_bundle.py \
  --config config/projects/wink_project_full.yaml \
  --output exports/wink_map
```

## Output Structure

```
exports/floydada_map/
├── manifest.json                      # Layer catalog and metadata
├── layers/                            # GeoJSON layers
│   ├── tickets_all.geojson           # All tickets
│   ├── tickets_normal.geojson        # Normal tickets only
│   ├── tickets_emergency.geojson     # Emergency tickets only
│   └── route_corridor.geojson        # Route with buffer
├── statistics/                        # Aggregated data
│   ├── summary.json                  # Overall statistics
│   ├── timeseries.json               # Tickets over time
│   ├── type_distribution.json        # Breakdown by type
│   └── spatial_distribution.json     # Per-route-leg stats
└── heatmaps/                         # Heat map data
    ├── hexbin_500m.geojson           # Hexagonal density bins
    ├── kernel_density.geojson        # Smooth density surface
    └── risk_zones.geojson            # High-priority patrol areas
```

## Use Case Examples

### 1. Web Map for Client Meeting

**Export:**
```bash
PYTHONPATH=src python src/tools/export/export_map_bundle.py \
  --config config/projects/floydada_project.yaml \
  --output client_presentation/floydada
```

**HTML/JavaScript:**
```html
<!DOCTYPE html>
<html>
<head>
  <script src='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js'></script>
  <link href='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css' rel='stylesheet' />
</head>
<body>
  <div id='map' style='width: 100%; height: 600px;'></div>
  <script>
    mapboxgl.accessToken = 'YOUR_TOKEN';
    const map = new mapboxgl.Map({
      container: 'map',
      style: 'mapbox://styles/mapbox/streets-v11',
      center: [-101.35, 34.0],
      zoom: 10
    });

    map.on('load', async () => {
      // Load manifest
      const manifest = await fetch('floydada/manifest.json').then(r => r.json());

      // Add tickets layer
      map.addSource('tickets', {
        type: 'geojson',
        data: 'floydada/layers/tickets_all.geojson'
      });

      map.addLayer({
        id: 'tickets',
        type: 'circle',
        source: 'tickets',
        paint: {
          'circle-radius': 6,
          'circle-color': [
            'match',
            ['get', 'ticket_type'],
            'Emergency', '#ff0000',
            'Normal', '#4caf50',
            '#999999'
          ]
        }
      });

      // Add hexbin heat map
      map.addSource('heatmap', {
        type: 'geojson',
        data: 'floydada/heatmaps/hexbin_500m.geojson'
      });

      map.addLayer({
        id: 'heatmap',
        type: 'fill',
        source: 'heatmap',
        paint: {
          'fill-color': [
            'interpolate',
            ['linear'],
            ['get', 'ticket_count'],
            0, '#ffffcc',
            10, '#feb24c',
            50, '#f03b20'
          ],
          'fill-opacity': 0.6
        }
      });

      // Add click handler
      map.on('click', 'tickets', (e) => {
        const props = e.features[0].properties;
        new mapboxgl.Popup()
          .setLngLat(e.lngLat)
          .setHTML(`
            <strong>Ticket #${props.ticket_number}</strong><br>
            Type: ${props.ticket_type}<br>
            Work: ${props.work_type}<br>
            Date: ${props.created_at}
          `)
          .addTo(map);
      });
    });
  </script>
</body>
</html>
```

### 2. Osprey Strike Integration

**Export GeoPackage:**
```python
from kcci_maintenance.export import GeoPackageExporter

exporter = GeoPackageExporter()
exporter.export_for_osprey(
    tickets_df=tickets_df,
    route_gdf=route_gdf,
    output_path='osprey_import/floydada.gpkg',
    include_patrol_zones=True
)
```

**Import into Osprey Strike:**
1. Open Osprey Strike
2. Go to Data → Import → GeoPackage
3. Select `floydada.gpkg`
4. Map fields:
   - `tickets` layer → Locate Events
   - `patrol_zones` layer → Patrol Routes
   - `route_segments` layer → Asset Segments

### 3. Programmatic Access

**Python:**
```python
import json
import geopandas as gpd

# Load manifest
with open('exports/floydada_map/manifest.json') as f:
    manifest = json.load(f)

# Load tickets
tickets_gdf = gpd.read_file('exports/floydada_map/layers/tickets_all.geojson')

# Filter to emergency tickets
emergency = tickets_gdf[tickets_gdf['ticket_type'] == 'Emergency']

# Load statistics
with open('exports/floydada_map/statistics/summary.json') as f:
    stats = json.load(f)

print(f"Total tickets: {stats['total_tickets']}")
print(f"Emergency tickets: {len(emergency)}")
```

**JavaScript/Node.js:**
```javascript
const fs = require('fs');

// Load manifest
const manifest = JSON.parse(
  fs.readFileSync('exports/floydada_map/manifest.json', 'utf8')
);

// Load tickets
const tickets = JSON.parse(
  fs.readFileSync('exports/floydada_map/layers/tickets_all.geojson', 'utf8')
);

console.log(`Loaded ${tickets.features.length} tickets`);
```

## Python API Usage

### Export Specific Layers

```python
from kcci_maintenance.export import GeoJSONExporter, HeatMapGenerator
import pandas as pd

# Initialize
exporter = GeoJSONExporter(output_dir='my_exports')
heatmap = HeatMapGenerator(output_dir='my_exports')

# Load your data
tickets_df = pd.read_csv('tickets.csv')

# Export all tickets
exporter.export_tickets(tickets_df, output_name='all_tickets.geojson')

# Export emergency only
exporter.export_tickets(
    tickets_df,
    output_name='emergency_only.geojson',
    filter_by={'ticket_type': 'Emergency'}
)

# Generate heat map
heatmap.generate_hexbin(tickets_df, resolution_m=1000)
```

### Generate Statistics

```python
from kcci_maintenance.export import StatisticsAggregator

aggregator = StatisticsAggregator(output_dir='stats')

# Overall summary
aggregator.generate_summary(tickets_df)

# Time series (monthly)
aggregator.generate_timeseries(tickets_df, bin_type='monthly')

# Type distribution
aggregator.generate_type_distribution(tickets_df, group_by='work_type')
```

## Advanced: Real-time 811 Monitoring

**Monitor Service (Future):**
```python
from kcci_maintenance.monitoring import Texas811Monitor

# Initialize monitor
monitor = Texas811Monitor(config_path='config/monitoring/texas811.yaml')

# Start monitoring
monitor.start()

# The monitor will:
# 1. Poll Texas 811 API for new tickets
# 2. Geocode incoming tickets
# 3. Check proximity to route corridors
# 4. Send alerts to Osprey Strike
# 5. Update heat maps and statistics
```

**Configuration:**
```yaml
# config/monitoring/texas811.yaml
monitor_name: "Texas 811 Watcher - Floydada"

polling:
  interval_seconds: 300
  api_url: "${TEXAS_811_API_URL}"
  api_key: "${TEXAS_811_API_KEY}"

projects:
  - config: config/projects/floydada_project.yaml
    alert_buffer_m: 500

integrations:
  osprey_strike:
    enabled: true
    webhook_url: "${OSPREY_WEBHOOK_URL}"

  email:
    enabled: true
    smtp_server: smtp.gmail.com
    recipients:
      - patrol@company.com
```

## Command Reference

### Export Complete Bundle
```bash
python src/tools/export/export_map_bundle.py \
  --config CONFIG_PATH \
  --output OUTPUT_DIR \
  [--no-heatmaps] \
  [--no-timeseries] \
  [--tiles]
```

### Options
- `--config` - Project YAML configuration (required)
- `--output` - Output directory for bundle (required)
- `--no-heatmaps` - Skip heat map generation
- `--no-timeseries` - Skip time series data
- `--tiles` - Generate vector tiles (future feature)

## Integration Checklist

### For Client Presentations
- [ ] Export map bundle with heat maps
- [ ] Test HTML viewer locally
- [ ] Prepare legend and layer controls
- [ ] Add popup templates for ticket details
- [ ] Test on client's network/browser

### For Osprey Strike
- [ ] Export GeoPackage with patrol zones
- [ ] Verify schema compatibility
- [ ] Test import in Osprey Strike
- [ ] Configure field mappings
- [ ] Set up automated updates (if needed)

### For 811 Monitoring
- [ ] Configure monitoring service
- [ ] Set up API credentials
- [ ] Test alert delivery
- [ ] Configure patrol response workflow
- [ ] Document escalation procedures

## Troubleshooting

**Issue:** "No tickets found"
- Check cache database path in config
- Verify tickets have lat/lon coordinates
- Run geocoding pipeline first

**Issue:** "Route not found"
- Check `route.kmz_path` in config
- Verify KMZ file exists
- Check file permissions

**Issue:** "Module not found"
- Ensure PYTHONPATH includes `src/`
- Activate virtual environment: `source venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`

## Support

For questions or issues:
1. Check documentation in `docs/`
2. Review example configs in `config/projects/`
3. See full architecture in `docs/MODULAR_ARCHITECTURE.md`
