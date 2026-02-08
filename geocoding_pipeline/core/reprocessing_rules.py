"""
Reprocessing decision logic for pipeline stages.

Determines whether a cached geocode should be skipped (reused) or
reprocessed based on quality tier, confidence, locks, and stage rules.
"""

from typing import Dict, Any, Optional

from ..cache.models import GeocodeRecord, QualityTier


class ReprocessingDecider:
    """Decides whether to skip or reprocess cached geocodes."""
    
    def should_skip(
        self,
        record: GeocodeRecord,
        stage_name: str,
        stage_config: Dict[str, Any]
    ) -> tuple[bool, str]:
        """Determine if cached geocode should be skipped (not reprocessed).
        
        Args:
            record: Cached GeocodeRecord
            stage_name: Name of stage considering reprocessing
            stage_config: Stage configuration with skip_rules
            
        Returns:
            Tuple of (should_skip: bool, reason: str)
        """
        skip_rules = stage_config.get("skip_rules", {})
        
        # Rule 1: Always skip if locked (human verified)
        if skip_rules.get("skip_if_locked", True) and record.locked:
            return True, f"Locked ({record.lock_reason})"
        
        # Rule 2: Skip if quality tier is in skip list
        skip_quality_tiers = skip_rules.get("skip_if_quality", [])
        if skip_quality_tiers:
            # Convert string tiers to QualityTier enums
            skip_tiers_enum = [
                QualityTier(t) if isinstance(t, str) else t
                for t in skip_quality_tiers
            ]
            if record.quality_tier in skip_tiers_enum:
                tier_value = record.quality_tier.value if isinstance(record.quality_tier, QualityTier) else record.quality_tier
                return True, f"Quality tier {tier_value} in skip list"
        
        # Rule 3: Skip if confidence above threshold
        skip_confidence = skip_rules.get("skip_if_confidence")
        if skip_confidence is not None and record.confidence is not None:
            if record.confidence >= skip_confidence:
                return True, f"Confidence {record.confidence:.2%} >= {skip_confidence:.2%}"
        
        # Rule 4: Skip if method matches
        skip_methods = skip_rules.get("skip_if_method", [])
        if skip_methods and record.method in skip_methods:
            return True, f"Method {record.method} in skip list"
        
        # Rule 5: Skip if approach matches
        skip_approaches = skip_rules.get("skip_if_approach", [])
        if skip_approaches and record.approach in skip_approaches:
            return True, f"Approach {record.approach} in skip list"
        
        # Rule 6: Skip if created by same stage (avoid infinite loop)
        if record.created_by_stage == stage_name:
            return True, f"Already processed by {stage_name}"
        
        # Default: don't skip (reprocess)
        return False, "No skip rules matched"
    
    def should_reprocess_by_quality(
        self,
        quality_tier: QualityTier,
        reprocess_threshold: Optional[str],
        locked: bool = False
    ) -> tuple[bool, str]:
        """Determine if geocode should be reprocessed based on quality.
        
        Args:
            quality_tier: Current quality tier
            reprocess_threshold: Threshold string
                - "always": Always reprocess
                - "minor_enhancement": Reprocess ACCEPTABLE and below
                - "major_enhancement": Reprocess GOOD and below
                - None: Never reprocess (EXCELLENT only)
            locked: Whether geocode is locked
            
        Returns:
            Tuple of (should_reprocess: bool, reason: str)
        """
        # Never reprocess locked geocodes
        if locked:
            return False, "Geocode is locked"
        
        # Always reprocess if threshold is "always"
        if reprocess_threshold == "always":
            return True, "Threshold is 'always'"
        
        # Minor enhancement: Reprocess ACCEPTABLE and below
        if reprocess_threshold == "minor_enhancement":
            if quality_tier in [
                QualityTier.ACCEPTABLE,
                QualityTier.REVIEW_NEEDED,
                QualityTier.FAILED
            ]:
                return True, f"Quality {quality_tier.value} <= ACCEPTABLE"
            return False, f"Quality {quality_tier.value} > ACCEPTABLE"
        
        # Major enhancement: Reprocess GOOD and below
        if reprocess_threshold == "major_enhancement":
            if quality_tier in [
                QualityTier.GOOD,
                QualityTier.ACCEPTABLE,
                QualityTier.REVIEW_NEEDED,
                QualityTier.FAILED
            ]:
                return True, f"Quality {quality_tier.value} <= GOOD"
            return False, f"Quality {quality_tier.value} > GOOD"
        
        # No threshold (None): Never reprocess (EXCELLENT only)
        return False, "No reprocess threshold (EXCELLENT only)"
    
    def explain_skip_decision(
        self,
        record: GeocodeRecord,
        stage_name: str,
        stage_config: Dict[str, Any]
    ) -> str:
        """Get detailed explanation of skip decision.
        
        Args:
            record: Cached GeocodeRecord
            stage_name: Name of stage
            stage_config: Stage configuration
            
        Returns:
            Human-readable explanation
        """
        should_skip, reason = self.should_skip(record, stage_name, stage_config)
        
        if should_skip:
            return f"✓ SKIP: {reason}"
        else:
            return f"✗ REPROCESS: {reason}"


