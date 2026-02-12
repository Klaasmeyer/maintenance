"""
GeoJSON exporter for ticket data and route corridors.

Exports geocoded tickets as GeoJSON FeatureCollections for use in:
- Web mapping libraries (Leaflet, Mapbox GL JS, Deck.gl)
- GIS software (QGIS, ArcGIS)
- External APIs and integrations
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString, mapping


class GeoJSONExporter:
    """Export ticket data as GeoJSON for web maps and GIS integration."""

    def __init__(self, output_dir: Path):
        """Initialize GeoJSON exporter.

        Args:
            output_dir: Directory for GeoJSON output files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_tickets(
        self,
        tickets_df: pd.DataFrame,
        output_name: str = "tickets_all.geojson",
        filter_by: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Export tickets as GeoJSON FeatureCollection.

        Args:
            tickets_df: DataFrame with ticket data (must have latitude, longitude)
            output_name: Output filename
            filter_by: Optional filters (e.g., {'ticket_type': 'Emergency'})

        Returns:
            Path to created GeoJSON file
        """
        # Filter data if specified
        if filter_by:
            for key, value in filter_by.items():
                if key in tickets_df.columns:
                    if isinstance(value, list):
                        tickets_df = tickets_df[tickets_df[key].isin(value)]
                    else:
                        tickets_df = tickets_df[tickets_df[key] == value]

        # Convert to GeoDataFrame
        gdf = gpd.GeoDataFrame(
            tickets_df,
            geometry=gpd.points_from_xy(tickets_df.longitude, tickets_df.latitude),
            crs='EPSG:4326'
        )

        # Build GeoJSON structure
        features = []
        for idx, row in gdf.iterrows():
            properties = row.drop('geometry').to_dict()

            # Convert timestamps to ISO format strings
            for key, value in properties.items():
                if pd.isna(value):
                    properties[key] = None
                elif isinstance(value, pd.Timestamp):
                    properties[key] = value.isoformat()

            feature = {
                'type': 'Feature',
                'geometry': mapping(row.geometry),
                'properties': properties
            }
            features.append(feature)

        geojson = {
            'type': 'FeatureCollection',
            'features': features,
            'metadata': {
                'generated': datetime.now().isoformat(),
                'count': len(features),
                'filters': filter_by or {}
            }
        }

        # Write to file
        output_path = self.output_dir / output_name
        with open(output_path, 'w') as f:
            json.dump(geojson, f, indent=2)

        return output_path

    def export_by_ticket_type(
        self,
        tickets_df: pd.DataFrame,
        ticket_types: Optional[List[str]] = None
    ) -> Dict[str, Path]:
        """Export separate GeoJSON files for each ticket type.

        Args:
            tickets_df: DataFrame with ticket data
            ticket_types: List of ticket types to export (default: all unique types)

        Returns:
            Dictionary mapping ticket type to output path
        """
        if ticket_types is None:
            ticket_types = tickets_df['ticket_type'].unique().tolist()

        output_paths = {}
        for ticket_type in ticket_types:
            if pd.isna(ticket_type):
                continue

            # Sanitize filename (replace spaces, slashes, and other problematic chars)
            safe_name = str(ticket_type).lower().replace(' ', '_').replace('/', '_').replace('\\', '_')
            output_name = f"tickets_{safe_name}.geojson"

            path = self.export_tickets(
                tickets_df,
                output_name=output_name,
                filter_by={'ticket_type': ticket_type}
            )
            output_paths[ticket_type] = path

        return output_paths

    def export_route_corridor(
        self,
        route_gdf: gpd.GeoDataFrame,
        output_name: str = "route_corridor.geojson",
        include_buffer: bool = True,
        buffer_distance_m: float = 500.0
    ) -> Path:
        """Export route corridor as GeoJSON.

        Args:
            route_gdf: GeoDataFrame with route geometry
            output_name: Output filename
            include_buffer: Whether to include buffer zone
            buffer_distance_m: Buffer distance in meters

        Returns:
            Path to created GeoJSON file
        """
        features = []

        for idx, row in route_gdf.iterrows():
            # Original route geometry
            feature = {
                'type': 'Feature',
                'geometry': mapping(row.geometry),
                'properties': {
                    'name': row.get('name', f'Route {idx}'),
                    'type': 'route_line'
                }
            }
            features.append(feature)

            # Buffer zone if requested
            if include_buffer:
                # Reproject to UTM for accurate buffer
                utm_crs = route_gdf.estimate_utm_crs()
                buffered = gpd.GeoSeries([row.geometry], crs=route_gdf.crs).to_crs(utm_crs)
                buffered = buffered.buffer(buffer_distance_m)
                buffered = buffered.to_crs('EPSG:4326')

                buffer_feature = {
                    'type': 'Feature',
                    'geometry': mapping(buffered.iloc[0]),
                    'properties': {
                        'name': f"{row.get('name', f'Route {idx}')} Buffer",
                        'type': 'buffer_zone',
                        'buffer_distance_m': buffer_distance_m
                    }
                }
                features.append(buffer_feature)

        geojson = {
            'type': 'FeatureCollection',
            'features': features,
            'metadata': {
                'generated': datetime.now().isoformat(),
                'buffer_distance_m': buffer_distance_m if include_buffer else None
            }
        }

        output_path = self.output_dir / output_name
        with open(output_path, 'w') as f:
            json.dump(geojson, f, indent=2)

        return output_path

    def export_temporal_slices(
        self,
        tickets_df: pd.DataFrame,
        time_column: str = 'created_at',
        bin_type: str = 'monthly'  # 'monthly', 'quarterly', 'yearly'
    ) -> Dict[str, Path]:
        """Export tickets grouped by time periods.

        Args:
            tickets_df: DataFrame with ticket data
            time_column: Column containing timestamps
            bin_type: Type of temporal binning

        Returns:
            Dictionary mapping time period to output path
        """
        # Convert to datetime if needed
        tickets_df = tickets_df.copy()
        tickets_df[time_column] = pd.to_datetime(tickets_df[time_column], errors='coerce')

        # Create time period column
        if bin_type == 'monthly':
            tickets_df['period'] = tickets_df[time_column].dt.to_period('M').astype(str)
        elif bin_type == 'quarterly':
            tickets_df['period'] = tickets_df[time_column].dt.to_period('Q').astype(str)
        elif bin_type == 'yearly':
            tickets_df['period'] = tickets_df[time_column].dt.to_period('Y').astype(str)
        else:
            raise ValueError(f"Unknown bin_type: {bin_type}")

        # Export each period
        output_paths = {}
        for period in tickets_df['period'].unique():
            if pd.isna(period):
                continue

            output_name = f"tickets_{bin_type}_{period}.geojson"
            path = self.export_tickets(
                tickets_df,
                output_name=output_name,
                filter_by={'period': period}
            )
            output_paths[period] = path

        return output_paths

    def create_manifest(
        self,
        project_name: str,
        layer_files: Dict[str, Path],
        bounds: Optional[Dict[str, float]] = None,
        statistics: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Create a manifest.json describing all exported layers.

        Args:
            project_name: Name of the project
            layer_files: Dictionary mapping layer IDs to file paths
            bounds: Bounding box {west, south, east, north}
            statistics: Project statistics

        Returns:
            Path to manifest.json
        """
        manifest = {
            'project': project_name,
            'generated': datetime.now().isoformat(),
            'bounds': bounds,
            'layers': []
        }

        # Add layer metadata
        for layer_id, file_path in layer_files.items():
            # Load GeoJSON to get properties
            with open(file_path) as f:
                geojson = json.load(f)

            properties = {}
            if geojson['features']:
                properties = {
                    k: type(v).__name__
                    for k, v in geojson['features'][0]['properties'].items()
                }

            manifest['layers'].append({
                'id': layer_id,
                'type': geojson['features'][0]['geometry']['type'] if geojson['features'] else 'Point',
                'source': str(file_path.relative_to(self.output_dir)),
                'properties': properties,
                'count': len(geojson['features'])
            })

        if statistics:
            manifest['statistics'] = statistics

        # Write manifest
        manifest_path = self.output_dir / 'manifest.json'
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        return manifest_path


if __name__ == "__main__":
    # Example usage
    print("GeoJSON Exporter - Example Usage")
    print("="*50)

    # This would be called from a pipeline script
    print("""
    from kcci_maintenance.export import GeoJSONExporter

    # Initialize exporter
    exporter = GeoJSONExporter(output_dir='exports/floydada/layers')

    # Export all tickets
    exporter.export_tickets(tickets_df, output_name='tickets_all.geojson')

    # Export by type
    exporter.export_by_ticket_type(tickets_df)

    # Export route corridor
    exporter.export_route_corridor(route_gdf, buffer_distance_m=500)

    # Create manifest
    exporter.create_manifest(
        project_name='Floydada',
        layer_files={'tickets': 'tickets_all.geojson'},
        bounds={'west': -101.5, 'south': 33.8, 'east': -101.2, 'north': 34.1}
    )
    """)
