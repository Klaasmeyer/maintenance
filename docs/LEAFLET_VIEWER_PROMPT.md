# Leaflet Map Viewer Implementation Prompt

## Objective

Create a professional, interactive web-based map viewer using Leaflet and OpenStreetMap that displays maintenance tickets, heat maps, pipeline routes, and crossings for all KCCI projects with no API keys or accounts required.

## Requirements

### Core Features

1. **Interactive Map Display**
   - OpenStreetMap basemap (no API key needed)
   - Smooth pan and zoom
   - Responsive design (desktop, tablet, mobile)
   - Works offline after initial load

2. **Multi-Project Support**
   - Display data from all projects (Floydada, Wink, etc.)
   - Toggle visibility by project
   - Color-code by project for easy identification
   - Show project boundaries/extents

3. **Ticket Data Layers**
   - All tickets with color coding by type:
     - Emergency (red)
     - Normal (green)
     - DigUp (yellow)
     - Update (blue)
     - Other types (gray)
   - Toggle by ticket type
   - Click for detailed popup with all attributes
   - Cluster markers at low zoom levels for performance

4. **Route Corridors**
   - Display route LineStrings from all projects
   - Load from KMZ files in `projects/*/route/*.kmz`
   - Style with distinct colors per project
   - Show route names on hover
   - Display route segments with proper attribution
   - Buffer zones (optional toggle, 500m default)

5. **Pipeline Crossings**
   - Display crossing points where pipelines intersect routes
   - Distinct icon/symbol (e.g., X or crossing symbol)
   - Different color than tickets (e.g., purple/magenta)
   - Popup with crossing details:
     - Pipeline ID/name
     - Crossing type
     - Route name
     - Coordinates
     - Any notes/metadata
   - Toggle layer on/off independently

6. **Heat Maps**
   - Hexbin density visualization (colored polygons)
   - Kernel density (smooth gradient)
   - Toggle between heat map styles
   - Adjustable opacity
   - Color gradient: yellow (low) → orange → red (high)

7. **High-Risk Areas**
   - Emergency ticket clusters highlighted
   - Red zones with transparency
   - Risk level indicators
   - Emergency count displayed

8. **Timeline Animation**
   - Time slider at bottom of map
   - Play/pause controls
   - Speed adjustment (1x, 2x, 5x, 10x)
   - Date range selector
   - Tickets appear/disappear based on created_at date
   - Show date range currently displayed
   - Step through daily, weekly, or monthly

9. **Layer Controls Panel**
   - Expandable/collapsible panel (top right)
   - Hierarchical organization:
     ```
     Projects
       ☐ Floydada (5,255 tickets)
         ☐ Tickets
         ☐ Routes
         ☐ Crossings
       ☐ Wink (22,855 tickets)
         ☐ Tickets
         ☐ Routes
         ☐ Crossings

     Ticket Types
       ☐ Emergency (308)
       ☐ Normal (4,019)
       ☐ DigUp (42)
       ☐ Update (697)

     Heat Maps
       ☐ Hexbin Density
       ☐ Kernel Density
       ☐ High Risk Zones

     Infrastructure
       ☐ Route Corridors
       ☐ Pipeline Crossings
       ☐ Buffer Zones
     ```
   - Check/uncheck to toggle visibility
   - Show feature counts

10. **Legend**
    - Color-coded legend (bottom right)
    - Shows ticket types with colors
    - Heat map gradient scale
    - Route line styles
    - Crossing symbols
    - Auto-updates based on visible layers

11. **Statistics Panel**
    - Expandable panel (top left)
    - Real-time statistics for visible data:
      - Total tickets shown
      - Breakdown by type
      - Date range
      - Projects included
      - Average risk score
      - Emergency count
    - Updates when filters change

12. **Interactive Popups**
    - Click any feature for details
    - **Tickets:** All attributes formatted nicely
    - **Hexbins:** Ticket count, density, priority
    - **Routes:** Name, length, project, ticket count along route
    - **Crossings:** Pipeline info, route info, coordinates
    - Links to related data (e.g., "Show tickets near this crossing")

13. **Search and Filter**
    - Search bar for ticket numbers
    - Filter by date range
    - Filter by risk score
    - Filter by location (city, county)
    - Filter by work type
    - Combine multiple filters

14. **Measurement Tools**
    - Measure distance
    - Measure area
    - Display coordinates on click

15. **Export Capabilities**
    - Export current view as PNG
    - Export visible data as CSV
    - Print map with legend
    - Generate shareable URL with current view state

## Data Sources

### Input Files

1. **Ticket Data (GeoJSON)**
   - Path: `exports/{project}_map/layers/tickets_*.geojson`
   - All projects: Floydada, Wink, etc.
   - Load all ticket type files per project

2. **Heat Maps (GeoJSON)**
   - Path: `exports/{project}_map/heatmaps/*.geojson`
   - Hexbin files
   - Kernel density files

3. **Route Data (KMZ/KML)**
   - Path: `projects/{project}/route/*.kmz`
   - Parse KMZ to extract KML
   - Convert to GeoJSON for display
   - Examples:
     - `projects/floydada/route/Klaasmeyer - Floydada.kmz`
     - `projects/wink/route/wink.kmz`

