# clustering_engine.py

"""
Spatial Clustering Engine for ReportForge 2.0 using DBSCAN.

Provides density-based spatial clustering on geographic coordinates:
- Uses sklearn.cluster.DBSCAN with metric="haversine" and algorithm="ball_tree".
- Accepts coordinates in degrees (latitude, longitude), validates boundaries
  (latitude [-90, +90], longitude [-180, +180]), and converts to radians.
- Converts distance threshold eps_km to radians using Earth radius R = 6371.0 km.
- Explicitly separates invalid/missing coordinate records from valid DBSCAN noise points.
- Labels core points, border points, and density noise (-1).

DBSCAN Concepts:
- Epsilon (eps): Neighborhood radius around a point.
- Min Samples (min_samples): Minimum points within eps to form a dense region (core point).
- Core Point: A point with at least min_samples neighbors within eps.
- Border Point: Within eps of a core point but has fewer than min_samples neighbors.
- Noise Point (-1): Not reachable from any core point. Noise points are geographically
  isolated records, which are not necessarily errors (e.g., remote rural hospitals).
"""

import math
import logging
from typing import Optional, List, Dict, Any

import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN

logger = logging.getLogger(__name__)

# Mean Earth radius in kilometres used for Haversine radian conversion
EARTH_RADIUS_KM = 6371.0


class ClusteringConfig:
    """
    Configuration for DBSCAN spatial clustering.

    Attributes:
        lat_column: Name of the latitude column.
        lon_column: Name of the longitude column.
        eps_km: Maximum neighbor distance threshold in kilometres (default 0.5).
        min_samples: Minimum neighborhood points required for core point (default 5).
    """

    def __init__(self,
                 lat_column: Optional[str] = None,
                 lon_column: Optional[str] = None,
                 eps_km: float = 0.5,
                 min_samples: int = 5):
        self.lat_column = lat_column
        self.lon_column = lon_column
        self.eps_km = float(eps_km)
        self.min_samples = int(min_samples)

        self._validate()

    def _validate(self):
        if not math.isfinite(self.eps_km) or self.eps_km <= 0:
            raise ValueError(f"eps_km must be a positive finite number, got {self.eps_km}")

        if self.min_samples < 1:
            raise ValueError(f"min_samples must be an integer >= 1, got {self.min_samples}")

    @property
    def eps_radians(self) -> float:
        """Convert epsilon from kilometres to radians on spherical Earth."""
        return self.eps_km / EARTH_RADIUS_KM


class ClusteringResult:
    """
    Container for DBSCAN spatial clustering results.
    """

    def __init__(self, eps_km: float, min_samples: int):
        self.eps_km = eps_km
        self.min_samples = min_samples
        self.eps_radians = eps_km / EARTH_RADIUS_KM
        self.total_records = 0
        self.valid_records = 0
        self.excluded_records = 0
        self.cluster_count = 0
        self.noise_count = 0
        self.noise_percentage = 0.0
        self.cluster_sizes = {}  # Dict mapping cluster_label (int) -> size
        self.evaluated_rows = []  # Detailed results per valid geographic record
        self.excluded_details = [] # Records excluded due to missing/invalid coordinates
        self.notes = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eps_km": self.eps_km,
            "min_samples": self.min_samples,
            "eps_radians": self.eps_radians,
            "total_records": self.total_records,
            "valid_records": self.valid_records,
            "excluded_records": self.excluded_records,
            "cluster_count": self.cluster_count,
            "noise_count": self.noise_count,
            "noise_percentage": self.noise_percentage,
            "cluster_sizes": self.cluster_sizes,
            "notes": self.notes,
        }


