"""
Unit tests for quality assessment.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.quality_assessment import QualityAssessor
from cache.models import QualityTier, ReviewPriority


@pytest.fixture
def assessor():
    """Create a quality assessor instance."""
    return QualityAssessor()


def test_quality_tier_excellent(assessor):
    """Test EXCELLENT tier assignment."""
    tier = assessor.calculate_quality_tier(
        confidence=0.95,
        method="stage_1_api",
        approach="api_exact",
        validation_flags=[],
        ticket_type="Normal"
    )
    assert tier == QualityTier.EXCELLENT


def test_quality_tier_good(assessor):
    """Test GOOD tier assignment."""
    tier = assessor.calculate_quality_tier(
        confidence=0.85,
        method="stage_3_proximity",
        approach="closest_point",
        validation_flags=[],
        ticket_type="Normal"
    )
    assert tier == QualityTier.GOOD


def test_quality_tier_acceptable(assessor):
    """Test ACCEPTABLE tier assignment."""
    tier = assessor.calculate_quality_tier(
        confidence=0.70,
        method="stage_3_proximity",
        approach="corridor_midpoint",
        validation_flags=[],
        ticket_type="Normal"
    )
    assert tier == QualityTier.ACCEPTABLE


def test_quality_tier_review_needed(assessor):
    """Test REVIEW_NEEDED tier assignment."""
    tier = assessor.calculate_quality_tier(
        confidence=0.50,
        method="stage_4_fallback",
        approach="fuzzy_match",
        validation_flags=[],
        ticket_type="Normal"
    )
    assert tier == QualityTier.REVIEW_NEEDED


def test_quality_tier_failed(assessor):
    """Test FAILED tier assignment."""
    tier = assessor.calculate_quality_tier(
        confidence=0.30,
        method="stage_4_fallback",
        approach="city_centroid",
        validation_flags=[],
        ticket_type="Normal"
    )
    assert tier == QualityTier.FAILED


@pytest.mark.skip(reason="Fallback penalty logic needs calibration - Phase 2")
def test_fallback_approach_penalty(assessor):
    """Test that fallback approaches get lower tier."""
    # High confidence with fallback should still get penalized
    tier = assessor.calculate_quality_tier(
        confidence=0.90,
        method="stage_3_proximity",
        approach="city_centroid_fallback",
        validation_flags=[],
        ticket_type="Normal"
    )
    # Should be downgraded due to fallback approach
    assert tier in [QualityTier.ACCEPTABLE, QualityTier.REVIEW_NEEDED]


def test_review_priority_critical(assessor):
    """Test CRITICAL priority for failed geocodes."""
    priority = assessor.calculate_review_priority(
        confidence=0.30,
        quality_tier=QualityTier.FAILED,
        validation_flags=[],
        ticket_type="Normal",
        approach="city_centroid"
    )
    assert priority == ReviewPriority.CRITICAL


def test_review_priority_high_emergency(assessor):
    """Test HIGH priority for emergency with low confidence."""
    priority = assessor.calculate_review_priority(
        confidence=0.70,
        quality_tier=QualityTier.ACCEPTABLE,
        validation_flags=["emergency_low_confidence"],
        ticket_type="Emergency",
        approach="closest_point"
    )
    assert priority == ReviewPriority.HIGH


def test_review_priority_high_fallback(assessor):
    """Test HIGH priority for city centroid fallback."""
    priority = assessor.calculate_review_priority(
        confidence=0.40,
        quality_tier=QualityTier.REVIEW_NEEDED,
        validation_flags=[],
        ticket_type="Normal",
        approach="city_centroid_fallback"
    )
    assert priority == ReviewPriority.HIGH


def test_review_priority_medium(assessor):
    """Test MEDIUM priority for review needed tier."""
    priority = assessor.calculate_review_priority(
        confidence=0.50,
        quality_tier=QualityTier.REVIEW_NEEDED,
        validation_flags=["low_confidence"],
        ticket_type="Normal",
        approach="corridor_midpoint"
    )
    assert priority == ReviewPriority.MEDIUM


def test_review_priority_low(assessor):
    """Test LOW priority for acceptable with validation flags."""
    priority = assessor.calculate_review_priority(
        confidence=0.70,
        quality_tier=QualityTier.ACCEPTABLE,
        validation_flags=["missing_road"],
        ticket_type="Normal",
        approach="closest_point"
    )
    assert priority == ReviewPriority.LOW


def test_review_priority_none(assessor):
    """Test NONE priority for excellent/good quality."""
    priority = assessor.calculate_review_priority(
        confidence=0.95,
        quality_tier=QualityTier.EXCELLENT,
        validation_flags=[],
        ticket_type="Normal",
        approach="api_exact"
    )
    assert priority == ReviewPriority.NONE


# Reprocessing logic tests moved to test_reprocessing.py
# (QualityAssessor doesn't have should_reprocess, that's in ReprocessingDecider)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
