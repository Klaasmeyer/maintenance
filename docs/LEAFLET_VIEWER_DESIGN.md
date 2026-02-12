# Leaflet Map Viewer - Technical Design Document

**Project:** KCCI Maintenance Ticket Visualization
**Version:** 1.0
**Date:** February 11, 2026
**Status:** Design Phase

---

## Executive Summary

Design for a professional web-based interactive map viewer using Leaflet and OpenStreetMap to visualize maintenance tickets, pipeline routes, crossings, and analytics for all KCCI projects. Zero configuration required - works immediately when opened in a browser.

### Key Goals

1. **Zero Setup:** No API keys, accounts, or installation required
2. **Multi-Project:** Support all projects (Floydada, Wink, future projects)
3. **Rich Visualization:** Tickets, heat maps, routes, crossings with interactive controls
4. **Timeline Analysis:** Animate tickets over time with playback controls
5. **Professional UX:** Polished interface suitable for client presentations
6. **Offline Capable:** Works without internet after initial load

---

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Browser (Client)                       │
│  ┌───────────────────────────────────────────────────┐  │
│  │              HTML/CSS/JavaScript                   │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │           Leaflet Map Viewer                 │  │  │
│  │  │  ┌────────────┬────────────┬──────────────┐ │  │  │
│  │  │  │ Layer Mgr  │ Timeline   │ Statistics   │ │  │  │
│  │  │  └────────────┴────────────┴──────────────┘ │  │  │
│  │  │  ┌────────────────────────────────────────┐ │  │  │
│  │  │  │      Leaflet.js Core                   │ │  │  │
│  │  │  └────────────────────────────────────────┘ │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
│         ↓                    ↓                    ↓      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   GeoJSON    │  │     KMZ      │  │ OSM Tiles    │  │
│  │   Files      │  │   Routes     │  │ (External)   │  │
│  │  (Local)     │  │  (Local)     │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Component Architecture

