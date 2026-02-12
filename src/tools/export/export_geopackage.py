#!/usr/bin/env python
"""
CLI tool to export GeoPackage for Osprey Strike integration.

Usage:
    python export_geopackage.py --config config/projects/floydada_project.yaml --output exports/floydada_osprey
"""

import argparse
from pathlib import Path
import sys
import pandas as pd
import geopandas as gpd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kcci_maintenance.config_manager import ConfigManager
from kcci_maintenance.cache.cache_manager import CacheManager
from kcci_maintenance.cache.models import CacheQuery
from kcci_maintenance.export import GeoPackageExporter


def load_tickets_from_cache(cache_path: Path) -> pd.DataFrame:
    """Load geocoded tickets from cache database.

    Args:
        cache_path: Path to cache database

    Returns:
        DataFrame with ticket data
    """
    print(f"Loading tickets from cache: {cache_path}")

    cache_manager = CacheManager(db_path=cache_path)

    # Get all geocoded records
    records = cache_manager.query(CacheQuery())

    if not records:
        raise ValueError("No cached records found")

    # Convert to DataFrame
    data = []
    for record in records:
        data.append({
            'ticket_number': record.ticket_number,
            'latitude': record.latitude,
            'longitude': record.longitude,
            'confidence': record.confidence,
            'method': record.method,
            'ticket_type': record.ticket_type,
            'duration': record.duration,
            'work_type': record.work_type,
            'excavator': record.excavator,
            'created_at': record.created_at,
            'route_leg': getattr(record, 'route_leg', None),
            'city': record.city,
            'county': record.county
        })

    df = pd.DataFrame(data)

    # Filter to valid coordinates
    df = df.dropna(subset=['latitude', 'longitude'])

    print(f"Loaded {len(df)} tickets")

    return df


def load_route_from_config(config: dict) -> gpd.GeoDataFrame:
    """Load route from KMZ file if configured.

    Args:
        config: Configuration dictionary

    Returns:
        GeoDataFrame with route geometry or None
    """
    if 'route' not in config or 'kmz_path' not in config['route']:
        return None

    kmz_path = Path(config['route']['kmz_path'])

    if not kmz_path.exists():
        print(f"Warning: Route file not found: {kmz_path}")
        return None

    print(f"Loading route from: {kmz_path}")

    try:
        import zipfile
        from lxml import etree

        # Extract KML from KMZ
        with zipfile.ZipFile(kmz_path, 'r') as kmz:
            kml_file = [f for f in kmz.namelist() if f.endswith('.kml')][0]
            kml_data = kmz.read(kml_file)

        # Parse KML
        root = etree.fromstring(kml_data)

        # Simple extraction (would need more robust parsing for complex KML)
        # For now, just return None if complex
        print("Route loading from KMZ not fully implemented, skipping route data")
        return None

    except Exception as e:
        print(f"Warning: Could not load route: {e}")
        return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Export GeoPackage for Osprey Strike OSP integration'
    )
    parser.add_argument(
        '--config',
        type=Path,
        required=True,
        help='Path to project configuration YAML file'
    )
    parser.add_argument(
        '--output',
        type=Path,
        required=True,
        help='Output directory for GeoPackage'
    )
    parser.add_argument(
        '--output-name',
        default='osprey_maintenance.gpkg',
        help='Output filename (default: osprey_maintenance.gpkg)'
    )
    parser.add_argument(
        '--patrol-zone-size',
        type=float,
        default=1000.0,
        help='Patrol zone grid size in meters (default: 1000.0)'
    )
    parser.add_argument(
        '--high-density-threshold',
        type=int,
        default=20,
        help='Ticket count threshold for high-priority zones (default: 20)'
    )

    args = parser.parse_args()

    # Load configuration
    print(f"Loading configuration from: {args.config}")
    config_manager = ConfigManager()
    config = config_manager.load(args.config)

    # Resolve cache path
    cache_path = Path(config.cache_db_path)

    if not cache_path.exists():
        print(f"Error: Cache database not found: {cache_path}")
        sys.exit(1)

    # Load tickets
    tickets_df = load_tickets_from_cache(cache_path)

    # Load route (optional)
    route_gdf = None  # Route loading from KMZ not fully implemented

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    # Initialize exporter
    print(f"\nExporting to: {args.output}")
    exporter = GeoPackageExporter(args.output)

    # Export Osprey package
    print("\nGenerating Osprey Strike GeoPackage...")
    gpkg_path = exporter.export_osprey_package(
        tickets_df,
        route_gdf=route_gdf,
        output_name=args.output_name,
        patrol_zone_size_m=args.patrol_zone_size,
        high_density_threshold=args.high_density_threshold
    )

    print(f"\n✓ GeoPackage created: {gpkg_path}")
    print(f"  Size: {gpkg_path.stat().st_size / 1024 / 1024:.1f} MB")

    # Read back and show layer info
    print("\nLayers:")
    import fiona
    layers = fiona.listlayers(str(gpkg_path))
    for layer in layers:
        gdf = gpd.read_file(gpkg_path, layer=layer)
        print(f"  - {layer}: {len(gdf)} features")

    # Export patrol schedule
    print("\nGenerating patrol schedule CSV...")
    schedule_path = exporter.export_patrol_schedule(
        tickets_df,
        route_gdf=route_gdf,
        output_name='patrol_schedule.csv'
    )

    print(f"✓ Patrol schedule created: {schedule_path}")

    print("\n✅ Export complete!")
    print(f"\nTo use in QGIS or ArcGIS:")
    print(f"  1. Open {gpkg_path}")
    print(f"  2. Load desired layers")
    print(f"  3. Style based on priority/risk_score fields")


if __name__ == '__main__':
    main()
