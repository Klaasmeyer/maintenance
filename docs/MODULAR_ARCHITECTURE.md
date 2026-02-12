# Modular Architecture for Downstream Integration

**Date:** February 11, 2026

## Overview

This document outlines the modular architecture for consuming ticket data in downstream systems including:
- Interactive project maps for client presentations
- Constructured Osprey Strike integration
- Intelligent patrol planning
- Texas 811 early dig warning integration

## Design Principles

1. **Separation of Concerns** - Data processing, analysis, and visualization are decoupled
2. **Standard Formats** - Use industry-standard geospatial formats (GeoJSON, GeoPackage, MVT)
3. **API-First** - Design data access layer that can be consumed via API or direct export
4. **Incremental Updates** - Support both full exports and incremental updates
5. **Real-time Ready** - Architecture supports streaming data for 811 integration

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                   Downstream Consumers                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Web Maps    │  │  Osprey      │  │  811 Monitor │      │
│  │  (Client)    │  │  Strike      │  │  (Real-time) │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ GeoJSON, GeoPackage, API
                            │
┌─────────────────────────────────────────────────────────────┐
│              Data Export & API Layer (NEW)                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  - Ticket Data Exporter (GeoJSON, GeoPackage)        │  │
│  │  - Heat Map Generator (density grids, contours)      │  │
│  │  - Statistics Aggregator (by type, time, location)   │  │
│  │  - Route Corridor Publisher                          │  │
│  │  - Real-time Event Stream (future: 811 webhooks)     │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │
┌─────────────────────────────────────────────────────────────┐
│           Analysis & Processing Layer (CURRENT)              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  - Geocoding Pipeline                                 │  │
│  │  - Route Assignment                                   │  │
│  │  - Ticket Classification                              │  │
│  │  - Cost Estimation                                    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │
┌─────────────────────────────────────────────────────────────┐
│              Data Storage Layer (CURRENT)                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  - Cache DB (SQLite with spatialite)                 │  │
│  │  - GeoPackage (route corridors, roads)               │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Modular Components

### 1. Data Export Module (`src/kcci_maintenance/export/`)

**Purpose:** Convert processed ticket data into consumable formats

**Components:**
```
export/
├── __init__.py
├── geojson_exporter.py      # Export tickets as GeoJSON
├── geopackage_exporter.py   # Export to GeoPackage for GIS
├── heatmap_generator.py     # Generate heat map data
├── statistics_aggregator.py # Aggregate by time, type, location
└── tile_generator.py        # Generate vector tiles (MVT) for web maps
```

**Key Exports:**
- **tickets.geojson** - All ticket points with properties
- **tickets_by_type.geojson** - Separate layers per ticket type
- **heatmap_density.geojson** - Hexbin or grid density data
- **route_corridors.geojson** - Route buffers and leg geometry
- **statistics.json** - Aggregated stats (time series, type distributions)
- **project.gpkg** - All-in-one GeoPackage for GIS software

### 2. Heat Map Generator

**Outputs:**
- **Hexbin Grid** - Hexagonal bins with ticket counts
- **Kernel Density** - Smooth density surface
- **Temporal Heat Maps** - Density by time period (month, season, year)
- **Risk Zones** - High-density areas flagged for patrol priority

**Configuration:**
```yaml
heatmap:
  grid_type: hexbin        # hexbin, square, or kernel
  resolution_m: 500        # Grid cell size in meters
  temporal_bins:
    - monthly
    - seasonal
    - yearly
  output_format: geojson   # geojson, gpkg, or mvt
```

### 3. Interactive Map Data Bundle

**Structure:**
```
exports/
└── {project_name}/
    ├── manifest.json                 # Metadata and layer definitions
    ├── layers/
    │   ├── tickets_all.geojson      # All tickets
    │   ├── tickets_normal.geojson   # Normal tickets only
    │   ├── tickets_emergency.geojson # Emergency tickets
    │   ├── heatmap_hexbin.geojson   # Hexbin density
    │   ├── heatmap_kernel.geojson   # Kernel density contours
    │   ├── route_corridor.geojson   # Route with buffer zones
    │   └── route_legs.geojson       # Individual route segments
    ├── statistics/
    │   ├── summary.json             # Overall stats
    │   ├── timeseries.json          # Ticket counts over time
    │   └── type_distribution.json   # Breakdown by type
    └── tiles/                       # Optional: vector tiles
        └── {z}/{x}/{y}.pbf          # For high-performance web maps
```

### 4. Manifest Format

