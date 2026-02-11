"""
Route corridor validation utilities.

Validates geocoded locations against expected fiber route corridors,
identifying locations that may be outside the planned route.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
from zipfile import ZipFile

import geopandas as gpd
import fiona
from shapely.geometry import Point, shape
from shapely.ops import nearest_points

logger = logging.getLogger(__name__)


class RouteCorridorValidator:
    """Validates locations against route corridor boundaries."""

    def __init__(
        self,
        kmz_path: Path,
        buffer_distance_m: float = 500.0,
    ):
        """Initialize route corridor validator.

        Args:
            kmz_path: Path to KMZ file containing route geometry
            buffer_distance_m: Buffer distance for corridor (default 500m)
        """
        self.kmz_path = kmz_path
        self.buffer_distance_m = buffer_distance_m

        # Load route geometry
        self.route_gdf: Optional[gpd.GeoDataFrame] = None
        self.buffered_corridor: Optional[gpd.GeoDataFrame] = None
        self._load_route_data()

    def _load_route_data(self) -> None:
        """Load and process KMZ route file."""
        try:
            # KMZ is a ZIP file containing KML
            # Use fiona to read KML from within the KMZ
            gdf = self._load_kmz_file(self.kmz_path)

            if gdf is None or gdf.empty:
                logger.warning(f"No route data loaded from {self.kmz_path}")
                self.route_gdf = None
                self.buffered_corridor = None
                return

            # Ensure CRS is EPSG:4326 (WGS84)
            if gdf.crs is None:
                logger.info("No CRS specified, assuming EPSG:4326")
                gdf = gdf.set_crs("EPSG:4326")
            elif gdf.crs != "EPSG:4326":
                logger.info(f"Reprojecting from {gdf.crs} to EPSG:4326")
                gdf = gdf.to_crs("EPSG:4326")

            self.route_gdf = gdf

            # Create buffered corridor for containment checks
            # Buffer in projected coordinates for accurate distance
            # Use local UTM zone for Texas (approximately UTM Zone 13N)
            gdf_projected = gdf.to_crs("EPSG:32613")  # UTM Zone 13N
            buffered_geom = gdf_projected.geometry.buffer(self.buffer_distance_m)

            # Convert back to WGS84 for consistency
            self.buffered_corridor = gpd.GeoDataFrame(
                geometry=buffered_geom,
                crs="EPSG:32613"
            ).to_crs("EPSG:4326")

            logger.info(
                f"Route loaded: {len(gdf)} features, "
                f"buffered by {self.buffer_distance_m}m"
            )

        except Exception as e:
            logger.error(f"Failed to load route data from {self.kmz_path}: {e}")
            self.route_gdf = None
            self.buffered_corridor = None

    def _load_kmz_file(self, kmz_path: Path) -> Optional[gpd.GeoDataFrame]:
        """Load KMZ file (compressed KML).

        Args:
            kmz_path: Path to KMZ file

        Returns:
            GeoDataFrame or None if load fails
        """
        try:
            # KMZ is a ZIP containing a KML file (usually named doc.kml)
            with ZipFile(kmz_path, 'r') as zf:
                # Find KML file in ZIP
                kml_files = [name for name in zf.namelist() if name.endswith('.kml')]

                if not kml_files:
                    logger.warning(f"No .kml file found in {kmz_path}")
                    return None

                if len(kml_files) > 1:
                    logger.warning(f"Multiple .kml files found, using first: {kml_files[0]}")

                kml_file = kml_files[0]

                # Extract KML to temp and read with fiona/geopandas
                # Use fiona's vsizip support
                vsi_path = f"/vsizip/{kmz_path}/{kml_file}"

                return gpd.read_file(vsi_path, driver='KML')

        except Exception as e:
            logger.error(f"Error loading KMZ file: {e}")
            return None

    def check_containment(
        self,
        lat: float,
        lng: float,
    ) -> Tuple[bool, Dict[str, any]]:
        """Check if location is within route corridor.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            Tuple of (is_within_corridor, metadata_dict)
            - is_within_corridor: True if within buffered corridor
            - metadata_dict: Contains distance_from_centerline_m, etc.
        """
        if self.route_gdf is None or self.buffered_corridor is None:
            return False, {
                "within_corridor": False,
                "distance_from_centerline_m": None,
                "error": "No route data available",
            }

        try:
            # Create point geometry
            point = Point(lng, lat)

            # Check if point is within buffered corridor
            is_within = self.buffered_corridor.contains(point).any()

            # Calculate distance from route centerline
            route_line = self.route_gdf.geometry.unary_union
            nearest_point_on_route, _ = nearest_points(point, route_line)

            distance_m = self._calculate_distance_meters(
                lat, lng,
                nearest_point_on_route.y, nearest_point_on_route.x
            )

            return is_within, {
                "within_corridor": is_within,
                "distance_from_centerline_m": round(distance_m, 2),
                "buffer_distance_m": self.buffer_distance_m,
            }

        except Exception as e:
            logger.error(f"Error checking corridor containment: {e}")
            return False, {
                "within_corridor": False,
                "distance_from_centerline_m": None,
                "error": str(e),
            }

    def _calculate_distance_meters(
        self,
        lat1: float,
        lng1: float,
        lat2: float,
        lng2: float,
    ) -> float:
        """Calculate distance in meters between two lat/lng points.

        Uses Haversine formula.

        Args:
            lat1, lng1: First point
            lat2, lng2: Second point

        Returns:
            Distance in meters
        """
        from math import radians, sin, cos, sqrt, atan2

        R = 6371000  # Earth radius in meters

        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        dlat = radians(lat2 - lat1)
        dlng = radians(lng2 - lng1)

        a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlng / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return R * c


if __name__ == "__main__":
    # Test the route corridor validator
    print("RouteCorridorValidator - Test Mode\n")

    # Example: Test with Wink project route data (if available)
    route_file = Path("projects/wink/route/wink.kmz")

    if route_file.exists():
        print(f"Loading route from {route_file}")

        validator = RouteCorridorValidator(
            kmz_path=route_file,
            buffer_distance_m=500.0,
        )

        # Test locations
        # Example coordinate near Wink, TX
        test_locations = [
            (31.7534, -103.1615, "Near Wink"),
            (31.5401, -103.1293, "Near Pyote"),
        ]

        for lat, lng, label in test_locations:
            is_within, metadata = validator.check_containment(lat, lng)

            print(f"\nTest Location: {label} ({lat}, {lng})")
            print(f"  Within corridor: {is_within}")
            print(f"  Distance from centerline: {metadata.get('distance_from_centerline_m')} m")
            print(f"  Buffer distance: {metadata.get('buffer_distance_m')} m")

    else:
        print(f"Test file not found: {route_file}")
        print("This is expected if running outside of the project directory")
