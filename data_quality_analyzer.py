# data_quality_analyzer.py

"""
Data Quality Analyzer Module for ReportForge 2.0.

Computes four primary data quality metrics per dataset:
1. Completeness — percentage of non-missing required cells.
   Absent configured required columns are explicitly counted as missing
   expected cells (not silently omitted from the denominator).
2. Validity — percentage of values passing configured validation rules
   (including originally populated values that failed type normalization).
3. Uniqueness — ratio of distinct normalized business keys to total usable keys.
4. Freshness — percentage of records updated within a configurable threshold
   (future timestamps are excluded from fresh counts and reported as issues).

Missing values vs normalization failures:
- Completeness checks original value presence; an originally populated value
  that fails numeric/date normalization is NOT counted as missing.
- Validity evaluates populated values (including normalization failures) and
  excludes originally missing values so completeness and validity stay distinct.
- Infinite numeric values (inf, -inf) are treated as invalid.

Timezone policy:
- Both timestamps and reference_time are normalized to tz-naive UTC when
  tz-aware, or compared as naive timestamps otherwise.
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def normalize_business_key(value) -> str:
    """
    Canonical business-key normalization used consistently across
    uniqueness analysis, exact matching, and Jaccard entity counting.
    """
    return str(value).strip().lower()


class QualityConfig:
    """
    Configuration for data quality analysis on a single dataset.
    """

    def __init__(self,
                 required_columns: Optional[list] = None,
                 identifier_column: Optional[str] = None,
                 timestamp_column: Optional[str] = None,
                 freshness_threshold_days: int = 30,
                 reference_time: Optional[datetime] = None,
                 validation_rules: Optional[dict] = None):
        self.required_columns = required_columns or []
        self.identifier_column = identifier_column
        self.timestamp_column = timestamp_column
        self.freshness_threshold_days = freshness_threshold_days
        self.reference_time = reference_time or datetime.now()
        self.validation_rules = validation_rules or {}


class QualityResult:
    """
    Container for data quality analysis results.
    """

    def __init__(self):
        self.source_name = ""
        self.filename = ""
        self.sheet_name = None
        self.total_records = 0
        self.completeness = None
        self.validity = None
        self.uniqueness = None
        self.freshness = None
        self.timestamp_coverage = None
        self.missing_value_count = 0
        self.duplicate_identifier_count = 0
        self.invalid_record_count = 0
        self.stale_record_count = 0
        self.issues = []
        self.completeness_explanation = ""
        self.validity_explanation = ""
        self.uniqueness_explanation = ""
        self.freshness_explanation = ""

    def to_summary_dict(self):
        """Return a summary dictionary for dashboard display."""
        def _fmt(val, explanation):
            if val is None:
                return f"N/A ({explanation})"
            return f"{val:.1f}%"

        return {
            "source_name": self.source_name,
            "filename": self.filename,
            "sheet_name": self.sheet_name or "N/A",
            "total_records": self.total_records,
            "completeness": _fmt(self.completeness, self.completeness_explanation),
            "completeness_value": self.completeness,
            "validity": _fmt(self.validity, self.validity_explanation),
            "validity_value": self.validity,
            "uniqueness": _fmt(self.uniqueness, self.uniqueness_explanation),
            "uniqueness_value": self.uniqueness,
            "freshness": _fmt(self.freshness, self.freshness_explanation),
            "freshness_value": self.freshness,
            "timestamp_coverage": (
                f"{self.timestamp_coverage:.1f}%"
                if self.timestamp_coverage is not None else "N/A"
            ),
            "timestamp_coverage_value": self.timestamp_coverage,
            "missing_values": self.missing_value_count,
            "duplicate_identifiers": self.duplicate_identifier_count,
            "invalid_records": self.invalid_record_count,
            "stale_records": self.stale_record_count,
        }


def analyze_quality(dataset, config: QualityConfig) -> QualityResult:
    """
    Perform data quality analysis on an IngestedDataset.
    """
    result = QualityResult()
    result.source_name = dataset.source_name
    result.filename = dataset.filename
    result.sheet_name = dataset.sheet_name
    result.total_records = len(dataset.raw_df)

    norm_df = dataset.normalized_df
    raw_df = dataset.raw_df
    norm_failures = getattr(dataset, "normalization_failures", {}) or {}

    if result.total_records == 0:
        result.completeness_explanation = "No records in dataset"
        result.validity_explanation = "No records in dataset"
        result.uniqueness_explanation = "No records in dataset"
        result.freshness_explanation = "No records in dataset"
        return result

    norm_cols = {c.lower(): c for c in norm_df.columns if c != "_original_row_id"}

    # Resolve configured columns while preserving absent ones for explicit reporting
    resolved_required_map = {
        c: _resolve_column(c, norm_cols) for c in config.required_columns
    }
    resolved_id = _resolve_column(config.identifier_column, norm_cols)
    resolved_ts = _resolve_column(config.timestamp_column, norm_cols)

    resolved_rules = {}
    absent_rule_cols = []
    for col, rules in config.validation_rules.items():
        rc = _resolve_column(col, norm_cols)
        if rc:
            resolved_rules[rc] = rules
        else:
            absent_rule_cols.append(col)

    # === Completeness ===
    result.completeness, result.missing_value_count, result.completeness_explanation = \
        _compute_completeness(norm_df, raw_df, resolved_required_map, norm_failures, result)

    # === Validity ===
    result.validity, result.invalid_record_count, result.validity_explanation = \
        _compute_validity(norm_df, raw_df, resolved_rules, absent_rule_cols, norm_failures, result)

    # === Uniqueness ===
    result.uniqueness, result.duplicate_identifier_count, result.uniqueness_explanation = \
        _compute_uniqueness(norm_df, raw_df, config.identifier_column, resolved_id, result)

    # === Freshness ===
    result.freshness, result.stale_record_count, result.timestamp_coverage, \
        result.freshness_explanation = \
        _compute_freshness(norm_df, raw_df, config.timestamp_column, resolved_ts,
                           norm_failures, config, result)

    return result


def _resolve_column(col_name, norm_cols):
    """Resolve a single column name case-insensitively."""
    if col_name is None:
        return None
    key = col_name.strip().lower()
    return norm_cols.get(key)


def _is_missing(value):
    """Check if a value is considered missing (NaN, None, empty, whitespace-only)."""
    if value is None:
        return True
    if isinstance(value, float) and np.isnan(value):
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    try:
        if pd.isna(value):
            return True
    except (ValueError, TypeError):
        pass
    return False


def _compute_completeness(norm_df, raw_df, required_map, norm_failures, result):
    """
    Completeness = (Non-missing required cells / Total expected required cells) × 100

    - Absent required columns are NOT silently dropped from the denominator:
      all rows for an absent required column count as missing expected cells.
    - Originally populated values that failed normalization are NOT counted
      as missing (they are validity failures).
    """
    if not required_map:
        return None, 0, "No required columns configured"

    total_expected = len(norm_df) * len(required_map)
    if total_expected == 0:
        return None, 0, "Zero expected cells (no records or no columns)"

    missing_count = 0

    for orig_req_col, resolved_col in required_map.items():
        if resolved_col is None or resolved_col not in norm_df.columns:
            # Absent required column: every row is missing this required field
            missing_count += len(norm_df)
            result.issues.append({
                "source_name": result.source_name,
                "filename": result.filename,
                "sheet_name": result.sheet_name,
                "row_id": 1,
                "business_id": None,
                "column": orig_req_col,
                "issue_type": "Missing required column",
                "original_value": "",
                "explanation": (
                    f"Configured required column '{orig_req_col}' is absent from "
                    f"the dataset ({len(norm_df)} expected cells counted as missing)."
                ),
            })
            continue

        raw_col = _find_raw_column(resolved_col, raw_df.columns)
        for idx, row in norm_df.iterrows():
            val = row[resolved_col]
            # If the cell failed normalization, it was originally populated -> not missing
            if (idx, resolved_col) in norm_failures:
                continue
            if _is_missing(val):
                raw_row = raw_df.loc[idx]
                raw_val = raw_row[raw_col] if raw_col else val
                # Double-check raw_val wasn't populated before coercion
                if not _is_missing(raw_val):
                    continue
                missing_count += 1
                row_id = raw_row.get("_original_row_id", idx + 1)

                result.issues.append({
                    "source_name": result.source_name,
                    "filename": result.filename,
                    "sheet_name": result.sheet_name,
                    "row_id": int(row_id),
                    "business_id": None,
                    "column": resolved_col,
                    "issue_type": "Missing required value",
                    "original_value": _safe_str(raw_val),
                    "explanation": f"Required column '{resolved_col}' has a missing value.",
                })

    non_missing = total_expected - missing_count
    completeness = (non_missing / total_expected) * 100
    return completeness, missing_count, ""


def _compute_validity(norm_df, raw_df, validation_rules, absent_rule_cols, norm_failures, result):
    """
    Validity = (Passing applicable checks / Total applicable checks) × 100

    - Originally missing values are excluded from applicable checks.
    - Originally populated values that failed normalization count as failing
      applicable checks (even if no extra rule was configured, or once if a rule exists).
    """
    for acol in absent_rule_cols:
        result.issues.append({
            "source_name": result.source_name,
            "filename": result.filename,
            "sheet_name": result.sheet_name,
            "row_id": 1,
            "business_id": None,
            "column": acol,
            "issue_type": "Missing configured column",
            "original_value": "",
            "explanation": f"Validation-rule column '{acol}' does not exist in dataset.",
        })

    if not validation_rules and not norm_failures:
        if absent_rule_cols:
            return None, 0, f"Configured validation column(s) not found: {absent_rule_cols}"
        return None, 0, "No validation rules configured"

    total_checks = 0
    passing_checks = 0
    invalid_rows = set()
    checked_norm_failure_keys = set()

    for col, rules in validation_rules.items():
        if col not in norm_df.columns:
            continue

        raw_col = _find_raw_column(col, raw_df.columns)

        for rule_idx, rule in enumerate(rules):
            rule_type = rule.get("type", "")

            for idx, row in norm_df.iterrows():
                failure_info = norm_failures.get((idx, col))
                val = row[col]

                if failure_info is not None:
                    # Value was populated in raw data but failed normalization
                    if rule_idx == 0:
                        checked_norm_failure_keys.add((idx, col))
                    total_checks += 1
                    invalid_rows.add(idx)
                    raw_row = raw_df.loc[idx]
                    row_id = raw_row.get("_original_row_id", idx + 1)
                    raw_val = failure_info["raw_value"]
                    issue_type = (
                        "Invalid timestamp" if failure_info["type"] == "date"
                        else "Invalid data type"
                    )
                    result.issues.append({
                        "source_name": result.source_name,
                        "filename": result.filename,
                        "sheet_name": result.sheet_name,
                        "row_id": int(row_id),
                        "business_id": None,
                        "column": col,
                        "issue_type": issue_type,
                        "original_value": _safe_str(raw_val),
                        "explanation": (
                            f"Value '{raw_val}' in column '{col}' failed "
                            f"{failure_info['type']} normalization."
                        ),
                    })
                    continue

                if _is_missing(val):
                    continue

                total_checks += 1
                is_valid, explanation = _check_rule(val, rule_type, rule)

                if is_valid:
                    passing_checks += 1
                else:
                    invalid_rows.add(idx)
                    raw_row = raw_df.loc[idx]
                    raw_val = raw_row[raw_col] if raw_col else val
                    row_id = raw_row.get("_original_row_id", idx + 1)

                    result.issues.append({
                        "source_name": result.source_name,
                        "filename": result.filename,
                        "sheet_name": result.sheet_name,
                        "row_id": int(row_id),
                        "business_id": None,
                        "column": col,
                        "issue_type": _issue_type_for_rule(rule_type),
                        "original_value": _safe_str(raw_val),
                        "explanation": explanation,
                    })

    # Include any normalization failures on columns that had no explicit validation_rules
    for (idx, col), failure_info in norm_failures.items():
        if (idx, col) in checked_norm_failure_keys:
            continue
        if col not in norm_df.columns:
            continue
        # For columns with coerce_numeric/parse_dates but no explicit rule,
        # count all populated values in that column as applicable checks
        if col not in validation_rules:
            # We'll handle unruled coerced columns once below
            pass

    coerced_unruled_cols = {
        col for (_, col) in norm_failures.keys()
        if col not in validation_rules and col in norm_df.columns
    }
    for col in coerced_unruled_cols:
        for idx, row in norm_df.iterrows():
            failure_info = norm_failures.get((idx, col))
            if failure_info is not None:
                total_checks += 1
                invalid_rows.add(idx)
                raw_row = raw_df.loc[idx]
                row_id = raw_row.get("_original_row_id", idx + 1)
                raw_val = failure_info["raw_value"]
                issue_type = (
                    "Invalid timestamp" if failure_info["type"] == "date"
                    else "Invalid data type"
                )
                result.issues.append({
                    "source_name": result.source_name,
                    "filename": result.filename,
                    "sheet_name": result.sheet_name,
                    "row_id": int(row_id),
                    "business_id": None,
                    "column": col,
                    "issue_type": issue_type,
                    "original_value": _safe_str(raw_val),
                    "explanation": (
                        f"Value '{raw_val}' in column '{col}' failed "
                        f"{failure_info['type']} normalization."
                    ),
                })
            elif not _is_missing(row[col]):
                total_checks += 1
                passing_checks += 1

    if total_checks == 0:
        return None, 0, "No applicable validation checks (all values missing or no matching columns)"

    validity = (passing_checks / total_checks) * 100
    return validity, len(invalid_rows), ""


def _check_rule(val, rule_type, rule):
    """
    Check a single value against a validation rule.
    Rejects non-finite numeric values (NaN, inf, -inf).
    """
    if rule_type == "numeric":
        try:
            num_val = float(val)
            if not math.isfinite(num_val):
                return False, f"Value '{val}' is not a finite number."
            return True, ""
        except (ValueError, TypeError):
            return False, f"Value '{val}' is not a valid number."

    elif rule_type == "range":
        try:
            num_val = float(val)
            if not math.isfinite(num_val):
                return False, f"Value '{val}' is not finite."
        except (ValueError, TypeError):
            return False, f"Value '{val}' is not numeric (expected for range check)."
        min_val = rule.get("min")
        max_val = rule.get("max")
        if min_val is not None and num_val < min_val:
            return False, f"Value {num_val} is below minimum {min_val}."
        if max_val is not None and num_val > max_val:
            return False, f"Value {num_val} exceeds maximum {max_val}."
        return True, ""

    elif rule_type == "non_negative":
        try:
            num_val = float(val)
            if not math.isfinite(num_val):
                return False, f"Value '{val}' is not finite."
        except (ValueError, TypeError):
            return False, f"Value '{val}' is not numeric (expected non-negative)."
        if num_val < 0:
            return False, f"Value {num_val} is negative."
        return True, ""

    elif rule_type == "categorical":
        allowed = rule.get("values", [])
        val_lower = str(val).strip().lower()
        allowed_lower = [str(v).strip().lower() for v in allowed]
        if val_lower in allowed_lower:
            return True, ""
        return False, f"Value '{val}' is not in allowed values: {allowed}."

    elif rule_type == "date":
        if isinstance(val, (pd.Timestamp, datetime)):
            return True, ""
        try:
            parsed = pd.to_datetime(val)
            if pd.isna(parsed):
                return False, f"Value '{val}' is not a valid date."
            return True, ""
        except (ValueError, TypeError):
            return False, f"Value '{val}' is not a valid date."

    elif rule_type == "latitude":
        try:
            num_val = float(val)
            if not math.isfinite(num_val):
                return False, f"Latitude '{val}' is not finite."
        except (ValueError, TypeError):
            return False, f"Value '{val}' is not a valid latitude (must be numeric)."
        if num_val < -90 or num_val > 90:
            return False, f"Latitude {num_val} is outside valid range [-90, +90]."
        return True, ""

    elif rule_type == "longitude":
        try:
            num_val = float(val)
            if not math.isfinite(num_val):
                return False, f"Longitude '{val}' is not finite."
        except (ValueError, TypeError):
            return False, f"Value '{val}' is not a valid longitude (must be numeric)."
        if num_val < -180 or num_val > 180:
            return False, f"Longitude {num_val} is outside valid range [-180, +180]."
        return True, ""

    return True, ""


def _issue_type_for_rule(rule_type):
    """Map rule type to issue type string."""
    mapping = {
        "numeric": "Invalid data type",
        "range": "Invalid numeric range",
        "non_negative": "Invalid numeric range",
        "categorical": "Invalid data type",
        "date": "Invalid timestamp",
        "latitude": "Invalid coordinate",
        "longitude": "Invalid coordinate",
    }
    return mapping.get(rule_type, "Invalid data type")


def _compute_uniqueness(norm_df, raw_df, orig_id_col, id_column, result):
    """
    Uniqueness = (Distinct usable normalized keys / Total records with usable keys) × 100
    """
    if not orig_id_col:
        return None, 0, "No identifier column configured"

    if not id_column or id_column not in norm_df.columns:
        result.issues.append({
            "source_name": result.source_name,
            "filename": result.filename,
            "sheet_name": result.sheet_name,
            "row_id": 1,
            "business_id": None,
            "column": orig_id_col,
            "issue_type": "Missing configured column",
            "original_value": "",
            "explanation": f"Identifier column '{orig_id_col}' not found in dataset.",
        })
        return None, 0, f"Identifier column '{orig_id_col}' not found in dataset"

    id_values = norm_df[id_column]
    usable_mask = id_values.apply(lambda x: not _is_missing(x))

    # Report missing identifiers
    missing_mask = ~usable_mask
    for idx in norm_df[missing_mask].index:
        raw_row = raw_df.loc[idx]
        row_id = raw_row.get("_original_row_id", idx + 1)
        result.issues.append({
            "source_name": result.source_name,
            "filename": result.filename,
            "sheet_name": result.sheet_name,
            "row_id": int(row_id),
            "business_id": None,
            "column": id_column,
            "issue_type": "Missing identifier",
            "original_value": "",
            "explanation": f"Business identifier column '{id_column}' is missing.",
        })

    usable_count = int(usable_mask.sum())
    if usable_count == 0:
        return None, 0, "No records have usable identifiers"

    usable_keys = id_values[usable_mask].apply(normalize_business_key)
    distinct_count = int(usable_keys.nunique())
    duplicate_count = int(usable_count - distinct_count)

    if duplicate_count > 0:
        dup_keys = usable_keys[usable_keys.duplicated(keep=False)]
        dup_groups = dup_keys.groupby(dup_keys).apply(lambda x: list(x.index))

        for dup_key, indices in dup_groups.items():
            dup_rows = norm_df.loc[indices]
            compare_cols = [c for c in dup_rows.columns
                            if c not in ("_original_row_id", id_column)]
            has_conflicts = False
            if compare_cols:
                has_conflicts = not dup_rows[compare_cols].apply(
                    lambda col: col.nunique(dropna=False) == 1
                ).all()

            for i in indices:
                raw_row = raw_df.loc[i]
                row_id = raw_row.get("_original_row_id", i + 1)
                raw_id_val = str(norm_df.loc[i, id_column])

                issue_type = "Duplicate identifier"
                explanation = (
                    f"Identifier '{raw_id_val}' appears {len(indices)} times."
                )
                if has_conflicts:
                    issue_type = "Duplicate record"
                    explanation += " Duplicate rows have conflicting attribute values."

                result.issues.append({
                    "source_name": result.source_name,
                    "filename": result.filename,
                    "sheet_name": result.sheet_name,
                    "row_id": int(row_id),
                    "business_id": raw_id_val,
                    "column": id_column,
                    "issue_type": issue_type,
                    "original_value": raw_id_val,
                    "explanation": explanation,
                })

    uniqueness = (distinct_count / usable_count) * 100
    return uniqueness, duplicate_count, ""


def _to_naive_utc_timestamp(ts_val) -> pd.Timestamp:
    """Normalize a datetime/Timestamp to tz-naive UTC for safe comparison."""
    ts = pd.Timestamp(ts_val)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts


def _compute_freshness(norm_df, raw_df, orig_ts_col, ts_column, norm_failures, config, result):
    """
    Freshness = (Records updated within [cutoff, reference_time] / Records with valid timestamps) × 100
    Timestamp Coverage = (Records with valid timestamps / Total records) × 100

    - Future timestamps (> reference_time) are NOT counted as fresh and are reported as issues.
    - Originally populated values that fail timestamp parsing are reported as 'Invalid timestamp'.
    """
    if not orig_ts_col:
        return None, 0, None, "No timestamp column configured"

    if not ts_column or ts_column not in norm_df.columns:
        result.issues.append({
            "source_name": result.source_name,
            "filename": result.filename,
            "sheet_name": result.sheet_name,
            "row_id": 1,
            "business_id": None,
            "column": orig_ts_col,
            "issue_type": "Missing configured column",
            "original_value": "",
            "explanation": f"Timestamp column '{orig_ts_col}' not found in dataset.",
        })
        return None, 0, None, f"Timestamp column '{orig_ts_col}' not found in dataset"

    total = len(norm_df)
    ref_ts = _to_naive_utc_timestamp(config.reference_time)
    cutoff_ts = ref_ts - timedelta(days=config.freshness_threshold_days)

    raw_col = _find_raw_column(ts_column, raw_df.columns)

    # Parse timestamps element-wise to handle mixed tz-aware and tz-naive strings
    parsed_list = []
    for idx in norm_df.index:
        val = norm_df.loc[idx, ts_column]
        if (idx, ts_column) in norm_failures or _is_missing(val):
            parsed_list.append(pd.NaT)
            continue
        if isinstance(val, (pd.Timestamp, datetime)):
            parsed_list.append(_to_naive_utc_timestamp(val))
        else:
            try:
                ts = pd.to_datetime(val, dayfirst=False)
                if pd.isna(ts):
                    parsed_list.append(pd.NaT)
                else:
                    parsed_list.append(_to_naive_utc_timestamp(ts))
            except Exception:
                parsed_list.append(pd.NaT)

    ts_series = pd.Series(parsed_list, index=norm_df.index)
    valid_mask = ts_series.notna()

    # Report missing vs invalid timestamps using original raw values
    for idx in norm_df[~valid_mask].index:
        raw_row = raw_df.loc[idx]
        failure_info = norm_failures.get((idx, ts_column))
        raw_val = failure_info["raw_value"] if failure_info else (
            raw_row[raw_col] if raw_col else norm_df.loc[idx, ts_column]
        )
        row_id = raw_row.get("_original_row_id", idx + 1)

        if _is_missing(raw_val):
            issue_type = "Missing required value"
            explanation = f"Timestamp column '{ts_column}' has a missing value."
        else:
            issue_type = "Invalid timestamp"
            explanation = f"Value '{raw_val}' is not a valid timestamp."

        result.issues.append({
            "source_name": result.source_name,
            "filename": result.filename,
            "sheet_name": result.sheet_name,
            "row_id": int(row_id),
            "business_id": None,
            "column": ts_column,
            "issue_type": issue_type,
            "original_value": _safe_str(raw_val),
            "explanation": explanation,
        })

    valid_count = int(valid_mask.sum())
    ts_coverage = (valid_count / total) * 100 if total > 0 else None

    if valid_count == 0:
        return None, 0, ts_coverage, "No records have valid timestamps"

    valid_ts = ts_series[valid_mask]

    # Detect future timestamps (> reference_time)
    future_mask = valid_ts > ref_ts
    for idx in valid_ts[future_mask].index:
        raw_row = raw_df.loc[idx]
        raw_val = raw_row[raw_col] if raw_col else norm_df.loc[idx, ts_column]
        row_id = raw_row.get("_original_row_id", idx + 1)

        result.issues.append({
            "source_name": result.source_name,
            "filename": result.filename,
            "sheet_name": result.sheet_name,
            "row_id": int(row_id),
            "business_id": None,
            "column": ts_column,
            "issue_type": "Unexpected future timestamp",
            "original_value": _safe_str(raw_val),
            "explanation": f"Timestamp '{raw_val}' is in the future (reference: {config.reference_time}).",
        })

    # Fresh records must be within [cutoff_ts, ref_ts] — future timestamps do NOT inflate freshness
    fresh_mask = (valid_ts >= cutoff_ts) & (valid_ts <= ref_ts)
    fresh_count = int(fresh_mask.sum())

    stale_mask = valid_ts < cutoff_ts
    stale_count = int(stale_mask.sum())

    for idx in valid_ts[stale_mask].index:
        raw_row = raw_df.loc[idx]
        raw_val = raw_row[raw_col] if raw_col else norm_df.loc[idx, ts_column]
        row_id = raw_row.get("_original_row_id", idx + 1)

        result.issues.append({
            "source_name": result.source_name,
            "filename": result.filename,
            "sheet_name": result.sheet_name,
            "row_id": int(row_id),
            "business_id": None,
            "column": ts_column,
            "issue_type": "Stale record",
            "original_value": _safe_str(raw_val),
            "explanation": (
                f"Record last updated '{raw_val}', which is older than "
                f"{config.freshness_threshold_days} days from reference "
                f"time {config.reference_time}."
            ),
        })

    freshness = (fresh_count / valid_count) * 100
    return freshness, stale_count, ts_coverage, ""


def _find_raw_column(norm_col, raw_columns):
    """Find the matching raw column name for a normalized column name."""
    for rc in raw_columns:
        if rc == "_original_row_id":
            continue
        if str(rc).strip().lower() == norm_col.strip().lower():
            return rc
    return None


def _safe_str(val):
    """Safely convert a value to string for display."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    return str(val)


def enrich_issues_with_business_id(result: QualityResult, norm_df: pd.DataFrame,
                                    id_column: Optional[str]):
    """
    Post-processing: fill in business_id for each issue where available.
    """
    if not id_column or id_column not in norm_df.columns:
        return

    for issue in result.issues:
        row_idx = issue["row_id"] - 1
        if 0 <= row_idx < len(norm_df):
            bid = norm_df.iloc[row_idx].get(id_column)
            if not _is_missing(bid):
                issue["business_id"] = str(bid)
