# anomaly_detector.py

"""
Statistical and Machine Learning Anomaly Detection Module for ReportForge 2.0.

Provides three analytical anomaly detection algorithms:
1. Interquartile Range (IQR) — Univariate statistical anomaly detection using
   linear-interpolated quartiles (Q1, Q3) and configurable multiplier k (default 1.5).
2. Z-Score — Univariate statistical anomaly detection using population standard
   deviation (ddof=0) and configurable threshold (default 3.0).
3. Isolation Forest — Multivariate unsupervised machine learning anomaly detection
   using sklearn.ensemble.IsolationForest on selected numerical features.

Assumptions & Policies:
- An anomaly flag indicates that a record warrants investigation, not proof of error.
- All algorithms preserve stable row provenance (_original_row_id) and raw values.
- Missing and non-finite values (NaN, inf, -inf) are tracked and reported as excluded,
  never silently discarded or treated as zero.
- Identifier columns are excluded from ML features unless explicitly selected.
- Contamination and model parameters are strictly validated.
"""

import math
import logging
from typing import Optional, List, Dict, Any, Tuple

import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)


class AnomalyConfig:
    """
    Configuration container for statistical and ML anomaly detection.

    Attributes:
        iqr_columns: List of column names for univariate IQR analysis.
        iqr_k: Multiplier for IQR boundaries (default 1.5).
        zscore_columns: List of column names for univariate Z-score analysis.
        zscore_threshold: Absolute Z-score threshold for anomalies (default 3.0).
        iforest_features: List of numerical feature names for Isolation Forest.
        iforest_n_estimators: Number of trees in Isolation Forest (default 100).
        iforest_contamination: Expected proportion of outliers (default 0.05 or 'auto').
        iforest_random_state: Random seed for reproducibility (default 42).
    """

    def __init__(self,
                 iqr_columns: Optional[List[str]] = None,
                 iqr_k: float = 1.5,
                 zscore_columns: Optional[List[str]] = None,
                 zscore_threshold: float = 3.0,
                 iforest_features: Optional[List[str]] = None,
                 iforest_n_estimators: int = 100,
                 iforest_contamination: Any = 0.05,
                 iforest_random_state: Optional[int] = 42):
        self.iqr_columns = iqr_columns or []
        self.iqr_k = float(iqr_k)
        self.zscore_columns = zscore_columns or []
        self.zscore_threshold = float(zscore_threshold)
        self.iforest_features = iforest_features or []
        self.iforest_n_estimators = int(iforest_n_estimators)
        self.iforest_contamination = iforest_contamination
        self.iforest_random_state = iforest_random_state

        self._validate()

    def _validate(self):
        if not math.isfinite(self.iqr_k) or self.iqr_k < 0:
            raise ValueError(f"IQR multiplier k must be a non-negative finite number, got {self.iqr_k}")

        if not math.isfinite(self.zscore_threshold) or self.zscore_threshold <= 0:
            raise ValueError(f"Z-score threshold must be a positive finite number, got {self.zscore_threshold}")

        if self.iforest_n_estimators <= 0:
            raise ValueError(f"Isolation Forest n_estimators must be a positive integer, got {self.iforest_n_estimators}")

        if isinstance(self.iforest_contamination, str):
            if self.iforest_contamination != "auto":
                raise ValueError(f"Isolation Forest contamination string must be 'auto', got '{self.iforest_contamination}'")
        else:
            try:
                c = float(self.iforest_contamination)
                if not (0.0 < c <= 0.5):
                    raise ValueError(f"Isolation Forest contamination must be in (0.0, 0.5], got {c}")
                self.iforest_contamination = c
            except (TypeError, ValueError) as e:
                raise ValueError(f"Invalid contamination value: {e}")


# ==============================================================================
# 1. Interquartile Range (IQR) Anomaly Detection
# ==============================================================================

