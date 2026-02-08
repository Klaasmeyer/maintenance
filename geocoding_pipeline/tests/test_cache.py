"""
Unit tests for cache management.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cache.cache_manager import CacheManager
from cache.models import GeocodeRecord, QualityTier, ReviewPriority, CacheQuery


@pytest.fixture
def cache_manager(tmp_path):
    """Create a temporary cache manager for testing."""
    db_path = tmp_path / "test_cache.db"
    return CacheManager(str(db_path))


@pytest.fixture
def sample_record():
    """Create a sample geocode record."""
    return GeocodeRecord(
        ticket_number="TEST001",
        geocode_key="test_key",
        street="Main St",
        intersection="1st Ave",
        city="Test City",
        county="Test County",
        latitude=31.5401,
        longitude=-103.1293,
        confidence=0.85,
        method="test_method",
        approach="test_approach",
        quality_tier=QualityTier.GOOD,
        review_priority=ReviewPriority.NONE,
    )


def test_cache_create_and_retrieve(cache_manager, sample_record):
    """Test creating and retrieving a cache entry."""
    # Create entry
    cache_id = cache_manager.set(sample_record, "test_stage")
    assert cache_id > 0

    # Retrieve entry
    retrieved = cache_manager.get_current(ticket_number="TEST001")
    assert retrieved is not None
    assert retrieved.ticket_number == "TEST001"
    assert retrieved.latitude == 31.5401
    assert retrieved.confidence == 0.85


def test_cache_versioning(cache_manager, sample_record):
    """Test version tracking when updating records."""
    # Create initial version
    cache_id_v1 = cache_manager.set(sample_record, "stage_1")

    # Update with better confidence
    sample_record.confidence = 0.95
    sample_record.quality_tier = QualityTier.EXCELLENT
    cache_id_v2 = cache_manager.set(sample_record, "stage_2")

    # Verify we have 2 versions
    history = cache_manager.get_version_history(ticket_number="TEST001")
    assert len(history) == 2
    assert history[0].version == 2  # Latest first
    assert history[1].version == 1

    # Current should be the latest
    current = cache_manager.get_current(ticket_number="TEST001")
    assert current.version == 2
    assert current.confidence == 0.95


def test_cache_locking(cache_manager, sample_record):
    """Test locking and unlocking records."""
    # Create entry
    cache_id = cache_manager.set(sample_record, "test_stage")

    # Lock it (use ticket_number, not cache_id)
    cache_manager.lock("TEST001", "Human verified")

    # Verify it's locked
    current = cache_manager.get_current(ticket_number="TEST001")
    assert current.locked is True
    assert current.lock_reason == "Human verified"

    # Unlock it (use ticket_number, not cache_id)
    cache_manager.unlock("TEST001")

    # Verify it's unlocked
    current = cache_manager.get_current(ticket_number="TEST001")
    assert current.locked is False
    assert current.lock_reason is None


@pytest.mark.skip(reason="Query filtering needs refinement - Phase 2")
def test_cache_query_by_quality(cache_manager):
    """Test querying by quality tier."""
    # Create records with different quality tiers
    for i, tier in enumerate([QualityTier.EXCELLENT, QualityTier.GOOD, QualityTier.ACCEPTABLE]):
        record = GeocodeRecord(
            ticket_number=f"TEST{i:03d}",
            geocode_key=f"key_{i}",
            latitude=31.5 + i * 0.01,
            longitude=-103.1 - i * 0.01,
            confidence=0.9 - i * 0.1,
            method="test",
            quality_tier=tier,
            review_priority=ReviewPriority.NONE,
        )
        cache_manager.set(record, "test_stage")

    # Query using CacheQuery object
    query = CacheQuery(quality_tier=[QualityTier.EXCELLENT])
    excellent = cache_manager.query(query)
    assert len(excellent) == 1
    assert excellent[0].quality_tier == QualityTier.EXCELLENT

    # Query for GOOD and ACCEPTABLE
    query2 = CacheQuery(quality_tier=[QualityTier.GOOD, QualityTier.ACCEPTABLE])
    good_acceptable = cache_manager.query(query2)
    assert len(good_acceptable) == 2


def test_cache_statistics(cache_manager):
    """Test cache statistics calculation."""
    # Create records with different quality tiers
    tiers = [QualityTier.EXCELLENT] * 3 + [QualityTier.GOOD] * 2 + [QualityTier.FAILED] * 1

    for i, tier in enumerate(tiers):
        record = GeocodeRecord(
            ticket_number=f"TEST{i:03d}",
            geocode_key=f"key_{i}",
            latitude=31.5,
            longitude=-103.1,
            confidence=0.8,
            method="test",
            quality_tier=tier,
            review_priority=ReviewPriority.NONE,
        )
        cache_manager.set(record, "test_stage")

    # Get statistics
    stats = cache_manager.get_statistics()
    assert stats["total_records"] == 6
    assert stats["quality_tiers"][QualityTier.EXCELLENT.value] == 3
    assert stats["quality_tiers"][QualityTier.GOOD.value] == 2
    assert stats["quality_tiers"][QualityTier.FAILED.value] == 1


def test_generate_geocode_key():
    """Test geocode key generation."""
    key1 = CacheManager.generate_geocode_key("Main St", "1st Ave", "City", "County")
    key2 = CacheManager.generate_geocode_key("Main St", "1st Ave", "City", "County")
    key3 = CacheManager.generate_geocode_key("Other St", "1st Ave", "City", "County")

    # Same inputs should produce same key
    assert key1 == key2

    # Different inputs should produce different keys
    assert key1 != key3

    # Key should be deterministic and consistent
    assert len(key1) == 64  # SHA256 hex digest length


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
