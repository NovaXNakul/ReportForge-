# tests/test_audit_bugs.py

"""
Regression tests for Feature 1 Reliability & Correctness Audit (Bugs 1-10).
"""

import os
import math
from datetime import datetime, timezone

import pandas as pd
import pytest

from data_ingestion import ingest_file, IngestionError
from data_quality_analyzer import QualityConfig, analyze_quality
from source_comparator import ComparisonConfig, compare_sources


# ==============================================================================
# BUG 1: Invalid Jaccard Similarity
# ==============================================================================

class TestBug1JaccardSimilarity:
    def test_missing_ids_with_exact_and_fuzzy_never_negative(self, tmp_dir):
        """Reproduced Bug 1: Missing IDs + Alpha/Beta + X/Gamma must give valid Jaccard in [0, 1]."""
        p_a = os.path.join(tmp_dir, "a.csv")
        p_b = os.path.join(tmp_dir, "b.csv")
        df = pd.DataFrame({
            "id": [None, None, "X"],
            "name": ["Alpha", "Beta", "Gamma"],
        })
        df.to_csv(p_a, index=False)
        df.to_csv(p_b, index=False)

        ds_a = ingest_file(p_a, "A")[0]
        ds_b = ingest_file(p_b, "B")[0]

        cfg = ComparisonConfig(
            id_column_a="id", id_column_b="id",
            name_column_a="name", name_column_b="name",
            use_exact=True, use_fuzzy=True, fuzzy_threshold=80.0,
        )
        res = compare_sources(ds_a, ds_b, cfg)

        assert res.total_a == 3
        assert res.total_b == 3
        assert len(res.matched) == 3
        assert res.jaccard_similarity == 1.0
        assert 0.0 <= res.jaccard_similarity <= 1.0
        assert res.jaccard_is_estimate is True

    def test_duplicate_ids_do_not_inflate_jaccard(self, tmp_dir):
        """Duplicate IDs in one source must not inflate confirmed matches or entity totals."""
        p_a = os.path.join(tmp_dir, "a.csv")
        p_b = os.path.join(tmp_dir, "b.csv")
        pd.DataFrame({"id": ["H1", "H1", "H2"], "name": ["A", "A", "B"]}).to_csv(p_a, index=False)
        pd.DataFrame({"id": ["H1", "H2"], "name": ["A", "B"]}).to_csv(p_b, index=False)

        ds_a = ingest_file(p_a, "A")[0]
        ds_b = ingest_file(p_b, "B")[0]

        res = compare_sources(ds_a, ds_b, ComparisonConfig(
            id_column_a="id", id_column_b="id", use_exact=True
        ))
        assert res.total_a == 2
        assert res.total_b == 2
        assert len(res.matched) == 1  # Only H2; H1 is ambiguous
        assert len(res.matched) <= min(res.total_a, res.total_b)
        assert 0.0 <= res.jaccard_similarity <= 1.0
        assert res.jaccard_is_estimate is True

    def test_geo_only_candidates_do_not_inflate_jaccard(self, tmp_dir):
        """Proximity-only candidates cannot be counted as confirmed matches in Jaccard."""
        p_a = os.path.join(tmp_dir, "a.csv")
        p_b = os.path.join(tmp_dir, "b.csv")
        pd.DataFrame({"name": ["Alpha"], "lat": [19.0], "lon": [72.0]}).to_csv(p_a, index=False)
        pd.DataFrame({"name": ["Beta"], "lat": [19.0], "lon": [72.0]}).to_csv(p_b, index=False)

        ds_a = ingest_file(p_a, "A")[0]
        ds_b = ingest_file(p_b, "B")[0]

        res = compare_sources(ds_a, ds_b, ComparisonConfig(
            lat_column_a="lat", lon_column_a="lon",
            lat_column_b="lat", lon_column_b="lon",
            use_exact=False, use_fuzzy=False, use_geo=True, distance_threshold_m=500.0
        ))
        assert len(res.matched) == 0
        assert res.jaccard_similarity == 0.0
        assert res.jaccard_is_estimate is True

    def test_duplicate_id_vs_missing_id_cannot_exceed_100_percent(self, tmp_dir):
        """
        Reproduced Issue 1:
        Source A: (ID X, Alpha), (ID X, Beta)
        Source B: (Missing, Alpha), (Missing, Beta)
        With compatible_ids=True, use_exact=True, use_fuzzy=True:
        Duplicate ID X in A is ambiguous within A and must not match both B rows.
        """
        p_a = os.path.join(tmp_dir, "a.csv")
        p_b = os.path.join(tmp_dir, "b.csv")
        pd.DataFrame({"id": ["X", "X"], "name": ["Alpha", "Beta"]}).to_csv(p_a, index=False)
        pd.DataFrame({"id": [None, None], "name": ["Alpha", "Beta"]}).to_csv(p_b, index=False)

        ds_a = ingest_file(p_a, "A")[0]
        ds_b = ingest_file(p_b, "B")[0]

        res = compare_sources(ds_a, ds_b, ComparisonConfig(
            id_column_a="id", id_column_b="id",
            name_column_a="name", name_column_b="name",
            compatible_ids=True, use_exact=True, use_fuzzy=True, fuzzy_threshold=80.0
        ))
        assert res.total_a == 1
        assert res.total_b == 2
        assert len(res.matched) == 0
        assert len(res.matched) <= min(res.total_a, res.total_b)
        assert len(res.ambiguous) == 2
        assert 0.0 <= res.jaccard_similarity <= 1.0
        assert res.jaccard_similarity == 0.0

    def test_duplicate_id_handled_even_with_exact_disabled(self, tmp_dir):
        """Duplicate business keys within a source are blocked even when use_exact=False."""
        p_a = os.path.join(tmp_dir, "a.csv")
        p_b = os.path.join(tmp_dir, "b.csv")
        pd.DataFrame({"id": ["X", "X"], "name": ["Alpha", "Beta"]}).to_csv(p_a, index=False)
        pd.DataFrame({"id": [None, None], "name": ["Alpha", "Beta"]}).to_csv(p_b, index=False)

        ds_a = ingest_file(p_a, "A")[0]
        ds_b = ingest_file(p_b, "B")[0]

        res = compare_sources(ds_a, ds_b, ComparisonConfig(
            id_column_a="id", id_column_b="id",
            name_column_a="name", name_column_b="name",
            compatible_ids=True, use_exact=False, use_fuzzy=True, fuzzy_threshold=80.0
        ))
        assert len(res.matched) == 0
        assert len(res.ambiguous) == 2
        assert 0.0 <= res.jaccard_similarity <= 1.0

    def test_approximate_jaccard_always_labeled_estimate(self, tmp_dir):
        """
        Reproduced Issue 2:
        compatible_ids=False, use_exact=False, use_fuzzy=True with clean 1-to-1
        fuzzy match must still set jaccard_is_estimate=True.
        """
        p_a = os.path.join(tmp_dir, "a.csv")
        p_b = os.path.join(tmp_dir, "b.csv")
        pd.DataFrame({"id": ["A"], "name": ["Alpha"]}).to_csv(p_a, index=False)
        pd.DataFrame({"id": ["B"], "name": ["Alpha"]}).to_csv(p_b, index=False)

        ds_a = ingest_file(p_a, "A")[0]
        ds_b = ingest_file(p_b, "B")[0]

        res = compare_sources(ds_a, ds_b, ComparisonConfig(
            id_column_a="id", id_column_b="id",
            name_column_a="name", name_column_b="name",
            compatible_ids=False, use_exact=False, use_fuzzy=True, fuzzy_threshold=80.0
        ))
        assert len(res.matched) == 1
        assert res.jaccard_similarity == 1.0
        assert res.jaccard_is_estimate is True
        assert "estimate" in res.jaccard_explanation.lower()


