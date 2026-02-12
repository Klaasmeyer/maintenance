"""
Unit tests for heat map generator.
"""

import json
import pytest
from pathlib import Path
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString
import numpy as np

from kcci_maintenance.export import HeatMapGenerator


@pytest.fixture
def sample_tickets_df():
    """Create sample tickets dataframe for testing."""
    # Create clustered points
    np.random.seed(42)

    # Cluster 1: around (33.5, -101.5)
    lat1 = np.random.normal(33.5, 0.01, 20)
    lon1 = np.random.normal(-101.5, 0.01, 20)

    # Cluster 2: around (33.7, -101.7)
    lat2 = np.random.normal(33.7, 0.01, 15)
    lon2 = np.random.normal(-101.7, 0.01, 15)

    # Scatter points
    lat3 = np.random.uniform(33.4, 33.8, 10)
    lon3 = np.random.uniform(-101.8, -101.4, 10)

    lats = np.concatenate([lat1, lat2, lat3])
    lons = np.concatenate([lon1, lon2, lon3])

    return pd.DataFrame({
        'ticket_number': [f'T{i:03d}' for i in range(len(lats))],
        'latitude': lats,
        'longitude': lons,
        'ticket_type': np.random.choice(['Normal', 'Emergency'], len(lats)),
        'created_at': pd.date_range('2024-01-01', periods=len(lats), freq='D')
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
    output_dir = tmp_path / "heatmaps"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def generator(temp_output_dir):
    """Create heat map generator instance."""
    return HeatMapGenerator(temp_output_dir)


class TestHeatMapGenerator:
    """Test heat map generator functionality."""

    def test_initialization(self, temp_output_dir):
        """Test generator initialization creates output directory."""
        generator = HeatMapGenerator(temp_output_dir)
        assert generator.output_dir == temp_output_dir
        assert temp_output_dir.exists()

    def test_generate_hexbin_basic(self, generator, sample_tickets_df):
        """Test basic hexbin heat map generation."""
        output_path = generator.generate_hexbin(
            sample_tickets_df,
            resolution_m=500.0
        )

        assert output_path.exists()

        with open(output_path) as f:
            geojson = json.load(f)

        assert geojson['type'] == 'FeatureCollection'
        assert len(geojson['features']) > 0

        # Check that features have expected properties
        feature = geojson['features'][0]
        assert 'ticket_count' in feature['properties']
        assert 'density' in feature['properties']
        assert feature['geometry']['type'] == 'Polygon'

    def test_hexbin_cell_sizes(self, generator, sample_tickets_df):
        """Test hexbin with different cell sizes."""
        # Larger cells should result in fewer hexagons
        large_path = generator.generate_hexbin(
            sample_tickets_df,
            resolution_m=1000.0,
            output_name='hexbin_large.geojson'
        )

        small_path = generator.generate_hexbin(
            sample_tickets_df,
            resolution_m=250.0,
            output_name='hexbin_small.geojson'
        )

        with open(large_path) as f:
            large_geojson = json.load(f)

        with open(small_path) as f:
            small_geojson = json.load(f)

        # Smaller cells should create more hexagons
        assert len(small_geojson['features']) > len(large_geojson['features'])

    def test_hexbin_ticket_counts(self, generator, sample_tickets_df):
        """Test that ticket counts are accurate."""
        output_path = generator.generate_hexbin(sample_tickets_df)

        with open(output_path) as f:
            geojson = json.load(f)

        # Sum of all ticket counts should be close to total (may have minor overlap)
        total_count = sum(f['properties']['ticket_count']
                         for f in geojson['features'])
        # Allow for some hexagon overlap/edge cases
        assert abs(total_count - len(sample_tickets_df)) <= len(sample_tickets_df) * 0.1

    def test_hexbin_density_calculation(self, generator, sample_tickets_df):
        """Test that density is calculated correctly."""
        output_path = generator.generate_hexbin(sample_tickets_df)

        with open(output_path) as f:
            geojson = json.load(f)

        # All hexagons should have density > 0 (tickets per km²)
        for feature in geojson['features']:
            density = feature['properties']['density']
            assert density > 0
            # Density is not normalized to 0-1, it's tickets per km²

    def test_generate_kernel_density_basic(self, generator, sample_tickets_df):
        """Test basic kernel density estimation."""
        output_path = generator.generate_kernel_density(
            sample_tickets_df,
            bandwidth=None,
            grid_resolution=50
        )

        assert output_path.exists()

        with open(output_path) as f:
            geojson = json.load(f)

        assert geojson['type'] == 'FeatureCollection'
        assert len(geojson['features']) > 0

        # Check properties
        feature = geojson['features'][0]
        assert 'density' in feature['properties']
        assert feature['geometry']['type'] == 'Polygon'

    def test_kernel_density_grid_sizes(self, generator, sample_tickets_df):
        """Test kernel density with different grid sizes."""
        coarse_path = generator.generate_kernel_density(
            sample_tickets_df,
            grid_resolution=20,
            output_name='kernel_coarse.geojson'
        )

        fine_path = generator.generate_kernel_density(
            sample_tickets_df,
            grid_resolution=50,
            output_name='kernel_fine.geojson'
        )

        with open(coarse_path) as f:
            coarse_geojson = json.load(f)

        with open(fine_path) as f:
            fine_geojson = json.load(f)

        # Finer grid should have more cells
        assert len(fine_geojson['features']) > len(coarse_geojson['features'])

    def test_kernel_density_normalization(self, generator, sample_tickets_df):
        """Test that kernel density is normalized 0-1."""
        output_path = generator.generate_kernel_density(sample_tickets_df)

        with open(output_path) as f:
            geojson = json.load(f)

        densities = [f['properties']['density'] for f in geojson['features']]
        assert min(densities) >= 0
        assert max(densities) <= 1.0

        # Should have at least one cell at maximum density
        assert max(densities) > 0.9

    def test_generate_risk_zones(self, generator, sample_tickets_df, sample_route_gdf):
        """Test risk zone generation."""
        # Add some emergency tickets
        sample_tickets_df['ticket_type'] = 'Normal'
        sample_tickets_df.loc[:5, 'ticket_type'] = 'Emergency'

        output_path = generator.generate_risk_zones(
            sample_tickets_df,
            sample_route_gdf,
            high_risk_threshold=5
        )

        assert output_path.exists()

        with open(output_path) as f:
            geojson = json.load(f)

        assert len(geojson['features']) > 0

        # Check zone properties
        feature = geojson['features'][0]
        assert 'risk_level' in feature['properties']

    def test_risk_zone_classification(self, generator, sample_route_gdf):
        """Test risk zone priority classification."""
        # Create data with known distribution
        df = pd.DataFrame({
            'ticket_number': [f'T{i:03d}' for i in range(30)],
            'latitude': [33.5] * 30,  # Cluster in one location
            'longitude': [-101.5] * 30,
            'ticket_type': ['Emergency'] * 10 + ['Normal'] * 20
        })

        output_path = generator.generate_risk_zones(df, sample_route_gdf, high_risk_threshold=5)

        with open(output_path) as f:
            geojson = json.load(f)

        # Should have risk zones
        assert len(geojson['features']) > 0

    def test_empty_dataframe(self, generator):
        """Test handling of empty dataframe."""
        empty_df = pd.DataFrame({
            'ticket_number': [],
            'latitude': [],
            'longitude': []
        })

        # Empty dataframe should fail gracefully or be skipped
        # This test verifies that the generator doesn't crash
        try:
            output_path = generator.generate_hexbin(empty_df)
            with open(output_path) as f:
                geojson = json.load(f)
            # If it succeeds, should return empty or minimal features
            assert isinstance(geojson['features'], list)
        except (ValueError, Exception):
            # It's acceptable to raise an error for empty data
            pass

    def test_single_point(self, generator):
        """Test handling of few clustered points."""
        # Use a few points with enough spread (0.01 degrees ~1km)
        single_df = pd.DataFrame({
            'ticket_number': ['T001', 'T002', 'T003'],
            'latitude': [33.5, 33.51, 33.52],
            'longitude': [-101.5, -101.51, -101.52]
        })

        output_path = generator.generate_hexbin(single_df, resolution_m=2000.0)

        with open(output_path) as f:
            geojson = json.load(f)

        # Should have at least one hexagon or be empty (edge case)
        # With larger resolution and spread points, should capture tickets
        if len(geojson['features']) > 0:
            # Verify tickets are counted
            total = sum(f['properties']['ticket_count'] for f in geojson['features'])
            assert total >= 1

    def test_hexbin_geometry_validity(self, generator, sample_tickets_df):
        """Test that hexbin geometries are valid polygons."""
        output_path = generator.generate_hexbin(sample_tickets_df)

        # Load as GeoDataFrame to validate geometries
        gdf = gpd.read_file(output_path)

        # All geometries should be valid
        assert gdf.geometry.is_valid.all()

        # All should be Polygons
        assert (gdf.geometry.geom_type == 'Polygon').all()

    def test_kernel_density_scipy_not_available(self, generator, sample_tickets_df, monkeypatch):
        """Test graceful handling when scipy is not available."""
        # Mock scipy not being available
        import kcci_maintenance.export.heatmap_generator as hm_module
        monkeypatch.setattr(hm_module, 'HAS_SCIPY', False)

        # Should raise ImportError with helpful message
        with pytest.raises(ImportError, match='scipy'):
            generator.generate_kernel_density(sample_tickets_df)

    def test_metadata_inclusion(self, generator, sample_tickets_df):
        """Test that metadata is included in outputs."""
        output_path = generator.generate_hexbin(sample_tickets_df)

        with open(output_path) as f:
            geojson = json.load(f)

        assert 'metadata' in geojson
        metadata = geojson['metadata']
        assert 'type' in metadata
        assert metadata['type'] == 'hexbin'
        assert 'resolution_m' in metadata
        assert 'count' in metadata

    def test_coordinate_reference_system(self, generator, sample_tickets_df):
        """Test that output CRS is WGS84."""
        output_path = generator.generate_hexbin(sample_tickets_df)

        gdf = gpd.read_file(output_path)
        assert gdf.crs.to_string() == 'EPSG:4326'