```
┌────────────────────────────────────────────────────────┐
│                  index.html (Single Page)               │
├────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────────────────────────────────────┐ │
│  │  UI Layer                                         │ │
│  │  ├─ LayerControlPanel      (toggle visibility)   │ │
│  │  ├─ TimelineSlider         (temporal filter)     │ │
│  │  ├─ StatisticsPanel        (live metrics)        │ │
│  │  ├─ Legend                 (symbology)           │ │
│  │  ├─ SearchBar              (find features)       │ │
│  │  └─ ExportTools            (save/share)          │ │
│  └──────────────────────────────────────────────────┘ │
│                       ↓                                 │
│  ┌──────────────────────────────────────────────────┐ │
│  │  Data Layer                                       │ │
│  │  ├─ DataLoader             (load GeoJSON/KMZ)    │ │
│  │  ├─ ProjectManager         (multi-project)       │ │
│  │  ├─ FeatureStyler          (apply symbology)     │ │
│  │  ├─ FilterEngine           (date/type/etc)       │ │
│  │  └─ CacheManager           (in-memory cache)     │ │
│  └──────────────────────────────────────────────────┘ │
│                       ↓                                 │
│  ┌──────────────────────────────────────────────────┐ │
│  │  Rendering Layer                                  │ │
│  │  ├─ MapRenderer            (Leaflet instance)    │ │
│  │  ├─ MarkerClusterer        (point aggregation)   │ │
│  │  ├─ HeatMapRenderer        (density viz)         │ │
│  │  └─ PopupBuilder           (feature details)     │ │
│  └──────────────────────────────────────────────────┘ │
│                       ↓                                 │
│  ┌──────────────────────────────────────────────────┐ │
│  │  Leaflet.js + Plugins                             │ │
│  └──────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

---

## Data Model

### Project Structure

```javascript
{
  "projects": [
    {
      "id": "floydada",
      "name": "Floydada - Klaasmeyer",
      "color": "#9C27B0",  // Purple
      "bounds": {
        "west": -103.155,
        "south": 31.566,
        "east": -100.423,
        "north": 34.748
      },
      "dataSources": {
        "tickets": "exports/floydada_map/layers/tickets_all.geojson",
        "route": "projects/floydada/route/Klaasmeyer - Floydada.kmz",
        "crossings": "projects/floydada/crossings/crossings.geojson",
        "heatmaps": {
          "hexbin": "exports/floydada_map/heatmaps/hexbin_500m.geojson",
          "kernel": "exports/floydada_map/heatmaps/kernel_density.geojson"
        },
        "statistics": "exports/floydada_map/statistics/summary.json"
      },
      "statistics": {
        "totalTickets": 5255,
        "dateRange": {
          "start": "2024-01-01",
          "end": "2024-12-31"
        },
        "ticketTypes": {
          "Normal": 4019,
          "Emergency": 308,
          "DigUp": 42,
          "Update": 697
        }
      }
    },
    {
      "id": "wink",
      "name": "Wink",
      "color": "#FF5722",  // Deep Orange
      "bounds": { /* ... */ },
      "dataSources": { /* ... */ },
      "statistics": { /* ... */ }
    }
  ]
}
```

### Ticket Feature Schema

```javascript
{
  "type": "Feature",
  "geometry": {
    "type": "Point",
    "coordinates": [-101.5, 33.5]
  },
  "properties": {
    "ticket_number": "T12345",
    "ticket_type": "Emergency",
    "work_type": "Repair-Pole",
    "created_at": "2024-06-15T14:30:00",
    "city": "Floydada",
    "county": "Floyd",
    "confidence": 0.92,
    "route_leg": "Leg 1",
    "risk_score": 85,
    "project": "floydada"
  }
}
```

### Route Feature Schema

```javascript
{
  "type": "Feature",
  "geometry": {
    "type": "LineString",
    "coordinates": [
      [-101.5, 33.5],
      [-101.6, 33.6],
      [-101.7, 33.7]
    ]
  },
  "properties": {
    "name": "Floydada Main Route",
    "project": "floydada",
    "length_km": 125.4,
    "ticket_count": 245,
    "emergency_count": 12,
    "segment_id": "SEG_001"
  }
}
```

### Pipeline Crossing Feature Schema

```javascript
{
  "type": "Feature",
  "geometry": {
    "type": "Point",
    "coordinates": [-101.5234, 33.5678]
  },
  "properties": {
    "crossing_id": "CROSS_001",
    "pipeline_name": "XYZ Pipeline",
    "pipeline_operator": "Company ABC",
    "pipeline_id": "PL-12345",
    "route_name": "Floydada Main",
    "crossing_type": "overhead",  // or "underground"
    "crossing_method": "bore",     // or "aerial", "open-cut"
    "diameter_inches": 24,
    "material": "steel",
    "installation_date": "2020-03-15",
    "inspection_required": true,
    "last_inspection": "2024-01-10",
    "priority": "HIGH",            // or "MEDIUM", "LOW"
    "notes": "High pressure gas line, requires 48hr notice",
    "tickets_nearby": 5,           // Count of tickets within 500m
    "emergency_nearby": 1,         // Emergency tickets within 500m
    "project": "floydada"
  }
}
```

### Hexbin Feature Schema

```javascript
{
  "type": "Feature",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[/* hexagon vertices */]]
  },
  "properties": {
    "ticket_count": 15,
    "density": 2.5,  // tickets per km²
    "priority": "MEDIUM"
  }
}
```

---

## Layer Management

### Layer Hierarchy

```
Root
├── Basemap (OSM)
├── Projects
│   ├── Floydada
│   │   ├── Route Corridor
│   │   ├── Buffer Zone (500m)
│   │   ├── Pipeline Crossings
│   │   ├── Tickets
│   │   │   ├── All Tickets (clustered)
│   │   │   ├── Emergency
│   │   │   ├── Normal
│   │   │   ├── DigUp
│   │   │   └── Update
│   │   └── Heat Maps
│   │       ├── Hexbin Density
│   │       ├── Kernel Density
│   │       └── High Risk Zones
│   └── Wink
│       └── (same structure)
└── Overlays
    ├── Measurement Layer
    └── Search Results
```

### Layer State Management

```javascript
class LayerManager {
  constructor(map) {
    this.map = map;
    this.layers = new Map();
    this.visibility = new Map();
    this.cache = new Map();
  }

  addLayer(id, layer, options = {}) {
    this.layers.set(id, layer);
    this.visibility.set(id, options.visible ?? false);
    if (options.visible) {
      layer.addTo(this.map);
    }
  }

  toggleLayer(id) {
    const layer = this.layers.get(id);
    const visible = this.visibility.get(id);

    if (visible) {
      this.map.removeLayer(layer);
      this.visibility.set(id, false);
    } else {
      layer.addTo(this.map);
      this.visibility.set(id, true);
    }

    this.updateStatistics();
    this.updateLegend();
  }

