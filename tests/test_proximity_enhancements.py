#!/usr/bin/env python3
"""
test_proximity_enhancements.py

Unit tests for proximity geocoder confidence adjustment enhancements.
Tests the _calculate_adjustment_factor() method with various ticket metadata combinations.
"""

import sys
import pytest
from pathlib import Path

# Add parent directory to path so we can import proximity_geocoder
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from proximity_geocoder import ProximityGeocoder


@pytest.fixture
def geocoder():
    """Provide a geocoder instance for testing."""
    roads_file = Path("roads_merged.gpkg")
    if not roads_file.exists():
        pytest.skip(f"Road network file not found: {roads_file}")
    return ProximityGeocoder(roads_file)


class TestAdjustmentFactorCalculation:
    """Test confidence adjustment factor calculations."""

    def test_no_metadata_returns_baseline(self, geocoder):
        """With no metadata, adjustment factor should be 1.0 (no adjustment)."""
        factor = geocoder._calculate_adjustment_factor(
            ticket_type=None,
            duration=None,
            work_type=None
        )
        assert factor == 1.0

    def test_emergency_ticket_boost(self, geocoder):
        """Emergency tickets should get +5% boost (factor 1.05)."""
        factor = geocoder._calculate_adjustment_factor(
            ticket_type="Emergency",
            duration=None,
            work_type=None
        )
        assert factor == 1.05

    def test_normal_ticket_baseline(self, geocoder):
        """Normal tickets should have baseline factor (1.0)."""
        factor = geocoder._calculate_adjustment_factor(
            ticket_type="Normal",
            duration=None,
            work_type=None
        )
        assert factor == 1.0

    def test_update_ticket_boost(self, geocoder):
        """Update tickets should get +2% boost (factor 1.02)."""
        factor = geocoder._calculate_adjustment_factor(
            ticket_type="Update",
            duration=None,
            work_type=None
        )
        assert factor == 1.02

    def test_survey_design_reduction(self, geocoder):
        """Survey/Design tickets should get -2% reduction (factor 0.98)."""
        factor = geocoder._calculate_adjustment_factor(
            ticket_type="Survey/Design",
            duration=None,
            work_type=None
        )
        assert factor == 0.98

    def test_short_duration_boost(self, geocoder):
        """Short duration (1 day) should get +10% boost (factor 1.1)."""
        factor = geocoder._calculate_adjustment_factor(
            ticket_type=None,
            duration="1 DAY",
            work_type=None
        )
        assert factor == 1.1

    def test_short_duration_hours_boost(self, geocoder):
        """Short duration (2 hours) should get +10% boost (factor 1.1)."""
        factor = geocoder._calculate_adjustment_factor(
            ticket_type=None,
            duration="2 HRS",
            work_type=None
        )
        assert factor == 1.1

    def test_long_duration_reduction(self, geocoder):
        """Long duration (2 months) should get -5% reduction (factor 0.95)."""
        factor = geocoder._calculate_adjustment_factor(
            ticket_type=None,
            duration="2 MONTHS",
            work_type=None
        )
        assert factor == 0.95

    def test_medium_duration_baseline(self, geocoder):
        """Medium duration (1 week) should have baseline factor (1.0)."""
        factor = geocoder._calculate_adjustment_factor(
            ticket_type=None,
            duration="1 WEEK",
            work_type=None
        )
        assert factor == 1.0

    def test_point_work_boost(self, geocoder):
        """Point work (hydro-excavation) should get +10% boost (factor 1.1)."""
        factor = geocoder._calculate_adjustment_factor(
            ticket_type=None,
            duration=None,
            work_type="Hydro-excavation"
        )
        assert factor == 1.1

    def test_pole_work_boost(self, geocoder):
        """Pole installation should get +10% boost (factor 1.1)."""
        factor = geocoder._calculate_adjustment_factor(
            ticket_type=None,
            duration=None,
            work_type="Setting-Poles"
        )
        assert factor == 1.1

    def test_corridor_work_reduction(self, geocoder):
        """Corridor work (pipeline) should get -5% reduction (factor 0.95)."""
        factor = geocoder._calculate_adjustment_factor(
            ticket_type=None,
            duration=None,
            work_type="Pipeline Maintenance"
        )
        assert factor == 0.95

    def test_construction_work_reduction(self, geocoder):
        """Construction work should get -5% reduction (factor 0.95)."""
        factor = geocoder._calculate_adjustment_factor(
            ticket_type=None,
            duration=None,
            work_type="Pipeline Construction"
        )
        assert factor == 0.95

    def test_combined_emergency_short_point(self, geocoder):
        """Emergency + short duration + point work should compound and clamp to 1.15."""
        factor = geocoder._calculate_adjustment_factor(
            ticket_type="Emergency",
            duration="1 DAY",
            work_type="Hydro-excavation"
        )
        # 1.05 * 1.1 * 1.1 = 1.2705, clamped to 1.15
        assert factor == 1.15

    def test_combined_normal_long_corridor(self, geocoder):
        """Normal + long duration + corridor work should reduce confidence."""
        factor = geocoder._calculate_adjustment_factor(
            ticket_type="Normal",
            duration="2 MONTHS",
            work_type="Pipeline Maintenance"
        )
        # 1.0 * 0.95 * 0.95 = 0.9025
        assert 0.90 <= factor <= 0.91

    def test_combined_survey_long_construction(self, geocoder):
        """Survey + long + construction should compound reductions."""
        factor = geocoder._calculate_adjustment_factor(
            ticket_type="Survey/Design",
            duration="60 DAYS",
            work_type="Power Line Construction"
        )
        # 0.98 * 0.95 * 0.95 = 0.8836
        assert 0.88 <= factor <= 0.89

    def test_clamping_lower_bound(self, geocoder):
        """Factor should never go below 0.85."""
        factor = geocoder._calculate_adjustment_factor(
            ticket_type="Survey/Design",
            duration="90 DAYS",
            work_type="Soil Remediation"
        )
        assert factor >= 0.85

    def test_clamping_upper_bound(self, geocoder):
        """Factor should never go above 1.15."""
        factor = geocoder._calculate_adjustment_factor(
            ticket_type="Emergency",
            duration="1 HR",
            work_type="Driving ground rods"
        )
        assert factor <= 1.15

    def test_case_insensitive_duration(self, geocoder):
        """Duration parsing should be case-insensitive."""
        factor_upper = geocoder._calculate_adjustment_factor(
            ticket_type=None,
            duration="1 DAY",
            work_type=None
        )
        factor_lower = geocoder._calculate_adjustment_factor(
            ticket_type=None,
            duration="1 day",
            work_type=None
        )
        assert factor_upper == factor_lower == 1.1

    def test_case_insensitive_work_type(self, geocoder):
        """Work type parsing should be case-insensitive."""
        factor_upper = geocoder._calculate_adjustment_factor(
            ticket_type=None,
            duration=None,
            work_type="HYDRO-EXCAVATION"
        )
        factor_lower = geocoder._calculate_adjustment_factor(
            ticket_type=None,
            duration=None,
            work_type="hydro-excavation"
        )
        assert factor_upper == factor_lower == 1.1

    def test_unknown_ticket_type_baseline(self, geocoder):
        """Unknown ticket types should default to baseline (1.0)."""
        factor = geocoder._calculate_adjustment_factor(
            ticket_type="Unknown Type",
            duration=None,
            work_type=None
        )
        assert factor == 1.0

    def test_unknown_work_type_baseline(self, geocoder):
        """Unknown work types should default to baseline (1.0)."""
        factor = geocoder._calculate_adjustment_factor(
            ticket_type=None,
            duration=None,
            work_type="Unknown Work"
        )
        assert factor == 1.0


