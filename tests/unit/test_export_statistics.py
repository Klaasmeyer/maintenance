"""
Unit tests for statistics aggregator.
"""

import json
import pytest
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString
import numpy as np

from kcci_maintenance.export import StatisticsAggregator


@pytest.fixture
def sample_tickets_df():
    """Create sample tickets dataframe for testing."""
    # Create tickets over 3 months
    base_date = datetime(2024, 1, 1)
    dates = [base_date + timedelta(days=i*3) for i in range(30)]

    return pd.DataFrame({
        'ticket_number': [f'T{i:03d}' for i in range(30)],
        'latitude': np.random.uniform(33.4, 33.8, 30),
        'longitude': np.random.uniform(-101.8, -101.4, 30),
        'ticket_type': np.random.choice(['Normal', 'Emergency', 'Update'], 30,
                                       p=[0.7, 0.2, 0.1]),
        'work_type': np.random.choice(['Repair', 'Install', 'Replace'], 30),
        'created_at': dates,
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
    output_dir = tmp_path / "statistics"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def aggregator(temp_output_dir):
    """Create statistics aggregator instance."""
    return StatisticsAggregator(temp_output_dir)


class TestStatisticsAggregator:
    """Test statistics aggregator functionality."""

    def test_initialization(self, temp_output_dir):
        """Test aggregator initialization creates output directory."""
        aggregator = StatisticsAggregator(temp_output_dir)
        assert aggregator.output_dir == temp_output_dir
        assert temp_output_dir.exists()

    def test_generate_summary_basic(self, aggregator, sample_tickets_df):
        """Test basic summary generation."""
        output_path = aggregator.generate_summary(sample_tickets_df)

        assert output_path.exists()

        with open(output_path) as f:
            summary = json.load(f)

        assert summary['total_tickets'] == 30
        assert 'date_range' in summary
        assert 'spatial' in summary
        assert 'ticket_types' in summary
        assert 'quality' in summary

    def test_summary_date_range(self, aggregator, sample_tickets_df):
        """Test date range calculation in summary."""
        output_path = aggregator.generate_summary(sample_tickets_df)

        with open(output_path) as f:
            summary = json.load(f)

        date_range = summary['date_range']
        assert date_range['start'] is not None
        assert date_range['end'] is not None
        assert date_range['days'] >= 0

        # Verify dates are in ISO format
        start = datetime.fromisoformat(date_range['start'])
        end = datetime.fromisoformat(date_range['end'])
        assert end >= start

    def test_summary_spatial_bounds(self, aggregator, sample_tickets_df):
        """Test spatial bounds calculation."""
        output_path = aggregator.generate_summary(sample_tickets_df)

        with open(output_path) as f:
            summary = json.load(f)

        bounds = summary['spatial']['bounds']
        assert 'west' in bounds
        assert 'south' in bounds
        assert 'east' in bounds
        assert 'north' in bounds

        # West should be less than east
        assert bounds['west'] < bounds['east']
        # South should be less than north
        assert bounds['south'] < bounds['north']

    def test_summary_ticket_types(self, aggregator, sample_tickets_df):
        """Test ticket type distribution in summary."""
        output_path = aggregator.generate_summary(sample_tickets_df)

        with open(output_path) as f:
            summary = json.load(f)

        ticket_types = summary['ticket_types']
        assert isinstance(ticket_types, dict)
        assert sum(ticket_types.values()) == 30

        # Should have the types we created
        assert 'Normal' in ticket_types
        assert 'Emergency' in ticket_types

    def test_summary_work_types(self, aggregator, sample_tickets_df):
        """Test work type distribution (top 10)."""
        output_path = aggregator.generate_summary(sample_tickets_df)

        with open(output_path) as f:
            summary = json.load(f)

        work_types = summary['work_types']
        assert isinstance(work_types, dict)
        assert len(work_types) <= 10  # Top 10 only

    def test_summary_quality_metrics(self, aggregator, sample_tickets_df):
        """Test quality metrics calculation."""
        output_path = aggregator.generate_summary(sample_tickets_df)

        with open(output_path) as f:
            summary = json.load(f)

        quality = summary['quality']
        assert 'avg_confidence' in quality
        assert 'min_confidence' in quality
        assert 'max_confidence' in quality

        # All values should be between 0 and 1
        assert 0 <= quality['avg_confidence'] <= 1
        assert 0 <= quality['min_confidence'] <= 1
        assert 0 <= quality['max_confidence'] <= 1

    def test_generate_timeseries_monthly(self, aggregator, sample_tickets_df):
        """Test monthly time series generation."""
        output_path = aggregator.generate_timeseries(
            sample_tickets_df,
            bin_type='monthly'
        )

        assert output_path.exists()

        with open(output_path) as f:
            timeseries = json.load(f)

        assert timeseries['bin_type'] == 'monthly'
        assert 'total' in timeseries
        assert 'by_type' in timeseries

        # Should have multiple months
        assert len(timeseries['total']) >= 1

        # Each entry should have date and count
        for entry in timeseries['total']:
            assert 'date' in entry
            assert 'count' in entry
            assert entry['count'] >= 0

    def test_generate_timeseries_different_frequencies(self, aggregator, sample_tickets_df):
        """Test time series with different frequencies."""
        for bin_type in ['daily', 'weekly', 'monthly', 'quarterly', 'yearly']:
            output_path = aggregator.generate_timeseries(
                sample_tickets_df,
                bin_type=bin_type,
                output_name=f'timeseries_{bin_type}.json'
            )

            assert output_path.exists()

            with open(output_path) as f:
                timeseries = json.load(f)

            assert timeseries['bin_type'] == bin_type
            assert len(timeseries['total']) > 0

    def test_timeseries_by_type(self, aggregator, sample_tickets_df):
        """Test time series breakdown by ticket type."""
        output_path = aggregator.generate_timeseries(sample_tickets_df)

        with open(output_path) as f:
            timeseries = json.load(f)

        by_type = timeseries['by_type']
        assert isinstance(by_type, dict)

        # Should have separate series for each ticket type
        assert 'Normal' in by_type
        assert 'Emergency' in by_type

        # Each type series should have date and count
        for type_series in by_type.values():
            for entry in type_series:
                assert 'date' in entry
                assert 'count' in entry

    def test_generate_type_distribution(self, aggregator, sample_tickets_df):
        """Test type distribution generation."""
        output_path = aggregator.generate_type_distribution(
            sample_tickets_df,
            group_by='ticket_type'
        )

        assert output_path.exists()

        with open(output_path) as f:
            distribution = json.load(f)

        assert distribution['group_by'] == 'ticket_type'
        assert 'distribution' in distribution
        assert distribution['total'] == 30

        # Check distribution entries
        for entry in distribution['distribution']:
            assert 'category' in entry
            assert 'count' in entry
            assert 'percentage' in entry
            assert 0 <= entry['percentage'] <= 100

        # Sum of percentages should be ~100
        total_pct = sum(e['percentage'] for e in distribution['distribution'])
        assert abs(total_pct - 100) < 0.01

    def test_generate_spatial_distribution(self, aggregator, sample_tickets_df):
        """Test spatial distribution generation."""
        output_path = aggregator.generate_spatial_distribution(
            sample_tickets_df,
            group_by='route_leg'
        )

        assert output_path.exists()

        with open(output_path) as f:
            distribution = json.load(f)

        assert distribution['group_by'] == 'route_leg'
        assert 'locations' in distribution

        # Check location entries
        for location in distribution['locations']:
            assert 'location' in location
            assert 'ticket_count' in location
            assert 'bounds' in location

            # Bounds should be valid
            bounds = location['bounds']
            assert bounds['west'] <= bounds['east']
            assert bounds['south'] <= bounds['north']

    def test_spatial_distribution_ticket_types(self, aggregator, sample_tickets_df):
        """Test ticket type breakdown in spatial distribution."""
        output_path = aggregator.generate_spatial_distribution(
            sample_tickets_df,
            group_by='route_leg'
        )

        with open(output_path) as f:
            distribution = json.load(f)

        # Each location should have ticket type breakdown
        for location in distribution['locations']:
            if 'ticket_types' in location:
                assert isinstance(location['ticket_types'], dict)
                # Sum should equal ticket_count
                assert sum(location['ticket_types'].values()) == location['ticket_count']

    def test_generate_osprey_summary(self, aggregator, sample_tickets_df, sample_route_gdf):
        """Test Osprey Strike summary generation."""
        output_path = aggregator.generate_osprey_summary(
            sample_tickets_df,
            sample_route_gdf
        )

        assert output_path.exists()

        with open(output_path) as f:
            summary = json.load(f)

        assert 'project_overview' in summary
        assert 'patrol_priorities' in summary
        assert 'high_risk_zones' in summary
        assert 'maintenance_schedule' in summary

    def test_osprey_patrol_priorities(self, aggregator, sample_tickets_df, sample_route_gdf):
        """Test patrol priority calculation."""
        # Add route_leg to tickets to match route names
        sample_tickets_df['route_leg'] = np.random.choice(['Leg1', 'Leg2', 'Leg3'], len(sample_tickets_df))

        output_path = aggregator.generate_osprey_summary(
            sample_tickets_df,
            sample_route_gdf
        )

        with open(output_path) as f:
            summary = json.load(f)

        priorities = summary['patrol_priorities']

        # Should have priority for each segment
        for priority in priorities:
            assert 'segment' in priority
            assert 'priority' in priority
            assert priority['priority'] in ['HIGH', 'MEDIUM', 'LOW']
            assert 'ticket_count' in priority
            assert 'recommended_frequency' in priority

    def test_osprey_high_risk_zones(self, aggregator, sample_route_gdf):
        """Test high-risk zone identification."""
        # Create tickets with emergencies
        df = pd.DataFrame({
            'ticket_number': [f'T{i:03d}' for i in range(20)],
            'latitude': [33.5] * 20,
            'longitude': [-101.5] * 20,
            'ticket_type': ['Emergency'] * 10 + ['Normal'] * 10,
            'route_leg': ['Leg1'] * 20
        })

        output_path = aggregator.generate_osprey_summary(df, sample_route_gdf)

        with open(output_path) as f:
            summary = json.load(f)

        high_risk = summary['high_risk_zones']

        # Should identify high-risk areas
        if len(high_risk) > 0:
            for zone in high_risk:
                assert 'location' in zone
                assert 'emergency_count' in zone
                assert 'requires_immediate_attention' in zone

    def test_empty_dataframe(self, aggregator):
        """Test handling of empty dataframe."""
        empty_df = pd.DataFrame({
            'ticket_number': [],
            'latitude': [],
            'longitude': []
        })

        output_path = aggregator.generate_summary(empty_df)

        with open(output_path) as f:
            summary = json.load(f)

        assert summary['total_tickets'] == 0

    def test_missing_columns(self, aggregator):
        """Test handling of missing columns."""
        minimal_df = pd.DataFrame({
            'ticket_number': ['T001'],
            'latitude': [33.5],
            'longitude': [-101.5]
        })

        # Should not fail with minimal columns
        output_path = aggregator.generate_summary(minimal_df)

        with open(output_path) as f:
            summary = json.load(f)

        assert summary['total_tickets'] == 1
        assert 'spatial' in summary

    def test_invalid_dates_handling(self, aggregator):
        """Test handling of invalid dates."""
        df = pd.DataFrame({
            'ticket_number': ['T001', 'T002', 'T003'],
            'latitude': [33.5, 33.6, 33.7],
            'longitude': [-101.5, -101.6, -101.7],
            'created_at': ['2024-01-01', 'invalid-date', '2024-01-03']
        })

        # Should handle invalid dates gracefully
        output_path = aggregator.generate_summary(df)

        with open(output_path) as f:
            summary = json.load(f)

        # Should still calculate date range from valid dates
        date_range = summary['date_range']
        assert date_range['start'] is not None
        assert date_range['end'] is not None

    def test_generated_timestamp(self, aggregator, sample_tickets_df):
        """Test that generated timestamp is included."""
        output_path = aggregator.generate_summary(sample_tickets_df)

        with open(output_path) as f:
            summary = json.load(f)

        assert 'generated' in summary
        # Should be valid ISO format
        generated = datetime.fromisoformat(summary['generated'])
        assert isinstance(generated, datetime)

    def test_custom_output_names(self, aggregator, sample_tickets_df):
        """Test custom output filenames."""
        output_path = aggregator.generate_summary(
            sample_tickets_df,
            output_name='custom_summary.json'
        )

        assert output_path.name == 'custom_summary.json'
        assert output_path.exists()