  getVisibleFeatures() {
    const features = [];
    for (const [id, visible] of this.visibility) {
      if (visible) {
        const layer = this.layers.get(id);
        layer.eachLayer(f => features.push(f));
      }
    }
    return features;
  }
}
```

---

## Styling Specifications

### Ticket Markers

```javascript
const ticketStyles = {
  Emergency: {
    color: '#ff0000',
    fillColor: '#ff0000',
    fillOpacity: 0.8,
    radius: 6,
    weight: 2,
    className: 'ticket-emergency'
  },
  Normal: {
    color: '#4CAF50',
    fillColor: '#4CAF50',
    fillOpacity: 0.8,
    radius: 5,
    weight: 1,
    className: 'ticket-normal'
  },
  DigUp: {
    color: '#FFC107',
    fillColor: '#FFC107',
    fillOpacity: 0.8,
    radius: 5,
    weight: 1,
    className: 'ticket-digup'
  },
  Update: {
    color: '#2196F3',
    fillColor: '#2196F3',
    fillOpacity: 0.8,
    radius: 5,
    weight: 1,
    className: 'ticket-update'
  }
};

function styleTicket(feature) {
  return ticketStyles[feature.properties.ticket_type] || ticketStyles.Normal;
}
```

### Route Lines

```javascript
const routeStyles = {
  floydada: {
    color: '#9C27B0',
    weight: 4,
    opacity: 0.8,
    dashArray: null
  },
  wink: {
    color: '#FF5722',
    weight: 4,
    opacity: 0.8,
    dashArray: null
  }
};

// Buffer zones
const bufferStyle = {
  color: '#666',
  weight: 1,
  opacity: 0.3,
  fillColor: '#666',
  fillOpacity: 0.1,
  dashArray: '5, 5'
};
```

### Pipeline Crossing Markers

```javascript
const crossingIcon = L.divIcon({
  className: 'crossing-marker',
  html: `
    <svg width="24" height="24" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="10" fill="#E91E63" stroke="#fff" stroke-width="2"/>
      <path d="M6 6 L18 18 M18 6 L6 18" stroke="#fff" stroke-width="2"/>
    </svg>
  `,
  iconSize: [24, 24],
  iconAnchor: [12, 12],
  popupAnchor: [0, -12]
});

function createCrossingMarker(latlng, properties) {
  return L.marker(latlng, {
    icon: crossingIcon,
    title: properties.crossing_id,
    riseOnHover: true
  });
}
```

### Heat Map Gradient

```javascript
const heatMapGradient = {
  0.0: '#ffffcc',  // Light yellow
  0.2: '#ffeda0',
  0.4: '#feb24c',  // Orange
  0.6: '#fd8d3c',
  0.8: '#fc4e2a',
  1.0: '#e31a1c'   // Red
};

const hexbinStyle = {
  weight: 1,
  opacity: 0.6,
  color: '#666',
  fillOpacity: 0.6
};

function getHexbinColor(ticketCount) {
  // Map ticket count to gradient
  const normalized = Math.min(ticketCount / 50, 1.0);
  return interpolateColor(heatMapGradient, normalized);
}
```

---

## Timeline Implementation

### Timeline Controller

```javascript
class TimelineController {
  constructor(map, features) {
    this.map = map;
    this.features = features;
    this.currentDate = null;
    this.dateRange = this.calculateDateRange();
    this.playing = false;
    this.speed = 1000; // ms per step

    this.initUI();
  }

  calculateDateRange() {
    const dates = this.features
      .map(f => new Date(f.properties.created_at))
      .filter(d => !isNaN(d));

    return {
      start: new Date(Math.min(...dates)),
      end: new Date(Math.max(...dates)),
      step: 'day' // or 'week', 'month'
    };
  }

  initUI() {
    // Create slider HTML
    const slider = document.createElement('input');
    slider.type = 'range';
    slider.min = this.dateRange.start.getTime();
    slider.max = this.dateRange.end.getTime();
    slider.step = 86400000; // 1 day in ms

    slider.addEventListener('input', (e) => {
      this.setDate(new Date(parseInt(e.target.value)));
    });

    // Add play/pause button
    // Add speed controls
    // Add date display
  }

  setDate(date) {
    this.currentDate = date;
    this.filterFeaturesByDate(date);
    this.updateDisplay();
  }

  filterFeaturesByDate(date) {
    this.features.forEach(feature => {
      const featureDate = new Date(feature.properties.created_at);
      const visible = featureDate <= date;

      if (visible) {
        feature.addTo(this.map);
      } else {
        this.map.removeLayer(feature);
      }
    });
  }