# ==============================================================================
# BUG 2: Fuzzy Matching Overrides Conflicting IDs
# ==============================================================================

class TestBug2ConflictingIDs:
    def test_fuzzy_rejects_conflicting_compatible_ids(self, tmp_dir):
        """Reproduced Bug 2: ID A vs ID B/C with identical names must NOT match via fuzzy."""
        p_a = os.path.join(tmp_dir, "a.csv")
        p_b = os.path.join(tmp_dir, "b.csv")
        pd.DataFrame({"id": ["A"], "name": ["City Hospital"]}).to_csv(p_a, index=False)
        pd.DataFrame({"id": ["B", "C"], "name": ["City Hospital", "City Hospital"]}).to_csv(p_b, index=False)

        ds_a = ingest_file(p_a, "A")[0]
        ds_b = ingest_file(p_b, "B")[0]

        res = compare_sources(ds_a, ds_b, ComparisonConfig(
            id_column_a="id", id_column_b="id",
            name_column_a="name", name_column_b="name",
            use_exact=True, use_fuzzy=True, compatible_ids=True, fuzzy_threshold=80.0
        ))
        assert len(res.matched) == 0
        assert len(res.ambiguous) == 0
        assert len(res.exclusive_a) == 1
        assert len(res.exclusive_b) == 2

    def test_incompatible_ids_allows_fuzzy_fallback(self, tmp_dir):
        """When compatible_ids=False, fuzzy matching can match records with different source IDs."""
        p_a = os.path.join(tmp_dir, "a.csv")
        p_b = os.path.join(tmp_dir, "b.csv")
        pd.DataFrame({"id": ["SRC1_1"], "name": ["City Hospital"]}).to_csv(p_a, index=False)
        pd.DataFrame({"id": ["SRC2_99"], "name": ["City Hospital"]}).to_csv(p_b, index=False)

        ds_a = ingest_file(p_a, "A")[0]
        ds_b = ingest_file(p_b, "B")[0]

        res = compare_sources(ds_a, ds_b, ComparisonConfig(
            id_column_a="id", id_column_b="id",
            name_column_a="name", name_column_b="name",
            use_exact=False, use_fuzzy=True, compatible_ids=False, fuzzy_threshold=80.0
        ))
        assert len(res.matched) == 1

    def test_exact_duplicate_ambiguity_not_resolved_by_fuzzy(self, tmp_dir):
        """Records with exact-stage duplicate ambiguity must not be silently resolved by fuzzy."""
        p_a = os.path.join(tmp_dir, "a.csv")
        p_b = os.path.join(tmp_dir, "b.csv")
        pd.DataFrame({"id": ["H1", "H1"], "name": ["City Hospital", "Other Clinic"]}).to_csv(p_a, index=False)
        pd.DataFrame({"id": ["H1"], "name": ["City Hospital"]}).to_csv(p_b, index=False)

        ds_a = ingest_file(p_a, "A")[0]
        ds_b = ingest_file(p_b, "B")[0]

        res = compare_sources(ds_a, ds_b, ComparisonConfig(
            id_column_a="id", id_column_b="id",
            name_column_a="name", name_column_b="name",
            use_exact=True, use_fuzzy=True, compatible_ids=True, fuzzy_threshold=80.0
        ))
        assert len(res.matched) == 0
        assert len(res.ambiguous) == 2