def run_spatial_clustering(df: pd.DataFrame,
                           lat_column: str,
                           lon_column: str,
                           eps_km: float = 0.5,
                           min_samples: int = 5,
                           source_name: str = "Source") -> ClusteringResult:
    """
    Execute DBSCAN spatial clustering on geographic coordinates in df.

    Steps:
    1. Validate eps_km and min_samples.
    2. Validate and filter coordinates:
       - Latitude in [-90, +90]
       - Longitude in [-180, +180]
       - Non-finite or missing coordinates are placed in excluded_records with reasons.
    3. Convert degree coordinates to radians: [lat_rad, lon_rad].
    4. Convert eps_km to eps_radians: eps_km / 6371.0.
    5. Fit DBSCAN(eps=eps_radians, min_samples=min_samples, metric="haversine", algorithm="ball_tree").
    6. Extract cluster labels (-1 = noise, 0, 1, 2... = clusters) and core sample flags.
    7. Compile results and summary.
    """
    config = ClusteringConfig(
        lat_column=lat_column,
        lon_column=lon_column,
        eps_km=eps_km,
        min_samples=min_samples,
    )

    res = ClusteringResult(eps_km=config.eps_km, min_samples=config.min_samples)
    res.total_records = len(df)

    if not lat_column or not lon_column:
        res.notes = "Latitude and longitude columns must both be specified."
        return res

    if lat_column not in df.columns or lon_column not in df.columns:
        res.notes = f"Coordinate column(s) not found in dataset: lat='{lat_column}', lon='{lon_column}'"
        return res

    row_id_col = "_original_row_id" if "_original_row_id" in df.columns else None

    valid_indices = []
    rad_coords = []

    for idx in df.index:
        row_id = int(df.loc[idx, row_id_col]) if row_id_col else (idx + 1)
        raw_lat = df.loc[idx, lat_column]
        raw_lon = df.loc[idx, lon_column]

        # Check for missing
        if raw_lat is None or raw_lon is None or pd.isna(raw_lat) or pd.isna(raw_lon):
            res.excluded_records += 1
            res.excluded_details.append({
                "row_id": row_id,
                "raw_latitude": str(raw_lat),
                "raw_longitude": str(raw_lon),
                "reason": "Missing coordinate value"
            })
            continue

        try:
            num_lat = float(raw_lat)
            num_lon = float(raw_lon)
        except (ValueError, TypeError):
            res.excluded_records += 1
            res.excluded_details.append({
                "row_id": row_id,
                "raw_latitude": str(raw_lat),
                "raw_longitude": str(raw_lon),
                "reason": "Non-numeric coordinate value"
            })
            continue

        if not (math.isfinite(num_lat) and math.isfinite(num_lon)):
            res.excluded_records += 1
            res.excluded_details.append({
                "row_id": row_id,
                "raw_latitude": str(raw_lat),
                "raw_longitude": str(raw_lon),
                "reason": "Non-finite coordinate value"
            })
            continue

        if not (-90.0 <= num_lat <= 90.0):
            res.excluded_records += 1
            res.excluded_details.append({
                "row_id": row_id,
                "raw_latitude": str(raw_lat),
                "raw_longitude": str(raw_lon),
                "reason": f"Latitude {num_lat} out of valid range [-90, +90]"
            })
            continue

        if not (-180.0 <= num_lon <= 180.0):
            res.excluded_records += 1
            res.excluded_details.append({
                "row_id": row_id,
                "raw_latitude": str(raw_lat),
                "raw_longitude": str(raw_lon),
                "reason": f"Longitude {num_lon} out of valid range [-180, +180]"
            })
            continue

        valid_indices.append((idx, row_id, num_lat, num_lon))
        # Sklearn Haversine expects [latitude, longitude] in radians
        rad_coords.append([math.radians(num_lat), math.radians(num_lon)])

    res.valid_records = len(valid_indices)

    if res.valid_records == 0:
        res.notes = "No valid geographic coordinates available for clustering."
        return res

    X_rad = np.array(rad_coords, dtype=float)

    # Execute DBSCAN with haversine metric on ball_tree
    dbscan = DBSCAN(
        eps=config.eps_radians,
        min_samples=config.min_samples,
        metric="haversine",
        algorithm="ball_tree"
    )
    dbscan.fit(X_rad)

    labels = dbscan.labels_
    core_indices_set = set(dbscan.core_sample_indices_)

    # Compile cluster sizes and counts
    cluster_sizes = {}
    noise_count = 0

    for i, (idx, row_id, lat_deg, lon_deg) in enumerate(valid_indices):
        lbl = int(labels[i])
        is_noise = (lbl == -1)
        is_core = (i in core_indices_set)

        if is_noise:
            noise_count += 1
        else:
            cluster_sizes[lbl] = cluster_sizes.get(lbl, 0) + 1

        res.evaluated_rows.append({
            "source_name": source_name,
            "row_id": row_id,
            "latitude": lat_deg,
            "longitude": lon_deg,
            "cluster_label": lbl,
            "is_noise": is_noise,
            "is_core_point": is_core,
        })

    res.cluster_sizes = cluster_sizes
    res.cluster_count = len(cluster_sizes)
    res.noise_count = noise_count
    res.noise_percentage = (noise_count / res.valid_records * 100) if res.valid_records > 0 else 0.0

    return res