  play() {
    this.playing = true;
    this.animate();
  }

  pause() {
    this.playing = false;
  }

  animate() {
    if (!this.playing) return;

    const nextDate = new Date(this.currentDate.getTime() + 86400000);

    if (nextDate > this.dateRange.end) {
      this.pause();
      return;
    }

    this.setDate(nextDate);
    setTimeout(() => this.animate(), this.speed);
  }
}
```

---

## Popup Templates

### Ticket Popup

```javascript
function createTicketPopup(properties) {
  return `
    <div class="popup-ticket">
      <h3 class="popup-header">
        <span class="ticket-icon ${properties.ticket_type.toLowerCase()}"></span>
        Ticket #${properties.ticket_number}
      </h3>
      <table class="popup-table">
        <tr>
          <td class="label">Type:</td>
          <td class="value">${properties.ticket_type}</td>
        </tr>
        <tr>
          <td class="label">Date:</td>
          <td class="value">${formatDate(properties.created_at)}</td>
        </tr>
        <tr>
          <td class="label">Work:</td>
          <td class="value">${properties.work_type}</td>
        </tr>
        <tr>
          <td class="label">Location:</td>
          <td class="value">${properties.city}, ${properties.county}</td>
        </tr>
        <tr>
          <td class="label">Risk Score:</td>
          <td class="value">
            <div class="risk-bar">
              <div class="risk-fill" style="width: ${properties.risk_score}%"></div>
              <span>${properties.risk_score}</span>
            </div>
          </td>
        </tr>
        <tr>
          <td class="label">Confidence:</td>
          <td class="value">${(properties.confidence * 100).toFixed(1)}%</td>
        </tr>
      </table>
      <div class="popup-actions">
        <button onclick="zoomToTicket('${properties.ticket_number}')">
          Zoom to Location
        </button>
        <button onclick="showNearbyTickets('${properties.ticket_number}')">
          Show Nearby
        </button>
      </div>
    </div>
  `;
}
```

### Pipeline Crossing Popup

```javascript
function createCrossingPopup(properties) {
  const warningClass = properties.priority === 'HIGH' ? 'warning-high' : '';

  return `
    <div class="popup-crossing ${warningClass}">
      <h3 class="popup-header">
        <span class="crossing-icon"></span>
        Pipeline Crossing
      </h3>
      <table class="popup-table">
        <tr>
          <td class="label">Crossing ID:</td>
          <td class="value">${properties.crossing_id}</td>
        </tr>
        <tr>
          <td class="label">Pipeline:</td>
          <td class="value">${properties.pipeline_name}</td>
        </tr>
        <tr>
          <td class="label">Operator:</td>
          <td class="value">${properties.pipeline_operator}</td>
        </tr>
        <tr>
          <td class="label">Route:</td>
          <td class="value">${properties.route_name}</td>
        </tr>
        <tr>
          <td class="label">Type:</td>
          <td class="value">${properties.crossing_type}</td>
        </tr>
        <tr>
          <td class="label">Diameter:</td>
          <td class="value">${properties.diameter_inches}"</td>
        </tr>
        <tr>
          <td class="label">Priority:</td>
          <td class="value">
            <span class="priority-badge ${properties.priority.toLowerCase()}">
              ${properties.priority}
            </span>
          </td>
        </tr>
        ${properties.inspection_required ? `
        <tr>
          <td class="label">Last Inspection:</td>
          <td class="value">${formatDate(properties.last_inspection)}</td>
        </tr>
        ` : ''}
        ${properties.tickets_nearby > 0 ? `
        <tr>
          <td class="label">Nearby Tickets:</td>
          <td class="value">
            ${properties.tickets_nearby}
            ${properties.emergency_nearby > 0 ?
              `<span class="emergency-count">(${properties.emergency_nearby} emergency)</span>`
              : ''}
          </td>
        </tr>
        ` : ''}
      </table>
      ${properties.notes ? `
        <div class="popup-notes">
          <strong>Notes:</strong> ${properties.notes}
        </div>
      ` : ''}
      <div class="popup-actions">
        <button onclick="showTicketsNearCrossing('${properties.crossing_id}')">
          Show Nearby Tickets
        </button>
        <button onclick="measureFromCrossing('${properties.crossing_id}')">
          Measure Distance
        </button>
      </div>
    </div>
  `;
}
```

### Route Popup

```javascript
function createRoutePopup(properties) {
  return `
    <div class="popup-route">
      <h3 class="popup-header">${properties.name}</h3>
      <table class="popup-table">
        <tr>
          <td class="label">Project:</td>
          <td class="value">${properties.project}</td>
        </tr>
        <tr>
          <td class="label">Length:</td>
          <td class="value">${properties.length_km.toFixed(1)} km</td>
        </tr>
        <tr>
          <td class="label">Tickets:</td>
          <td class="value">
            ${properties.ticket_count}
            ${properties.emergency_count > 0 ?
              `<span class="emergency-count">(${properties.emergency_count} emergency)</span>`
              : ''}
          </td>
        </tr>
      </table>
      <div class="popup-actions">
        <button onclick="showRouteTickets('${properties.segment_id}')">
          Show Tickets on Route
        </button>
        <button onclick="zoomToRoute('${properties.segment_id}')">
          Zoom to Route
        </button>
      </div>
    </div>
  `;
}
```

---

## Statistics Panel

### Statistics Calculator

```javascript
class StatisticsPanel {
  constructor(layerManager) {
    this.layerManager = layerManager;
    this.panel = document.getElementById('statistics-panel');
  }

