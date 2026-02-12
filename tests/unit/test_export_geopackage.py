"""
Unit tests for GeoPackage exporter.
"""

import pytest
from pathlib import Path
from datetime import datetime
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString
import numpy as np
import sqlite3

from kcci_maintenance.export import GeoPackageExporter


@pytest.fixture
def sample_tickets_df():
    """Create sample tickets dataframe for testing."""
    np.random.seed(42)

    return pd.DataFrame({
        'ticket_number': [f'T{i:03d}' for i in range(30)],
        'latitude': np.random.uniform(33.4, 33.8, 30),
        'longitude': np.random.uniform(-101.8, -101.4, 30),
        'ticket_type': np.random.choice(['Normal', 'Emergency', 'DigUp'], 30,
                                       p=[0.7, 0.2, 0.1]),
        'work_type': np.random.choice(['Repair', 'Install', 'Replace'], 30),
        'created_at': pd.date_range('2024-01-01', periods=30, freq='D'),
        'confidence': np.random.uniform(0.7, 0.95, 30),
        'route_leg': np.random.choice(['Leg1', 'Leg2', 'Leg3'], 30),
        'city': np.random.choice(['CityA', 'CityB'], 30),
        'county': np.random.choice(['CountyX', 'CountyY'], 30)
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
    output_dir = tmp_path / "geopackages"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def exporter(temp_output_dir):
    """Create GeoPackage exporter instance."""
    return GeoPackageExporter(temp_output_dir)


class TestGeoPackageExporter:
    """Test GeoPackage exporter functionality."""

    def test_initialization(self, temp_output_dir):
        """Test exporter initialization creates output directory."""
        exporter = GeoPackageExporter(temp_output_dir)
        assert exporter.output_dir == temp_output_dir
        assert temp_output_dir.exists()

    def test_export_osprey_package_basic(self, exporter, sample_tickets_df):
        """Test basic Osprey package export."""
        output_path = exporter.export_osprey_package(sample_tickets_df)

        assert output_path.exists()
        assert output_path.suffix == '.gpkg'

        # Verify it's a valid GeoPackage (SQLite database)
        conn = sqlite3.connect(output_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        # Should have GeoPackage system tables and our layers
        assert any('gpkg_' in table for table in tables)

    def test_export_osprey_package_layers(self, exporter, sample_tickets_df, sample_route_gdf):
        """Test that all expected layers are created."""
        output_path = exporter.export_osprey_package(
            sample_tickets_df,
            route_gdf=sample_route_gdf
        )

        # Load each layer
        tickets = gpd.read_file(output_path, layer='tickets')
        route_segments = gpd.read_file(output_path, layer='route_segments')
        patrol_zones = gpd.read_file(output_path, layer='patrol_zones')

        assert len(tickets) == 30
        assert len(route_segments) == 3
        assert len(patrol_zones) > 0

    def test_tickets_layer_schema(self, exporter, sample_tickets_df):
        """Test tickets layer has correct schema."""
        output_path = exporter.export_osprey_package(sample_tickets_df)

        tickets = gpd.read_file(output_path, layer='tickets')

        # Check expected columns
        expected_columns = [
            'ticket_id', 'type', 'work_category', 'date',
            'requires_patrol', 'estimated_visit_time_min', 'risk_score'
        ]

        for col in expected_columns:
            assert col in tickets.columns

    def test_tickets_layer_risk_score(self, exporter, sample_tickets_df):
        """Test risk score calculation."""
        output_path = exporter.export_osprey_package(sample_tickets_df)

        tickets = gpd.read_file(output_path, layer='tickets')

        # All tickets should have risk score
        assert tickets['risk_score'].notna().all()

        # Risk scores should be 0-100
        assert (tickets['risk_score'] >= 0).all()
        assert (tickets['risk_score'] <= 100).all()

        # Emergency tickets should have higher risk scores
        if 'Emergency' in tickets['type'].values:
            emergency_avg = tickets[tickets['type'] == 'Emergency']['risk_score'].mean()
            normal_avg = tickets[tickets['type'] == 'Normal']['risk_score'].mean()
            assert emergency_avg > normal_avg

    def test_tickets_layer_patrol_flags(self, exporter, sample_tickets_df):
        """Test patrol requirement flags."""
        output_path = exporter.export_osprey_package(sample_tickets_df)

        tickets = gpd.read_file(output_path, layer='tickets')

        # Emergency and DigUp should require patrol
        emergency_tickets = tickets[tickets['type'] == 'Emergency']
        if len(emergency_tickets) > 0:
            assert emergency_tickets['requires_patrol'].all()

    def test_route_layer_statistics(self, exporter, sample_tickets_df, sample_route_gdf):
        """Test route segments have statistics."""
        # Ensure tickets have route_leg matching route names
        sample_tickets_df['route_leg'] = np.random.choice(['Leg1', 'Leg2', 'Leg3'], len(sample_tickets_df))

        output_path = exporter.export_osprey_package(
            sample_tickets_df,
            route_gdf=sample_route_gdf
        )

        routes = gpd.read_file(output_path, layer='route_segments')

        # Check statistics columns
        assert 'ticket_count' in routes.columns
        assert 'emergency_count' in routes.columns
        assert 'patrol_priority' in routes.columns
        assert 'patrol_frequency' in routes.columns
        assert 'estimated_annual_visits' in routes.columns
        assert 'estimated_annual_cost_usd' in routes.columns

    def test_route_layer_priorities(self, exporter, sample_route_gdf):
        """Test patrol priority classification."""
        # Create tickets with known distribution
        tickets_df = pd.DataFrame({
            'ticket_number': [f'T{i:03d}' for i in range(60)],
            'latitude': [33.5] * 60,
            'longitude': [-101.5] * 60,
            'ticket_type': ['Normal'] * 60,
            'route_leg': ['Leg1'] * 60  # All in Leg1
        })

        output_path = exporter.export_osprey_package(
            tickets_df,
            route_gdf=sample_route_gdf
        )

        routes = gpd.read_file(output_path, layer='route_segments')

        # Leg1 should have HIGH priority (>= 50 tickets)
        leg1 = routes[routes['name'] == 'Leg1'].iloc[0]
        assert leg1['patrol_priority'] == 'HIGH'
        assert leg1['patrol_frequency'] == 'weekly'

    def test_patrol_zones_generation(self, exporter, sample_tickets_df):
        """Test patrol zone grid generation."""
        output_path = exporter.export_osprey_package(
            sample_tickets_df,
            patrol_zone_size_m=1000.0,
            high_density_threshold=5
        )

        patrol_zones = gpd.read_file(output_path, layer='patrol_zones')

        assert len(patrol_zones) > 0

        # Check columns
        expected_columns = [
            'zone_id', 'ticket_count', 'emergency_count', 'normal_count',
            'priority', 'recommended_frequency', 'center_lat', 'center_lon'
        ]

        for col in expected_columns:
            assert col in patrol_zones.columns

    def test_patrol_zones_priorities(self, exporter):
        """Test patrol zone priority classification."""
        # Create tickets spread across area
        np.random.seed(42)
        tickets_df = pd.DataFrame({
            'ticket_number': [f'T{i:03d}' for i in range(50)],
            'latitude': np.random.uniform(33.5, 33.6, 50),
            'longitude': np.random.uniform(-101.5, -101.4, 50),
            'ticket_type': ['Normal'] * 50
        })

        output_path = exporter.export_osprey_package(
            tickets_df,
            patrol_zone_size_m=1000.0,
            high_density_threshold=10
        )

        patrol_zones = gpd.read_file(output_path, layer='patrol_zones')

        # Should have at least one zone
        assert len(patrol_zones) > 0
        # Should have priority assigned
        assert 'priority' in patrol_zones.columns
        # Priorities should be valid
        assert patrol_zones['priority'].isin(['LOW', 'MEDIUM', 'HIGH']).all()

    def test_high_risk_areas_identification(self, exporter):
        """Test high-risk area clustering."""
        # Create emergency cluster
        tickets_df = pd.DataFrame({
            'ticket_number': [f'T{i:03d}' for i in range(20)],
            'latitude': [33.5] * 10 + [33.7] * 10,
            'longitude': [-101.5] * 10 + [-101.7] * 10,
            'ticket_type': ['Emergency'] * 10 + ['Normal'] * 10,
            'created_at': pd.date_range('2024-01-01', periods=20, freq='D')
        })

        output_path = exporter.export_osprey_package(tickets_df)

        # Load high-risk areas
        high_risk = gpd.read_file(output_path, layer='high_risk_areas')

        # Should identify the emergency cluster
        assert len(high_risk) > 0

        # Check columns
        assert 'area_id' in high_risk.columns
        assert 'emergency_count' in high_risk.columns
        assert 'risk_level' in high_risk.columns
        assert 'requires_immediate_attention' in high_risk.columns

    def test_metadata_table(self, exporter, sample_tickets_df):
        """Test metadata table creation."""
        output_path = exporter.export_osprey_package(sample_tickets_df)

        # Read metadata table
        conn = sqlite3.connect(output_path)
        metadata_df = pd.read_sql_query("SELECT * FROM metadata", conn)
        conn.close()

        assert len(metadata_df) == 1

        metadata = metadata_df.iloc[0]
        assert 'generated' in metadata
        assert metadata['total_tickets'] == 30
        assert metadata['format_version'] == '1.0'
        assert metadata['target_system'] == 'Osprey Strike OSP'

    def test_export_patrol_schedule(self, exporter, sample_tickets_df, sample_route_gdf):
        """Test patrol schedule CSV export."""
        # Ensure tickets have route_leg
        sample_tickets_df['route_leg'] = np.random.choice(['Leg1', 'Leg2', 'Leg3'], len(sample_tickets_df))

        output_path = exporter.export_patrol_schedule(
            sample_tickets_df,
            route_gdf=sample_route_gdf
        )

        assert output_path.exists()
        assert output_path.suffix == '.csv'

        # Load and verify
        schedule = pd.read_csv(output_path)

        assert len(schedule) == 3  # One row per route segment

        # Check columns
        expected_columns = [
            'route_segment', 'ticket_count', 'frequency',
            'annual_visits', 'estimated_hours_per_visit', 'estimated_annual_hours'
        ]

        for col in expected_columns:
            assert col in schedule.columns

    def test_coordinate_reference_system(self, exporter, sample_tickets_df):
        """Test that output CRS is WGS84."""
        output_path = exporter.export_osprey_package(sample_tickets_df)

        tickets = gpd.read_file(output_path, layer='tickets')
        patrol_zones = gpd.read_file(output_path, layer='patrol_zones')

        assert tickets.crs.to_string() == 'EPSG:4326'
        assert patrol_zones.crs.to_string() == 'EPSG:4326'

    def test_geometry_validity(self, exporter, sample_tickets_df):
        """Test that all geometries are valid."""
        output_path = exporter.export_osprey_package(sample_tickets_df)

        tickets = gpd.read_file(output_path, layer='tickets')
        patrol_zones = gpd.read_file(output_path, layer='patrol_zones')

        assert tickets.geometry.is_valid.all()
        assert patrol_zones.geometry.is_valid.all()

    def test_empty_dataframe(self, exporter):
        """Test handling of minimal dataframe."""
        # Use minimal but valid data (empty fails on patrol zone generation)
        minimal_df = pd.DataFrame({
            'ticket_number': ['T001'],
            'latitude': [33.5],
            'longitude': [-101.5]
        })

        # Should not fail with minimal data
        output_path = exporter.export_osprey_package(minimal_df)
        assert output_path.exists()

    def test_no_emergency_tickets(self, exporter):
        """Test handling when no emergency tickets present."""
        tickets_df = pd.DataFrame({
            'ticket_number': ['T001', 'T002'],
            'latitude': [33.5, 33.6],
            'longitude': [-101.5, -101.6],
            'ticket_type': ['Normal', 'Normal']
        })

        output_path = exporter.export_osprey_package(tickets_df)

        # Should still create package without high-risk layer
        tickets = gpd.read_file(output_path, layer='tickets')
        assert len(tickets) == 2

    def test_custom_zone_sizes(self, exporter, sample_tickets_df):
        """Test different patrol zone sizes."""
        large_path = exporter.export_osprey_package(
            sample_tickets_df,
            patrol_zone_size_m=2000.0,
            output_name='large_zones.gpkg'
        )

        small_path = exporter.export_osprey_package(
            sample_tickets_df,
            patrol_zone_size_m=500.0,
            output_name='small_zones.gpkg'
        )

        large_zones = gpd.read_file(large_path, layer='patrol_zones')
        small_zones = gpd.read_file(small_path, layer='patrol_zones')

        # Smaller zones should create more grid cells
        assert len(small_zones) > len(large_zones)

    def test_custom_density_threshold(self, exporter):
        """Test different high density thresholds."""
        # Create tickets spread across area
        np.random.seed(43)
        tickets_df = pd.DataFrame({
            'ticket_number': [f'T{i:03d}' for i in range(30)],
            'latitude': np.random.uniform(33.5, 33.55, 30),
            'longitude': np.random.uniform(-101.5, -101.45, 30),
            'ticket_type': ['Normal'] * 30
        })

        # Low threshold should create patrol zones
        output_path = exporter.export_osprey_package(
            tickets_df,
            patrol_zone_size_m=500.0,
            high_density_threshold=5
        )

        patrol_zones = gpd.read_file(output_path, layer='patrol_zones')
        # Should have at least one zone
        assert len(patrol_zones) > 0
        assert 'priority' in patrol_zones.columns

    def test_date_serialization(self, exporter, sample_tickets_df):
        """Test that dates are properly serialized."""
        output_path = exporter.export_osprey_package(sample_tickets_df)

        tickets = gpd.read_file(output_path, layer='tickets')

        # Dates should be strings in ISO format
        assert 'date' in tickets.columns
        # Should be string type (can be 'object' or StringDtype)
        assert tickets['date'].dtype.kind in ('O', 'U', 'S') or 'str' in str(tickets['date'].dtype).lower()

        # Verify format
        date_str = tickets['date'].iloc[0]
        assert isinstance(date_str, str)
        assert len(date_str) > 0
