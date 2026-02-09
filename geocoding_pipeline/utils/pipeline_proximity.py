"""
Pipeline proximity analysis utilities.

Analyzes geocoded locations relative to known pipeline infrastructure
from RRC (Railroad Commission) shapefiles. Provides confidence boosts
for tickets located near known pipelines.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zipfile import ZipFile

import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import nearest_points

logger = logging.getLogger(__name__)


class PipelineProximityAnalyzer:
    """Analyzes proximity to known pipeline infrastructure."""

    def __init__(
        self,
        shapefile_paths: List[Path],
        boost_thresholds: Optional[Dict[int, float]] = None,
        validation_distance_m: float = 500.0,
    ):
        """Initialize pipeline proximity analyzer.

        Args:
            shapefile_paths: List of paths to pipeline shapefiles (ZIP or direct .shp)
            boost_thresholds: Distance-to-boost mapping in meters
                            e.g., {10: 0.15, 25: 0.10, 50: 0.05, 100: 0.02}
            validation_distance_m: Distance threshold for validation warnings (default 500m)
        """
        self.shapefile_paths = shapefile_paths
        self.validation_distance_m = validation_distance_m

        # Default boost thresholds
        if boost_thresholds is None:
            self.boost_thresholds = {
                10: 0.15,   # ≤10m: +15% boost
                25: 0.10,   # ≤25m: +10% boost
                50: 0.05,   # ≤50m: +5% boost
                100: 0.02,  # ≤100m: +2% boost
            }
        else:
            self.boost_thresholds = boost_thresholds

        # Sort thresholds for efficient lookup (ascending order)
        self.sorted_thresholds = sorted(self.boost_thresholds.keys())

        # Load pipeline geometries
        self.pipelines_gdf: Optional[gpd.GeoDataFrame] = None
        self._load_pipeline_data()

    def _load_pipeline_data(self) -> None:
        """Load and merge all pipeline shapefiles into a single GeoDataFrame."""
        all_gdfs = []

        for path in self.shapefile_paths:
            try:
                gdf = self._load_single_shapefile(path)
                if gdf is not None and not gdf.empty:
                    all_gdfs.append(gdf)
                    logger.info(f"Loaded {len(gdf)} pipeline features from {path.name}")
            except Exception as e:
                logger.error(f"Failed to load pipeline data from {path}: {e}")

        if not all_gdfs:
            logger.warning("No pipeline data loaded - proximity analysis will be disabled")
            self.pipelines_gdf = None
            return

        # Merge all GeoDataFrames
        self.pipelines_gdf = gpd.GeoDataFrame(
            pd.concat(all_gdfs, ignore_index=True),
            crs=all_gdfs[0].crs,
        )

        # Ensure CRS is EPSG:4326 (WGS84) for lat/lng compatibility
        if self.pipelines_gdf.crs != "EPSG:4326":
            logger.info(f"Reprojecting from {self.pipelines_gdf.crs} to EPSG:4326")
            self.pipelines_gdf = self.pipelines_gdf.to_crs("EPSG:4326")

        # Build spatial index for fast nearest-neighbor queries
        self.pipelines_gdf.sindex

        logger.info(
            f"Pipeline data loaded: {len(self.pipelines_gdf)} total features"
        )

    def _load_single_shapefile(self, path: Path) -> Optional[gpd.GeoDataFrame]:
        """Load a single shapefile (from ZIP or direct .shp file).

        Args:
            path: Path to ZIP file containing shapefile or direct .shp file

        Returns:
            GeoDataFrame or None if load fails
        """
        if path.suffix.lower() == ".zip":
            # Extract shapefile from ZIP
            return self._load_from_zip(path)
        elif path.suffix.lower() == ".shp":
            # Direct shapefile
            return gpd.read_file(path)
        else:
            logger.warning(f"Unsupported file type: {path.suffix}")
            return None

    def _load_from_zip(self, zip_path: Path) -> Optional[gpd.GeoDataFrame]:
        """Load shapefile from a ZIP archive.

        Args:
            zip_path: Path to ZIP file

        Returns:
            GeoDataFrame or None if load fails
        """
        with ZipFile(zip_path, 'r') as zf:
            # Find .shp file in ZIP
            shp_files = [name for name in zf.namelist() if name.endswith('.shp')]

            if not shp_files:
                logger.warning(f"No .shp file found in {zip_path}")
                return None

            if len(shp_files) > 1:
                logger.warning(f"Multiple .shp files in {zip_path}, using first: {shp_files[0]}")

            # Extract to temp location and read
            # GeoPandas can read directly from ZIP using vsizip
            shp_file = shp_files[0]
            vsi_path = f"/vsizip/{zip_path}/{shp_file}"

            return gpd.read_file(vsi_path)

    def calculate_proximity_boost(
        self,
        lat: float,
        lng: float,
    ) -> Tuple[float, Dict[str, any]]:
        """Calculate confidence boost based on proximity to pipelines.

        Args:
            lat: Latitude of geocoded location
            lng: Longitude of geocoded location

        Returns:
            Tuple of (boost_amount, metadata_dict)
            - boost_amount: Confidence boost (0.0 to 0.15)
            - metadata_dict: Contains distance_m, confidence_level, etc.
        """
        if self.pipelines_gdf is None or self.pipelines_gdf.empty:
            return 0.0, {
                "pipeline_proximity_m": None,
                "pipeline_proximity_boost": 0.0,
                "pipeline_confidence": "NONE",
                "error": "No pipeline data available",
            }

        try:
            # Create point geometry
            point = Point(lng, lat)  # Note: Point(x, y) = Point(lng, lat)

            # Find nearest pipeline
            nearest_geom = self.pipelines_gdf.geometry.unary_union
            nearest_point_on_pipeline, _ = nearest_points(point, nearest_geom)

            # Calculate distance in meters using geodesic distance
            # For small distances, simple CRS calculation is sufficient
            # For more accuracy, could use GeoPandas distance with projected CRS
            distance_m = self._calculate_distance_meters(
                lat, lng,
                nearest_point_on_pipeline.y, nearest_point_on_pipeline.x
            )

            # Determine boost based on distance thresholds
            boost = 0.0
            confidence_level = "NONE"

            for threshold in self.sorted_thresholds:
                if distance_m <= threshold:
                    boost = self.boost_thresholds[threshold]
                    if threshold <= 10:
                        confidence_level = "HIGH"
                    elif threshold <= 25:
                        confidence_level = "MEDIUM"
                    elif threshold <= 50:
                        confidence_level = "LOW"
                    else:
                        confidence_level = "MINIMAL"
                    break

            return boost, {
                "pipeline_proximity_m": round(distance_m, 2),
                "pipeline_proximity_boost": boost,
                "pipeline_confidence": confidence_level,
                "within_validation_distance": distance_m <= self.validation_distance_m,
            }

        except Exception as e:
            logger.error(f"Error calculating pipeline proximity: {e}")
            return 0.0, {
                "pipeline_proximity_m": None,
                "pipeline_proximity_boost": 0.0,
                "pipeline_confidence": "ERROR",
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

        Uses Haversine formula for accuracy.

        Args:
            lat1, lng1: First point coordinates
            lat2, lng2: Second point coordinates

        Returns:
            Distance in meters
        """
        from math import radians, sin, cos, sqrt, atan2

        # Earth radius in meters
        R = 6371000

        # Convert to radians
        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        dlat = radians(lat2 - lat1)
        dlng = radians(lng2 - lng1)

        # Haversine formula
        a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlng / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        distance = R * c

        return distance

    def is_near_pipeline(self, lat: float, lng: float, threshold_m: float = 500.0) -> bool:
        """Check if a location is within threshold distance of any pipeline.

        Args:
            lat: Latitude
            lng: Longitude
            threshold_m: Distance threshold in meters (default 500m)

        Returns:
            True if within threshold, False otherwise
        """
        _, metadata = self.calculate_proximity_boost(lat, lng)
        distance = metadata.get("pipeline_proximity_m")

        if distance is None:
            return False

        return distance <= threshold_m