4. **Pipeline Crossings (New)**
   - Path: TBD - may need to generate from route analysis
   - Or load from: `projects/{project}/crossings/*.geojson`
   - Format: Point geometries with properties:
     ```json
     {
       "crossing_id": "CROSS_001",
       "pipeline_name": "Pipeline XYZ",
       "pipeline_id": "PL-12345",
       "route_name": "Floydada Main",
       "crossing_type": "overhead|underground",
       "coordinates": [-101.5, 33.5],
       "notes": "High priority area"
     }
     ```

5. **Statistics (JSON)**
   - Path: `exports/{project}_map/statistics/*.json`
   - Summary stats
   - Time series data

6. **GeoPackage (Optional Alternative)**
   - Path: `exports/{project}_osprey/*.gpkg`
   - Contains all layers in single file
   - Can use as alternative data source

### Data Loading Strategy

1. **Lazy Loading**
   - Only load visible layers
   - Load data when user toggles layer on
   - Improves initial load time

2. **Clustering**
   - Cluster markers at low zoom for performance
   - Show individual tickets at high zoom
   - Display cluster counts

3. **Simplification**
   - Simplify route geometries at low zoom
   - Full resolution at high zoom
   - Reduces memory usage

## Technical Implementation

### Technology Stack

- **Leaflet.js** (v1.9+) - Core mapping library
- **OpenStreetMap** - Free basemap tiles
- **Leaflet Plugins:**
  - `leaflet.markercluster` - Marker clustering
  - `leaflet-timeline` - Timeline slider
  - `leaflet-heat` - Heat map rendering (alternative)
  - `leaflet.draw` - Drawing/measurement tools
  - `leaflet-omnivore` - Load KML/GPX/CSV files
- **Pure JavaScript** - No frameworks needed (or use vanilla JS modules)
- **HTML5/CSS3** - Modern, responsive design

### File Structure

```
exports/leaflet_viewer/
├── index.html                    # Main viewer file
├── css/
│   └── styles.css               # Custom styles
├── js/
│   ├── map-init.js              # Map initialization
│   ├── data-loader.js           # Load GeoJSON/KMZ data
│   ├── layer-controls.js        # Layer toggle logic
│   ├── timeline.js              # Timeline slider
│   ├── popups.js                # Popup templates
│   ├── statistics.js            # Stats panel
│   ├── filters.js               # Search/filter logic
│   └── utils.js                 # Helper functions
├── data/
│   ├── projects.json            # Project metadata
│   └── config.json              # Viewer configuration
└── libs/
    └── leaflet/                 # Leaflet library (optional local copy)
```

### Key Functions to Implement

1. **loadProjectData(projectName)**
   - Load all data for a project
   - Parse tickets, routes, crossings
   - Add to map with proper styling

2. **loadRouteKMZ(kmzPath)**
   - Extract KML from KMZ
   - Parse KML to GeoJSON
   - Add to map as LineString layer
   - Handle route metadata

3. **loadPipelineCrossings(projectName)**
   - Load crossing points
   - Create custom markers
   - Setup popup templates
   - Link to related tickets/routes

4. **styleTicketMarker(ticketType)**
   - Return icon/color based on type
   - Consistent with legend

5. **createTimeline(tickets)**
   - Build timeline slider
   - Filter tickets by date
   - Animate playback

6. **updateStatistics(visibleFeatures)**
   - Calculate stats for visible data
   - Update stats panel
   - Real-time updates

7. **handleLayerToggle(layerId, visible)**
   - Show/hide layers
   - Update legend
   - Update statistics

8. **exportView(format)**
   - Export as PNG/PDF
   - Export data as CSV
   - Generate shareable URL

## Styling Guidelines

### Color Scheme

**Tickets:**
- Emergency: `#ff0000` (red)
- Normal: `#4CAF50` (green)
- DigUp: `#FFC107` (yellow/amber)
- Update: `#2196F3` (blue)
- Other: `#9E9E9E` (gray)

**Routes:**
- Floydada: `#9C27B0` (purple)
- Wink: `#FF5722` (deep orange)
- Other projects: Auto-assign from palette

**Pipeline Crossings:**
- Icon: `#E91E63` (pink/magenta)
- Hover: `#C2185B` (darker pink)

**Heat Maps:**
- Low: `#ffffcc` (light yellow)
- Medium: `#feb24c` (orange)
- High: `#e31a1c` (red)

**High-Risk Areas:**
- Fill: `#ff0000` with 30% opacity
- Border: `#cc0000` solid

### Icons

- **Tickets:** Circle markers (5-8px radius)
- **Crossings:** Custom SVG icon (X or crossing symbol)
- **Clusters:** Circle with count (blue gradient)

### UI Components

- **Panels:** White background, subtle shadow, rounded corners
- **Controls:** Material Design style buttons
- **Slider:** Custom styled range input
- **Legend:** Semi-transparent white, good contrast

## Performance Considerations