class IQRColumnResult:
    """Results of univariate IQR analysis on a single column."""

    def __init__(self, column: str):
        self.column = column
        self.total_records = 0
        self.evaluated_records = 0
        self.excluded_records = 0
        self.q1 = None
        self.q3 = None
        self.iqr = None
        self.lower_bound = None
        self.upper_bound = None
        self.k = 1.5
        self.anomalies = []  # List of dicts with row_id, value, bound_violated, difference
        self.excluded_details = []  # List of dicts with row_id, raw_value, reason
        self.is_constant = False
        self.zero_iqr = False
        self.notes = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "column": self.column,
            "total_records": self.total_records,
            "evaluated_records": self.evaluated_records,
            "excluded_records": self.excluded_records,
            "q1": self.q1,
            "q3": self.q3,
            "iqr": self.iqr,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "k": self.k,
            "anomaly_count": len(self.anomalies),
            "anomaly_percentage": (len(self.anomalies) / self.evaluated_records * 100) if self.evaluated_records > 0 else 0.0,
            "is_constant": self.is_constant,
            "zero_iqr": self.zero_iqr,
            "notes": self.notes,
        }


def detect_iqr_anomalies(df: pd.DataFrame,
                         columns: List[str],
                         k: float = 1.5,
                         source_name: str = "Source") -> Dict[str, IQRColumnResult]:
    """
    Perform univariate IQR anomaly detection on specified columns.

    Calculates:
    - Q1: 25th percentile (linear interpolation)
    - Q3: 75th percentile (linear interpolation)
    - IQR = Q3 - Q1
    - Lower Bound = Q1 - k * IQR
    - Upper Bound = Q3 + k * IQR

    Policy on Zero IQR & Constant Data:
    - If all evaluated values are identical, IQR is 0 and is_constant is True.
      Since all values equal the median/bounds, 0 anomalies are flagged.
    - If Q1 == Q3 (zero IQR) but extreme distinct values exist, non-equal values
      fall outside the boundaries and are flagged.
    """
    if not math.isfinite(k) or k < 0:
        raise ValueError(f"IQR multiplier k must be non-negative and finite, got {k}")

    results = {}
    row_id_col = "_original_row_id" if "_original_row_id" in df.columns else None

    for col in columns:
        res = IQRColumnResult(column=col)
        res.k = k
        res.total_records = len(df)

        if col not in df.columns:
            res.notes = f"Column '{col}' does not exist in dataset."
            results[col] = res
            continue

        valid_rows = []
        for idx in df.index:
            row_id = int(df.loc[idx, row_id_col]) if row_id_col else (idx + 1)
            raw_val = df.loc[idx, col]

            if raw_val is None or (isinstance(raw_val, float) and np.isnan(raw_val)) or pd.isna(raw_val):
                res.excluded_records += 1
                res.excluded_details.append({
                    "row_id": row_id,
                    "column": col,
                    "raw_value": str(raw_val),
                    "reason": "Missing value"
                })
                continue

            try:
                num_val = float(raw_val)
                if not math.isfinite(num_val):
                    res.excluded_records += 1
                    res.excluded_details.append({
                        "row_id": row_id,
                        "column": col,
                        "raw_value": str(raw_val),
                        "reason": "Non-finite numeric value"
                    })
                    continue
                valid_rows.append((idx, row_id, num_val))
            except (ValueError, TypeError):
                res.excluded_records += 1
                res.excluded_details.append({
                    "row_id": row_id,
                    "column": col,
                    "raw_value": str(raw_val),
                    "reason": "Non-numeric string value"
                })

        res.evaluated_records = len(valid_rows)
        if res.evaluated_records == 0:
            res.notes = "No valid numerical values to evaluate."
            results[col] = res
            continue

        values = np.array([v[2] for v in valid_rows], dtype=float)

        # Standard linear-interpolated quartiles (compatible with numpy and pandas)
        q1 = float(np.percentile(values, 25, method="linear"))
        q3 = float(np.percentile(values, 75, method="linear"))
        iqr = q3 - q1
        lower_bound = q1 - k * iqr
        upper_bound = q3 + k * iqr

        res.q1 = q1
        res.q3 = q3
        res.iqr = iqr
        res.lower_bound = lower_bound
        res.upper_bound = upper_bound

        if np.all(values == values[0]):
            res.is_constant = True
            res.zero_iqr = True
            res.notes = "All evaluated values are identical (constant column)."
        elif iqr == 0.0:
            res.zero_iqr = True
            res.notes = "Zero IQR detected (>= 50% identical values at median)."

        for idx, row_id, num_val in valid_rows:
            raw_val = df.loc[idx, col]
            if num_val < lower_bound:
                res.anomalies.append({
                    "source_name": source_name,
                    "row_id": row_id,
                    "column": col,
                    "value": num_val,
                    "raw_value": str(raw_val),
                    "boundary_violated": "lower",
                    "bound_value": lower_bound,
                    "deviation": lower_bound - num_val,
                    "explanation": f"Value {num_val} is below lower bound {lower_bound:.4f} (Q1={q1:.4f}, IQR={iqr:.4f})."
                })
            elif num_val > upper_bound:
                res.anomalies.append({
                    "source_name": source_name,
                    "row_id": row_id,
                    "column": col,
                    "value": num_val,
                    "raw_value": str(raw_val),
                    "boundary_violated": "upper",
                    "bound_value": upper_bound,
                    "deviation": num_val - upper_bound,
                    "explanation": f"Value {num_val} exceeds upper bound {upper_bound:.4f} (Q3={q3:.4f}, IQR={iqr:.4f})."
                })

        results[col] = res

    return results


