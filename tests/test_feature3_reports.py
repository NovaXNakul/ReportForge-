# tests/test_feature3_reports.py
import pytest
import os
import pandas as pd
from anomaly_detector import (
    detect_iqr_anomalies,
    detect_zscore_anomalies,
    detect_isolation_forest_anomalies,
)
from clustering_engine import (
    run_spatial_clustering,
)
from feature3_report_generator import (
    Feature3Bundle,
    generate_feature3_excel_bytes,
    generate_feature3_ppt_bytes,
)


@pytest.fixture
def sample_hospital_df():
    csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "sample_hospitals_anomaly.csv")
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)
    # Fallback minimal df
    return pd.DataFrame({
        "hospital_id": [f"H{i:03d}" for i in range(1, 11)],
        "name": [f"Hospital {i}" for i in range(1, 11)],
        "latitude": [19.0760 + i * 0.001 for i in range(10)],
        "longitude": [72.8777 + i * 0.001 for i in range(10)],
        "bed_count": [100 + i * 10 for i in range(9)] + [1500],
        "icu_beds": [20 + i * 2 for i in range(10)],
        "daily_admissions": [50 + i * 5 for i in range(10)],
        "er_wait_time_min": [30 + i * 2 for i in range(10)],
    })


def test_feature3_bundle_and_reports(sample_hospital_df):
    df = sample_hospital_df
    numeric_cols = ["bed_count", "icu_beds", "daily_admissions", "er_wait_time_min"]
    existing_cols = [c for c in numeric_cols if c in df.columns]

    iqr_res = detect_iqr_anomalies(df, existing_cols, k=1.5)
    zscore_res = detect_zscore_anomalies(df, existing_cols, threshold=3.0)
    iforest_res = detect_isolation_forest_anomalies(df, existing_cols, random_state=42)
    dbscan_res = run_spatial_clustering(df, "latitude", "longitude", eps_km=1.0, min_samples=3)

    bundle = Feature3Bundle(
        dataset_name="Sample Hospitals Test",
        filename="sample_hospitals_anomaly.csv",
        total_rows=len(df),
        iqr_results=iqr_res,
        zscore_results=zscore_res,
        iforest_result=iforest_res,
        clustering_result=dbscan_res,
        config_summary={
            "iqr_k": 1.5,
            "zscore_threshold": 3.0,
            "iforest_contamination": 0.05,
            "eps_km": 1.0,
            "min_samples": 3,
            "numeric_columns": existing_cols,
        }
    )

    # Verify Excel Generation
    excel_bytes = generate_feature3_excel_bytes(bundle)
    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 1000

    # Verify PPT Generation
    ppt_bytes = generate_feature3_ppt_bytes(bundle)
    assert isinstance(ppt_bytes, bytes)
    assert len(ppt_bytes) > 1000