**manifest.json:**
```json
{
  "project": "Floydada - Klaasmeyer",
  "generated": "2026-02-11T18:00:00Z",
  "bounds": {
    "west": -101.5,
    "south": 33.8,
    "east": -101.2,
    "north": 34.1
  },
  "layers": [
    {
      "id": "tickets_all",
      "type": "point",
      "source": "layers/tickets_all.geojson",
      "properties": {
        "ticket_number": "string",
        "ticket_type": "string",
        "created_at": "datetime",
        "confidence": "float",
        "work_type": "string"
      },
      "style": {
        "color": "#FF6B6B",
        "radius": 6
      }
    },
    {
      "id": "heatmap_hexbin",
      "type": "polygon",
      "source": "layers/heatmap_hexbin.geojson",
      "properties": {
        "ticket_count": "integer",
        "density": "float"
      },
      "style": {
        "colorScale": "YlOrRd",
        "opacity": 0.7
      }
    }
  ],
  "statistics": {
    "total_tickets": 785,
    "date_range": {
      "start": "2022-01-01",
      "end": "2025-12-31"
    },
    "ticket_types": {
      "Normal": 600,
      "Emergency": 150,
      "DigUp": 35
    }
  }
}
```

## Use Case Implementation

### Use Case 1: Interactive Web Map for Client Meetings

**Requirements:**
- Interactive ticket visualization
- Toggle layers (by type, by time period)
- Heat maps showing dig activity hotspots
- Route corridor overlay
- Click on ticket for details

**Export Command:**
```bash
python -m kcci_maintenance.export.map_bundle \
  --project floydada \
  --output exports/floydada_map \
  --include-heatmaps \
  --include-timeseries \
  --tile-format mvt
```

**Web Integration:**
```javascript
// Using Mapbox GL JS or Leaflet
const manifest = await fetch('exports/floydada_map/manifest.json');
const layers = manifest.layers;

// Add ticket layer
map.addLayer({
  id: 'tickets',
  type: 'circle',
  source: { type: 'geojson', data: 'exports/floydada_map/layers/tickets_all.geojson' },
  paint: {
    'circle-radius': 6,
    'circle-color': [
      'match',
      ['get', 'ticket_type'],
      'Emergency', '#FF0000',
      'Normal', '#4CAF50',
      'DigUp', '#FFC107',
      '#999999'
    ]
  }
});

// Add heat map
map.addLayer({
  id: 'heatmap',
  type: 'heatmap',
  source: { type: 'geojson', data: 'exports/floydada_map/layers/heatmap_kernel.geojson' }
});
```

### Use Case 2: Osprey Strike Integration

**Requirements:**
- GeoPackage with all project data
- Standardized schema compatible with OSP software
- Patrol zone definitions based on ticket density
- Maintenance cost estimates per segment

**Export Command:**
```bash
python -m kcci_maintenance.export.osprey \
  --project floydada \
  --output osprey_import/floydada.gpkg \
  --include-patrol-zones \
  --include-cost-estimates
```

**GeoPackage Structure:**
```
floydada.gpkg
├── tickets              # Point layer
├── route_segments       # LineString layer with cost estimates
├── patrol_zones         # Polygon layer (high-priority areas)
├── heat_zones           # Polygon layer with density ratings
└── metadata            # Project metadata table
```

**Schema:**
```sql
CREATE TABLE tickets (
  fid INTEGER PRIMARY KEY,
  ticket_number TEXT,
  ticket_type TEXT,
  created_at TEXT,
  work_type TEXT,
  route_leg TEXT,
  confidence REAL,
  geom POINT
);

CREATE TABLE route_segments (
  fid INTEGER PRIMARY KEY,
  segment_name TEXT,
  length_miles REAL,
  annual_tickets INTEGER,
  annual_cost_usd REAL,
  patrol_priority INTEGER,  -- 1=high, 2=medium, 3=low
  geom LINESTRING
);

CREATE TABLE patrol_zones (
  fid INTEGER PRIMARY KEY,
  zone_name TEXT,
  ticket_density REAL,     -- tickets per square km
  priority INTEGER,
  patrol_frequency TEXT,   -- e.g., "weekly", "monthly"
  geom POLYGON
);
```

### Use Case 3: Texas 811 Early Warning Integration

**Requirements:**
- Real-time or near-real-time ticket ingestion
- Spatial matching against route corridors
- Alert generation for tickets near infrastructure
- Historical context (past dig activity nearby)