# ==============================================================================
# 2. Z-Score Anomaly Detection
# ==============================================================================

class ZScoreColumnResult:
    """Results of univariate Z-score analysis on a single column."""

    def __init__(self, column: str):
        self.column = column
        self.total_records = 0
        self.evaluated_records = 0
        self.excluded_records = 0
        self.mean = None
        self.std = None
        self.threshold = 3.0
        self.anomalies = []  # List of dicts with row_id, value, z_score
        self.all_scores = []  # List of dicts with row_id, value, z_score, is_anomaly
        self.excluded_details = []  # List of dicts with row_id, raw_value, reason
        self.is_constant = False
        self.notes = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "column": self.column,
            "total_records": self.total_records,
            "evaluated_records": self.evaluated_records,
            "excluded_records": self.excluded_records,
            "mean": self.mean,
            "std": self.std,
            "threshold": self.threshold,
            "anomaly_count": len(self.anomalies),
            "anomaly_percentage": (len(self.anomalies) / self.evaluated_records * 100) if self.evaluated_records > 0 else 0.0,
            "is_constant": self.is_constant,
            "notes": self.notes,
        }


def detect_zscore_anomalies(df: pd.DataFrame,
                            columns: List[str],
                            threshold: float = 3.0,
                            source_name: str = "Source") -> Dict[str, ZScoreColumnResult]:
    """
    Perform univariate Z-score anomaly detection on specified columns.

    Formula: Z = (x - mean) / std
    Convention: Uses population standard deviation (ddof=0).

    Policy on Zero Variance / Constant Data:
    - If std == 0, all values equal the mean, so all Z-scores are 0.0 without division by zero.
    - Anomaly is flagged when abs(z_score) > threshold.
    """
    if not math.isfinite(threshold) or threshold <= 0:
        raise ValueError(f"Z-score threshold must be positive and finite, got {threshold}")

    results = {}
    row_id_col = "_original_row_id" if "_original_row_id" in df.columns else None

    for col in columns:
        res = ZScoreColumnResult(column=col)
        res.threshold = threshold
        res.total_records = len(df)

        if col not in df.columns:
            res.notes = f"Column '{col}' does not exist in dataset."
            results[col] = res
            continue

        valid_rows = []
        for idx in df.index:
            row_id = int(df.loc[idx, row_id_col]) if row_id_col else (idx + 1)
            raw_val = df.loc[idx, col]

            if raw_val is None or (isinstance(raw_val, float) and np.isnan(raw_val)) or pd.isna(raw_val):
                res.excluded_records += 1
                res.excluded_details.append({
                    "row_id": row_id,
                    "column": col,
                    "raw_value": str(raw_val),
                    "reason": "Missing value"
                })
                continue

            try:
                num_val = float(raw_val)
                if not math.isfinite(num_val):
                    res.excluded_records += 1
                    res.excluded_details.append({
                        "row_id": row_id,
                        "column": col,
                        "raw_value": str(raw_val),
                        "reason": "Non-finite numeric value"
                    })
                    continue
                valid_rows.append((idx, row_id, num_val))
            except (ValueError, TypeError):
                res.excluded_records += 1
                res.excluded_details.append({
                    "row_id": row_id,
                    "column": col,
                    "raw_value": str(raw_val),
                    "reason": "Non-numeric string value"
                })

        res.evaluated_records = len(valid_rows)
        if res.evaluated_records == 0:
            res.notes = "No valid numerical values to evaluate."
            results[col] = res
            continue

        values = np.array([v[2] for v in valid_rows], dtype=float)
        mean_val = float(np.mean(values))
        # Population standard deviation convention ddof=0
        std_val = float(np.std(values, ddof=0))

        res.mean = mean_val
        res.std = std_val

        if std_val == 0.0:
            res.is_constant = True
            res.notes = "Zero variance detected: all evaluated values are identical."
            for idx, row_id, num_val in valid_rows:
                raw_val = df.loc[idx, col]
                res.all_scores.append({
                    "source_name": source_name,
                    "row_id": row_id,
                    "column": col,
                    "value": num_val,
                    "raw_value": str(raw_val),
                    "z_score": 0.0,
                    "is_anomaly": False,
                })
            results[col] = res
            continue

        for idx, row_id, num_val in valid_rows:
            raw_val = df.loc[idx, col]
            z = float((num_val - mean_val) / std_val)
            is_anom = abs(z) > threshold

            score_record = {
                "source_name": source_name,
                "row_id": row_id,
                "column": col,
                "value": num_val,
                "raw_value": str(raw_val),
                "z_score": round(z, 4),
                "is_anomaly": is_anom,
            }
            res.all_scores.append(score_record)

            if is_anom:
                res.anomalies.append({
                    "source_name": source_name,
                    "row_id": row_id,
                    "column": col,
                    "value": num_val,
                    "raw_value": str(raw_val),
                    "z_score": round(z, 4),
                    "deviation_from_mean": num_val - mean_val,
                    "explanation": f"Z-score {z:.4f} exceeds threshold ±{threshold:.1f} (mean={mean_val:.4f}, std={std_val:.4f})."
                })

        results[col] = res

    return results


