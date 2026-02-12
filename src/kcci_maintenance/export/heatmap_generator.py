"""
Heat map generator for ticket density visualization.

Generates various heat map representations:
- Hexbin grids (hexagonal bins with counts)
- Kernel density estimation (smooth density surfaces)
- Temporal heat maps (density by time period)
- Risk zones (high-density areas for patrol priority)
"""

import json
from pathlib import Path
from typing import Optional, Tuple, List
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon, mapping

# Optional dependency for kernel density estimation
try:
    from scipy.stats import gaussian_kde
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


class HeatMapGenerator:
    """Generate heat map data from ticket locations."""

    def __init__(self, output_dir: Path):
        """Initialize heat map generator.

        Args:
            output_dir: Directory for heat map output files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_hexbin(
        self,
        tickets_df: pd.DataFrame,
        resolution_m: float = 500.0,
        output_name: str = "heatmap_hexbin.geojson"
    ) -> Path:
        """Generate hexagonal bin heat map.

        Args:
            tickets_df: DataFrame with ticket data (latitude, longitude)
            resolution_m: Size of hexagons in meters
            output_name: Output filename

        Returns:
            Path to GeoJSON file with hexbin polygons
        """
        # Convert to GeoDataFrame
        gdf = gpd.GeoDataFrame(
            tickets_df,
            geometry=gpd.points_from_xy(tickets_df.longitude, tickets_df.latitude),
            crs='EPSG:4326'
        )

        # Reproject to UTM for accurate hexagon sizing
        utm_crs = gdf.estimate_utm_crs()
        gdf_utm = gdf.to_crs(utm_crs)

        # Calculate bounds
        minx, miny, maxx, maxy = gdf_utm.total_bounds

        # Ensure minimum grid size
        if maxx - minx < resolution_m:
            maxx = minx + resolution_m * 3
        if maxy - miny < resolution_m:
            maxy = miny + resolution_m * 3

        # Generate hexagons
        hexagons = self._create_hexagon_grid(
            minx, miny, maxx, maxy, resolution_m
        )

        # Count tickets in each hexagon
        hex_counts = []
        for hex_geom in hexagons:
            count = gdf_utm.within(hex_geom).sum()
            if count > 0:  # Only include non-empty hexagons
                hex_counts.append({
                    'geometry': hex_geom,
                    'ticket_count': int(count),
                    'density': count / (resolution_m ** 2 / 1000000)  # tickets per km²
                })

        # Handle edge case of no hexagons with tickets
        if not hex_counts:
            # Create empty GeoDataFrame with correct schema
            hex_gdf = gpd.GeoDataFrame(
                {'ticket_count': [], 'density': []},
                geometry=[],
                crs=utm_crs
            )
        else:
            # Convert back to WGS84
            hex_gdf = gpd.GeoDataFrame(hex_counts, crs=utm_crs)

        hex_gdf = hex_gdf.to_crs('EPSG:4326')

        # Export as GeoJSON
        features = []
        for idx, row in hex_gdf.iterrows():
            feature = {
                'type': 'Feature',
                'geometry': mapping(row.geometry),
                'properties': {
                    'ticket_count': row['ticket_count'],
                    'density': float(row['density'])
                }
            }
            features.append(feature)

        geojson = {
            'type': 'FeatureCollection',
            'features': features,
            'metadata': {
                'type': 'hexbin',
                'resolution_m': resolution_m,
                'count': len(features)
            }
        }

        output_path = self.output_dir / output_name
        with open(output_path, 'w') as f:
            json.dump(geojson, f, indent=2)

        return output_path

    def _create_hexagon_grid(
        self,
        minx: float,
        miny: float,
        maxx: float,
        maxy: float,
        size: float
    ) -> List[Polygon]:
        """Create hexagonal grid covering bounding box.

        Args:
            minx, miny, maxx, maxy: Bounding box coordinates
            size: Hexagon size (flat-to-flat distance)

        Returns:
            List of hexagon Polygon geometries
        """
        hexagons = []

        # Hexagon geometry parameters
        width = size
        height = size * np.sqrt(3) / 2
        h = height / 2
        w = width / 2

        # Generate hexagons
        row = 0
        y = miny
        while y < maxy:
            col = 0
            x = minx if row % 2 == 0 else minx + w

            while x < maxx:
                # Create hexagon vertices
                vertices = [
                    (x, y + h),
                    (x + w, y),
                    (x + width, y + h),
                    (x + width, y + h + height),
                    (x + w, y + 2*height),
                    (x, y + h + height)
                ]
                hexagons.append(Polygon(vertices))

                col += 1
                x += width

            row += 1
            y += height * 1.5

        return hexagons

    def generate_kernel_density(
        self,
        tickets_df: pd.DataFrame,
        grid_resolution: int = 100,
        bandwidth: Optional[float] = None,
        contour_levels: List[float] = [0.25, 0.5, 0.75, 0.9],
        output_name: str = "heatmap_kernel.geojson"
    ) -> Path:
        """Generate kernel density estimation heat map.

        Args:
            tickets_df: DataFrame with ticket data (latitude, longitude)
            grid_resolution: Number of grid points in each dimension
            bandwidth: KDE bandwidth (None = auto)
            contour_levels: Density levels for contours (0-1)
            output_name: Output filename

        Returns:
            Path to GeoJSON file with density contours

        Raises:
            ImportError: If scipy is not installed
        """
        if not HAS_SCIPY:
            raise ImportError(
                "scipy is required for kernel density estimation. "
                "Install it with: pip install scipy"
            )

        # Extract coordinates
        coords = tickets_df[['longitude', 'latitude']].values.T

        # Perform KDE
        kde = gaussian_kde(coords, bw_method=bandwidth)

        # Create grid
        lon_min, lon_max = coords[0].min(), coords[0].max()
        lat_min, lat_max = coords[1].min(), coords[1].max()

        # Add padding
        lon_pad = (lon_max - lon_min) * 0.1
        lat_pad = (lat_max - lat_min) * 0.1

        lon_grid = np.linspace(lon_min - lon_pad, lon_max + lon_pad, grid_resolution)
        lat_grid = np.linspace(lat_min - lat_pad, lat_max + lat_pad, grid_resolution)

        lon_mesh, lat_mesh = np.meshgrid(lon_grid, lat_grid)
        grid_coords = np.vstack([lon_mesh.ravel(), lat_mesh.ravel()])

        # Evaluate KDE on grid
        density = kde(grid_coords).reshape(lon_mesh.shape)

        # Normalize to 0-1
        density = (density - density.min()) / (density.max() - density.min())

        # Generate contours (simplified for GeoJSON)
        # In production, use matplotlib.pyplot.contour for proper contours
        features = []

        # For now, create grid cells with density values
        # This is a simplified version - proper contours would be better
        for i in range(grid_resolution - 1):
            for j in range(grid_resolution - 1):
                cell_density = density[i, j]

                # Only include cells above minimum threshold
                if cell_density > 0.1:
                    # Create cell polygon
                    cell = Polygon([
                        (lon_grid[j], lat_grid[i]),
                        (lon_grid[j+1], lat_grid[i]),
                        (lon_grid[j+1], lat_grid[i+1]),
                        (lon_grid[j], lat_grid[i+1])
                    ])

                    feature = {
                        'type': 'Feature',
                        'geometry': mapping(cell),
                        'properties': {
                            'density': float(cell_density)
                        }
                    }
                    features.append(feature)

        geojson = {
            'type': 'FeatureCollection',
            'features': features,
            'metadata': {
                'type': 'kernel_density',
                'grid_resolution': grid_resolution,
                'bandwidth': bandwidth
            }
        }

        output_path = self.output_dir / output_name
        with open(output_path, 'w') as f:
            json.dump(geojson, f, indent=2)

        return output_path

    def generate_risk_zones(
        self,
        tickets_df: pd.DataFrame,
        route_gdf: gpd.GeoDataFrame,
        high_risk_threshold: int = 10,  # tickets per mile per year
        output_name: str = "risk_zones.geojson"
    ) -> Path:
        """Generate risk zones for patrol priority.

        Args:
            tickets_df: DataFrame with ticket data
            route_gdf: GeoDataFrame with route segments
            high_risk_threshold: Threshold for high-risk classification
            output_name: Output filename

        Returns:
            Path to GeoJSON file with risk zones
        """
        # Calculate ticket density per route segment
        risk_zones = []

        for idx, route in route_gdf.iterrows():
            # Find tickets within buffer of this segment
            segment_geom = route.geometry

            # Reproject for accurate distance
            utm_crs = route_gdf.estimate_utm_crs()
            segment_utm = gpd.GeoSeries([segment_geom], crs=route_gdf.crs).to_crs(utm_crs)
            buffer = segment_utm.buffer(500)  # 500m buffer

            # Convert tickets to same CRS
            tickets_gdf = gpd.GeoDataFrame(
                tickets_df,
                geometry=gpd.points_from_xy(tickets_df.longitude, tickets_df.latitude),
                crs='EPSG:4326'
            ).to_crs(utm_crs)

            # Count tickets in buffer
            tickets_in_buffer = tickets_gdf[tickets_gdf.within(buffer.iloc[0])].shape[0]

            # Calculate segment length in miles
            segment_length_mi = segment_utm.length.iloc[0] / 1609.34

            # Calculate density
            tickets_per_mile = tickets_in_buffer / segment_length_mi if segment_length_mi > 0 else 0

            # Determine risk level
            if tickets_per_mile >= high_risk_threshold:
                risk_level = 'high'
                priority = 1
            elif tickets_per_mile >= high_risk_threshold / 2:
                risk_level = 'medium'
                priority = 2
            else:
                risk_level = 'low'
                priority = 3

            # Convert buffer back to WGS84
            buffer_wgs84 = buffer.to_crs('EPSG:4326')

            risk_zones.append({
                'type': 'Feature',
                'geometry': mapping(buffer_wgs84.iloc[0]),
                'properties': {
                    'segment_name': route.get('name', f'Segment {idx}'),
                    'tickets_per_mile': float(tickets_per_mile),
                    'risk_level': risk_level,
                    'patrol_priority': priority,
                    'total_tickets': int(tickets_in_buffer)
                }
            })

        geojson = {
            'type': 'FeatureCollection',
            'features': risk_zones,
            'metadata': {
                'type': 'risk_zones',
                'high_risk_threshold': high_risk_threshold
            }
        }

        output_path = self.output_dir / output_name
        with open(output_path, 'w') as f:
            json.dump(geojson, f, indent=2)

        return output_path


if __name__ == "__main__":
    print("Heat Map Generator - Example Usage")
    print("="*50)
    print("""
    from kcci_maintenance.export import HeatMapGenerator

    generator = HeatMapGenerator(output_dir='exports/floydada/heatmaps')

    # Generate hexbin heat map
    generator.generate_hexbin(tickets_df, resolution_m=500)

    # Generate kernel density
    generator.generate_kernel_density(tickets_df, grid_resolution=100)

    # Generate risk zones for patrol planning
    generator.generate_risk_zones(tickets_df, route_gdf, high_risk_threshold=10)
    """)