  update() {
    const features = this.layerManager.getVisibleFeatures();

    const stats = {
      totalTickets: features.length,
      byType: this.countByType(features),
      byProject: this.countByProject(features),
      dateRange: this.getDateRange(features),
      avgRiskScore: this.getAvgRiskScore(features),
      emergencyCount: this.countEmergencies(features)
    };

    this.render(stats);
  }

  countByType(features) {
    const counts = {};
    features.forEach(f => {
      const type = f.feature.properties.ticket_type;
      counts[type] = (counts[type] || 0) + 1;
    });
    return counts;
  }

  render(stats) {
    this.panel.innerHTML = `
      <h3>📊 Statistics</h3>
      <div class="stat-row">
        <span class="stat-label">Total Tickets:</span>
        <span class="stat-value">${stats.totalTickets.toLocaleString()}</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Emergency:</span>
        <span class="stat-value emergency">${stats.emergencyCount}</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Avg Risk Score:</span>
        <span class="stat-value">${stats.avgRiskScore.toFixed(1)}</span>
      </div>
      <div class="stat-section">
        <h4>By Type</h4>
        ${Object.entries(stats.byType).map(([type, count]) => `
          <div class="stat-row">
            <span class="stat-label">${type}:</span>
            <span class="stat-value">${count}</span>
          </div>
        `).join('')}
      </div>
      <div class="stat-section">
        <h4>Date Range</h4>
        <div class="stat-row">
          <span class="stat-value">
            ${formatDate(stats.dateRange.start)} - ${formatDate(stats.dateRange.end)}
          </span>
        </div>
      </div>
    `;
  }
}
```

---

## Performance Optimization

### Marker Clustering

```javascript
// Use Leaflet.markercluster plugin
const markers = L.markerClusterGroup({
  maxClusterRadius: 50,
  spiderfyOnMaxZoom: true,
  showCoverageOnHover: false,
  zoomToBoundsOnClick: true,
  iconCreateFunction: function(cluster) {
    const count = cluster.getChildCount();
    let className = 'cluster-small';

    if (count > 100) className = 'cluster-large';
    else if (count > 10) className = 'cluster-medium';

    return L.divIcon({
      html: `<div><span>${count}</span></div>`,
      className: `marker-cluster ${className}`,
      iconSize: L.point(40, 40)
    });
  }
});

// Add markers to cluster group
tickets.forEach(ticket => {
  const marker = L.circleMarker([ticket.lat, ticket.lng], style);
  marker.bindPopup(createTicketPopup(ticket.properties));
  markers.addLayer(marker);
});

map.addLayer(markers);
```

### Lazy Loading

```javascript
class DataLoader {
  constructor() {
    this.cache = new Map();
    this.loading = new Set();
  }

  async loadLayer(layerId, url) {
    // Return cached if available
    if (this.cache.has(layerId)) {
      return this.cache.get(layerId);
    }

    // Don't load twice
    if (this.loading.has(layerId)) {
      return this.waitForLoad(layerId);
    }

    this.loading.add(layerId);

    try {
      const response = await fetch(url);
      const data = await response.json();
      this.cache.set(layerId, data);
      return data;
    } finally {
      this.loading.delete(layerId);
    }
  }