# ==============================================================================
# BUG 3: Greedy Fuzzy Matching Accepts Ambiguous Candidates
# ==============================================================================

class TestBug3AmbiguousFuzzy:
    def test_near_tied_fuzzy_candidates_remain_unresolved(self, tmp_dir):
        """Reproduced Bug 3: A vs B1 (score ~95) and B2 (score ~94) must remain ambiguous."""
        p_a = os.path.join(tmp_dir, "a.csv")
        p_b = os.path.join(tmp_dir, "b.csv")
        pd.DataFrame({"name": ["Saint Mary General Hospital"]}).to_csv(p_a, index=False)
        pd.DataFrame({"name": [
            "Saint Mary General Hosp",
            "Saint Mary General Hospi"
        ]}).to_csv(p_b, index=False)

        ds_a = ingest_file(p_a, "A")[0]
        ds_b = ingest_file(p_b, "B")[0]

        res = compare_sources(ds_a, ds_b, ComparisonConfig(
            name_column_a="name", name_column_b="name",
            use_exact=False, use_fuzzy=True, fuzzy_threshold=80.0, fuzzy_margin=5.0
        ))
        assert len(res.matched) == 0
        assert len(res.ambiguous) == 2

    def test_tied_scores_and_reordered_inputs_deterministic(self, tmp_dir):
        """Tied scores on either side remain unresolved regardless of input row order."""
        p_a = os.path.join(tmp_dir, "a.csv")
        p_b1 = os.path.join(tmp_dir, "b1.csv")
        p_b2 = os.path.join(tmp_dir, "b2.csv")

        pd.DataFrame({"name": ["Alpha Clinic", "Unique Place"]}).to_csv(p_a, index=False)
        pd.DataFrame({"name": ["Alpha Clinic", "Alpha Clinic", "Unique Place"]}).to_csv(p_b1, index=False)
        pd.DataFrame({"name": ["Unique Place", "Alpha Clinic", "Alpha Clinic"]}).to_csv(p_b2, index=False)

        ds_a = ingest_file(p_a, "A")[0]
        ds_b1 = ingest_file(p_b1, "B1")[0]
        ds_b2 = ingest_file(p_b2, "B2")[0]

        cfg = ComparisonConfig(
            name_column_a="name", name_column_b="name",
            use_exact=False, use_fuzzy=True, fuzzy_threshold=80.0, fuzzy_margin=5.0
        )
        res1 = compare_sources(ds_a, ds_b1, cfg)
        res2 = compare_sources(ds_a, ds_b2, cfg)

        assert len(res1.matched) == 1
        assert len(res2.matched) == 1
        assert res1.matched[0]["id_a"] == "Unique Place"
        assert res2.matched[0]["id_a"] == "Unique Place"
        assert len(res1.ambiguous) == 2
        assert len(res2.ambiguous) == 2


