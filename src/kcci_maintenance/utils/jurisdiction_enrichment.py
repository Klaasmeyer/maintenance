"""
Jurisdiction enrichment utilities.

Performs spatial joins to determine permitting authority and jurisdiction
information for geocoded locations.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

import geopandas as gpd
from shapely.geometry import Point

logger = logging.getLogger(__name__)


class JurisdictionEnricher:
    """Enriches geocoded locations with jurisdiction and permitting data."""

    def __init__(
        self,
        geojson_path: Path,
        attributes: Optional[list[str]] = None,
        cache_spatial_index: bool = True,
    ):
        """Initialize jurisdiction enricher.

        Args:
            geojson_path: Path to GeoJSON file with jurisdiction polygons
            attributes: List of attribute names to extract (default: all)
            cache_spatial_index: Whether to build spatial index (default: True)
        """
        self.geojson_path = geojson_path
        self.attributes = attributes or []
        self.cache_spatial_index = cache_spatial_index

        # Load jurisdiction data
        self.jurisdictions_gdf: Optional[gpd.GeoDataFrame] = None
        self._load_jurisdiction_data()

    def _load_jurisdiction_data(self) -> None:
        """Load GeoJSON and build spatial index."""
        try:
            logger.info(f"Loading jurisdiction data from {self.geojson_path}")
            self.jurisdictions_gdf = gpd.read_file(self.geojson_path)

            # Ensure EPSG:4326
            if self.jurisdictions_gdf.crs != "EPSG:4326":
                logger.info(f"Reprojecting from {self.jurisdictions_gdf.crs} to EPSG:4326")
                self.jurisdictions_gdf = self.jurisdictions_gdf.to_crs("EPSG:4326")

            # Build spatial index if requested
            if self.cache_spatial_index:
                self.jurisdictions_gdf.sindex  # Access triggers creation
                logger.info("Spatial index created")

            logger.info(f"Loaded {len(self.jurisdictions_gdf)} jurisdiction features")

        except Exception as e:
            logger.error(f"Failed to load jurisdiction data: {e}")
            self.jurisdictions_gdf = None

    def determine_jurisdiction(
        self,
        lat: float,
        lng: float,
    ) -> Tuple[bool, Dict[str, any]]:
        """Determine jurisdiction for a geocoded location.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            Tuple of (success, jurisdiction_data)
            - success: True if jurisdiction found
            - jurisdiction_data: Dict with jurisdiction attributes
        """
        if self.jurisdictions_gdf is None or self.jurisdictions_gdf.empty:
            return False, {
                "error": "No jurisdiction data available",
            }

        try:
            point = Point(lng, lat)

            # Find containing polygon(s)
            mask = self.jurisdictions_gdf.contains(point)
            matching = self.jurisdictions_gdf[mask]

            if matching.empty:
                return False, {
                    "jurisdiction_found": False,
                    "message": "Location not within any known jurisdiction",
                }

            # Use first match (could handle overlaps differently if needed)
            jurisdiction = matching.iloc[0]

            # Extract requested attributes or all
            result = {"jurisdiction_found": True}

            if self.attributes:
                for attr in self.attributes:
                    if attr in jurisdiction:
                        result[attr] = jurisdiction[attr]
            else:
                # Return all non-geometry attributes
                for col in jurisdiction.index:
                    if col != "geometry":
                        result[col] = jurisdiction[col]

            return True, result

        except Exception as e:
            logger.error(f"Error determining jurisdiction: {e}")
            return False, {
                "error": str(e),
            }


if __name__ == "__main__":
    # Test the jurisdiction enricher
    print("JurisdictionEnricher - Test Mode\n")

    # Example: Test with Wink project jurisdiction data (if available)
    jurisdiction_file = Path("projects/wink/permitting/Wink APN - Jurisdictions and Permitting.geojson")

    if jurisdiction_file.exists():
        print(f"Loading jurisdiction data from {jurisdiction_file}")

        enricher = JurisdictionEnricher(
            geojson_path=jurisdiction_file,
            attributes=["authority_name", "jurisdiction_type", "permit_required"],
            cache_spatial_index=True,
        )

        # Test locations
        # Example coordinates near Wink, TX
        test_locations = [
            (31.7534, -103.1615, "Near Wink"),
            (31.5401, -103.1293, "Near Pyote"),
        ]

        for lat, lng, label in test_locations:
            success, jurisdiction_data = enricher.determine_jurisdiction(lat, lng)

            print(f"\nTest Location: {label} ({lat}, {lng})")
            print(f"  Success: {success}")
            print(f"  Jurisdiction data: {jurisdiction_data}")

    else:
        print(f"Test file not found: {jurisdiction_file}")
        print("This is expected if running outside of the project directory")