**Architecture:**
```python
# Monitoring service
class Texas811Monitor:
    """Monitor Texas 811 for new tickets near infrastructure."""

    def __init__(self, config_path):
        self.config = load_config(config_path)
        self.route_corridors = load_route_corridors()
        self.historical_data = load_ticket_cache()

    def process_new_ticket(self, ticket_data):
        """Process incoming 811 ticket."""
        # Geocode ticket
        location = geocode_ticket(ticket_data)

        # Check proximity to routes
        nearby_routes = self.find_nearby_routes(location, buffer_m=500)

        if nearby_routes:
            # Get historical context
            history = self.get_historical_context(location, radius_m=1000)

            # Generate alert
            alert = {
                'ticket_number': ticket_data['ticket_number'],
                'location': location,
                'nearby_routes': nearby_routes,
                'historical_tickets': history['count'],
                'risk_level': self.calculate_risk(ticket_data, history),
                'patrol_recommended': True
            }

            # Send to Osprey Strike
            self.send_alert(alert)
```

**Configuration:**
```yaml
texas_811_monitor:
  enabled: true
  check_interval: 300  # seconds
  alert_buffer_m: 500  # Alert if ticket within 500m of route

  integrations:
    osprey_strike:
      enabled: true
      api_endpoint: "https://osprey.constructured.com/api/alerts"
      api_key: "${OSPREY_API_KEY}"

    email:
      enabled: true
      recipients:
        - "patrol@company.com"
        - "operations@company.com"
```

## Implementation Plan

### Phase 1: Core Export Module (Week 1)
- [ ] Create export module structure
- [ ] Implement GeoJSON exporter
- [ ] Implement statistics aggregator
- [ ] Add export CLI command

### Phase 2: Heat Map Generation (Week 1-2)
- [ ] Implement hexbin grid generator
- [ ] Implement kernel density estimation
- [ ] Add temporal heat maps (monthly, seasonal)
- [ ] Generate risk zones from density

### Phase 3: Interactive Map Bundle (Week 2)
- [ ] Create manifest generator
- [ ] Build complete map data bundle exporter
- [ ] Add example HTML/JS map viewer
- [ ] Document web integration

### Phase 4: Osprey Strike Integration (Week 2-3)
- [ ] Design GeoPackage schema
- [ ] Implement GeoPackage exporter
- [ ] Add patrol zone generator
- [ ] Create import scripts for Osprey

### Phase 5: Real-time Monitoring (Week 3-4)
- [ ] Design 811 monitoring service
- [ ] Implement spatial matching
- [ ] Build alert generation
- [ ] Add Osprey Strike webhook integration

## API Design (Future)

**REST Endpoints:**
```
GET  /api/projects                      # List all projects
GET  /api/projects/{id}/tickets         # Get tickets (with filters)
GET  /api/projects/{id}/heatmap         # Get heat map data
GET  /api/projects/{id}/statistics      # Get aggregated stats
GET  /api/projects/{id}/route           # Get route corridor
POST /api/tickets/geocode               # Geocode new ticket
POST /api/alerts/811                    # Webhook for 811 tickets
```

**Example Request:**
```bash
# Get tickets from last 30 days within 500m of route
curl "https://api.company.com/api/projects/floydada/tickets?\
  date_from=2026-01-11&\
  date_to=2026-02-11&\
  near_route=true&\
  buffer_m=500"
```

## Configuration

Add to project YAML configs:

```yaml
# Export settings
exports:
  enabled: true
  output_dir: "${project_root}/exports"

  formats:
    - geojson
    - geopackage
    - vector_tiles

  layers:
    - tickets_all
    - tickets_by_type
    - heatmap_hexbin
    - heatmap_kernel
    - route_corridor

  heatmap:
    grid_type: hexbin
    resolution_m: 500
    temporal_bins:
      - monthly
      - seasonal

  osprey_strike:
    enabled: true
    include_patrol_zones: true
    patrol_priority_threshold: 10  # tickets/mile/year

  real_time:
    enabled: false  # Future
    texas_811:
      api_url: "${TEXAS_811_API}"
      check_interval: 300
```

## Benefits

✓ **Decoupled Architecture** - Data processing independent of visualization
✓ **Multiple Consumers** - Same data feeds web maps, GIS, and APIs
✓ **Standard Formats** - GeoJSON, GeoPackage work with all tools
✓ **Real-time Ready** - Architecture supports streaming updates
✓ **Extensible** - Easy to add new export formats or integrations
✓ **Client-Ready** - Beautiful interactive maps for presentations
✓ **Operations-Ready** - Integration with patrol planning and monitoring

## Next Steps

1. **Review Architecture** - Validate approach with team
2. **Prioritize Use Cases** - Which integration is most valuable first?
3. **Implement Phase 1** - Start with core export module
4. **Prototype Web Map** - Build example interactive map
5. **Design Osprey Schema** - Work with Constructured on integration spec
