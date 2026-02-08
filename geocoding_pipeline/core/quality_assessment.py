"""
Quality assessment for geocoding results.

Calculates quality tiers and review priorities based on confidence,
method, validation flags, and business rules.
"""

from typing import List, Optional
from enum import Enum

from ..cache.models import QualityTier, ReviewPriority


class QualityAssessor:
    """Assess geocoding quality and assign tiers."""
    
    # Quality tier thresholds
    TIER_THRESHOLDS = {
        QualityTier.EXCELLENT: 0.90,
        QualityTier.GOOD: 0.80,
        QualityTier.ACCEPTABLE: 0.65,
        QualityTier.REVIEW_NEEDED: 0.40,
        QualityTier.FAILED: 0.0,
    }
    
    # Method quality multipliers
    METHOD_QUALITY = {
        "API_PRIMARY": 1.0,          # Trust Google Maps
        "GEOMETRIC_INTERSECTION": 1.0,  # High confidence
        "PROXIMITY_BASED": 1.0,      # Use confidence as-is
        "MANUAL": 1.1,               # Human verified - boost
        "city_centroid_fallback": 0.8,  # Lower inherent quality
    }
    
    def calculate_quality_tier(
        self,
        confidence: Optional[float],
        method: str,
        approach: Optional[str] = None,
        validation_flags: Optional[List[str]] = None,
        ticket_type: Optional[str] = None,
    ) -> QualityTier:
        """Calculate quality tier for a geocode result.
        
        Args:
            confidence: Geocoding confidence (0-1)
            method: Geocoding method used
            approach: Specific approach (for proximity-based)
            validation_flags: List of validation issues
            ticket_type: Type of ticket (Emergency, Normal, etc.)
            
        Returns:
            QualityTier enum value
        """
        # Handle failed geocodes
        if confidence is None or confidence == 0:
            return QualityTier.FAILED
        
        # Apply method-based adjustments
        adjusted_confidence = confidence

        # Penalize fallback approaches (but not too harshly)
        if approach == "city_centroid_fallback":
            adjusted_confidence *= 0.9  # 10% penalty

        # Penalize if validation flags present (but cap at 15% total)
        if validation_flags:
            # Each flag reduces confidence by 3%, max 15%
            penalty = min(len(validation_flags) * 0.03, 0.15)
            adjusted_confidence *= (1.0 - penalty)
        
        # Determine tier based on adjusted confidence
        if adjusted_confidence >= self.TIER_THRESHOLDS[QualityTier.EXCELLENT]:
            return QualityTier.EXCELLENT
        elif adjusted_confidence >= self.TIER_THRESHOLDS[QualityTier.GOOD]:
            return QualityTier.GOOD
        elif adjusted_confidence >= self.TIER_THRESHOLDS[QualityTier.ACCEPTABLE]:
            return QualityTier.ACCEPTABLE
        elif adjusted_confidence >= self.TIER_THRESHOLDS[QualityTier.REVIEW_NEEDED]:
            return QualityTier.REVIEW_NEEDED
        else:
            return QualityTier.FAILED
    
    def calculate_review_priority(
        self,
        confidence: Optional[float],
        quality_tier: QualityTier,
        validation_flags: Optional[List[str]] = None,
        ticket_type: Optional[str] = None,
        approach: Optional[str] = None,
    ) -> ReviewPriority:
        """Calculate review priority for a geocode result.

        Args:
            confidence: Geocoding confidence (0-1)
            quality_tier: Calculated quality tier
            validation_flags: List of validation issues
            ticket_type: Type of ticket (Emergency, Normal, etc.)
            approach: Specific geocoding approach used

        Returns:
            ReviewPriority enum value
        """
        # HIGH: City centroid fallback (both roads missing) - check first
        # This overrides FAILED tier because fallback is expected to be low quality
        if approach == "city_centroid_fallback":
            return ReviewPriority.HIGH

        # CRITICAL: Failed geocodes (after checking fallback)
        if quality_tier == QualityTier.FAILED:
            return ReviewPriority.CRITICAL
        
        # HIGH: Emergency tickets with low confidence
        if ticket_type == "Emergency" and confidence and confidence < 0.75:
            return ReviewPriority.HIGH
        
        # HIGH: Very low confidence
        if confidence and confidence < 0.50:
            return ReviewPriority.HIGH
        
        # MEDIUM: Review needed tier or medium confidence
        if quality_tier == QualityTier.REVIEW_NEEDED:
            return ReviewPriority.MEDIUM
        
        # MEDIUM: Multiple validation flags
        if validation_flags and len(validation_flags) >= 2:
            return ReviewPriority.MEDIUM
        
        # LOW: Acceptable tier with validation flags
        if quality_tier == QualityTier.ACCEPTABLE and validation_flags:
            return ReviewPriority.LOW
        
        # NONE: Good quality, no issues
        return ReviewPriority.NONE
    
    def should_reprocess(
        self,
        quality_tier: QualityTier,
        reprocess_threshold: str,
        locked: bool = False,
    ) -> bool:
        """Determine if a geocode should be reprocessed.
        
        Args:
            quality_tier: Current quality tier
            reprocess_threshold: Threshold from stage config
                - "always": Always reprocess
                - "minor_enhancement": ACCEPTABLE and below
                - "major_enhancement": GOOD and below
                - None: Never reprocess (EXCELLENT only)
            locked: Whether geocode is locked (human verified)
            
        Returns:
            True if should reprocess, False otherwise
        """
        # Never reprocess locked geocodes
        if locked:
            return False
        
        # Always reprocess failed or unset threshold
        if reprocess_threshold == "always":
            return True
        
        # Minor enhancement: Reprocess ACCEPTABLE and below
        if reprocess_threshold == "minor_enhancement":
            return quality_tier in [
                QualityTier.ACCEPTABLE,
                QualityTier.REVIEW_NEEDED,
                QualityTier.FAILED
            ]
        
        # Major enhancement: Reprocess GOOD and below
        if reprocess_threshold == "major_enhancement":
            return quality_tier in [
                QualityTier.GOOD,
                QualityTier.ACCEPTABLE,
                QualityTier.REVIEW_NEEDED,
                QualityTier.FAILED
            ]
        
        # No threshold (None): Never reprocess (EXCELLENT only)
        return False
    
    def get_quality_summary(self, quality_tier: QualityTier) -> str:
        """Get human-readable summary of quality tier.
        
        Args:
            quality_tier: Quality tier
            
        Returns:
            Description string
        """
        descriptions = {
            QualityTier.EXCELLENT: "High confidence, no review needed",
            QualityTier.GOOD: "Reliable, reprocess only with major improvements",
            QualityTier.ACCEPTABLE: "Usable, reprocess with any improvement",
            QualityTier.REVIEW_NEEDED: "Low confidence, human review recommended",
            QualityTier.FAILED: "Geocoding failed, manual intervention required",
        }
        return descriptions.get(quality_tier, "Unknown quality tier")