# Import pandas after conditional imports above
import pandas as pd


if __name__ == "__main__":
    # Test the pipeline proximity analyzer
    print("PipelineProximityAnalyzer - Test Mode\n")

    # Example: Test with Wink project pipeline data (if available)
    pipeline_dir = Path("projects/wink/utilities/pipeline/Pipeline Layers")

    if pipeline_dir.exists():
        shapefiles = list(pipeline_dir.glob("*.zip"))
        print(f"Found {len(shapefiles)} pipeline shapefiles")

        if shapefiles:
            analyzer = PipelineProximityAnalyzer(
                shapefile_paths=shapefiles,
                validation_distance_m=500.0,
            )

            # Test proximity calculation
            # Example coordinate near Wink, TX
            test_lat, test_lng = 31.7534, -103.1615

            boost, metadata = analyzer.calculate_proximity_boost(test_lat, test_lng)

            print(f"\nTest Location: ({test_lat}, {test_lng})")
            print(f"  Distance to nearest pipeline: {metadata.get('pipeline_proximity_m')} m")
            print(f"  Confidence boost: +{boost * 100:.1f}%")
            print(f"  Pipeline confidence: {metadata.get('pipeline_confidence')}")
            print(f"  Within validation distance: {metadata.get('within_validation_distance')}")
        else:
            print("No pipeline shapefiles found in test directory")
    else:
        print(f"Test directory not found: {pipeline_dir}")
        print("This is expected if running outside of the project directory")