# ==============================================================================
# BUG 4: Geographic Proximity Incorrectly Confirms Entity Identity
# ==============================================================================

class TestBug4GeoProximity:
    def test_geo_alone_never_confirms_identity(self, tmp_dir):
        """Reproduced Bug 4: Same coordinates with different names/IDs must NOT be confirmed."""
        p_a = os.path.join(tmp_dir, "a.csv")
        p_b = os.path.join(tmp_dir, "b.csv")
        pd.DataFrame({"id": ["A"], "name": ["Alpha"], "lat": [19.0], "lon": [72.0]}).to_csv(p_a, index=False)
        pd.DataFrame({"id": ["B"], "name": ["Beta"], "lat": [19.0], "lon": [72.0]}).to_csv(p_b, index=False)

        ds_a = ingest_file(p_a, "A")[0]
        ds_b = ingest_file(p_b, "B")[0]

        res = compare_sources(ds_a, ds_b, ComparisonConfig(
            lat_column_a="lat", lon_column_a="lon",
            lat_column_b="lat", lon_column_b="lon",
            use_exact=False, use_fuzzy=False, use_geo=True, distance_threshold_m=500.0
        ))
        assert len(res.matched) == 0
        assert len(res.potential_geo_matches) == 1

    def test_fuzzy_plus_geo_requires_both_signals(self, tmp_dir):
        """When both fuzzy and geo are enabled, far-apart same-name entities must NOT match."""
        p_a = os.path.join(tmp_dir, "a.csv")
        p_b = os.path.join(tmp_dir, "b.csv")
        pd.DataFrame({"name": ["City Hospital"], "lat": [19.0], "lon": [72.0]}).to_csv(p_a, index=False)
        pd.DataFrame({"name": ["City Hospital"], "lat": [28.6], "lon": [77.2]}).to_csv(p_b, index=False)

        ds_a = ingest_file(p_a, "A")[0]
        ds_b = ingest_file(p_b, "B")[0]

        res = compare_sources(ds_a, ds_b, ComparisonConfig(
            name_column_a="name", name_column_b="name",
            lat_column_a="lat", lon_column_a="lon",
            lat_column_b="lat", lon_column_b="lon",
            use_exact=False, use_fuzzy=True, use_geo=True,
            fuzzy_threshold=80.0, distance_threshold_m=500.0
        ))
        assert len(res.matched) == 0

    def test_invalid_distance_threshold_raises(self, tmp_dir):
        """Non-finite or negative distance thresholds raise ValueError."""
        p_a = os.path.join(tmp_dir, "a.csv")
        pd.DataFrame({"lat": [19.0], "lon": [72.0]}).to_csv(p_a, index=False)
        ds_a = ingest_file(p_a, "A")[0]
        with pytest.raises(ValueError):
            compare_sources(ds_a, ds_a, ComparisonConfig(
                use_exact=False, use_geo=True, distance_threshold_m=-10.0
            ))


# ==============================================================================
# BUG 5: Failed Normalization Treated as Missing Data
# ==============================================================================

