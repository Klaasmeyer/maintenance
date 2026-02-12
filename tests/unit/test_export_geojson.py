"""
Unit tests for GeoJSON exporter.
"""

import json
import pytest
from pathlib import Path
from datetime import datetime
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString

from kcci_maintenance.export import GeoJSONExporter


@pytest.fixture
def sample_tickets_df():
    """Create sample tickets dataframe for testing."""
    return pd.DataFrame({
        'ticket_number': ['T001', 'T002', 'T003', 'T004', 'T005'],
        'latitude': [33.5, 33.6, 33.7, 33.8, 33.9],
        'longitude': [-101.5, -101.6, -101.7, -101.8, -101.9],
        'ticket_type': ['Normal', 'Emergency', 'Normal', 'DigUp', 'Emergency'],
        'work_type': ['Repair', 'Replace', 'Install', 'Survey', 'Repair'],
        'created_at': [
            '2024-01-01', '2024-01-15', '2024-02-01', '2024-02-15', '2024-03-01'
        ],
        'city': ['CityA', 'CityB', 'CityA', 'CityC', 'CityB'],
        'county': ['CountyX', 'CountyY', 'CountyX', 'CountyZ', 'CountyY'],
        'confidence': [0.95, 0.88, 0.92, 0.85, 0.90],
        'route_leg': ['Leg1', 'Leg2', 'Leg1', 'Leg3', 'Leg2']
    })