1. **Marker Clustering**
   - Use for 1000+ markers
   - Cluster radius: 50-80px
   - Show individual markers at zoom level 15+

2. **GeoJSON Simplification**
   - Simplify routes at low zoom
   - Use Turf.js or similar for simplification

3. **Lazy Loading**
   - Don't load all projects at once
   - Load on-demand when user toggles

4. **Web Workers**
   - Use for heavy computations
   - Parse large GeoJSON in background

5. **Caching**
   - Cache loaded GeoJSON in memory
   - Don't reload if already loaded

## User Experience

### Initial State
- Map centered on all project data (fit bounds)
- All project routes visible
- Tickets hidden initially (too many points)
- Heat map visible at low opacity
- Legend and controls visible

### Workflow Examples

**Scenario 1: View Emergency Tickets for Floydada**
1. Toggle off "All Projects"
2. Toggle on "Floydada"
3. Toggle on "Emergency" tickets
4. Click ticket to see details
5. Use timeline to see historical pattern

**Scenario 2: Find Pipeline Crossings Near Emergencies**
1. Toggle on "Pipeline Crossings"
2. Toggle on "Emergency" tickets
3. Visually identify crossings near emergency clusters
4. Click crossing for details
5. Use "Show tickets nearby" link in popup

**Scenario 3: Compare Projects**
1. Toggle on "Floydada" and "Wink"
2. Different route colors show both projects
3. Heat maps overlay shows density comparison
4. Statistics panel shows counts for each

**Scenario 4: Timeline Analysis**
1. Toggle on specific ticket type
2. Set date range to last year
3. Click play to watch animation
4. Observe seasonal patterns
5. Pause at interesting dates to investigate

## Testing Requirements

1. **Browser Compatibility**
   - Test in Chrome, Safari, Firefox, Edge
   - Mobile Safari, Chrome Android

2. **Performance Testing**
   - Load all projects simultaneously
   - Verify smooth performance with 20K+ markers
   - Test timeline animation smoothness

3. **Data Validation**
   - Verify ticket counts match source data
   - Check coordinate accuracy
   - Validate route geometries

4. **Offline Functionality**
   - Test with no internet (after initial load)
   - Verify all features work locally

## Deployment Options

### Option 1: Local Files
- Zip folder, share with team
- Double-click HTML to open
- No server required

### Option 2: Network Drive
- Place on shared drive
- Team accesses via file:// URL

### Option 3: Web Server
- Upload to company web server
- Access via https://
- Can add authentication if needed

### Option 4: Electron App (Advanced)
- Package as desktop application
- Includes Node.js runtime
- Professional installer

## Future Enhancements

1. **Real-time Updates**
   - WebSocket connection to live data
   - Auto-refresh new tickets

2. **Route Planning**
   - Plan patrol routes
   - Optimize based on ticket density

3. **Integration with Osprey Strike**
   - Export selected tickets to Osprey
   - Import field inspection data

4. **Texas 811 Integration**
   - Monitor new tickets in real-time
   - Alert on emergencies

5. **Mobile App**
   - Offline-first PWA
   - GPS location tracking
   - Field data collection

## Success Criteria

- ✅ Opens in browser with double-click (no setup)
- ✅ All tickets, routes, and crossings display correctly
- ✅ Heat maps show density patterns
- ✅ Timeline animation is smooth
- ✅ Layer controls toggle visibility
- ✅ Popups show complete information
- ✅ Legend matches displayed data
- ✅ Statistics update in real-time
- ✅ Works for all projects (Floydada, Wink, etc.)
- ✅ Performance is good with 20K+ markers
- ✅ Professional appearance suitable for client presentations
- ✅ No API keys or accounts required
- ✅ Works offline after initial load

## Implementation Timeline

**Phase 1 (Core Functionality):**
- Basic map with OpenStreetMap
- Load and display tickets
- Load routes from KMZ files
- Basic layer controls
- Popups with ticket info
- **Estimate: 4-6 hours**

**Phase 2 (Enhanced Features):**
- Pipeline crossings layer
- Heat maps (hexbin)
- Timeline slider
- Statistics panel
- Legend
- **Estimate: 3-4 hours**

**Phase 3 (Polish):**
- Search and filters
- Multi-project support
- Export capabilities
- Performance optimization
- Responsive design
- **Estimate: 2-3 hours**

**Total: 9-13 hours of development**

## References

- Leaflet Documentation: https://leafletjs.com/reference.html
- Leaflet Plugins: https://leafletjs.com/plugins.html
- OpenStreetMap Tile Usage Policy: https://operations.osmfoundation.org/policies/tiles/
- GeoJSON Specification: https://geojson.org/
- KML Reference: https://developers.google.com/kml/documentation/kmlreference

## Notes

- Keep HTML file size under 500KB for fast loading
- Bundle critical CSS/JS inline to reduce HTTP requests
- Use CDN for Leaflet library or include local copy for offline use
- Test with actual project data to ensure accuracy
- Get user feedback on UI/UX before finalizing design
- Document any assumptions about data formats
- Include fallbacks for missing data (graceful degradation)