# ==============================================================================
# 3. Isolation Forest Anomaly Detection
# ==============================================================================

class IsolationForestResult:
    """Results of multivariate Isolation Forest anomaly detection."""

    def __init__(self, features: List[str]):
        self.features = features
        self.total_records = 0
        self.evaluated_records = 0
        self.excluded_records = 0
        self.anomaly_count = 0
        self.anomaly_percentage = 0.0
        self.n_estimators = 100
        self.contamination = 0.05
        self.random_state = 42
        self.evaluated_rows = []  # Detailed results per evaluated row
        self.anomalies = []       # Subset of evaluated_rows flagged as anomalies
        self.excluded_details = [] # Rows excluded from complete-case training
        self.notes = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "features": self.features,
            "total_records": self.total_records,
            "evaluated_records": self.evaluated_records,
            "excluded_records": self.excluded_records,
            "anomaly_count": self.anomaly_count,
            "anomaly_percentage": self.anomaly_percentage,
            "n_estimators": self.n_estimators,
            "contamination": self.contamination,
            "random_state": self.random_state,
            "notes": self.notes,
        }


def detect_isolation_forest_anomalies(df: pd.DataFrame,
                                     features: List[str],
                                     n_estimators: int = 100,
                                     contamination: Any = 0.05,
                                     random_state: Optional[int] = 42,
                                     source_name: str = "Source") -> IsolationForestResult:
    """
    Perform multivariate anomaly detection using sklearn.ensemble.IsolationForest.

    Preprocessing:
    - Complete-case analysis across selected features.
    - Non-finite or missing values in any selected feature cause the row to be excluded.
    - Explicitly checks minimum sample size (at least 2 valid samples required).

    Model Outputs:
    - prediction: 1 = inlier, -1 = outlier
    - decision_function(): Average anomaly score.
      In scikit-learn, negative values indicate outliers; lower scores mean more abnormal.
    """
    cfg = AnomalyConfig(
        iforest_features=features,
        iforest_n_estimators=n_estimators,
        iforest_contamination=contamination,
        iforest_random_state=random_state,
    )

    res = IsolationForestResult(features=features)
    res.total_records = len(df)
    res.n_estimators = cfg.iforest_n_estimators
    res.contamination = cfg.iforest_contamination
    res.random_state = cfg.iforest_random_state

    if not features:
        res.notes = "No features selected for Isolation Forest."
        return res

    missing_cols = [f for f in features if f not in df.columns]
    if missing_cols:
        res.notes = f"Selected feature(s) not found in dataset: {missing_cols}"
        return res

    row_id_col = "_original_row_id" if "_original_row_id" in df.columns else None

    valid_indices = []
    matrix_rows = []

    for idx in df.index:
        row_id = int(df.loc[idx, row_id_col]) if row_id_col else (idx + 1)
        row_vals = []
        is_valid = True
        reason = ""

        for f in features:
            val = df.loc[idx, f]
            if val is None or (isinstance(val, float) and np.isnan(val)) or pd.isna(val):
                is_valid = False
                reason = f"Missing value in feature '{f}'"
                break
            try:
                num = float(val)
                if not math.isfinite(num):
                    is_valid = False
                    reason = f"Non-finite numeric value in feature '{f}'"
                    break
                row_vals.append(num)
            except (ValueError, TypeError):
                is_valid = False
                reason = f"Non-numeric value in feature '{f}'"
                break

        if is_valid:
            valid_indices.append((idx, row_id, row_vals))
            matrix_rows.append(row_vals)
        else:
            res.excluded_records += 1
            res.excluded_details.append({
                "row_id": row_id,
                "reason": reason,
            })

    res.evaluated_records = len(valid_indices)

    # Minimum sample size requirement
    MIN_SAMPLES = 2
    if res.evaluated_records < MIN_SAMPLES:
        res.notes = (
            f"Insufficient valid complete-case samples ({res.evaluated_records} < {MIN_SAMPLES}) "
            f"to train Isolation Forest."
        )
        return res

    X = np.array(matrix_rows, dtype=float)

    # Fit Isolation Forest
    model = IsolationForest(
        n_estimators=cfg.iforest_n_estimators,
        contamination=cfg.iforest_contamination,
        random_state=cfg.iforest_random_state,
    )
    model.fit(X)

    predictions = model.predict(X)  # 1: inlier, -1: outlier
    decision_scores = model.decision_function(X)

    for i, (idx, row_id, row_vals) in enumerate(valid_indices):
        pred = int(predictions[i])
        score = float(decision_scores[i])
        is_anom = (pred == -1)

        feature_dict = {f: row_vals[j] for j, f in enumerate(features)}

        row_record = {
            "source_name": source_name,
            "row_id": row_id,
            "features": feature_dict,
            "prediction": pred,
            "decision_score": round(score, 4),
            "is_anomaly": is_anom,
        }
        res.evaluated_rows.append(row_record)

        if is_anom:
            res.anomalies.append(row_record)

    res.anomaly_count = len(res.anomalies)
    res.anomaly_percentage = (res.anomaly_count / res.evaluated_records * 100) if res.evaluated_records > 0 else 0.0

    return res