@pytest.fixture
def sample_route_gdf():
    """Create sample route geodataframe for testing."""
    return gpd.GeoDataFrame({
        'name': ['Leg1', 'Leg2', 'Leg3'],
        'geometry': [
            LineString([(-101.5, 33.5), (-101.6, 33.6)]),
            LineString([(-101.6, 33.6), (-101.7, 33.7)]),
            LineString([(-101.7, 33.7), (-101.8, 33.8)])
        ]
    }, crs='EPSG:4326')


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create temporary output directory."""
    output_dir = tmp_path / "exports"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def exporter(temp_output_dir):
    """Create GeoJSON exporter instance."""
    return GeoJSONExporter(temp_output_dir)


class TestGeoJSONExporter:
    """Test GeoJSON exporter functionality."""

    def test_initialization(self, temp_output_dir):
        """Test exporter initialization creates output directory."""
        exporter = GeoJSONExporter(temp_output_dir)
        assert exporter.output_dir == temp_output_dir
        assert temp_output_dir.exists()

    def test_export_tickets_basic(self, exporter, sample_tickets_df, temp_output_dir):
        """Test basic ticket export to GeoJSON."""
        output_path = exporter.export_tickets(sample_tickets_df, output_name='test.geojson')

        assert output_path.exists()
        assert output_path == temp_output_dir / 'test.geojson'

        # Load and verify GeoJSON structure
        with open(output_path) as f:
            geojson = json.load(f)

        assert geojson['type'] == 'FeatureCollection'
        assert len(geojson['features']) == 5
        assert 'metadata' in geojson
        assert geojson['metadata']['count'] == 5

    def test_export_tickets_geometry(self, exporter, sample_tickets_df):
        """Test that geometries are correctly formatted."""
        output_path = exporter.export_tickets(sample_tickets_df)

        with open(output_path) as f:
            geojson = json.load(f)

        # Check first feature
        feature = geojson['features'][0]
        assert feature['type'] == 'Feature'
        assert feature['geometry']['type'] == 'Point'
        assert len(feature['geometry']['coordinates']) == 2
        assert feature['geometry']['coordinates'][0] == -101.5  # longitude
        assert feature['geometry']['coordinates'][1] == 33.5    # latitude

    def test_export_tickets_properties(self, exporter, sample_tickets_df):
        """Test that properties are correctly transferred."""
        output_path = exporter.export_tickets(sample_tickets_df)

        with open(output_path) as f:
            geojson = json.load(f)

        properties = geojson['features'][0]['properties']
        assert properties['ticket_number'] == 'T001'
        assert properties['ticket_type'] == 'Normal'
        assert properties['city'] == 'CityA'
        assert properties['confidence'] == 0.95

    def test_export_tickets_with_filter(self, exporter, sample_tickets_df):
        """Test filtering tickets by type."""
        output_path = exporter.export_tickets(
            sample_tickets_df,
            filter_by={'ticket_type': 'Emergency'}
        )

        with open(output_path) as f:
            geojson = json.load(f)

        assert len(geojson['features']) == 2
        assert all(f['properties']['ticket_type'] == 'Emergency'
                  for f in geojson['features'])

    def test_export_tickets_with_list_filter(self, exporter, sample_tickets_df):
        """Test filtering with list of values."""
        output_path = exporter.export_tickets(
            sample_tickets_df,
            filter_by={'ticket_type': ['Emergency', 'DigUp']}
        )

        with open(output_path) as f:
            geojson = json.load(f)

        assert len(geojson['features']) == 3

    def test_export_by_ticket_type(self, exporter, sample_tickets_df):
        """Test exporting separate files per ticket type."""
        output_paths = exporter.export_by_ticket_type(sample_tickets_df)

        assert len(output_paths) == 3  # Normal, Emergency, DigUp
        assert 'Normal' in output_paths
        assert 'Emergency' in output_paths
        assert 'DigUp' in output_paths

        # Verify each file exists and has correct content
        for ticket_type, path in output_paths.items():
            assert path.exists()
            with open(path) as f:
                geojson = json.load(f)
            assert all(f['properties']['ticket_type'] == ticket_type
                      for f in geojson['features'])

    def test_export_by_ticket_type_filename_sanitization(self, exporter):
        """Test that problematic characters in filenames are sanitized."""
        df = pd.DataFrame({
            'ticket_number': ['T001'],
            'latitude': [33.5],
            'longitude': [-101.5],
            'ticket_type': ['Survey/Design']
        })

        output_paths = exporter.export_by_ticket_type(df)

        # Should replace slash with underscore
        assert 'Survey/Design' in output_paths
        path = output_paths['Survey/Design']
        assert 'survey_design' in path.name

    def test_export_route_corridor(self, exporter, sample_route_gdf, temp_output_dir):
        """Test route corridor export."""
        output_path = exporter.export_route_corridor(
            sample_route_gdf,
            include_buffer=False
        )

        assert output_path.exists()

        with open(output_path) as f:
            geojson = json.load(f)

        # Should have 3 route features
        assert len(geojson['features']) == 3
        assert all(f['geometry']['type'] == 'LineString'
                  for f in geojson['features'])

    def test_export_route_corridor_with_buffer(self, exporter, sample_route_gdf):
        """Test route corridor export with buffer zones."""
        output_path = exporter.export_route_corridor(
            sample_route_gdf,
            include_buffer=True,
            buffer_distance_m=500.0
        )

        with open(output_path) as f:
            geojson = json.load(f)

        # Should have 6 features: 3 routes + 3 buffers
        assert len(geojson['features']) == 6

        route_features = [f for f in geojson['features']
                         if f['properties']['type'] == 'route_line']
        buffer_features = [f for f in geojson['features']
                          if f['properties']['type'] == 'buffer_zone']

        assert len(route_features) == 3
        assert len(buffer_features) == 3

    def test_export_temporal_slices_monthly(self, exporter, sample_tickets_df):
        """Test temporal slicing by month."""
        output_paths = exporter.export_temporal_slices(
            sample_tickets_df,
            bin_type='monthly'
        )

        # Should have 3 months: Jan, Feb, Mar 2024
        assert len(output_paths) == 3

        for period, path in output_paths.items():
            assert path.exists()
            assert '2024' in period

    def test_create_manifest(self, exporter, sample_tickets_df, temp_output_dir):
        """Test manifest creation."""
        # Export some layers first
        layer_files = {
            'tickets_all': exporter.export_tickets(sample_tickets_df, 'tickets.geojson')
        }

        bounds = {
            'west': -101.9,
            'south': 33.5,
            'east': -101.5,
            'north': 33.9
        }

        manifest_path = exporter.create_manifest(
            'Test Project',
            layer_files,
            bounds=bounds
        )

        assert manifest_path.exists()
        assert manifest_path.name == 'manifest.json'

        with open(manifest_path) as f:
            manifest = json.load(f)

        assert manifest['project'] == 'Test Project'
        assert manifest['bounds'] == bounds
        assert len(manifest['layers']) == 1
        assert manifest['layers'][0]['id'] == 'tickets_all'
        assert manifest['layers'][0]['count'] == 5

    def test_null_handling(self, exporter):
        """Test that null values are handled correctly."""
        df = pd.DataFrame({
            'ticket_number': ['T001', 'T002'],
            'latitude': [33.5, 33.6],
            'longitude': [-101.5, -101.6],
            'ticket_type': ['Normal', None],
            'city': [None, 'CityB']
        })

        output_path = exporter.export_tickets(df)

        with open(output_path) as f:
            geojson = json.load(f)

        # Null values should be exported as JSON null
        assert geojson['features'][0]['properties']['city'] is None
        assert geojson['features'][1]['properties']['ticket_type'] is None

    def test_timestamp_serialization(self, exporter):
        """Test that timestamps are converted to ISO format."""
        df = pd.DataFrame({
            'ticket_number': ['T001'],
            'latitude': [33.5],
            'longitude': [-101.5],
            'created_at': [pd.Timestamp('2024-01-15 14:30:00')]
        })

        output_path = exporter.export_tickets(df)

        with open(output_path) as f:
            geojson = json.load(f)

        created_at = geojson['features'][0]['properties']['created_at']
        assert isinstance(created_at, str)
        assert '2024-01-15' in created_at
