# tests/test_data_quality.py

"""Tests for the data_quality_analyzer module."""

import pytest
import pandas as pd
from datetime import datetime, timedelta

from data_ingestion import ingest_file
from data_quality_analyzer import (
    QualityConfig, QualityResult, analyze_quality, enrich_issues_with_business_id
)


class TestCompleteness:
    """Test completeness metric calculation."""

    def test_completeness_all_present(self, synthetic_hospitals_b):
        """100% completeness when all required values are present."""
        datasets = ingest_file(synthetic_hospitals_b, source_name="B")
        ds = datasets[0]

        config = QualityConfig(
            required_columns=["HospitalID", "Name"],
        )
        result = analyze_quality(ds, config)
        assert result.completeness == 100.0
        assert result.missing_value_count == 0

    def test_completeness_with_missing(self, synthetic_hospitals_a):
        """Correct completeness when some required values are missing."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="A")
        ds = datasets[0]

        config = QualityConfig(
            required_columns=["Name", "Beds"],
        )
        result = analyze_quality(ds, config)
        # Row 3: empty Name. Row 7: missing Beds. -> 2 missing out of 20
        assert result.completeness == 90.0
        assert result.missing_value_count == 2

    def test_completeness_no_required_columns(self, synthetic_hospitals_a):
        """Completeness is N/A when no required columns configured."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="A")
        ds = datasets[0]

        config = QualityConfig(required_columns=[])
        result = analyze_quality(ds, config)
        assert result.completeness is None
        assert "No required columns" in result.completeness_explanation

    def test_completeness_missing_column(self, synthetic_hospitals_a):
        """Absent required columns count as missing expected cells (0% completeness)."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="A")
        ds = datasets[0]

        config = QualityConfig(required_columns=["NonExistentColumn"])
        result = analyze_quality(ds, config)
        assert result.completeness == 0.0
        assert result.missing_value_count == 10


class TestValidity:
    """Test validity metric calculation."""

    def test_validity_numeric(self, synthetic_hospitals_a):
        """Validity detects non-numeric values in numeric columns."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="A")
        ds = datasets[0]

        config = QualityConfig(
            validation_rules={
                "Beds": [{"type": "numeric"}],
            }
        )
        result = analyze_quality(ds, config)
        # Row 7 has None Beds, which is missing, not invalid.
        # All non-missing Beds values are numeric.
        assert result.validity == 100.0

    def test_validity_latitude(self, synthetic_hospitals_a):
        """Validity detects invalid latitude values."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="A")
        ds = datasets[0]

        config = QualityConfig(
            validation_rules={
                "Latitude": [{"type": "latitude"}],
            }
        )
        result = analyze_quality(ds, config)
        # Row 6 has latitude 999.0 (invalid)
        # 10 rows total, 10 have non-missing lat, 1 is invalid
        assert result.validity == 90.0
        assert result.invalid_record_count == 1

    def test_validity_longitude(self, synthetic_hospitals_b):
        """Validity passes for valid longitude values."""
        datasets = ingest_file(synthetic_hospitals_b, source_name="B")
        ds = datasets[0]

        config = QualityConfig(
            validation_rules={
                "Longitude": [{"type": "longitude"}],
            }
        )
        result = analyze_quality(ds, config)
        assert result.validity == 100.0

    def test_validity_range(self, synthetic_hospitals_a):
        """Validity detects out-of-range numeric values."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="A")
        ds = datasets[0]

        config = QualityConfig(
            validation_rules={
                "Beds": [{"type": "range", "min": 50, "max": 250}],
            }
        )
        result = analyze_quality(ds, config)
        # Row 6 has Beds=300, which exceeds max 250
        # 9 non-missing Beds values, 1 out of range
        assert abs(result.validity - (8 / 9 * 100)) < 0.1

    def test_validity_no_rules(self, synthetic_hospitals_a):
        """Validity is N/A when no rules configured."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="A")
        ds = datasets[0]

        config = QualityConfig(validation_rules={})
        result = analyze_quality(ds, config)
        assert result.validity is None
        assert "No validation rules" in result.validity_explanation

    def test_validity_invalid_coordinates(self, tmp_dir):
        """Validity correctly flags invalid geographic coordinates."""
        import os
        data = {
            "ID": ["1", "2", "3"],
            "Lat": [91.0, -91.0, 45.0],  # Two invalid
            "Lon": [72.0, 181.0, -180.0],  # One invalid
        }
        filepath = os.path.join(tmp_dir, "bad_coords.csv")
        pd.DataFrame(data).to_csv(filepath, index=False)

        datasets = ingest_file(filepath, source_name="Coords")
        ds = datasets[0]

        config = QualityConfig(
            validation_rules={
                "Lat": [{"type": "latitude"}],
                "Lon": [{"type": "longitude"}],
            }
        )
        result = analyze_quality(ds, config)
        # Lat: 2 invalid out of 3; Lon: 1 invalid out of 3; total checks=6, passing=3
        assert result.validity == 50.0


class TestUniqueness:
    """Test uniqueness metric calculation."""

    def test_uniqueness_with_duplicates(self, synthetic_hospitals_a):
        """Uniqueness detects duplicate identifiers."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="A")
        ds = datasets[0]

        config = QualityConfig(identifier_column="HospitalID")
        result = analyze_quality(ds, config)
        # 10 records, all have IDs, H102 appears twice -> 9 distinct / 10 usable
        assert result.uniqueness == 90.0
        assert result.duplicate_identifier_count == 1

    def test_uniqueness_no_duplicates(self, synthetic_hospitals_b):
        """Uniqueness is 100% when all identifiers are unique."""
        datasets = ingest_file(synthetic_hospitals_b, source_name="B")
        ds = datasets[0]

        config = QualityConfig(identifier_column="HospitalID")
        result = analyze_quality(ds, config)
        assert result.uniqueness == 100.0
        assert result.duplicate_identifier_count == 0

    def test_uniqueness_no_id_column(self, synthetic_hospitals_a):
        """Uniqueness is N/A when no identifier column configured."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="A")
        ds = datasets[0]

        config = QualityConfig(identifier_column=None)
        result = analyze_quality(ds, config)
        assert result.uniqueness is None
        assert "No identifier column" in result.uniqueness_explanation

    def test_uniqueness_missing_identifiers(self, tmp_dir):
        """Uniqueness excludes records with missing identifiers."""
        import os
        data = {
            "ID": ["A", "B", "A", None, ""],
            "Name": ["X1", "X2", "X3", "X4", "X5"],
        }
        filepath = os.path.join(tmp_dir, "missing_ids.csv")
        pd.DataFrame(data).to_csv(filepath, index=False)

        datasets = ingest_file(filepath, source_name="Missing IDs")
        ds = datasets[0]

        config = QualityConfig(identifier_column="ID")
        result = analyze_quality(ds, config)
        # Usable IDs: A, B, A = 3 usable, 2 distinct -> 66.7%
        assert abs(result.uniqueness - (2 / 3 * 100)) < 0.1
        # Should have issues for missing IDs and duplicate ID


class TestFreshness:
    """Test freshness metric calculation."""

    def test_freshness_calculation(self, synthetic_hospitals_a, reference_time):
        """Freshness correctly counts fresh vs stale records."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="A")
        ds = datasets[0]

        config = QualityConfig(
            timestamp_column="LastUpdated",
            freshness_threshold_days=30,
            reference_time=reference_time,
        )
        result = analyze_quality(ds, config)
        # Reference: 2026-11-24. Threshold: 30 days -> cutoff: 2026-10-25
        # Valid timestamps: rows 1-9 (row 10 is "not-a-date" = invalid)
        # Row 1: 2026-11-01 (fresh)
        # Row 2: 2026-11-10 (fresh)
        # Row 3: 2026-10-15 (stale - before cutoff)
        # Row 4: 2026-11-20 (fresh)
        # Row 5: 2026-11-10 (fresh)
        # Row 6: 2026-09-01 (stale)
        # Row 7: 2026-11-05 (fresh)
        # Row 8: 2027-01-01 (future - excluded from fresh count)
        # Row 9: 2025-01-01 (stale)
        # Valid: 9, Fresh: 5, Stale: 3, Future: 1
        assert result.freshness is not None
        assert abs(result.freshness - (5 / 9 * 100)) < 0.1
        assert result.stale_record_count == 3

    def test_freshness_timestamp_coverage(self, synthetic_hospitals_a, reference_time):
        """Timestamp coverage is correctly calculated."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="A")
        ds = datasets[0]

        config = QualityConfig(
            timestamp_column="LastUpdated",
            freshness_threshold_days=30,
            reference_time=reference_time,
        )
        result = analyze_quality(ds, config)
        # 9 valid timestamps out of 10 records = 90%
        assert result.timestamp_coverage == 90.0

    def test_freshness_no_timestamp(self, synthetic_hospitals_a):
        """Freshness is N/A when no timestamp column configured."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="A")
        ds = datasets[0]

        config = QualityConfig(timestamp_column=None)
        result = analyze_quality(ds, config)
        assert result.freshness is None
        assert result.timestamp_coverage is None

    def test_freshness_future_timestamps(self, synthetic_hospitals_a, reference_time):
        """Future timestamps are detected and reported."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="A")
        ds = datasets[0]

        config = QualityConfig(
            timestamp_column="LastUpdated",
            reference_time=reference_time,
        )
        result = analyze_quality(ds, config)
        future_issues = [i for i in result.issues
                         if i["issue_type"] == "Unexpected future timestamp"]
        assert len(future_issues) >= 1  # Row 8: 2027-01-01

    def test_freshness_invalid_timestamps(self, synthetic_hospitals_a, reference_time):
        """Invalid timestamps are detected and reported."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="A")
        ds = datasets[0]

        config = QualityConfig(
            timestamp_column="LastUpdated",
            reference_time=reference_time,
        )
        result = analyze_quality(ds, config)
        invalid_ts_issues = [i for i in result.issues
                             if i["issue_type"] == "Invalid timestamp"]
        assert len(invalid_ts_issues) >= 1  # Row 10: "not-a-date"

    def test_freshness_stale_records(self, synthetic_hospitals_a, reference_time):
        """Stale records are detected and reported."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="A")
        ds = datasets[0]

        config = QualityConfig(
            timestamp_column="LastUpdated",
            freshness_threshold_days=30,
            reference_time=reference_time,
        )
        result = analyze_quality(ds, config)
        stale_issues = [i for i in result.issues
                        if i["issue_type"] == "Stale record"]
        assert len(stale_issues) == 3


class TestIssueReport:
    """Test issue report generation."""

    def test_issues_traceable_to_rows(self, synthetic_hospitals_a, reference_time):
        """Each issue has a valid row_id traceable to the original data."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="A")
        ds = datasets[0]

        config = QualityConfig(
            required_columns=["Name", "Beds"],
            identifier_column="HospitalID",
            timestamp_column="LastUpdated",
            freshness_threshold_days=30,
            reference_time=reference_time,
            validation_rules={
                "Latitude": [{"type": "latitude"}],
            }
        )
        result = analyze_quality(ds, config)
        for issue in result.issues:
            assert "row_id" in issue
            assert isinstance(issue["row_id"], int)
            assert 1 <= issue["row_id"] <= len(ds.raw_df)

    def test_issue_types_comprehensive(self, synthetic_hospitals_a, reference_time):
        """Multiple issue types are generated from the synthetic dataset."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="A")
        ds = datasets[0]

        config = QualityConfig(
            required_columns=["Name", "Beds"],
            identifier_column="HospitalID",
            timestamp_column="LastUpdated",
            freshness_threshold_days=30,
            reference_time=reference_time,
            validation_rules={
                "Latitude": [{"type": "latitude"}],
            }
        )
        result = analyze_quality(ds, config)
        issue_types = {i["issue_type"] for i in result.issues}

        assert "Missing required value" in issue_types
        assert "Duplicate identifier" in issue_types or "Duplicate record" in issue_types
        assert "Invalid coordinate" in issue_types
        assert "Stale record" in issue_types
        assert "Invalid timestamp" in issue_types

    def test_enrich_issues_with_business_id(self, synthetic_hospitals_a, reference_time):
        """Business IDs are added to issues when identifier column is configured."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="A")
        ds = datasets[0]

        config = QualityConfig(
            required_columns=["Name"],
            identifier_column="HospitalID",
        )
        result = analyze_quality(ds, config)

        # Resolve the identifier column
        norm_cols = {c.lower(): c for c in ds.normalized_df.columns}
        resolved_id = norm_cols.get("hospitalid")
        enrich_issues_with_business_id(result, ds.normalized_df, resolved_id)

        # Check that at least some issues have business_id populated
        ids_with_bid = [i for i in result.issues if i.get("business_id")]
        assert len(ids_with_bid) > 0


class TestEmptyDataset:
    """Test handling of empty datasets."""

    def test_empty_dataset_quality(self, empty_csv):
        """Quality metrics handle empty datasets gracefully."""
        datasets = ingest_file(empty_csv, source_name="Empty")
        ds = datasets[0]

        config = QualityConfig(
            required_columns=["ID"],
            identifier_column="ID",
        )
        result = analyze_quality(ds, config)
        assert result.total_records == 0
        assert result.completeness is None
        assert result.validity is None
        assert result.uniqueness is None
        assert result.freshness is None