if __name__ == "__main__":
    # Test reprocessing decider
    from ..cache.models import ReviewPriority
    
    decider = ReprocessingDecider()
    
    print("Testing ReprocessingDecider...\n")
    
    # Test case 1: Skip EXCELLENT quality
    record1 = GeocodeRecord(
        ticket_number="TEST1",
        geocode_key="key1",
        method="API_PRIMARY",
        quality_tier=QualityTier.EXCELLENT,
        confidence=0.95,
        locked=False
    )
    stage_config1 = {
        "skip_rules": {
            "skip_if_quality": ["EXCELLENT", "GOOD"],
            "skip_if_locked": True
        }
    }
    should_skip1, reason1 = decider.should_skip(record1, "stage_3_proximity", stage_config1)
    print(f"✓ Test 1 - EXCELLENT quality: skip={should_skip1}, reason={reason1}")
    assert should_skip1 is True
    
    # Test case 2: Don't skip ACCEPTABLE quality
    record2 = GeocodeRecord(
        ticket_number="TEST2",
        geocode_key="key2",
        method="PROXIMITY_BASED",
        quality_tier=QualityTier.ACCEPTABLE,
        confidence=0.70,
        locked=False
    )
    should_skip2, reason2 = decider.should_skip(record2, "stage_3_proximity", stage_config1)
    print(f"✓ Test 2 - ACCEPTABLE quality: skip={should_skip2}, reason={reason2}")
    assert should_skip2 is False
    
    # Test case 3: Skip locked geocode
    record3 = GeocodeRecord(
        ticket_number="TEST3",
        geocode_key="key3",
        method="PROXIMITY_BASED",
        quality_tier=QualityTier.REVIEW_NEEDED,
        confidence=0.45,
        locked=True,
        lock_reason="Human verified"
    )
    should_skip3, reason3 = decider.should_skip(record3, "stage_3_proximity", stage_config1)
    print(f"✓ Test 3 - Locked geocode: skip={should_skip3}, reason={reason3}")
    assert should_skip3 is True
    
    # Test case 4: Skip by confidence threshold
    record4 = GeocodeRecord(
        ticket_number="TEST4",
        geocode_key="key4",
        method="PROXIMITY_BASED",
        quality_tier=QualityTier.GOOD,
        confidence=0.85,
        locked=False
    )
    stage_config4 = {
        "skip_rules": {
            "skip_if_confidence": 0.75
        }
    }
    should_skip4, reason4 = decider.should_skip(record4, "stage_3_proximity", stage_config4)
    print(f"✓ Test 4 - High confidence: skip={should_skip4}, reason={reason4}")
    assert should_skip4 is True
    
    # Test case 5: Reprocess by quality - minor enhancement
    should_reprocess5, reason5 = decider.should_reprocess_by_quality(
        quality_tier=QualityTier.ACCEPTABLE,
        reprocess_threshold="minor_enhancement",
        locked=False
    )
    print(f"\n✓ Test 5 - Minor enhancement ACCEPTABLE: reprocess={should_reprocess5}, reason={reason5}")
    assert should_reprocess5 is True
    
    # Test case 6: Don't reprocess GOOD with minor enhancement
    should_reprocess6, reason6 = decider.should_reprocess_by_quality(
        quality_tier=QualityTier.GOOD,
        reprocess_threshold="minor_enhancement",
        locked=False
    )
    print(f"✓ Test 6 - Minor enhancement GOOD: reprocess={should_reprocess6}, reason={reason6}")
    assert should_reprocess6 is False
    
    # Test case 7: Reprocess GOOD with major enhancement
    should_reprocess7, reason7 = decider.should_reprocess_by_quality(
        quality_tier=QualityTier.GOOD,
        reprocess_threshold="major_enhancement",
        locked=False
    )
    print(f"✓ Test 7 - Major enhancement GOOD: reprocess={should_reprocess7}, reason={reason7}")
    assert should_reprocess7 is True
    
    # Test case 8: Skip same stage (avoid loop)
    record8 = GeocodeRecord(
        ticket_number="TEST8",
        geocode_key="key8",
        method="PROXIMITY_BASED",
        quality_tier=QualityTier.ACCEPTABLE,
        confidence=0.70,
        locked=False,
        created_by_stage="stage_3_proximity"
    )
    should_skip8, reason8 = decider.should_skip(record8, "stage_3_proximity", {})
    print(f"\n✓ Test 8 - Same stage: skip={should_skip8}, reason={reason8}")
    assert should_skip8 is True
    
    print("\n✓ All ReprocessingDecider tests passed!")
