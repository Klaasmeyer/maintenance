"""
Validation rules for geocoding results.

Each rule checks for specific quality issues and returns validation results
with severity levels and descriptions.
"""

from typing import List, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class ValidationResult:
    """Result of a validation rule check."""
    flag: str  # Short identifier (e.g., "low_confidence")
    severity: str  # "INFO", "WARNING", "ERROR"
    message: str  # Human-readable description
    action: str  # Suggested action


class ValidationRule(ABC):
    """Base class for validation rules."""
    
    @abstractmethod
    def check(
        self,
        latitude: Optional[float],
        longitude: Optional[float],
        confidence: Optional[float],
        method: str,
        approach: Optional[str],
        street: Optional[str],
        intersection: Optional[str],
        city: Optional[str],
        county: Optional[str],
        ticket_type: Optional[str],
        **kwargs
    ) -> Optional[ValidationResult]:
        """Check if validation rule applies.
        
        Args:
            latitude: Geocoded latitude
            longitude: Geocoded longitude
            confidence: Confidence score
            method: Geocoding method
            approach: Specific approach
            street: Street name
            intersection: Intersection name
            city: City name
            county: County name
            ticket_type: Type of ticket
            **kwargs: Additional fields
            
        Returns:
            ValidationResult if rule triggered, None otherwise
        """
        pass


class LowConfidenceRule(ValidationRule):
    """Flag geocodes with low confidence."""
    
    def __init__(self, threshold: float = 0.65):
        self.threshold = threshold
    
    def check(self, confidence: Optional[float], **kwargs) -> Optional[ValidationResult]:
        if confidence is not None and confidence < self.threshold:
            return ValidationResult(
                flag="low_confidence",
                severity="WARNING",
                message=f"Confidence {confidence:.1%} is below threshold {self.threshold:.1%}",
                action="Review location accuracy; consider alternative geocoding methods"
            )
        return None


class EmergencyLowConfidenceRule(ValidationRule):
    """Flag emergency tickets with insufficient confidence."""
    
    def __init__(self, threshold: float = 0.75):
        self.threshold = threshold
    
    def check(
        self,
        confidence: Optional[float],
        ticket_type: Optional[str],
        **kwargs
    ) -> Optional[ValidationResult]:
        if ticket_type == "Emergency" and confidence is not None and confidence < self.threshold:
            return ValidationResult(
                flag="emergency_low_confidence",
                severity="ERROR",
                message=f"Emergency ticket has {confidence:.1%} confidence (below {self.threshold:.1%})",
                action="High priority review - emergency response location must be accurate"
            )
        return None