class TestBug5NormalizationVsMissing:
    def test_failed_numeric_coercion_reduces_validity_not_completeness(self, tmp_dir):
        """Reproduced Bug 5: beds=[10, 'invalid'] with coerce_numeric=['beds']."""
        p = os.path.join(tmp_dir, "beds.csv")
        pd.DataFrame({"beds": ["10", "invalid"]}).to_csv(p, index=False)

        ds = ingest_file(
            p, "Test",
            normalize_config={"coerce_numeric": ["beds"]}
        )[0]
        qr = analyze_quality(ds, QualityConfig(
            required_columns=["beds"],
            validation_rules={"beds": [{"type": "numeric"}]},
        ))

        assert qr.completeness == 100.0
        assert qr.missing_value_count == 0
        assert qr.validity == 50.0
        assert qr.invalid_record_count == 1
        assert any(
            i["issue_type"] == "Invalid data type" and i["original_value"] == "invalid"
            for i in qr.issues
        )

    def test_failed_date_coercion_labeled_invalid_timestamp(self, tmp_dir):
        """Malformed timestamps after parse_dates must be labeled Invalid timestamp, not missing."""
        p = os.path.join(tmp_dir, "ts.csv")
        pd.DataFrame({"updated": ["2026-11-20", "bad-date"]}).to_csv(p, index=False)

        ds = ingest_file(p, "Test", normalize_config={"parse_dates": ["updated"]})[0]
        qr = analyze_quality(ds, QualityConfig(
            required_columns=["updated"],
            timestamp_column="updated",
            reference_time=datetime(2026, 11, 24),
        ))
        assert qr.completeness == 100.0
        assert qr.timestamp_coverage == 50.0
        assert any(
            i["issue_type"] == "Invalid timestamp" and i["original_value"] == "bad-date"
            for i in qr.issues
        )


# ==============================================================================
# BUG 6: Leading-Zero IDs Lost Through Default Ingestion
# ==============================================================================

class TestBug6LeadingZeroIDs:
    def test_csv_leading_zeros_preserved_without_identifier_columns_hint(self, tmp_dir):
        """Reproduced Bug 6: Streamlit path calls ingest_file without identifier_columns."""
        p = os.path.join(tmp_dir, "temp_upload_0.csv")
        with open(p, "w") as f:
            f.write("id,name\n00501,Alpha\n01001,Beta\n")

        # Simulate Streamlit call without identifier_columns, with original_filename
        ds = ingest_file(p, "Source 1", original_filename="zips.csv")[0]

        assert ds.filename == "zips.csv"
        assert ds.raw_df["id"].tolist() == ["00501", "01001"]
        assert ds.normalized_df["id"].tolist() == ["00501", "01001"]

    def test_xlsx_text_leading_zeros_preserved_without_hint(self, tmp_dir):
        """Text-stored leading-zero IDs in XLSX survive without identifier_columns hint."""
        p = os.path.join(tmp_dir, "zips.xlsx")
        pd.DataFrame({"id": ["00501", "01001"], "name": ["A", "B"]}).to_excel(p, index=False)

        ds = ingest_file(p, "Excel")[0]
        assert ds.raw_df["id"].tolist() == ["00501", "01001"]
        assert ds.normalized_df["id"].tolist() == ["00501", "01001"]


# ==============================================================================
# BUG 7: Missing Required Columns Silently Ignored
# ==============================================================================

class TestBug7MissingRequiredColumns:
    def test_absent_required_column_not_ignored(self, tmp_dir):
        """Reproduced Bug 7: dataset=['id'], required=['id', 'name'] -> Completeness 50%."""
        p = os.path.join(tmp_dir, "cols.csv")
        pd.DataFrame({"id": ["1", "2"]}).to_csv(p, index=False)

        ds = ingest_file(p, "Test")[0]
        qr = analyze_quality(ds, QualityConfig(required_columns=["id", "name"]))

        assert qr.completeness == 50.0
        assert qr.missing_value_count == 2
        assert any(i["issue_type"] == "Missing required column" and i["column"] == "name" for i in qr.issues)


# ==============================================================================
# BUG 8: Comparison Categories Overlap Incorrectly
# ==============================================================================

