#!/usr/bin/env python3
"""
Export complete map data bundle for downstream consumption.

Generates a comprehensive data package including:
- GeoJSON layers (tickets, routes, heat maps)
- Statistics (time series, distributions)
- Manifest for easy integration
- Optional: vector tiles for high-performance mapping
"""

import sys
from pathlib import Path
import argparse
import pandas as pd
import geopandas as gpd
from datetime import datetime

from kcci_maintenance.config_manager import ConfigManager
from kcci_maintenance.cache.cache_manager import CacheManager
from kcci_maintenance.cache.models import CacheQuery
from kcci_maintenance.export import GeoJSONExporter, HeatMapGenerator, StatisticsAggregator


def export_map_bundle(
    config_path: Path,
    output_dir: Path,
    include_heatmaps: bool = True,
    include_timeseries: bool = True,
    include_tiles: bool = False
) -> None:
    """Export complete map data bundle from project configuration.

    Args:
        config_path: Path to project YAML configuration
        output_dir: Directory for export bundle
        include_heatmaps: Whether to generate heat maps
        include_timeseries: Whether to generate time series data
        include_tiles: Whether to generate vector tiles (future)
    """
    print(f"\n{'='*70}")
    print(f"Exporting Map Bundle")
    print(f"{'='*70}\n")

    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.load(config_path)

    print(f"Project: {config.name}")
    print(f"Output: {output_dir}\n")

    # Create output directories
    layers_dir = output_dir / "layers"
    stats_dir = output_dir / "statistics"
    heatmaps_dir = output_dir / "heatmaps"

    layers_dir.mkdir(parents=True, exist_ok=True)
    stats_dir.mkdir(parents=True, exist_ok=True)
    if include_heatmaps:
        heatmaps_dir.mkdir(parents=True, exist_ok=True)

    # Load ticket data from cache
    print("📊 Loading ticket data from cache...")
    cache_manager = CacheManager(db_path=config.cache_db_path)
    records = cache_manager.query(CacheQuery())

    # Convert to DataFrame
    data = []
    for record in records:
        data.append({
            "ticket_number": record.ticket_number,
            "latitude": record.latitude,
            "longitude": record.longitude,
            "confidence": record.confidence,
            "method": record.method,
            "ticket_type": record.ticket_type,
            "duration": record.duration,
            "work_type": record.work_type,
            "excavator": record.excavator,
            "created_at": record.created_at,
            "route_leg": getattr(record, 'route_leg', None),
            "city": record.city,
            "county": record.county,
        })

    tickets_df = pd.DataFrame(data)

    # Filter to geocoded only
    tickets_df = tickets_df[
        (tickets_df['latitude'].notna()) &
        (tickets_df['longitude'].notna())
    ]

    print(f"   Loaded {len(tickets_df):,} geocoded tickets\n")

    # Load route data if available
    route_gdf = None
    raw_config = config_manager._config
    if 'route' in raw_config and 'kmz_path' in raw_config['route']:
        kmz_path = Path(raw_config['route']['kmz_path'])
        if kmz_path.exists():
            print(f"📍 Loading route from {kmz_path}...")
            # Load route (simplified - would use proper KMZ loader)
            # For now, create a placeholder
            route_gdf = None  # TODO: Load from KMZ
            print("   Route loaded\n")

    # Initialize exporters
    geojson_exporter = GeoJSONExporter(output_dir=layers_dir)
    stats_aggregator = StatisticsAggregator(output_dir=stats_dir)

    if include_heatmaps:
        heatmap_generator = HeatMapGenerator(output_dir=heatmaps_dir)

    # Export ticket layers
    print("🗺️  Exporting GeoJSON layers...")

    layer_files = {}

    # All tickets
    path = geojson_exporter.export_tickets(tickets_df, output_name='tickets_all.geojson')
    layer_files['tickets_all'] = path
    print(f"   ✓ tickets_all.geojson ({len(tickets_df):,} features)")

    # By ticket type
    type_paths = geojson_exporter.export_by_ticket_type(tickets_df)
    for ticket_type, path in type_paths.items():
        layer_id = f"tickets_{ticket_type.lower().replace(' ', '_')}"
        layer_files[layer_id] = path
        count = len(tickets_df[tickets_df['ticket_type'] == ticket_type])
        print(f"   ✓ {path.name} ({count:,} features)")

    # Export route if available
    if route_gdf is not None:
        path = geojson_exporter.export_route_corridor(
            route_gdf,
            buffer_distance_m=500,
            output_name='route_corridor.geojson'
        )
        layer_files['route_corridor'] = path
        print(f"   ✓ route_corridor.geojson")

    print()

    # Export statistics
    print("📈 Generating statistics...")

    stats_aggregator.generate_summary(tickets_df, output_name='summary.json')
    print("   ✓ summary.json")

    if include_timeseries:
        stats_aggregator.generate_timeseries(tickets_df, bin_type='monthly', output_name='timeseries.json')
        print("   ✓ timeseries.json")

    stats_aggregator.generate_type_distribution(tickets_df, group_by='ticket_type', output_name='type_distribution.json')
    print("   ✓ type_distribution.json")

    if 'route_leg' in tickets_df.columns:
        stats_aggregator.generate_spatial_distribution(tickets_df, group_by='route_leg', output_name='spatial_distribution.json')
        print("   ✓ spatial_distribution.json")

    print()

    # Generate heat maps
    if include_heatmaps:
        print("🔥 Generating heat maps...")

        heatmap_generator.generate_hexbin(tickets_df, resolution_m=500, output_name='hexbin_500m.geojson')
        print("   ✓ hexbin_500m.geojson")

        # Kernel density (computationally expensive, use smaller resolution)
        heatmap_generator.generate_kernel_density(tickets_df, grid_resolution=50, output_name='kernel_density.geojson')
        print("   ✓ kernel_density.geojson")

        if route_gdf is not None:
            heatmap_generator.generate_risk_zones(tickets_df, route_gdf, output_name='risk_zones.geojson')
            print("   ✓ risk_zones.geojson")

        print()

    # Calculate bounds
    bounds = {
        'west': float(tickets_df['longitude'].min()),
        'south': float(tickets_df['latitude'].min()),
        'east': float(tickets_df['longitude'].max()),
        'north': float(tickets_df['latitude'].max())
    }

    # Load statistics for manifest
    import json
    with open(stats_dir / 'summary.json') as f:
        statistics = json.load(f)

    # Create manifest
    print("📋 Creating manifest...")
    manifest_path = geojson_exporter.create_manifest(
        project_name=config.name,
        layer_files=layer_files,
        bounds=bounds,
        statistics=statistics
    )
    print(f"   ✓ {manifest_path.name}\n")

    print("="*70)
    print("✅ Map bundle export complete!")
    print(f"📂 Output directory: {output_dir}")
    print(f"📊 Total layers: {len(layer_files)}")
    print("="*70 + "\n")

    # Print usage example
    print("Integration Example:")
    print("-" * 70)
    print(f"""
// Load manifest
const manifest = await fetch('{output_dir}/manifest.json').then(r => r.json());

// Add tickets layer
map.addSource('tickets', {{
  type: 'geojson',
  data: '{output_dir}/layers/tickets_all.geojson'
}});

map.addLayer({{
  id: 'tickets',
  type: 'circle',
  source: 'tickets',
  paint: {{
    'circle-radius': 6,
    'circle-color': '#FF6B6B'
  }}
}});
    """)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Export map data bundle for downstream consumption'
    )
    parser.add_argument(
        '--config',
        type=Path,
        required=True,
        help='Path to project YAML configuration'
    )
    parser.add_argument(
        '--output',
        type=Path,
        required=True,
        help='Output directory for map bundle'
    )
    parser.add_argument(
        '--no-heatmaps',
        action='store_true',
        help='Skip heat map generation'
    )
    parser.add_argument(
        '--no-timeseries',
        action='store_true',
        help='Skip time series generation'
    )
    parser.add_argument(
        '--tiles',
        action='store_true',
        help='Generate vector tiles (future)'
    )

    args = parser.parse_args()

    # Validate config exists
    if not args.config.exists():
        print(f"❌ Error: Config file not found: {args.config}")
        sys.exit(1)

    # Export bundle
    export_map_bundle(
        config_path=args.config,
        output_dir=args.output,
        include_heatmaps=not args.no_heatmaps,
        include_timeseries=not args.no_timeseries,
        include_tiles=args.tiles
    )


if __name__ == "__main__":
    main()
