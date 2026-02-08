#!/usr/bin/env python3
"""
proximity_geocoder.py

Proximity-based geocoding for 811 tickets where "intersection" means
"work area on Street near/along Intersection" rather than geometric intersection.

Strategy Selection Based on Road Characteristics:

    Approach 2 (Closest Point): Roads parallel/nearby, both found
        - Best for: County roads in rural areas (CR & CR, CR & FM)
        - Example: "CR 426 & CR 432" → point on CR 426 closest to CR 432
        - Why: Rural roads often run parallel; work is "on A, near B"

    Approach 3 (Corridor Midpoint): Major + minor road, defines a segment
        - Best for: Interstate/highway with local reference (I-20 & CR 516)
        - Example: "I-20 & FM 516" → midpoint of I-20 segment near FM 516
        - Why: Describes a segment of major road bounded by minor road

    Approach 4 (City + Primary Street): One road missing or very local
        - Best for: Local streets, missing roads (LAKEVIEW DR & I-20)
        - Example: "LAKEVIEW DR & I-20" → point on I-20 near city center
        - Why: Local street provides city context, work likely on major road

Author: Corey Klaasmeyer / Claude Code
Date: 2026-02-08
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import geopandas as gpd
from shapely.geometry import Point, LineString
from shapely.ops import nearest_points

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


@dataclass
class ProximityResult:
    """Result from proximity-based geocoding."""
    success: bool
    lat: Optional[float] = None
    lng: Optional[float] = None
    confidence: float = 0.0
    method: str = "proximity"
    approach: Optional[str] = None  # "closest_point", "corridor_midpoint", "city_primary"
    reasoning: Optional[str] = None  # Why this approach was chosen
    error: Optional[str] = None
    metadata: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "lat": self.lat,
            "lng": self.lng,
            "confidence": self.confidence,
            "method": self.method,
            "approach": self.approach,
            "reasoning": self.reasoning,
            "error": self.error,
            "metadata": self.metadata or {},
        }


class RoadCharacteristics:
    """Classify road types and contexts for decision-making."""

    ROAD_HIERARCHY = {
        "Interstate": 5,
        "US": 4,
        "TX_SH": 3,
        "FM": 2,
        "RM": 2,
        "CR": 1,
        "CR_NUMBERED": 1,
        "OTHER": 0,
        "OTHER_NUMBERED": 0,
    }

    RURAL_COUNTIES = ["WARD", "WINKLER", "ANDREWS"]
    RURAL_CITIES = ["PYOTE", "BARSTOW", "COYANOSA", "MONAHANS", "KERMIT"]

    @classmethod
    def get_hierarchy(cls, road_type: str) -> int:
        """Get road hierarchy level (higher = more major road)."""
        return cls.ROAD_HIERARCHY.get(road_type, 0)

    @classmethod
    def is_rural(cls, county: str, city: str) -> bool:
        """Determine if location is rural based on county/city."""
        return (county.upper() in cls.RURAL_COUNTIES or
                city.upper() in cls.RURAL_CITIES)

    @classmethod
    def is_major_road(cls, road_type: str) -> bool:
        """Check if road is major (Interstate, US, State Highway)."""
        return cls.get_hierarchy(road_type) >= 3


class ProximityGeocoder:
    """Geocode 811 tickets using proximity-based approaches."""

    # City centroids for fallback geocoding (approximate coordinates)
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

    def __init__(self, roads_file: Path):
        """Initialize with road network data."""
        self.roads_file = Path(roads_file)
        self.roads: Optional[gpd.GeoDataFrame] = None
        self._load_roads()

    def _load_roads(self) -> None:
        """Load road network from GeoPackage."""
        if not self.roads_file.exists():
            raise FileNotFoundError(f"Road network file not found: {self.roads_file}")

        logging.info(f"Loading road network from {self.roads_file}")
        self.roads = gpd.read_file(self.roads_file, layer="roads")

        # Normalize column names
        if "road_name" in self.roads.columns and "name" not in self.roads.columns:
            self.roads["name"] = self.roads["road_name"]
        if "road_ref" in self.roads.columns and "ref" not in self.roads.columns:
            self.roads["ref"] = self.roads["road_ref"]

        logging.info(f"Loaded {len(self.roads)} road segments")

    def _normalize_road_name(self, name: str) -> str:
        """Normalize road name for matching."""
        if not name:
            return ""

        import re
        name = str(name).strip().upper()

        # Normalize common suffixes
        name = name.replace(" RD", "").replace(" ROAD", "")
        name = name.replace(" HWY", "").replace(" HIGHWAY", "")
        name = name.replace(" AVE", "").replace(" AVENUE", "")
        name = name.replace(" ST", "").replace(" STREET", "")
        name = name.replace(" DR", "").replace(" DRIVE", "")

        # Normalize common prefixes and variations
        name = name.replace("U.S. HWY", "US")
        name = name.replace("U.S.", "US")
        name = name.replace("UNITED STATES HWY", "US")
        name = name.replace("STATE HWY", "SH")
        name = name.replace("STATE HIGHWAY", "SH")
        name = name.replace("FARM TO MARKET", "FM")
        name = name.replace("FARM MARKET", "FM")
        name = name.replace("COUNTY ROAD", "CR")
        name = name.replace("CO RD", "CR")
        name = name.replace("RANCH ROAD", "RR")

        # Fix spacing issues (e.g., "FM516" -> "FM 516")
        name = re.sub(r'(FM|CR|SH|TX|US|RR|RRM)(\d)', r'\1 \2', name)

        # Normalize spacing and hyphens
        name = name.replace("-", " ")
        name = re.sub(r'\s+', ' ', name).strip()

        return name

    def _get_road_name_variations(self, name: str) -> list[str]:
        """Generate common variations of a road name for fuzzy matching.

        Returns list of normalized variations to try when exact match fails.
        Examples:
            "HWY 115" -> ["HWY 115", "SH 115", "TX 115", "115"]
            "FM516" -> ["FM 516", "FM516"]
            "HWY 516" -> ["HWY 516", "CR 516", "FM 516"]
        """
        if not name:
            return []

        import re
        normalized = self._normalize_road_name(name)
        variations = [normalized]

        # Extract number if present
        number_match = re.search(r'\b(\d+)\b', normalized)
        if not number_match:
            return variations

        number = number_match.group(1)

        # Generate prefix variations based on patterns in failures
        # "HWY" could be SH, TX, CR, FM
        if normalized.startswith("HWY"):
            variations.extend([
                f"SH {number}",
                f"TX {number}",
                f"CR {number}",
                f"FM {number}",
            ])
        elif normalized.startswith("CR"):
            variations.append(f"FM {number}")
            variations.append(f"HWY {number}")
        elif normalized.startswith("FM"):
            variations.append(f"CR {number}")
            variations.append(f"HWY {number}")
        elif normalized.startswith("SH") or normalized.startswith("TX"):
            variations.append(f"HWY {number}")
            variations.append(f"FM {number}")
        elif normalized.startswith("US"):
            variations.append(f"HWY {number}")

        # Also try just the number (might match ref field)
        variations.append(number)

        return list(set(variations))  # Remove duplicates

    def _find_road(self, road_name: str) -> Optional[gpd.GeoDataFrame]:
        """Find road segments matching name with variation support."""
        if self.roads is None or not road_name:
            return None

        normalized = self._normalize_road_name(road_name)

        # Try exact match first
        candidates = self.roads[
            (self.roads["name"].str.upper().str.replace(r'[-\s]+', ' ', regex=True).str.strip() == normalized) |
            (self.roads["ref"].str.upper().str.replace(r'[-\s]+', ' ', regex=True).str.strip() == normalized)
        ]

        if len(candidates) > 0:
            return candidates

        # Try variations (HWY->SH, CR->FM, etc.)
        variations = self._get_road_name_variations(road_name)
        for variation in variations:
            if variation == normalized:
                continue  # Already tried

            candidates = self.roads[
                (self.roads["name"].str.upper().str.replace(r'[-\s]+', ' ', regex=True).str.strip() == variation) |
                (self.roads["ref"].str.upper().str.replace(r'[-\s]+', ' ', regex=True).str.strip() == variation)
            ]

            if len(candidates) > 0:
                logging.debug(f"Found road using variation: {road_name} -> {variation}")
                return candidates

        # Try partial match as last resort
        tokens = normalized.split()
        if len(tokens) >= 2:
            mask = self.roads["name"].str.upper().str.contains(tokens[0], na=False) & \
                   self.roads["name"].str.upper().str.contains(tokens[1], na=False)
            mask |= self.roads["ref"].str.upper().str.contains(tokens[0], na=False) & \
                    self.roads["ref"].str.upper().str.contains(tokens[1], na=False)
            candidates = self.roads[mask]
        else:
            candidates = self.roads[
                self.roads["name"].str.upper().str.contains(normalized, na=False) |
                self.roads["ref"].str.upper().str.contains(normalized, na=False)
            ]

        return candidates if len(candidates) > 0 else None

    def _approach_2_closest_point(
        self,
        primary_roads: gpd.GeoDataFrame,
        reference_roads: gpd.GeoDataFrame,
        ticket_type: Optional[str] = None,
        duration: Optional[str] = None,
        work_type: Optional[str] = None,
    ) -> Tuple[Point, float, str]:
        """Approach 2: Find closest point on primary road to reference road.

        Best for: Parallel county roads in rural areas.
        Returns: (point, confidence, reasoning)
        """
        # Combine all geometries
        primary_geom = primary_roads.unary_union
        reference_geom = reference_roads.unary_union

        # Find nearest points
        nearest = nearest_points(primary_geom, reference_geom)
        point_on_primary = nearest[0]

        # Calculate distance for confidence (closer = higher confidence)
        distance = point_on_primary.distance(reference_geom)

        # Confidence: high if within 0.01 degrees (~1km), decreasing with distance
        base_confidence = max(0.5, min(0.95, 1.0 - (distance * 50)))

        # Apply adjustment based on ticket metadata
        adjustment_factor = self._calculate_adjustment_factor(
            ticket_type, duration, work_type
        )
        confidence = min(0.95, base_confidence * adjustment_factor)

        reasoning = (
            f"Rural/parallel roads: Found closest approach point between roads. "
            f"Distance: {distance:.4f} degrees (~{distance * 111:.1f}km). "
            f"Adjustment factor: {adjustment_factor:.2f} "
            f"(base: {base_confidence:.2%}, adjusted: {confidence:.2%})"
        )

        return point_on_primary, confidence, reasoning

    def _approach_3_corridor_midpoint(
        self,
        major_roads: gpd.GeoDataFrame,
        minor_roads: gpd.GeoDataFrame,
        ticket_type: Optional[str] = None,
        duration: Optional[str] = None,
        work_type: Optional[str] = None,
    ) -> Tuple[Point, float, str]:
        """Approach 3: Midpoint of major road segment near minor road.

        Best for: Work on major highway, referenced by local road.
        Returns: (point, confidence, reasoning)
        """
        minor_geom = minor_roads.unary_union

        # Find major road segments within reasonable distance of minor road
        buffer_distance = 0.05  # ~5km buffer
        search_area = minor_geom.buffer(buffer_distance)

        nearby_segments = major_roads[major_roads.intersects(search_area)]

        if len(nearby_segments) == 0:
            # Fall back to closest point on any major road segment
            major_geom = major_roads.unary_union
            nearest = nearest_points(major_geom, minor_geom)
            point = nearest[0]
            base_confidence = 0.6
            reasoning_prefix = "Major highway: Used closest point (no segments in buffer)"
        else:
            # Use centroid of nearby segments
            combined_geom = nearby_segments.unary_union
            point = combined_geom.centroid
            base_confidence = 0.75
            reasoning_prefix = (
                f"Major highway corridor: Used midpoint of {len(nearby_segments)} "
                f"segment(s) near reference road."
            )

        # Apply adjustment based on ticket metadata
        adjustment_factor = self._calculate_adjustment_factor(
            ticket_type, duration, work_type
        )
        confidence = min(0.95, base_confidence * adjustment_factor)

        reasoning = (
            f"{reasoning_prefix} Adjustment factor: {adjustment_factor:.2f} "
            f"(base: {base_confidence:.2%}, adjusted: {confidence:.2%})"
        )

        return point, confidence, reasoning

    def _fallback_city_centroid(
        self,
        city: str,
        county: str,
        ticket_type: Optional[str] = None,
        duration: Optional[str] = None,
        work_type: Optional[str] = None,
    ) -> Tuple[Point, float, str]:
        """Fallback: Use city centroid when both roads are missing.

        Best for: Complete road data unavailability.
        Returns: (point, low confidence, reasoning)
        """
        city_key = (city.upper(), county.upper())

        # Try exact city/county match
        if city_key in self.CITY_CENTROIDS:
            lat, lng = self.CITY_CENTROIDS[city_key]
            point = Point(lng, lat)
            base_confidence = 0.35

            # Apply minimal adjustment (city fallback inherently uncertain)
            adjustment_factor = self._calculate_adjustment_factor(
                ticket_type, duration, work_type
            )
            confidence = min(0.50, base_confidence * adjustment_factor)

            reasoning = (
                f"City centroid fallback: Both roads missing from network. "
                f"Using approximate city center for {city}, {county}. "
                f"Adjustment factor: {adjustment_factor:.2f} "
                f"(base: {base_confidence:.2%}, adjusted: {confidence:.2%}). "
                f"⚠️ Low confidence - recommend manual review."
            )

            return point, confidence, reasoning

        # If city not in our centroid database, fail
        raise ValueError(f"City centroid not available for {city}, {county}")

    def _approach_4_city_primary(
        self,
        available_road: gpd.GeoDataFrame,
        city: str,
        county: str,
        ticket_type: Optional[str] = None,
        duration: Optional[str] = None,
        work_type: Optional[str] = None,
    ) -> Tuple[Point, float, str]:
        """Approach 4: Point on available road biased toward city center.

        Best for: One road missing, use city + available road.
        Returns: (point, confidence, reasoning)
        """
        # Use centroid of available road as approximation
        road_geom = available_road.unary_union
        point = road_geom.centroid

        base_confidence = 0.65

        # Apply adjustment based on ticket metadata
        adjustment_factor = self._calculate_adjustment_factor(
            ticket_type, duration, work_type
        )
        confidence = min(0.95, base_confidence * adjustment_factor)

        reasoning = (
            f"City-based approximation: One road not found in network. "
            f"Using centroid of available road near {city}, {county}. "
            f"Adjustment factor: {adjustment_factor:.2f} "
            f"(base: {base_confidence:.2%}, adjusted: {confidence:.2%})"
        )

        return point, confidence, reasoning

    def _calculate_adjustment_factor(
        self,
        ticket_type: Optional[str],
        duration: Optional[str],
        work_type: Optional[str]
    ) -> float:
        """Calculate confidence adjustment based on ticket metadata.

        Returns multiplicative factor between 0.85 and 1.15:
        - < 1.0 = reduces confidence (more spatial uncertainty)
        - = 1.0 = no adjustment
        - > 1.0 = increases confidence (more spatial precision)

        Args:
            ticket_type: Type of ticket (Emergency, Normal, Update, Survey/Design)
            duration: Work duration string (e.g., "1 DAY", "2 MONTHS")
            work_type: Nature of work (e.g., "Hydro-excavation", "Pipeline Maintenance")

        Returns:
            Adjustment factor clamped to [0.85, 1.15]
        """
        factor = 1.0

        # Ticket Type adjustment
        if ticket_type:
            ticket_multipliers = {
                "Emergency": 1.05,
                "Normal": 1.0,
                "Update": 1.02,
                "Survey/Design": 0.98,
            }
            factor *= ticket_multipliers.get(ticket_type, 1.0)

        # Duration adjustment
        if duration:
            duration_upper = duration.upper()
            if any(x in duration_upper for x in ["1 DAY", "2 HRS", "1 HR", "HOUR", "1 day"]):
                factor *= 1.1  # Short duration = precise
            elif any(x in duration_upper for x in ["MONTH", "60 DAYS", "90 DAYS", "YEAR"]):
                factor *= 0.95  # Long duration = corridor
            # else: medium duration (weeks) = no adjustment

        # Work Type adjustment
        if work_type:
            work_upper = work_type.upper()
            # Point work (precise)
            if any(x in work_upper for x in ["HYDRO-EXCAVATION", "TEST STATION",
                                              "POLE", "ANCHOR", "GROUND ROD"]):
                factor *= 1.1
            # Corridor work (less precise)
            elif any(x in work_upper for x in ["PIPELINE", "CONSTRUCTION",
                                                 "SOIL REMEDIATION", "POWER LINE"]):
                factor *= 0.95

        # Clamp to reasonable bounds (max ±15% adjustment)
        return max(0.85, min(1.15, factor))

    def _select_approach(
        self,
        street: str,
        intersection: str,
        street_roads: Optional[gpd.GeoDataFrame],
        intersection_roads: Optional[gpd.GeoDataFrame],
        county: str,
        city: str
    ) -> str:
        """Select best geocoding approach based on characteristics.

        Returns: "approach_2", "approach_3", or "approach_4"
        """
        # If either road is missing, use approach 4
        if street_roads is None or intersection_roads is None:
            return "approach_4"

        # Get road types
        street_type = street_roads.iloc[0]["road_type"] if len(street_roads) > 0 else "OTHER"
        intersection_type = intersection_roads.iloc[0]["road_type"] if len(intersection_roads) > 0 else "OTHER"

        street_hierarchy = RoadCharacteristics.get_hierarchy(street_type)
        intersection_hierarchy = RoadCharacteristics.get_hierarchy(intersection_type)
        is_rural = RoadCharacteristics.is_rural(county, city)

        # Decision logic

        # Case 1: Major road + local/minor reference → Approach 3 (corridor)
        if (street_hierarchy >= 3 and intersection_hierarchy <= 2) or \
           (intersection_hierarchy >= 3 and street_hierarchy <= 2):
            return "approach_3"

        # Case 2: Both county roads in rural area → Approach 2 (closest point)
        if is_rural and street_hierarchy <= 2 and intersection_hierarchy <= 2:
            return "approach_2"

        # Case 3: Similar hierarchy roads in rural → Approach 2 (closest point)
        if is_rural and abs(street_hierarchy - intersection_hierarchy) <= 1:
            return "approach_2"

        # Default: Approach 3 (works for most cases)
        return "approach_3"

    def geocode_proximity(
        self,
        street: str,
        intersection: str,
        county: str,
        city: str,
        ticket_type: Optional[str] = None,
        duration: Optional[str] = None,
        work_type: Optional[str] = None,
    ) -> ProximityResult:
        """Geocode using proximity-based approach with intelligent selection.

        Args:
            street: Primary street name
            intersection: Reference/intersection street name
            county: County name
            city: City name
            ticket_type: Optional ticket type (Emergency, Normal, Update, Survey/Design)
            duration: Optional work duration (e.g., "1 DAY", "2 MONTHS")
            work_type: Optional nature of work (e.g., "Hydro-excavation", "Pipeline Maintenance")

        Returns:
            ProximityResult with adjusted confidence scores based on ticket metadata
        """

        # Find roads
        street_roads = self._find_road(street)
        intersection_roads = self._find_road(intersection)

        # Check if we found both roads
        if street_roads is None and intersection_roads is None:
            # Try city-centroid fallback as last resort
            try:
                point, confidence, reasoning = self._fallback_city_centroid(
                    city, county,
                    ticket_type, duration, work_type
                )

                return ProximityResult(
                    success=True,
                    lat=point.y,
                    lng=point.x,
                    confidence=confidence,
                    method="proximity",
                    approach="city_centroid_fallback",
                    reasoning=reasoning,
                    metadata={
                        "street": street,
                        "intersection": intersection,
                        "county": county,
                        "city": city,
                        "ticket_type": ticket_type,
                        "duration": duration,
                        "work_type": work_type,
                        "fallback_reason": "Both roads missing from network",
                    }
                )
            except ValueError as e:
                # City centroid not available
                return ProximityResult(
                    success=False,
                    error=f"Neither road found in network: {street}, {intersection}. {str(e)}",
                )

        # Select approach
        approach = self._select_approach(
            street, intersection, street_roads, intersection_roads, county, city
        )

        try:
            if approach == "approach_4":
                # One road missing - use city + available road
                available_road = street_roads if street_roads is not None else intersection_roads
                available_name = street if street_roads is not None else intersection

                point, confidence, reasoning = self._approach_4_city_primary(
                    available_road, city, county,
                    ticket_type, duration, work_type
                )

                return ProximityResult(
                    success=True,
                    lat=point.y,
                    lng=point.x,
                    confidence=confidence,
                    method="proximity",
                    approach="city_primary",
                    reasoning=reasoning,
                    metadata={
                        "street": street,
                        "intersection": intersection,
                        "available_road": available_name,
                        "county": county,
                        "city": city,
                        "ticket_type": ticket_type,
                        "duration": duration,
                        "work_type": work_type,
                    }
                )

            elif approach == "approach_2":
                # Closest point between parallel roads
                point, confidence, reasoning = self._approach_2_closest_point(
                    street_roads, intersection_roads,
                    ticket_type, duration, work_type
                )

                return ProximityResult(
                    success=True,
                    lat=point.y,
                    lng=point.x,
                    confidence=confidence,
                    method="proximity",
                    approach="closest_point",
                    reasoning=reasoning,
                    metadata={
                        "street": street,
                        "intersection": intersection,
                        "street_segments": len(street_roads),
                        "intersection_segments": len(intersection_roads),
                        "county": county,
                        "city": city,
                        "ticket_type": ticket_type,
                        "duration": duration,
                        "work_type": work_type,
                    }
                )

            else:  # approach_3
                # Corridor midpoint
                # Determine which is major road
                street_type = street_roads.iloc[0]["road_type"]
                intersection_type = intersection_roads.iloc[0]["road_type"]

                if RoadCharacteristics.is_major_road(street_type):
                    major_roads = street_roads
                    minor_roads = intersection_roads
                else:
                    major_roads = intersection_roads
                    minor_roads = street_roads

                point, confidence, reasoning = self._approach_3_corridor_midpoint(
                    major_roads, minor_roads,
                    ticket_type, duration, work_type
                )

                return ProximityResult(
                    success=True,
                    lat=point.y,
                    lng=point.x,
                    confidence=confidence,
                    method="proximity",
                    approach="corridor_midpoint",
                    reasoning=reasoning,
                    metadata={
                        "street": street,
                        "intersection": intersection,
                        "county": county,
                        "city": city,
                        "ticket_type": ticket_type,
                        "duration": duration,
                        "work_type": work_type,
                    }
                )

        except Exception as e:
            return ProximityResult(
                success=False,
                error=f"Error calculating proximity: {str(e)}",
            )


def main():
    """Demo/test the proximity geocoder."""
    roads_file = Path("roads_merged.gpkg")

    if not roads_file.exists():
        logging.error(f"Road network file not found: {roads_file}")
        return

    geocoder = ProximityGeocoder(roads_file)

    # Test cases representing different scenarios
    test_cases = [
        # Approach 2: Rural parallel county roads
        ("CR 426", "CR 432", "Ward", "Pyote", "Parallel county roads in rural area"),
        ("CR 516", "CR 432", "Ward", "Pyote", "Parallel county roads in rural area"),

        # Approach 3: Major highway + local reference
        ("I-20", "CR 516", "Ward", "Barstow", "Interstate with county road reference"),
        ("US 385", "FM 1788", "Andrews", "Andrews", "US highway with FM reference"),

        # Approach 4: One road missing
        ("LAKEVIEW DR", "I-20", "Ward", "Barstow", "Local street (missing) + Interstate"),
        ("SE 8000", "US 385", "Andrews", "Gardendale", "Numbered road + US highway"),
    ]

    print("\n" + "=" * 80)
    print("PROXIMITY-BASED GEOCODING TEST")
    print("=" * 80)

    for street, intersection, county, city, description in test_cases:
        print(f"\n📍 {description}")
        print(f"   {street} & {intersection} ({city}, {county})")
        print("-" * 80)

        result = geocoder.geocode_proximity(street, intersection, county, city)

        if result.success:
            print(f"✅ SUCCESS - {result.approach}")
            print(f"   Lat/Lng: {result.lat:.6f}, {result.lng:.6f}")
            print(f"   Confidence: {result.confidence:.1%}")
            print(f"   Reasoning: {result.reasoning}")
        else:
            print(f"❌ FAILED")
            print(f"   Error: {result.error}")

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
