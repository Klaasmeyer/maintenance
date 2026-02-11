#!/usr/bin/env python3
"""
geometric_geocoder.py

Calculate intersection coordinates from road geometries using spatial analysis.
This provides a fallback geocoding method when Google Geocoding API returns
ZERO_RESULTS for intersection queries.

Algorithm:
1. Load road network from GeoPackage
2. For each failed intersection:
   a. Fuzzy match road names to geometries in network
   b. Find all segments for both roads
   c. Calculate geometric intersections
   d. Filter by county/city bounds
   e. Return best intersection point with confidence score

Usage:
    from geometric_geocoder import GeometricGeocoder

    geocoder = GeometricGeocoder("roads.gpkg")
    result = geocoder.geocode_intersection(
        street="US 385",
        intersection="FM 1788",
        county="Andrews",
        city="Andrews"
    )

    if result["success"]:
        print(f"Location: {result['lat']}, {result['lng']}")
        print(f"Confidence: {result['confidence']}")
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import nearest_points

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


@dataclass
class IntersectionResult:
    """Result from geometric intersection calculation."""

    success: bool
    lat: Optional[float] = None
    lng: Optional[float] = None
    confidence: float = 0.0
    method: str = "geometric"
    error: Optional[str] = None
    metadata: Optional[dict] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "lat": self.lat,
            "lng": self.lng,
            "confidence": self.confidence,
            "method": self.method,
            "error": self.error,
            "metadata": self.metadata or {},
        }


class GeometricGeocoder:
    """Geocode intersections using road network geometry."""

    def __init__(self, roads_file: Path):
        """Initialize geocoder with road network data.

        Args:
            roads_file: Path to GeoPackage containing road geometries
        """
        self.roads_file = Path(roads_file)
        self.roads: Optional[gpd.GeoDataFrame] = None
        self._load_roads()

    def _load_roads(self) -> None:
        """Load road network from GeoPackage."""
        if not self.roads_file.exists():
            raise FileNotFoundError(f"Road network file not found: {self.roads_file}")

        logging.info(f"Loading road network from {self.roads_file}")
        self.roads = gpd.read_file(self.roads_file, layer="roads")
        logging.info(f"Loaded {len(self.roads)} road segments")

        # Normalize column names for compatibility
        if "road_name" in self.roads.columns and "name" not in self.roads.columns:
            self.roads["name"] = self.roads["road_name"]
        if "road_ref" in self.roads.columns and "ref" not in self.roads.columns:
            self.roads["ref"] = self.roads["road_ref"]

    def _normalize_road_name(self, name: str) -> str:
        """Normalize road name for matching.

        This should use the same normalization as geocode-routes.py
        """
        if not name:
            return ""

        # Basic normalization
        name = str(name).strip().upper()

        # Remove common prefixes/suffixes that vary
        name = name.replace(" RD", "")
        name = name.replace(" ROAD", "")
        name = name.replace(" HWY", "")
        name = name.replace(" HIGHWAY", "")

        # Normalize spacing around dashes
        name = name.replace("-", " ")

        # Collapse multiple spaces
        import re
        name = re.sub(r'\s+', ' ', name).strip()

        return name

    def _find_road_candidates(
        self,
        road_name: str,
        max_candidates: int = 20
    ) -> gpd.GeoDataFrame:
        """Find road segments matching the given name.

        Uses fuzzy matching to handle name variants.

        Args:
            road_name: Name or reference of road to find
            max_candidates: Maximum number of segments to return

        Returns:
            GeoDataFrame of matching road segments
        """
        if self.roads is None or road_name == "":
            return gpd.GeoDataFrame()

        normalized = self._normalize_road_name(road_name)

        # Try exact match first (on normalized names)
        candidates = self.roads[
            (self.roads["name"].str.upper().str.replace(r'[-\s]+', ' ', regex=True).str.strip() == normalized) |
            (self.roads["ref"].str.upper().str.replace(r'[-\s]+', ' ', regex=True).str.strip() == normalized)
        ].copy()

        if len(candidates) > 0:
            logging.debug(f"Found {len(candidates)} exact matches for '{road_name}'")
            return candidates.head(max_candidates)

        # Try partial match
        # Split normalized name into tokens and match any
        tokens = normalized.split()
        if len(tokens) >= 2:
            # For multi-token names, require both tokens present
            mask = self.roads["name"].str.upper().str.contains(tokens[0], na=False) & \
                   self.roads["name"].str.upper().str.contains(tokens[1], na=False)
            mask |= self.roads["ref"].str.upper().str.contains(tokens[0], na=False) & \
                    self.roads["ref"].str.upper().str.contains(tokens[1], na=False)

            candidates = self.roads[mask].copy()
        else:
            # Single token - just do contains match
            candidates = self.roads[
                self.roads["name"].str.upper().str.contains(normalized, na=False) |
                self.roads["ref"].str.upper().str.contains(normalized, na=False)
            ].copy()

        if len(candidates) > 0:
            logging.debug(f"Found {len(candidates)} partial matches for '{road_name}'")
            return candidates.head(max_candidates)

        logging.warning(f"No road segments found for '{road_name}'")
        return gpd.GeoDataFrame()

    def _calculate_intersections(
        self,
        roads_a: gpd.GeoDataFrame,
        roads_b: gpd.GeoDataFrame
    ) -> list[Point]:
        """Calculate all intersection points between two sets of road segments.

        Args:
            roads_a: First set of road segments
            roads_b: Second set of road segments

        Returns:
            List of intersection Points
        """
        intersections = []

        for _, road_a in roads_a.iterrows():
            geom_a = road_a.geometry

            for _, road_b in roads_b.iterrows():
                geom_b = road_b.geometry

                # Check if they intersect
                if geom_a.intersects(geom_b):
                    intersection = geom_a.intersection(geom_b)

                    # Handle different intersection types
                    if intersection.geom_type == "Point":
                        intersections.append(intersection)
                    elif intersection.geom_type == "MultiPoint":
                        intersections.extend(list(intersection.geoms))
                    elif intersection.geom_type == "LineString":
                        # Roads overlap - use midpoint
                        intersections.append(intersection.centroid)
                    elif intersection.geom_type == "GeometryCollection":
                        # Extract points from collection
                        for geom in intersection.geoms:
                            if geom.geom_type == "Point":
                                intersections.append(geom)

        return intersections

    def _filter_by_bounds(
        self,
        points: list[Point],
        county: str,
        city: str
    ) -> list[Point]:
        """Filter intersection points to those within reasonable bounds.

        For now, this is a placeholder. In a full implementation, you would:
        - Load county/city boundaries
        - Filter points to those within bounds
        - Optionally use route corridor to further filter

        Args:
            points: List of intersection points
            county: County name
            city: City name

        Returns:
            Filtered list of points
        """
        # TODO: Implement proper bounds checking
        # For now, return all points
        return points

    def _choose_best_intersection(
        self,
        points: list[Point],
        city: str
    ) -> tuple[Point, float]:
        """Choose the best intersection point from multiple candidates.

        Strategy:
        - If only one point, return it with high confidence
        - If multiple, prefer points closer to city center (if known)
        - Otherwise, return first point with moderate confidence

        Args:
            points: List of candidate intersection points
            city: City name (for disambiguation)

        Returns:
            (best_point, confidence_score)
        """
        if not points:
            return None, 0.0

        if len(points) == 1:
            # Single intersection - high confidence
            return points[0], 0.95

        # Multiple intersections - need disambiguation
        # For now, use centroid of all points as a compromise
        # TODO: Implement city center lookup for better disambiguation

        logging.warning(
            f"Found {len(points)} intersection points for {city}. "
            f"Using centroid - consider implementing city-based disambiguation."
        )

        # Calculate centroid of all intersection points
        from shapely.geometry import MultiPoint
        multi = MultiPoint(points)
        centroid = multi.centroid

        # Find closest actual intersection to centroid
        best_point = min(points, key=lambda p: p.distance(centroid))

        # Moderate confidence due to ambiguity
        confidence = 0.75 - (len(points) * 0.05)  # Decrease confidence with more ambiguity
        confidence = max(confidence, 0.5)  # Floor at 0.5

        return best_point, confidence

    def geocode_intersection(
        self,
        street: str,
        intersection: str,
        county: str,
        city: str
    ) -> IntersectionResult:
        """Geocode an intersection using geometric calculation.

        Args:
            street: First road name
            intersection: Second road name (cross street)
            county: County name
            city: City name

        Returns:
            IntersectionResult with lat/lng and confidence score
        """
        # Find road segments for both roads
        roads_a = self._find_road_candidates(street)
        roads_b = self._find_road_candidates(intersection)

        # Check if we found both roads
        if len(roads_a) == 0:
            return IntersectionResult(
                success=False,
                error=f"Road not found in network: {street}",
                metadata={"street": street, "intersection": intersection}
            )

        if len(roads_b) == 0:
            return IntersectionResult(
                success=False,
                error=f"Road not found in network: {intersection}",
                metadata={"street": street, "intersection": intersection}
            )

        logging.info(
            f"Found {len(roads_a)} segments for '{street}', "
            f"{len(roads_b)} segments for '{intersection}'"
        )

        # Calculate intersections
        intersection_points = self._calculate_intersections(roads_a, roads_b)

        if not intersection_points:
            return IntersectionResult(
                success=False,
                error=f"Roads do not intersect: {street} & {intersection}",
                metadata={
                    "street": street,
                    "intersection": intersection,
                    "street_segments": len(roads_a),
                    "intersection_segments": len(roads_b),
                }
            )

        logging.info(f"Found {len(intersection_points)} intersection point(s)")

        # Filter by bounds (if applicable)
        filtered_points = self._filter_by_bounds(intersection_points, county, city)

        if not filtered_points:
            return IntersectionResult(
                success=False,
                error=f"No intersections within bounds for {county}, {city}",
                metadata={
                    "street": street,
                    "intersection": intersection,
                    "total_intersections": len(intersection_points),
                }
            )

        # Choose best intersection
        best_point, confidence = self._choose_best_intersection(filtered_points, city)

        if best_point is None:
            return IntersectionResult(
                success=False,
                error="Failed to select best intersection",
                metadata={"street": street, "intersection": intersection}
            )

        return IntersectionResult(
            success=True,
            lat=best_point.y,
            lng=best_point.x,
            confidence=confidence,
            method="geometric",
            metadata={
                "street": street,
                "intersection": intersection,
                "county": county,
                "city": city,
                "total_intersections": len(filtered_points),
                "street_segments": len(roads_a),
                "intersection_segments": len(roads_b),
            }
        )


def main():
    """Demo/test the geometric geocoder."""
    roads_file = Path("roads.gpkg")

    if not roads_file.exists():
        logging.error(f"Road network file not found: {roads_file}")
        logging.info("Please run download_road_network.py first")
        return

    geocoder = GeometricGeocoder(roads_file)

    # Test cases from actual failures
    test_cases = [
        ("US 385", "FM 1788", "Andrews", "Andrews"),
        ("TX 115", "FM 1788", "Andrews", "Andrews"),  # Ranch Rd 1788 variant
        ("I 20", "US 385", "Ward", "Monahans"),
        ("FM 1882", "US 385", "Ward", "Pyote"),
    ]

    print("\n" + "=" * 70)
    print("GEOMETRIC GEOCODER TEST")
    print("=" * 70)

    for street, intersection_rd, county, city in test_cases:
        print(f"\n🔍 Testing: {street} & {intersection_rd} ({city}, {county})")
        print("-" * 70)

        result = geocoder.geocode_intersection(street, intersection_rd, county, city)

        if result.success:
            print(f"  ✅ SUCCESS")
            print(f"     Location: {result.lat:.6f}, {result.lng:.6f}")
            print(f"     Confidence: {result.confidence:.2%}")
            print(f"     Intersections found: {result.metadata.get('total_intersections', 0)}")
        else:
            print(f"  ❌ FAILED")
            print(f"     Error: {result.error}")

    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