class TestBug8MutuallyExclusiveCategories:
    def test_every_row_in_exactly_one_category(self, tmp_dir):
        """matched + ambiguous + unmatchable + exclusive must partition all rows."""
        p_a = os.path.join(tmp_dir, "a.csv")
        p_b = os.path.join(tmp_dir, "b.csv")
        pd.DataFrame({
            "id": ["M1", "D1", "D1", None, "EX_A"],
            "name": ["Match", "Dup1", "Dup2", "NoID", "OnlyA"],
        }).to_csv(p_a, index=False)
        pd.DataFrame({
            "id": ["M1", "D1", "EX_B"],
            "name": ["Match", "DupB", "OnlyB"],
        }).to_csv(p_b, index=False)

        ds_a = ingest_file(p_a, "A")[0]
        ds_b = ingest_file(p_b, "B")[0]

        res = compare_sources(ds_a, ds_b, ComparisonConfig(
            id_column_a="id", id_column_b="id", use_exact=True, use_fuzzy=False
        ))

        matched_a = {m["row_id_a"] for m in res.matched}
        ambig_a = {a["row_id_a"] for a in res.ambiguous}
        unmatch_a = set(res.unmatchable_a["_original_row_id"].tolist())
        excl_a = set(res.exclusive_a["_original_row_id"].tolist())

        # Pairwise disjoint
        assert matched_a.isdisjoint(ambig_a)
        assert matched_a.isdisjoint(unmatch_a)
        assert matched_a.isdisjoint(excl_a)
        assert ambig_a.isdisjoint(unmatch_a)
        assert ambig_a.isdisjoint(excl_a)
        assert unmatch_a.isdisjoint(excl_a)

        # Complete cover
        assert matched_a | ambig_a | unmatch_a | excl_a == {1, 2, 3, 4, 5}


# ==============================================================================
# BUG 10: Unsupported XLS, Future Timestamps, Timezones, Collisions
# ==============================================================================

class TestBug10InputAndTimestampHandling:
    def test_xls_rejected_cleanly(self, tmp_dir):
        """Legacy .xls files are rejected with clear IngestionError."""
        p = os.path.join(tmp_dir, "legacy.xls")
        with open(p, "w") as f:
            f.write("dummy")
        with pytest.raises(IngestionError, match="Unsupported file format"):
            ingest_file(p, "Legacy")

    def test_future_timestamps_do_not_inflate_freshness(self, tmp_dir):
        """Future timestamps must NOT count as fresh."""
        p = os.path.join(tmp_dir, "future.csv")
        pd.DataFrame({"ts": ["2026-11-20", "2027-05-01"]}).to_csv(p, index=False)

        ds = ingest_file(p, "Future")[0]
        qr = analyze_quality(ds, QualityConfig(
            timestamp_column="ts",
            freshness_threshold_days=30,
            reference_time=datetime(2026, 11, 24),
        ))
        assert qr.freshness == 50.0  # 1 fresh out of 2 valid; future is NOT fresh
        assert any(i["issue_type"] == "Unexpected future timestamp" for i in qr.issues)

    def test_mixed_timezone_timestamps_handled(self, tmp_dir):
        """Mixed tz-aware and tz-naive timestamps compare cleanly without TypeError."""
        p = os.path.join(tmp_dir, "tz.csv")
        pd.DataFrame({"ts": ["2026-11-20T10:00:00Z", "2026-11-20 10:00:00"]}).to_csv(p, index=False)

        ds = ingest_file(p, "TZ", normalize_config={"parse_dates": ["ts"]})[0]
        qr = analyze_quality(ds, QualityConfig(
            timestamp_column="ts",
            freshness_threshold_days=30,
            reference_time=datetime(2026, 11, 24, tzinfo=timezone.utc),
        ))
        assert qr.freshness == 100.0
        assert qr.timestamp_coverage == 100.0

    def test_normalized_column_collision_disambiguated(self, tmp_dir):
        """Columns like 'Name' and ' name ' disambiguate cleanly with warning."""
        p = os.path.join(tmp_dir, "col_collide.csv")
        with open(p, "w") as f:
            f.write("Name, name \nAlpha,Beta\n")

        ds = ingest_file(p, "Collide")[0]
        assert len(ds.normalized_df.columns) == 3  # _original_row_id, name, name_2
        assert any("collision" in w.lower() for w in ds.ingestion_warnings)

    def test_reserved_column_collision_rejected(self, tmp_dir):
        """Reserved metadata column '_original_row_id' raises IngestionError."""
        p = os.path.join(tmp_dir, "reserved.csv")
        pd.DataFrame({"_original_row_id": [1], "name": ["A"]}).to_csv(p, index=False)
        with pytest.raises(IngestionError, match="Reserved metadata column"):
            ingest_file(p, "Reserved")
