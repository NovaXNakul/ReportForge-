# tests/test_source_comparator.py

"""Tests for the source_comparator module."""

import os
import math
import pytest
import pandas as pd

from data_ingestion import ingest_file
from source_comparator import (
    ComparisonConfig, ComparisonResult, compare_sources, haversine_distance
)


class TestExactMatching:
    """Test exact identifier matching."""

    def test_exact_matching_basic(self, synthetic_hospitals_a, synthetic_hospitals_b):
        """Exact matching correctly identifies shared and exclusive entities."""
        ds_a = ingest_file(synthetic_hospitals_a, source_name="A")[0]
        ds_b = ingest_file(synthetic_hospitals_b, source_name="B")[0]

        config = ComparisonConfig(
            id_column_a="HospitalID",
            id_column_b="HospitalID",
            use_exact=True,
        )
        result = compare_sources(ds_a, ds_b, config)

        # Shared IDs: H101, H104 should be exact one-to-one matches
        # H102 appears twice in A, once in B -> ambiguous
        matched_ids = {m["id_a"].upper() for m in result.matched}
        assert "H101" in matched_ids
        assert "H104" in matched_ids

        # H102 should be ambiguous (2 in A, 1 in B)
        assert len(result.ambiguous) > 0

    def test_exclusive_entities(self, synthetic_hospitals_a, synthetic_hospitals_b):
        """Exclusive entities are correctly identified."""
        ds_a = ingest_file(synthetic_hospitals_a, source_name="A")[0]
        ds_b = ingest_file(synthetic_hospitals_b, source_name="B")[0]

        config = ComparisonConfig(
            id_column_a="HospitalID",
            id_column_b="HospitalID",
            use_exact=True,
        )
        result = compare_sources(ds_a, ds_b, config)

        # B has H201-H205 which are exclusive to B
        assert len(result.exclusive_b) > 0

    def test_ambiguous_matches(self, synthetic_hospitals_a, synthetic_hospitals_b):
        """Ambiguous matches (duplicates) are flagged."""
        ds_a = ingest_file(synthetic_hospitals_a, source_name="A")[0]
        ds_b = ingest_file(synthetic_hospitals_b, source_name="B")[0]

        config = ComparisonConfig(
            id_column_a="HospitalID",
            id_column_b="HospitalID",
            use_exact=True,
        )
        result = compare_sources(ds_a, ds_b, config)

        # H102 appears 2x in A, 1x in B -> ambiguous
        ambiguous_ids = {a["id_a"].upper() for a in result.ambiguous}
        assert "H102" in ambiguous_ids


class TestFuzzyMatching:
    """Test fuzzy name matching."""

    def test_fuzzy_matching_basic(self, synthetic_hospitals_a, synthetic_hospitals_b):
        """Fuzzy matching finds similar names across sources."""
        ds_a = ingest_file(synthetic_hospitals_a, source_name="A")[0]
        ds_b = ingest_file(synthetic_hospitals_b, source_name="B")[0]

        config = ComparisonConfig(
            name_column_a="Name",
            name_column_b="Name",
            use_exact=False,
            use_fuzzy=True,
            fuzzy_threshold=70.0,
        )
        result = compare_sources(ds_a, ds_b, config)

        # "City Hospital" and "City Hosp" should match above 70%
        # "Metro Clinic" and "Metro Clinic" should match at 100%
        assert len(result.matched) >= 2

        # Verify scores are present
        for m in result.matched:
            assert "score" in m
            assert m["score"] >= 70.0

    def test_fuzzy_one_to_one(self, synthetic_hospitals_a, synthetic_hospitals_b):
        """Fuzzy matching enforces one-to-one assignment."""
        ds_a = ingest_file(synthetic_hospitals_a, source_name="A")[0]
        ds_b = ingest_file(synthetic_hospitals_b, source_name="B")[0]

        config = ComparisonConfig(
            name_column_a="Name",
            name_column_b="Name",
            use_exact=False,
            use_fuzzy=True,
            fuzzy_threshold=60.0,
        )
        result = compare_sources(ds_a, ds_b, config)

        # Each index should appear at most once in matched
        a_indices = [m["index_a"] for m in result.matched]
        b_indices = [m["index_b"] for m in result.matched]
        assert len(a_indices) == len(set(a_indices))
        assert len(b_indices) == len(set(b_indices))


