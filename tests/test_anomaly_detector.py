# tests/test_anomaly_detector.py
import pytest
import math
import numpy as np
import pandas as pd
from anomaly_detector import (
    AnomalyConfig,
    IQRColumnResult,
    detect_iqr_anomalies,
    ZScoreColumnResult,
    detect_zscore_anomalies,
    IsolationForestResult,
    detect_isolation_forest_anomalies,
)


class TestIQRAnomalyDetector:
    def test_iqr_clean_dataset_with_outlier(self):
        # 10 values, 1 clear outlier
        data = [10.0, 11.0, 12.0, 11.5, 12.5, 13.0, 10.5, 11.8, 12.2, 100.0]
        df = pd.DataFrame({"val": data})

        res = detect_iqr_anomalies(df, ["val"], k=1.5)
        assert "val" in res
        col_res: IQRColumnResult = res["val"]
        assert col_res.total_records == 10
        assert col_res.evaluated_records == 10
        assert len(col_res.anomalies) == 1
        assert col_res.anomalies[0]["row_id"] == 10  # 1-based row_id
        assert col_res.anomalies[0]["value"] == 100.0
        assert col_res.anomalies[0]["boundary_violated"] == "upper"

    def test_iqr_no_outliers(self):
        data = [10.0, 11.0, 12.0, 13.0, 14.0]
        df = pd.DataFrame({"val": data})
        res = detect_iqr_anomalies(df, ["val"])
        col_res = res["val"]
        assert len(col_res.anomalies) == 0

    def test_iqr_constant_column_zero_iqr(self):
        data = [5.0, 5.0, 5.0, 5.0, 5.0]
        df = pd.DataFrame({"val": data})
        res = detect_iqr_anomalies(df, ["val"])
        col_res = res["val"]
        assert col_res.iqr == 0.0
        assert col_res.is_constant is True
        assert len(col_res.anomalies) == 0

    def test_iqr_missing_and_infinite_values(self):
        # 8 valid points clustered around 10-12, plus 1 outlier 200, plus nans and infs
        data = [10.0, 10.5, 11.0, 11.5, 12.0, np.nan, np.inf, -np.inf, 200.0]
        df = pd.DataFrame({"val": data})
        res = detect_iqr_anomalies(df, ["val"], k=1.5)
        col_res = res["val"]
        assert col_res.total_records == 9
        assert col_res.excluded_records == 3
        assert col_res.evaluated_records == 6
        assert len(col_res.anomalies) == 1
        assert col_res.anomalies[0]["value"] == 200.0

    def test_iqr_empty_dataframe(self):
        df = pd.DataFrame({"val": []})
        res = detect_iqr_anomalies(df, ["val"])
        col_res = res["val"]
        assert col_res.total_records == 0
        assert col_res.evaluated_records == 0
        assert len(col_res.anomalies) == 0

    def test_iqr_invalid_multiplier_raises(self):
        df = pd.DataFrame({"val": [1, 2, 3]})
        with pytest.raises(ValueError, match="k must be non-negative"):
            detect_iqr_anomalies(df, ["val"], k=-1.0)


class TestZScoreAnomalyDetector:
    def test_zscore_known_distribution(self):
        # 10 points around 0, plus 1 extreme point 100
        data = [-1.0, 0.0, 1.0, -0.5, 0.5, -0.2, 0.2, -0.1, 0.1, 100.0]
        df = pd.DataFrame({"val": data})
        res = detect_zscore_anomalies(df, ["val"], threshold=2.5)
        col_res: ZScoreColumnResult = res["val"]
        assert col_res.total_records == 10
        assert col_res.evaluated_records == 10
        assert len(col_res.anomalies) == 1
        assert col_res.anomalies[0]["row_id"] == 10
        assert col_res.anomalies[0]["z_score"] > 2.5

    def test_zscore_constant_column_zero_std(self):
        data = [42.0, 42.0, 42.0]
        df = pd.DataFrame({"val": data})
        res = detect_zscore_anomalies(df, ["val"])
        col_res = res["val"]
        assert col_res.std == 0.0
        assert col_res.is_constant is True
        assert len(col_res.anomalies) == 0

    def test_zscore_missing_and_infinite_values(self):
        data = [10.0, 10.0, np.nan, np.inf, 100.0]
        df = pd.DataFrame({"val": data})
        res = detect_zscore_anomalies(df, ["val"])
        col_res = res["val"]
        assert col_res.total_records == 5
        assert col_res.excluded_records == 2
        assert col_res.evaluated_records == 3

    def test_zscore_invalid_threshold_raises(self):
        df = pd.DataFrame({"val": [1, 2, 3]})
        with pytest.raises(ValueError, match="threshold must be positive"):
            detect_zscore_anomalies(df, ["val"], threshold=0.0)


class TestIsolationForestAnomalyDetector:
    def test_isolation_forest_synthetic_cluster_and_outlier(self):
        rng = np.random.RandomState(42)
        # Cluster of 50 points around (10, 10)
        x1 = rng.normal(10, 1, 50)
        y1 = rng.normal(10, 1, 50)
        # 2 extreme outliers
        x_out = np.array([50.0, -40.0])
        y_out = np.array([50.0, -40.0])
        x = np.concatenate([x1, x_out])
        y = np.concatenate([y1, y_out])

        df = pd.DataFrame({"feat_a": x, "feat_b": y})
        res = detect_isolation_forest_anomalies(
            df,
            ["feat_a", "feat_b"],
            contamination=0.04,  # ~2 / 52
            random_state=42
        )
        assert isinstance(res, IsolationForestResult)
        assert res.total_records == 52
        assert res.evaluated_records == 52
        assert res.anomaly_count >= 2
        # Check that outlier row_ids (51, 52) are flagged
        anom_row_ids = [a["row_id"] for a in res.anomalies]
        assert 51 in anom_row_ids or 52 in anom_row_ids

    def test_isolation_forest_reproducibility(self):
        df = pd.DataFrame({
            "a": [1.0, 2.0, 1.5, 2.2, 10.0, 1.8, 2.1, 1.9],
            "b": [1.1, 2.1, 1.4, 2.0, 10.0, 1.7, 2.0, 1.8]
        })
        res1 = detect_isolation_forest_anomalies(df, ["a", "b"], contamination=0.15, random_state=42)
        res2 = detect_isolation_forest_anomalies(df, ["a", "b"], contamination=0.15, random_state=42)
        assert res1.anomaly_count == res2.anomaly_count
        assert [a["row_id"] for a in res1.anomalies] == [a["row_id"] for a in res2.anomalies]

    def test_isolation_forest_missing_values_excluded(self):
        df = pd.DataFrame({
            "a": [1.0, 2.0, np.nan, 2.2, 10.0],
            "b": [1.1, 2.1, 1.4, np.inf, 10.0]
        })
        res = detect_isolation_forest_anomalies(df, ["a", "b"])
        # Rows 3 and 4 (1-based) should be excluded
        assert res.total_records == 5
        assert res.evaluated_records == 3
        assert res.excluded_records == 2
        assert [e["row_id"] for e in res.excluded_details] == [3, 4]

    def test_isolation_forest_insufficient_samples(self):
        df = pd.DataFrame({"a": [1.0], "b": [2.0]})
        res = detect_isolation_forest_anomalies(df, ["a", "b"])
        assert res.evaluated_records == 1
        assert res.anomaly_count == 0

    def test_isolation_forest_invalid_contamination_raises(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        with pytest.raises(ValueError, match="contamination must be in"):
            detect_isolation_forest_anomalies(df, ["a", "b"], contamination=0.6)