class TestConfidenceAdjustmentIntegration:
    """Integration tests for confidence adjustments in full geocoding workflow."""

    def test_geocoding_with_metadata(self, geocoder):
        """Test full geocoding with metadata produces adjusted confidence."""
        result = geocoder.geocode_proximity(
            street="CR 426",
            intersection="CR 432",
            county="Ward",
            city="Pyote",
            ticket_type="Emergency",
            duration="1 DAY",
            work_type="Hydro-excavation"
        )

        assert result.success
        # Should have high confidence due to all positive adjustments
        assert result.confidence > 0.85
        # Reasoning should mention adjustment factor
        assert "Adjustment factor:" in result.reasoning
        assert "base:" in result.reasoning
        assert "adjusted:" in result.reasoning

    def test_geocoding_without_metadata(self, geocoder):
        """Test geocoding without metadata still works (backward compatibility)."""
        result = geocoder.geocode_proximity(
            street="CR 426",
            intersection="CR 432",
            county="Ward",
            city="Pyote"
        )

        assert result.success
        # Should still get a valid confidence score
        assert 0.5 <= result.confidence <= 0.95

    def test_metadata_stored_in_result(self, geocoder):
        """Test that ticket metadata is stored in result metadata."""
        result = geocoder.geocode_proximity(
            street="CR 426",
            intersection="CR 432",
            county="Ward",
            city="Pyote",
            ticket_type="Emergency",
            duration="1 DAY",
            work_type="Hydro-excavation"
        )

        assert result.success
        assert result.metadata is not None
        assert result.metadata["ticket_type"] == "Emergency"
        assert result.metadata["duration"] == "1 DAY"
        assert result.metadata["work_type"] == "Hydro-excavation"