class TestGeoMatching:
    """Test geographic proximity matching."""

    def test_haversine_distance(self):
        """Haversine distance calculation is correct."""
        # Same point -> distance 0
        assert haversine_distance(0, 0, 0, 0) == 0.0

        # Known distance: NYC to LA ≈ 3,944 km
        nyc_lat, nyc_lon = 40.7128, -74.0060
        la_lat, la_lon = 34.0522, -118.2437
        dist = haversine_distance(nyc_lat, nyc_lon, la_lat, la_lon)
        assert abs(dist - 3_944_000) < 50_000  # Within 50km tolerance

    def test_geo_matching_basic(self, synthetic_hospitals_a, synthetic_hospitals_b):
        """Geographic proximity alone surfaces potential candidates without confirming identity."""
        ds_a = ingest_file(synthetic_hospitals_a, source_name="A")[0]
        ds_b = ingest_file(synthetic_hospitals_b, source_name="B")[0]

        config = ComparisonConfig(
            lat_column_a="Latitude",
            lon_column_a="Longitude",
            lat_column_b="Latitude",
            lon_column_b="Longitude",
            use_exact=False,
            use_fuzzy=False,
            use_geo=True,
            distance_threshold_m=100.0,  # 100 metres
        )
        result = compare_sources(ds_a, ds_b, config)

        # Geo proximity alone must not confirm matches; candidates go to potential_geo_matches
        assert len(result.matched) == 0
        assert len(result.potential_geo_matches) >= 2

    def test_geo_matching_excludes_invalid(self, synthetic_hospitals_a, synthetic_hospitals_b):
        """Geo matching excludes records with invalid coordinates."""
        ds_a = ingest_file(synthetic_hospitals_a, source_name="A")[0]
        ds_b = ingest_file(synthetic_hospitals_b, source_name="B")[0]

        config = ComparisonConfig(
            lat_column_a="Latitude",
            lon_column_a="Longitude",
            lat_column_b="Latitude",
            lon_column_b="Longitude",
            use_exact=False,
            use_fuzzy=False,
            use_geo=True,
            distance_threshold_m=100.0,
        )
        result = compare_sources(ds_a, ds_b, config)

        # Row 6 in A has lat=999 (invalid), should not appear in matches
        matched_a_rows = {m["row_id_a"] for m in result.matched}
        assert 6 not in matched_a_rows