  async loadKMZ(url) {
    // Extract KML from KMZ
    const response = await fetch(url);
    const blob = await response.blob();
    const zip = await JSZip.loadAsync(blob);

    // Find KML file
    const kmlFile = Object.keys(zip.files).find(f => f.endsWith('.kml'));
    const kml = await zip.files[kmlFile].async('string');

    // Parse KML to GeoJSON
    const geojson = toGeoJSON.kml(new DOMParser().parseFromString(kml, 'text/xml'));

    return geojson;
  }
}
```

### Viewport-Based Loading

```javascript
// Only load data within current viewport
map.on('moveend', function() {
  const bounds = map.getBounds();
  loadVisibleData(bounds);
});

function loadVisibleData(bounds) {
  projects.forEach(project => {
    if (boundsIntersect(bounds, project.bounds)) {
      if (!loadedProjects.has(project.id)) {
        loadProjectData(project.id);
        loadedProjects.add(project.id);
      }
    }
  });
}
```

---

## File Size Optimization

### Minification

- Minify HTML/CSS/JS for production
- Use CDN for Leaflet library
- Bundle only required plugins

### Data Optimization

- Use GeoJSON with coordinate precision limited to 6 decimals
- Remove unnecessary properties from features
- Compress large files (gzip)

### Progressive Loading

1. Load critical UI first
2. Load visible project data
3. Load heat maps on demand
4. Load other projects when toggled

---

## Browser Compatibility

### Target Browsers

- Chrome 90+ ✅
- Safari 14+ ✅
- Firefox 88+ ✅
- Edge 90+ ✅
- Mobile Safari (iOS 14+) ✅
- Chrome Android ✅

### Fallbacks

- Detect WebGL support for advanced rendering
- Fallback to Canvas for older browsers
- Graceful degradation of features

---

## Testing Strategy

### Unit Tests

- Test data loading functions
- Test filtering logic
- Test statistics calculations
- Test timeline controls

### Integration Tests

- Test layer visibility toggling
- Test popup generation
- Test timeline animation
- Test multi-project loading

### Performance Tests

- Load 20K+ markers
- Measure initial load time
- Test timeline animation smoothness
- Test on mobile devices

### User Acceptance Tests

- Client presentation scenario
- Field team usage scenario
- Analysis workflow scenario

---

## Deployment

### Package Structure

```
leaflet-viewer-v1.0.zip
├── index.html                 # Main viewer
├── README.md                  # Usage instructions
├── css/
│   └── styles.css
├── js/
│   ├── config.js             # Projects configuration
│   ├── app.js                # Main application
│   └── libs/
│       ├── leaflet.js
│       ├── leaflet.markercluster.js
│       └── jszip.min.js
└── data/
    └── projects.json         # Project metadata
```

### Installation

1. Unzip package
2. Double-click `index.html`
3. Map opens in browser

### Server Deployment (Optional)

```nginx
# nginx configuration
server {
    listen 80;
    server_name maps.kcci.com;

    root /var/www/leaflet-viewer;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    # Enable gzip compression
    gzip on;
    gzip_types application/json;
}
```

---

## Future Enhancements

### Phase 2 Features

1. **Advanced Filtering**
   - Spatial queries (within polygon)
   - Complex boolean filters
   - Saved filter presets

2. **Route Planning**
   - Draw custom patrol routes
   - Optimize based on ticket density
   - Export route for GPS

3. **Data Export**
   - Export filtered tickets as CSV
   - Export map as PDF with legend
   - Export GeoPackage for QGIS

4. **Integration**
   - WebSocket for real-time updates
   - Texas 811 API integration
   - Osprey Strike data sync

### Phase 3 Features

1. **Mobile App (PWA)**
   - Offline-first design
   - GPS tracking
   - Field data collection

2. **Analytics Dashboard**
   - Trend analysis
   - Predictive modeling
   - Cost forecasting

3. **Collaboration**
   - Multi-user cursors
   - Shared annotations
   - Comment threads

---

## Conclusion

This design provides a comprehensive, performant, and user-friendly web-based map viewer for KCCI maintenance tickets. The architecture supports all current requirements and provides extensibility for future enhancements.

**Key Advantages:**
- ✅ Zero setup required
- ✅ Works offline
- ✅ Professional UX
- ✅ Multi-project support
- ✅ Rich interactivity
- ✅ Good performance
- ✅ Easy to deploy

**Implementation Timeline:** 9-13 hours
**Maintenance:** Low (static HTML/JS)
**Cost:** $0 (uses free OSM tiles)

---

**Document Version:** 1.0
**Last Updated:** February 11, 2026
**Status:** Ready for Implementation
