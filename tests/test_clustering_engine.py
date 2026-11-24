# tests/test_clustering_engine.py
import pytest
import numpy as np
import pandas as pd
from clustering_engine import (
    ClusteringConfig,
    ClusteringResult,
    run_spatial_clustering,
)


class TestSpatialClusteringEngine:
    def test_two_clusters_and_noise(self):
        # Cluster 1: 5 points around 19.0760, 72.8777 (Mumbai) within ~500m
        c1_lat = [19.0760, 19.0762, 19.0758, 19.0765, 19.0759]
        c1_lon = [72.8777, 72.8779, 72.8775, 72.8778, 72.8776]

        # Cluster 2: 5 points around 18.9220, 72.8347 (Colaba) within ~500m (~17km away from c1)
        c2_lat = [18.9220, 18.9222, 18.9218, 18.9225, 18.9219]
        c2_lon = [72.8347, 72.8349, 72.8345, 72.8348, 72.8346]

        # Noise point: 1 point far away (Pune: 18.5204, 73.8567)
        noise_lat = [18.5204]
        noise_lon = [73.8567]

        df = pd.DataFrame({
            "lat": c1_lat + c2_lat + noise_lat,
            "lon": c1_lon + c2_lon + noise_lon,
        })

        res = run_spatial_clustering(df, "lat", "lon", eps_km=1.0, min_samples=3)

        assert isinstance(res, ClusteringResult)
        assert res.total_records == 11
        assert res.valid_records == 11
        assert len(res.excluded_details) == 0
        assert res.cluster_count == 2
        assert res.noise_count == 1
        assert len(res.cluster_sizes) == 2

        # Cluster labels should have two non -1 clusters and 1 noise
        labels = [r["cluster_label"] for r in res.evaluated_rows]
        assert -1 in labels
        assert len(set(labels) - {-1}) == 2

        # Noise point is the 11th record (row_id 11)
        pune_pt = next(r for r in res.evaluated_rows if r["row_id"] == 11)
        assert pune_pt["cluster_label"] == -1
        assert pune_pt["is_noise"] is True

    def test_invalid_coordinates_excluded_not_noise(self):
        df = pd.DataFrame({
            "lat": [19.0760, 19.0762, 95.0, np.nan, "invalid"],
            "lon": [72.8777, 72.8779, 72.8775, 72.8778, 72.8776],
        })
        res = run_spatial_clustering(df, "lat", "lon", eps_km=1.0, min_samples=2)

        assert res.total_records == 5
        assert res.valid_records == 2
        assert res.excluded_records == 3
        assert len(res.excluded_details) == 3
        # Excluded records are distinct from noise
        excluded_row_ids = [e["row_id"] for e in res.excluded_details]
        assert 3 in excluded_row_ids
        assert 4 in excluded_row_ids
        assert 5 in excluded_row_ids

    def test_all_points_noise(self):
        # Points far apart with small eps
        df = pd.DataFrame({
            "lat": [10.0, 20.0, 30.0],
            "lon": [10.0, 20.0, 30.0],
        })
        res = run_spatial_clustering(df, "lat", "lon", eps_km=1.0, min_samples=2)
        assert res.cluster_count == 0
        assert res.noise_count == 3

    def test_single_cluster_all_points(self):
        # 4 identical/near points
        df = pd.DataFrame({
            "lat": [19.0760, 19.07601, 19.07602, 19.07603],
            "lon": [72.8777, 72.87771, 72.87772, 72.87773],
        })
        res = run_spatial_clustering(df, "lat", "lon", eps_km=1.0, min_samples=2)
        assert res.cluster_count == 1
        assert res.noise_count == 0

    def test_invalid_parameters_raise(self):
        df = pd.DataFrame({"lat": [1.0], "lon": [1.0]})
        with pytest.raises(ValueError, match="eps_km must be a positive"):
            run_spatial_clustering(df, "lat", "lon", eps_km=0)

        with pytest.raises(ValueError, match="min_samples must be an integer >= 1"):
            run_spatial_clustering(df, "lat", "lon", min_samples=0)