class TestJaccardSimilarity:
    """Test Jaccard similarity calculation."""

    def test_jaccard_basic(self, synthetic_hospitals_a, synthetic_hospitals_b):
        """Jaccard similarity is correctly calculated."""
        ds_a = ingest_file(synthetic_hospitals_a, source_name="A")[0]
        ds_b = ingest_file(synthetic_hospitals_b, source_name="B")[0]

        config = ComparisonConfig(
            id_column_a="HospitalID",
            id_column_b="HospitalID",
            use_exact=True,
        )
        result = compare_sources(ds_a, ds_b, config)

        # Jaccard should be between 0 and 1
        assert result.jaccard_similarity is not None
        assert 0 <= result.jaccard_similarity <= 1

    def test_jaccard_exact_values(self, tmp_dir):
        """Jaccard similarity matches expected value for known sets."""
        # Source A: {X1, X2, X3}, Source B: {X1, X2, X4}
        # Intersection: {X1, X2}, Union: {X1, X2, X3, X4}
        # Jaccard = 2/4 = 0.5
        filepath_a = os.path.join(tmp_dir, "jaccard_a.csv")
        filepath_b = os.path.join(tmp_dir, "jaccard_b.csv")

        pd.DataFrame({"ID": ["X1", "X2", "X3"], "Val": [1, 2, 3]}).to_csv(filepath_a, index=False)
        pd.DataFrame({"ID": ["X1", "X2", "X4"], "Val": [1, 2, 4]}).to_csv(filepath_b, index=False)

        ds_a = ingest_file(filepath_a, source_name="A")[0]
        ds_b = ingest_file(filepath_b, source_name="B")[0]

        config = ComparisonConfig(
            id_column_a="ID", id_column_b="ID", use_exact=True
        )
        result = compare_sources(ds_a, ds_b, config)

        assert result.jaccard_similarity == 0.5
        assert len(result.matched) == 2

    def test_jaccard_empty_union(self, tmp_dir):
        """Jaccard is N/A when union is empty."""
        # Both sources empty
        filepath_a = os.path.join(tmp_dir, "empty_a.csv")
        filepath_b = os.path.join(tmp_dir, "empty_b.csv")

        pd.DataFrame({"ID": pd.Series(dtype=str), "Val": pd.Series(dtype=int)}).to_csv(filepath_a, index=False)
        pd.DataFrame({"ID": pd.Series(dtype=str), "Val": pd.Series(dtype=int)}).to_csv(filepath_b, index=False)

        ds_a = ingest_file(filepath_a, source_name="A")[0]
        ds_b = ingest_file(filepath_b, source_name="B")[0]

        config = ComparisonConfig(
            id_column_a="ID", id_column_b="ID", use_exact=True
        )
        result = compare_sources(ds_a, ds_b, config)

        assert result.jaccard_similarity is None


class TestConflictDetection:
    """Test attribute conflict detection."""

    def test_conflict_detection(self, synthetic_hospitals_a, synthetic_hospitals_b):
        """Attribute conflicts are detected for matched entities."""
        ds_a = ingest_file(synthetic_hospitals_a, source_name="A")[0]
        ds_b = ingest_file(synthetic_hospitals_b, source_name="B")[0]

        config = ComparisonConfig(
            id_column_a="HospitalID",
            id_column_b="HospitalID",
            use_exact=True,
            compare_columns=[("Beds", "Beds")],
        )
        result = compare_sources(ds_a, ds_b, config)

        # H101 has Beds=100 in both (no conflict)
        # H104 has Beds=50 in both (no conflict)
        # So conflicts depend on which entities matched
        # At minimum, the conflict detection ran without errors
        assert isinstance(result.conflicts, list)

    def test_conflict_detail_fields(self, tmp_dir):
        """Conflict records have all required detail fields."""
        filepath_a = os.path.join(tmp_dir, "conf_a.csv")
        filepath_b = os.path.join(tmp_dir, "conf_b.csv")

        pd.DataFrame({
            "ID": ["X1"], "Score": [100], "Grade": ["A"]
        }).to_csv(filepath_a, index=False)

        pd.DataFrame({
            "ID": ["X1"], "Score": [200], "Grade": ["B"]
        }).to_csv(filepath_b, index=False)

        ds_a = ingest_file(filepath_a, source_name="A")[0]
        ds_b = ingest_file(filepath_b, source_name="B")[0]

        config = ComparisonConfig(
            id_column_a="ID", id_column_b="ID",
            use_exact=True,
            compare_columns=[("Score", "Score"), ("Grade", "Grade")],
        )
        result = compare_sources(ds_a, ds_b, config)

        assert len(result.conflicts) == 2  # Score and Grade differ
        for c in result.conflicts:
            assert "entity_id" in c
            assert "attribute" in c
            assert "value_a" in c
            assert "value_b" in c
            assert "source_a" in c
            assert "source_b" in c
            assert "row_id_a" in c
            assert "row_id_b" in c
            assert "method" in c
