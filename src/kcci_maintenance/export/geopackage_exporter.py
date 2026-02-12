"""
GeoPackage exporter for Osprey Strike OSP software integration.

Exports geocoded tickets and route data as GeoPackage format for:
- Osprey Strike Fiber OSP Maintenance software
- GIS applications (QGIS, ArcGIS)
- Mobile field applications

GeoPackage is an SQLite-based format providing vector features,
tile matrix sets, attributes, and extensions in a single file.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, box
import numpy as np


class GeoPackageExporter:
    """Export ticket and route data as GeoPackage for OSP integration."""

    def __init__(self, output_dir: Path):
        """Initialize GeoPackage exporter.

        Args:
            output_dir: Directory for GeoPackage output files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_osprey_package(
        self,
        tickets_df: pd.DataFrame,
        route_gdf: Optional[gpd.GeoDataFrame] = None,
        output_name: str = "osprey_maintenance.gpkg",
        patrol_zone_size_m: float = 1000.0,
        high_density_threshold: int = 20
    ) -> Path:
        """Export comprehensive GeoPackage for Osprey Strike.

        Creates a single GeoPackage with multiple layers:
        - tickets: All ticket locations with attributes
        - route_segments: Route corridors with maintenance estimates
        - patrol_zones: Grid cells with ticket density and priority
        - high_risk_areas: Emergency hotspots requiring attention

        Args:
            tickets_df: DataFrame with ticket data
            route_gdf: Optional GeoDataFrame with route geometry
            output_name: Output filename
            patrol_zone_size_m: Size of patrol grid cells in meters
            high_density_threshold: Tickets per zone for high-priority classification

        Returns:
            Path to created GeoPackage file
        """
        output_path = self.output_dir / output_name

        # Convert tickets to GeoDataFrame
        tickets_gdf = gpd.GeoDataFrame(
            tickets_df,
            geometry=gpd.points_from_xy(tickets_df.longitude, tickets_df.latitude),
            crs='EPSG:4326'
        )

        # Layer 1: All tickets with full attributes
        tickets_layer = self._prepare_tickets_layer(tickets_gdf)
        tickets_layer.to_file(output_path, layer='tickets', driver='GPKG')

        # Layer 2: Route segments with maintenance costs
        if route_gdf is not None:
            route_layer = self._prepare_route_layer(route_gdf, tickets_gdf)
            route_layer.to_file(output_path, layer='route_segments', driver='GPKG', mode='a')

        # Layer 3: Patrol zones with density analysis
        patrol_zones = self._generate_patrol_zones(
            tickets_gdf,
            patrol_zone_size_m,
            high_density_threshold
        )
        patrol_zones.to_file(output_path, layer='patrol_zones', driver='GPKG', mode='a')

        # Layer 4: High-risk areas (emergency ticket clusters)
        high_risk = self._identify_high_risk_areas(tickets_gdf)
        if len(high_risk) > 0:
            high_risk.to_file(output_path, layer='high_risk_areas', driver='GPKG', mode='a')

        # Add metadata table
        self._add_metadata(output_path, tickets_gdf, route_gdf)

        return output_path

    def _prepare_tickets_layer(self, tickets_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Prepare tickets layer with Osprey Strike schema.

        Args:
            tickets_gdf: GeoDataFrame with ticket data

        Returns:
            Prepared GeoDataFrame with standardized schema
        """
        # Create copy to avoid modifying original
        layer = tickets_gdf.copy()

        # Standardize column names for Osprey Strike
        column_mapping = {
            'ticket_number': 'ticket_id',
            'ticket_type': 'type',
            'work_type': 'work_category',
            'created_at': 'date',
            'route_leg': 'route_segment',
            'confidence': 'geocode_quality'
        }

        layer = layer.rename(columns={
            k: v for k, v in column_mapping.items() if k in layer.columns
        })

        # Add Osprey-specific fields
        if 'type' in layer.columns:
            layer['requires_patrol'] = layer['type'].isin(['Emergency', 'DigUp'])
            layer['estimated_visit_time_min'] = layer['type'].map({
                'Emergency': 30,
                'DigUp': 20,
                'Normal': 10,
                'Update': 5
            }).fillna(10)
        else:
            layer['requires_patrol'] = False
            layer['estimated_visit_time_min'] = 10

        # Calculate risk score (0-100)
        layer['risk_score'] = self._calculate_risk_score(layer)

        # Convert timestamps to ISO format strings
        if 'date' in layer.columns:
            layer['date'] = pd.to_datetime(layer['date'], errors='coerce')
            layer['date'] = layer['date'].dt.strftime('%Y-%m-%d %H:%M:%S')

        # Keep only relevant columns
        keep_columns = [
            'geometry', 'ticket_id', 'type', 'work_category', 'date',
            'route_segment', 'geocode_quality', 'requires_patrol',
            'estimated_visit_time_min', 'risk_score', 'city', 'county'
        ]
        layer = layer[[col for col in keep_columns if col in layer.columns]]

        return layer

    def _prepare_route_layer(
        self,
        route_gdf: gpd.GeoDataFrame,
        tickets_gdf: gpd.GeoDataFrame
    ) -> gpd.GeoDataFrame:
        """Prepare route segments layer with maintenance estimates.

        Args:
            route_gdf: GeoDataFrame with route geometry
            tickets_gdf: GeoDataFrame with ticket data for cost estimation

        Returns:
            Route layer with maintenance cost estimates
        """
        layer = route_gdf.copy()

        # Ensure CRS is WGS84
        if layer.crs != 'EPSG:4326':
            layer = layer.to_crs('EPSG:4326')

        # Add segment statistics
        for idx, segment in layer.iterrows():
            segment_name = segment.get('name', f'Segment {idx}')

            # Find tickets near this segment
            if 'route_leg' in tickets_gdf.columns:
                segment_tickets = tickets_gdf[tickets_gdf['route_leg'] == segment_name]
            else:
                # Simple spatial filter (within 500m buffer)
                utm_crs = layer.estimate_utm_crs()
                segment_geom = gpd.GeoSeries([segment.geometry], crs=layer.crs).to_crs(utm_crs)
                buffered = segment_geom.buffer(500)
                tickets_utm = tickets_gdf.to_crs(utm_crs)
                segment_tickets = tickets_gdf[tickets_utm.within(buffered.iloc[0])]

            # Calculate segment statistics
            layer.at[idx, 'ticket_count'] = len(segment_tickets)
            layer.at[idx, 'emergency_count'] = len(
                segment_tickets[segment_tickets.get('ticket_type', '') == 'Emergency']
            )

            # Calculate patrol frequency and cost estimates
            ticket_count = len(segment_tickets)
            if ticket_count >= 50:
                priority = 'HIGH'
                frequency = 'weekly'
                annual_visits = 52
            elif ticket_count >= 20:
                priority = 'MEDIUM'
                frequency = 'monthly'
                annual_visits = 12
            else:
                priority = 'LOW'
                frequency = 'quarterly'
                annual_visits = 4

            layer.at[idx, 'patrol_priority'] = priority
            layer.at[idx, 'patrol_frequency'] = frequency
            layer.at[idx, 'estimated_annual_visits'] = annual_visits

            # Estimate annual maintenance cost
            # Base cost: $200/visit + $50/emergency ticket
            base_cost = 200 * annual_visits
            emergency_cost = layer.at[idx, 'emergency_count'] * 50
            layer.at[idx, 'estimated_annual_cost_usd'] = base_cost + emergency_cost

        return layer

    def _generate_patrol_zones(
        self,
        tickets_gdf: gpd.GeoDataFrame,
        zone_size_m: float,
        high_density_threshold: int
    ) -> gpd.GeoDataFrame:
        """Generate patrol zone grid with ticket density.

        Args:
            tickets_gdf: GeoDataFrame with ticket data
            zone_size_m: Size of grid cells in meters
            high_density_threshold: Threshold for high-priority zones

        Returns:
            GeoDataFrame with patrol zones
        """
        # Reproject to UTM for accurate distance calculations
        utm_crs = tickets_gdf.estimate_utm_crs()
        tickets_utm = tickets_gdf.to_crs(utm_crs)

        # Get bounds
        minx, miny, maxx, maxy = tickets_utm.total_bounds

        # Ensure minimum grid size
        if maxx - minx < zone_size_m:
            maxx = minx + zone_size_m * 2
        if maxy - miny < zone_size_m:
            maxy = miny + zone_size_m * 2

        # Create grid
        grid_cells = []
        x_coords = np.arange(minx, maxx, zone_size_m)
        y_coords = np.arange(miny, maxy, zone_size_m)

        for x in x_coords:
            for y in y_coords:
                cell = box(x, y, x + zone_size_m, y + zone_size_m)
                grid_cells.append(cell)

        # Create GeoDataFrame
        grid = gpd.GeoDataFrame({'geometry': grid_cells}, crs=utm_crs)

        # Count tickets in each cell
        grid['ticket_count'] = 0
        grid['emergency_count'] = 0
        grid['normal_count'] = 0

        for idx, cell in grid.iterrows():
            tickets_in_cell = tickets_utm[tickets_utm.within(cell.geometry)]
            grid.at[idx, 'ticket_count'] = len(tickets_in_cell)

            if 'ticket_type' in tickets_in_cell.columns:
                grid.at[idx, 'emergency_count'] = len(
                    tickets_in_cell[tickets_in_cell['ticket_type'] == 'Emergency']
                )
                grid.at[idx, 'normal_count'] = len(
                    tickets_in_cell[tickets_in_cell['ticket_type'] == 'Normal']
                )

        # Filter to zones with tickets
        grid = grid[grid['ticket_count'] > 0].copy()

        # Assign priority
        grid['priority'] = 'LOW'
        grid.loc[grid['ticket_count'] >= high_density_threshold, 'priority'] = 'HIGH'
        grid.loc[
            (grid['ticket_count'] >= high_density_threshold // 2) &
            (grid['ticket_count'] < high_density_threshold),
            'priority'
        ] = 'MEDIUM'

        # Calculate patrol recommendation
        grid['recommended_frequency'] = grid['priority'].map({
            'HIGH': 'weekly',
            'MEDIUM': 'monthly',
            'LOW': 'quarterly'
        })

        # Add zone ID
        grid['zone_id'] = [f'ZONE_{i:04d}' for i in range(len(grid))]

        # Calculate centroid for labels
        grid['center_lat'] = grid.geometry.centroid.to_crs('EPSG:4326').y
        grid['center_lon'] = grid.geometry.centroid.to_crs('EPSG:4326').x

        # Convert back to WGS84
        grid = grid.to_crs('EPSG:4326')

        return grid

    def _identify_high_risk_areas(
        self,
        tickets_gdf: gpd.GeoDataFrame,
        buffer_distance_m: float = 500.0
    ) -> gpd.GeoDataFrame:
        """Identify high-risk areas with emergency ticket clusters.

        Args:
            tickets_gdf: GeoDataFrame with ticket data
            buffer_distance_m: Buffer distance for clustering

        Returns:
            GeoDataFrame with high-risk areas
        """
        # Filter to emergency tickets
        if 'ticket_type' not in tickets_gdf.columns:
            return gpd.GeoDataFrame(columns=['geometry'], crs='EPSG:4326')

        emergency = tickets_gdf[tickets_gdf['ticket_type'] == 'Emergency'].copy()

        if len(emergency) == 0:
            return gpd.GeoDataFrame(columns=['geometry'], crs='EPSG:4326')

        # Reproject to UTM for buffering
        utm_crs = emergency.estimate_utm_crs()
        emergency_utm = emergency.to_crs(utm_crs)

        # Buffer and dissolve to create clusters
        buffered = emergency_utm.buffer(buffer_distance_m)
        clusters = gpd.GeoDataFrame({'geometry': buffered}, crs=utm_crs)
        clusters = clusters.dissolve()

        # Explode multipolygons to individual polygons
        clusters = clusters.explode(index_parts=False)

        # Count tickets in each cluster
        clusters['emergency_count'] = 0
        clusters['latest_incident'] = None

        for idx, cluster in clusters.iterrows():
            tickets_in_cluster = emergency_utm[emergency_utm.within(cluster.geometry)]
            clusters.at[idx, 'emergency_count'] = len(tickets_in_cluster)

            if 'created_at' in tickets_in_cluster.columns:
                dates = pd.to_datetime(tickets_in_cluster['created_at'], errors='coerce')
                if len(dates.dropna()) > 0:
                    clusters.at[idx, 'latest_incident'] = dates.max().isoformat()

        # Add risk assessment
        clusters['risk_level'] = 'CRITICAL'
        clusters['requires_immediate_attention'] = clusters['emergency_count'] >= 3

        # Add area ID
        clusters = clusters.reset_index(drop=True)
        clusters['area_id'] = [f'RISK_{i:03d}' for i in range(len(clusters))]

        # Convert back to WGS84
        clusters = clusters.to_crs('EPSG:4326')

        return clusters

    def _calculate_risk_score(self, tickets_df: pd.DataFrame) -> pd.Series:
        """Calculate risk score (0-100) for each ticket.

        Args:
            tickets_df: DataFrame with ticket data

        Returns:
            Series with risk scores
        """
        score = pd.Series(30.0, index=tickets_df.index)  # Base score

        # Type-based scoring
        if 'type' in tickets_df.columns:
            score += tickets_df['type'].map({
                'Emergency': 50,
                'DigUp': 30,
                'Normal': 10,
                'Update': 5
            }).fillna(10)

        # Geocode quality factor
        if 'geocode_quality' in tickets_df.columns:
            score *= tickets_df['geocode_quality'].fillna(0.7)

        # Cap at 100
        score = score.clip(upper=100)

        return score

    def _add_metadata(
        self,
        gpkg_path: Path,
        tickets_gdf: gpd.GeoDataFrame,
        route_gdf: Optional[gpd.GeoDataFrame] = None
    ) -> None:
        """Add metadata table to GeoPackage.

        Args:
            gpkg_path: Path to GeoPackage file
            tickets_gdf: GeoDataFrame with ticket data
            route_gdf: Optional GeoDataFrame with route data
        """
        metadata = {
            'generated': datetime.now().isoformat(),
            'total_tickets': len(tickets_gdf),
            'date_range_start': None,
            'date_range_end': None,
            'route_segments': len(route_gdf) if route_gdf is not None else 0,
            'format_version': '1.0',
            'software': 'KCCI Maintenance Pipeline',
            'target_system': 'Osprey Strike OSP'
        }

        # Calculate date range
        if 'created_at' in tickets_gdf.columns:
            dates = pd.to_datetime(tickets_gdf['created_at'], errors='coerce')
            valid_dates = dates.dropna()
            if len(valid_dates) > 0:
                metadata['date_range_start'] = valid_dates.min().isoformat()
                metadata['date_range_end'] = valid_dates.max().isoformat()

        # Convert to DataFrame
        metadata_df = pd.DataFrame([metadata])

        # Append to GeoPackage (non-spatial table)
        import sqlite3
        conn = sqlite3.connect(gpkg_path)
        metadata_df.to_sql('metadata', conn, if_exists='replace', index=False)
        conn.close()

    def export_patrol_schedule(
        self,
        tickets_df: pd.DataFrame,
        route_gdf: Optional[gpd.GeoDataFrame] = None,
        output_name: str = "patrol_schedule.csv"
    ) -> Path:
        """Export recommended patrol schedule as CSV.

        Args:
            tickets_df: DataFrame with ticket data
            route_gdf: Optional GeoDataFrame with route geometry
            output_name: Output filename

        Returns:
            Path to CSV file
        """
        schedule = []

        if route_gdf is not None and 'route_leg' in tickets_df.columns:
            # Group by route segment
            for segment in route_gdf['name'].unique():
                segment_tickets = tickets_df[tickets_df['route_leg'] == segment]
                ticket_count = len(segment_tickets)

                # Determine frequency
                if ticket_count >= 50:
                    frequency = 'weekly'
                    annual_visits = 52
                elif ticket_count >= 20:
                    frequency = 'monthly'
                    annual_visits = 12
                else:
                    frequency = 'quarterly'
                    annual_visits = 4

                schedule.append({
                    'route_segment': segment,
                    'ticket_count': ticket_count,
                    'frequency': frequency,
                    'annual_visits': annual_visits,
                    'estimated_hours_per_visit': 2.0,
                    'estimated_annual_hours': annual_visits * 2.0
                })

        schedule_df = pd.DataFrame(schedule)
        output_path = self.output_dir / output_name
        schedule_df.to_csv(output_path, index=False)

        return output_path


if __name__ == "__main__":
    print("GeoPackage Exporter - Example Usage")
    print("="*50)
    print("""
    from kcci_maintenance.export import GeoPackageExporter

    # Initialize exporter
    exporter = GeoPackageExporter(output_dir='exports/floydada/osprey')

    # Export comprehensive GeoPackage for Osprey Strike
    exporter.export_osprey_package(
        tickets_df,
        route_gdf,
        output_name='osprey_maintenance.gpkg',
        patrol_zone_size_m=1000.0,
        high_density_threshold=20
    )

    # Export patrol schedule
    exporter.export_patrol_schedule(tickets_df, route_gdf)
    """)