if __name__ == "__main__":
    # Test quality assessor
    assessor = QualityAssessor()
    
    print("Testing QualityAssessor...\n")
    
    # Test case 1: Excellent quality
    tier1 = assessor.calculate_quality_tier(
        confidence=0.95,
        method="API_PRIMARY",
        validation_flags=None
    )
    print(f"Test 1 - High confidence API: {tier1.value}")
    assert tier1 == QualityTier.EXCELLENT
    
    # Test case 2: Good quality with minor flag
    tier2 = assessor.calculate_quality_tier(
        confidence=0.85,
        method="PROXIMITY_BASED",
        validation_flags=["low_confidence"]
    )
    print(f"Test 2 - Good with flag: {tier2.value}")
    
    # Test case 3: City centroid fallback
    tier3 = assessor.calculate_quality_tier(
        confidence=0.35,
        method="PROXIMITY_BASED",
        approach="city_centroid_fallback",
        validation_flags=["fallback_used"]
    )
    priority3 = assessor.calculate_review_priority(
        confidence=0.35,
        quality_tier=tier3,
        approach="city_centroid_fallback"
    )
    print(f"Test 3 - City centroid: {tier3.value}, Priority: {priority3.value}")
    assert priority3 == ReviewPriority.HIGH
    
    # Test case 4: Emergency ticket with low confidence
    priority4 = assessor.calculate_review_priority(
        confidence=0.65,
        quality_tier=QualityTier.ACCEPTABLE,
        ticket_type="Emergency"
    )
    print(f"Test 4 - Emergency low conf: Priority: {priority4.value}")
    assert priority4 == ReviewPriority.HIGH
    
    # Test case 5: Reprocessing logic
    should_reprocess_excellent = assessor.should_reprocess(
        quality_tier=QualityTier.EXCELLENT,
        reprocess_threshold="minor_enhancement"
    )
    should_reprocess_acceptable = assessor.should_reprocess(
        quality_tier=QualityTier.ACCEPTABLE,
        reprocess_threshold="minor_enhancement"
    )
    print(f"\nTest 5 - Reprocess EXCELLENT: {should_reprocess_excellent}")
    print(f"Test 5 - Reprocess ACCEPTABLE: {should_reprocess_acceptable}")
    assert not should_reprocess_excellent
    assert should_reprocess_acceptable
    
    # Test case 6: Locked geocode
    should_reprocess_locked = assessor.should_reprocess(
        quality_tier=QualityTier.REVIEW_NEEDED,
        reprocess_threshold="always",
        locked=True
    )
    print(f"Test 6 - Reprocess locked: {should_reprocess_locked}")
    assert not should_reprocess_locked
    
    print("\n✓ All QualityAssessor tests passed!")