class CityDistanceRule(ValidationRule):
    """Flag geocodes far from expected city center."""
    
    # City centroids (from ProximityGeocoder)
    CITY_CENTROIDS = {
        ("KERMIT", "WINKLER"): (31.8576, -103.0930),
        ("PYOTE", "WARD"): (31.5401, -103.1293),
        ("BARSTOW", "WARD"): (31.4596, -103.3954),
        ("MONAHANS", "WARD"): (31.5943, -102.8929),
        ("ANDREWS", "ANDREWS"): (32.3185, -102.5457),
        ("GARDENDALE", "ANDREWS"): (32.0165, -102.3779),
        ("COYANOSA", "WARD"): (31.2693, -103.0324),
        ("WICKETT", "WARD"): (31.5768, -103.0010),
        ("THORNTONVILLE", "WARD"): (31.4446, -103.1079),
    }
    
    def __init__(self, max_km: float = 50):
        self.max_km = max_km
    
    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance in km between two points."""
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371  # Earth radius in km
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        
        return R * c
    
    def check(
        self,
        latitude: Optional[float],
        longitude: Optional[float],
        city: Optional[str],
        county: Optional[str],
        **kwargs
    ) -> Optional[ValidationResult]:
        if latitude is None or longitude is None:
            return None
        
        if city is None or county is None:
            return None
        
        city_key = (city.upper(), county.upper())
        if city_key not in self.CITY_CENTROIDS:
            return None
        
        city_lat, city_lng = self.CITY_CENTROIDS[city_key]
        distance = self.haversine_distance(latitude, longitude, city_lat, city_lng)
        
        if distance > self.max_km:
            return ValidationResult(
                flag="distance_from_city",
                severity="WARNING",
                message=f"Location {distance:.1f}km from {city} center (max: {self.max_km}km)",
                action="Verify location is correct for this city"
            )
        return None


class FallbackGeocodeRule(ValidationRule):
    """Flag geocodes using fallback methods."""
    
    def check(self, approach: Optional[str], **kwargs) -> Optional[ValidationResult]:
        if approach == "city_centroid_fallback":
            return ValidationResult(
                flag="fallback_used",
                severity="ERROR",
                message="Both roads missing from network; used city centroid approximation",
                action="Locate actual work area - city centroid is very approximate"
            )
        return None


class MissingRoadRule(ValidationRule):
    """Flag geocodes where one road is missing."""
    
    def check(self, approach: Optional[str], **kwargs) -> Optional[ValidationResult]:
        if approach == "city_primary":
            return ValidationResult(
                flag="one_road_missing",
                severity="WARNING",
                message="One road not found in network; used city + available road",
                action="Consider finding missing road for more precise location"
            )
        return None


class ValidationEngine:
    """Runs validation rules and collects results."""
    
    def __init__(self, rules: Optional[List[ValidationRule]] = None):
        """Initialize validation engine.
        
        Args:
            rules: List of validation rules to apply
        """
        self.rules = rules or self._get_default_rules()
    
    @staticmethod
    def _get_default_rules() -> List[ValidationRule]:
        """Get default validation rules."""
        return [
            LowConfidenceRule(threshold=0.65),
            EmergencyLowConfidenceRule(threshold=0.75),
            CityDistanceRule(max_km=50),
            FallbackGeocodeRule(),
            MissingRoadRule(),
        ]
    
    def validate(self, **geocode_data) -> List[ValidationResult]:
        """Run all validation rules.
        
        Args:
            **geocode_data: Geocode fields to validate
            
        Returns:
            List of ValidationResult for triggered rules
        """
        results = []
        
        for rule in self.rules:
            result = rule.check(**geocode_data)
            if result is not None:
                results.append(result)
        
        return results
    
    def get_validation_flags(self, results: List[ValidationResult]) -> List[str]:
        """Extract validation flags from results.
        
        Args:
            results: List of ValidationResult
            
        Returns:
            List of flag strings
        """
        return [r.flag for r in results]


if __name__ == "__main__":
    # Test validation engine
    engine = ValidationEngine()
    
    print("Testing ValidationEngine...\n")
    
    # Test case 1: Low confidence
    results1 = engine.validate(
        confidence=0.55,
        latitude=31.5,
        longitude=-103.1,
        city="Pyote",
        county="Ward",
        ticket_type="Normal",
        method="PROXIMITY_BASED",
        approach="closest_point"
    )
    print(f"Test 1 - Low confidence: {len(results1)} flags")
    for r in results1:
        print(f"  • {r.flag}: {r.message}")
    assert len(results1) == 1
    assert results1[0].flag == "low_confidence"
    
    # Test case 2: Emergency low confidence
    results2 = engine.validate(
        confidence=0.65,
        latitude=31.5,
        longitude=-103.1,
        city="Pyote",
        county="Ward",
        ticket_type="Emergency",
        method="PROXIMITY_BASED",
        approach="closest_point"
    )
    print(f"\nTest 2 - Emergency low conf: {len(results2)} flags")
    for r in results2:
        print(f"  • {r.flag}: {r.message}")
    assert len(results2) == 2  # low_confidence + emergency_low_confidence
    
    # Test case 3: City centroid fallback
    results3 = engine.validate(
        confidence=0.35,
        latitude=31.8576,
        longitude=-103.0930,
        city="Kermit",
        county="Winkler",
        ticket_type="Normal",
        method="PROXIMITY_BASED",
        approach="city_centroid_fallback"
    )
    print(f"\nTest 3 - City centroid fallback: {len(results3)} flags")
    for r in results3:
        print(f"  • {r.flag}: {r.message}")
    assert "fallback_used" in [r.flag for r in results3]
    
    # Test case 4: Distance from city
    results4 = engine.validate(
        confidence=0.85,
        latitude=32.0,  # Far from Barstow (31.4596, -103.3954)
        longitude=-102.0,
        city="Barstow",
        county="Ward",
        ticket_type="Normal",
        method="PROXIMITY_BASED",
        approach="closest_point"
    )
    print(f"\nTest 4 - Far from city: {len(results4)} flags")
    for r in results4:
        print(f"  • {r.flag}: {r.message}")
    assert "distance_from_city" in [r.flag for r in results4]
    
    # Test case 5: No issues (high quality)
    results5 = engine.validate(
        confidence=0.95,
        latitude=31.5401,
        longitude=-103.1293,
        city="Pyote",
        county="Ward",
        ticket_type="Normal",
        method="API_PRIMARY",
        approach=None
    )
    print(f"\nTest 5 - High quality: {len(results5)} flags")
    assert len(results5) == 0
    
    print("\n✓ All ValidationEngine tests passed!")
