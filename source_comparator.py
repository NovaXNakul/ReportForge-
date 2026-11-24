# source_comparator.py

"""
Multi-Source Comparison Module for ReportForge 2.0.

Supports pairwise comparison of datasets using:
1. Exact identifier matching — when sources share compatible business keys.
2. Fuzzy name matching — RapidFuzz token_sort_ratio with configurable
   similarity threshold and ambiguity margin (no greedy false confirmation).
3. Geographic proximity matching — Haversine distance in metres. Proximity
   alone never confirms entity identity; it either filters/combines with
   fuzzy name matching or surfaces unresolved proximity-only candidates.
4. Jaccard similarity — consistent unique-entity overlap estimation.
5. Attribute conflict detection — comparing matched entity attributes.

Entity Counting & Matching Eligibility Policy:
- When compatible identifiers are configured (compatible_ids=True and both
  id_column_a and id_column_b are provided):
  * Rows with usable IDs are grouped by canonical normalized business key
    (strip + lower) so duplicate rows do not inflate entity counts.
  * Conflicting trustworthy IDs (usable ID A != usable ID B) are NEVER
    overridden by fuzzy or geographic fallback matching.
  * Duplicate-key ambiguities from exact matching are never silently resolved
    by later stages.
  * Rows without usable IDs are unmatchable if fallback matching is disabled,
    or counted as record-level entities eligible for fallback matching if
    fallback matching (fuzzy) is enabled.
- Every original row in Source A and Source B is classified into exactly one
  mutually exclusive category: matched, ambiguous (including proximity-only
  unresolved candidates), unmatchable, or exclusive.
"""

import logging
import math
from typing import Optional

import pandas as pd
import numpy as np

from data_quality_analyzer import normalize_business_key

logger = logging.getLogger(__name__)

# Earth radius in metres for Haversine
EARTH_RADIUS_M = 6_371_000


class ComparisonConfig:
    """
    Configuration for pairwise source comparison.
    """

    def __init__(self,
                 id_column_a: Optional[str] = None,
                 id_column_b: Optional[str] = None,
                 name_column_a: Optional[str] = None,
                 name_column_b: Optional[str] = None,
                 lat_column_a: Optional[str] = None,
                 lon_column_a: Optional[str] = None,
                 lat_column_b: Optional[str] = None,
                 lon_column_b: Optional[str] = None,
                 fuzzy_threshold: float = 80.0,
                 fuzzy_margin: float = 5.0,
                 distance_threshold_m: float = 500.0,
                 compare_columns: Optional[list] = None,
                 use_exact: bool = True,
                 use_fuzzy: bool = False,
                 use_geo: bool = False,
                 compatible_ids: bool = True):
        self.id_column_a = id_column_a
        self.id_column_b = id_column_b
        self.name_column_a = name_column_a
        self.name_column_b = name_column_b
        self.lat_column_a = lat_column_a
        self.lon_column_a = lon_column_a
        self.lat_column_b = lat_column_b
        self.lon_column_b = lon_column_b
        self.fuzzy_threshold = fuzzy_threshold
        self.fuzzy_margin = fuzzy_margin
        self.distance_threshold_m = distance_threshold_m
        self.compare_columns = compare_columns or []
        self.use_exact = use_exact
        self.use_fuzzy = use_fuzzy
        self.use_geo = use_geo
        self.compatible_ids = compatible_ids


class ComparisonResult:
    """
    Container for pairwise comparison results.
    """

    def __init__(self):
        self.source_a_name = ""
        self.source_b_name = ""
        self.matched = []
        self.exclusive_a = pd.DataFrame()
        self.exclusive_b = pd.DataFrame()
        self.ambiguous = []
        self.potential_geo_matches = []
        self.unmatchable_a = pd.DataFrame()
        self.unmatchable_b = pd.DataFrame()
        self.jaccard_similarity = None
        self.jaccard_is_estimate = False
        self.jaccard_explanation = ""
        self.conflicts = []
        self.total_a = 0
        self.total_b = 0
        self.total_rows_a = 0
        self.total_rows_b = 0

    def to_summary_dict(self):
        """Return a summary dictionary for dashboard display."""
        return {
            "source_a": self.source_a_name,
            "source_b": self.source_b_name,
            "total_a": self.total_a,
            "total_b": self.total_b,
            "total_rows_a": self.total_rows_a,
            "total_rows_b": self.total_rows_b,
            "matched_count": len(self.matched),
            "exclusive_a_count": len(self.exclusive_a),
            "exclusive_b_count": len(self.exclusive_b),
            "ambiguous_count": len(self.ambiguous),
            "potential_geo_count": len(self.potential_geo_matches),
            "unmatchable_a_count": len(self.unmatchable_a),
            "unmatchable_b_count": len(self.unmatchable_b),
            "jaccard_similarity": self.jaccard_similarity,
            "jaccard_is_estimate": self.jaccard_is_estimate,
            "jaccard_explanation": self.jaccard_explanation,
            "conflict_count": len(self.conflicts),
        }


def compare_sources(dataset_a, dataset_b, config: ComparisonConfig) -> ComparisonResult:
    """
    Perform pairwise comparison of two IngestedDataset objects.
    """
    if config.distance_threshold_m is not None:
        if not math.isfinite(config.distance_threshold_m) or config.distance_threshold_m < 0:
            raise ValueError(
                f"distance_threshold_m must be a finite non-negative number, got {config.distance_threshold_m}"
            )
    if not math.isfinite(config.fuzzy_threshold) or not (0 <= config.fuzzy_threshold <= 100):
        raise ValueError(
            f"fuzzy_threshold must be between 0 and 100, got {config.fuzzy_threshold}"
        )
    if not math.isfinite(config.fuzzy_margin) or config.fuzzy_margin < 0:
        raise ValueError(
            f"fuzzy_margin must be a finite non-negative number, got {config.fuzzy_margin}"
        )

    result = ComparisonResult()
    result.source_a_name = dataset_a.source_name
    result.source_b_name = dataset_b.source_name

    norm_a = dataset_a.normalized_df
    norm_b = dataset_b.normalized_df
    raw_a = dataset_a.raw_df
    raw_b = dataset_b.raw_df

    result.total_rows_a = len(norm_a)
    result.total_rows_b = len(norm_b)

    cols_a = {c.lower(): c for c in norm_a.columns if c != "_original_row_id"}
    cols_b = {c.lower(): c for c in norm_b.columns if c != "_original_row_id"}

    id_col_a = _resolve(config.id_column_a, cols_a)
    id_col_b = _resolve(config.id_column_b, cols_b)
    has_compatible_ids = bool(config.compatible_ids and id_col_a and id_col_b)

    name_col_a = _resolve(config.name_column_a, cols_a)
    name_col_b = _resolve(config.name_column_b, cols_b)
    lat_a = _resolve(config.lat_column_a, cols_a)
    lon_a = _resolve(config.lon_column_a, cols_a)
    lat_b = _resolve(config.lat_column_b, cols_b)
    lon_b = _resolve(config.lon_column_b, cols_b)

    matched_a_indices = set()
    matched_b_indices = set()
    ambiguous_a_indices = set()
    ambiguous_b_indices = set()
    all_matches = []
    all_ambiguous = []
    potential_geo = []

    # === Stage 1: Exact ID Matching ===
    if config.use_exact and has_compatible_ids:
        exact_matches, exact_ambiguous, ex_a_used, ex_b_used, ex_amb_a, ex_amb_b = \
            _exact_match(norm_a, norm_b, raw_a, raw_b, id_col_a, id_col_b,
                         dataset_a.source_name, dataset_b.source_name)
        all_matches.extend(exact_matches)
        all_ambiguous.extend(exact_ambiguous)
        matched_a_indices.update(ex_a_used)
        matched_b_indices.update(ex_b_used)
        ambiguous_a_indices.update(ex_amb_a)
        ambiguous_b_indices.update(ex_amb_b)

    # Detect within-source duplicate business keys independently (even if unshared or use_exact=False)
    # so multiple rows for one counted entity can never produce >1 confirmed match.
    if has_compatible_ids:
        dup_amb_a, dup_idx_a = _detect_within_source_duplicates(
            norm_a, raw_a, id_col_a, dataset_a.source_name,
            already_ambiguous=ambiguous_a_indices, is_source_a=True
        )
        dup_amb_b, dup_idx_b = _detect_within_source_duplicates(
            norm_b, raw_b, id_col_b, dataset_b.source_name,
            already_ambiguous=ambiguous_b_indices, is_source_a=False
        )
        all_ambiguous.extend(dup_amb_a)
        all_ambiguous.extend(dup_amb_b)
        ambiguous_a_indices.update(dup_idx_a)
        ambiguous_b_indices.update(dup_idx_b)

    # Eligible indices for approximate stages exclude matched and duplicate-ambiguous records
    ineligible_a = matched_a_indices | ambiguous_a_indices
    ineligible_b = matched_b_indices | ambiguous_b_indices

    # === Stage 2: Approximate Matching (Fuzzy Name and/or Geo Proximity) ===
    geo_configured = bool(config.use_geo and lat_a and lon_a and lat_b and lon_b)
    fuzzy_configured = bool(config.use_fuzzy and name_col_a and name_col_b)

    if fuzzy_configured:
        rem_a = norm_a[~norm_a.index.isin(ineligible_a)]
        rem_b = norm_b[~norm_b.index.isin(ineligible_b)]

        fuzzy_matches, fuzzy_ambiguous, f_a_used, f_b_used, f_amb_a, f_amb_b, geo_only_cands = \
            _fuzzy_match(
                rem_a, rem_b, raw_a, raw_b,
                name_col_a, name_col_b,
                config.fuzzy_threshold, config.fuzzy_margin,
                dataset_a.source_name, dataset_b.source_name,
                id_col_a=id_col_a if has_compatible_ids else None,
                id_col_b=id_col_b if has_compatible_ids else None,
                require_geo=geo_configured,
                lat_a=lat_a, lon_a=lon_a, lat_b=lat_b, lon_b=lon_b,
                distance_threshold_m=config.distance_threshold_m,
            )
        all_matches.extend(fuzzy_matches)
        all_ambiguous.extend(fuzzy_ambiguous)
        potential_geo.extend(geo_only_cands)
        matched_a_indices.update(f_a_used)
        matched_b_indices.update(f_b_used)
        ambiguous_a_indices.update(f_amb_a)
        ambiguous_b_indices.update(f_amb_b)

    elif geo_configured:
        # Geo proximity alone: NEVER confirms identity; surfaces unresolved proximity candidates
        rem_a = norm_a[~norm_a.index.isin(ineligible_a)]
        rem_b = norm_b[~norm_b.index.isin(ineligible_b)]

        geo_cands, g_amb_a, g_amb_b = _geo_proximity_candidates(
            rem_a, rem_b, raw_a, raw_b,
            lat_a, lon_a, lat_b, lon_b,
            config.distance_threshold_m,
            dataset_a.source_name, dataset_b.source_name,
            id_col_a=id_col_a if has_compatible_ids else None,
            id_col_b=id_col_b if has_compatible_ids else None,
        )
        potential_geo.extend(geo_cands)
        all_ambiguous.extend(geo_cands)
        ambiguous_a_indices.update(g_amb_a)
        ambiguous_b_indices.update(g_amb_b)

    # Ensure ambiguous sets do not overlap with matched sets
    ambiguous_a_indices -= matched_a_indices
    ambiguous_b_indices -= matched_b_indices

    # Deterministic ordering
    all_matches.sort(key=lambda m: (m["row_id_a"] or 0, m["row_id_b"] or 0))
    all_ambiguous.sort(key=lambda m: (m["row_id_a"] or 0, m["row_id_b"] or 0))
    potential_geo.sort(key=lambda m: (m["row_id_a"] or 0, m["row_id_b"] or 0))

    result.matched = all_matches
    result.ambiguous = all_ambiguous
    result.potential_geo_matches = potential_geo

    # === Stage 3: Mutually Exclusive Classification of Remaining Rows ===
    resolved_or_ambig_a = matched_a_indices | ambiguous_a_indices
    resolved_or_ambig_b = matched_b_indices | ambiguous_b_indices

    unmatchable_a_indices = _find_unmatchable_indices(
        norm_a, resolved_or_ambig_a,
        use_exact=bool(config.use_exact and has_compatible_ids),
        id_col=id_col_a,
        use_fuzzy=fuzzy_configured,
        name_col=name_col_a,
        use_geo=geo_configured,
        lat_col=lat_a, lon_col=lon_a,
    )
    unmatchable_b_indices = _find_unmatchable_indices(
        norm_b, resolved_or_ambig_b,
        use_exact=bool(config.use_exact and has_compatible_ids),
        id_col=id_col_b,
        use_fuzzy=fuzzy_configured,
        name_col=name_col_b,
        use_geo=geo_configured,
        lat_col=lat_b, lon_col=lon_b,
    )

    exclusive_a_indices = set(norm_a.index) - resolved_or_ambig_a - unmatchable_a_indices
    exclusive_b_indices = set(norm_b.index) - resolved_or_ambig_b - unmatchable_b_indices

    result.unmatchable_a = raw_a.loc[sorted(unmatchable_a_indices)].copy()
    result.unmatchable_b = raw_b.loc[sorted(unmatchable_b_indices)].copy()
    result.exclusive_a = raw_a.loc[sorted(exclusive_a_indices)].copy()
    result.exclusive_b = raw_b.loc[sorted(exclusive_b_indices)].copy()

    # === Stage 4: Consistent Entity Counting & Jaccard Similarity ===
    result.total_a, fallback_a_count = _count_entities(
        norm_a, id_col_a if has_compatible_ids else None,
        fuzzy_configured=fuzzy_configured,
        unmatchable_indices=unmatchable_a_indices,
    )
    result.total_b, fallback_b_count = _count_entities(
        norm_b, id_col_b if has_compatible_ids else None,
        fuzzy_configured=fuzzy_configured,
        unmatchable_indices=unmatchable_b_indices,
    )

    approximate_used = bool(
        fuzzy_configured or geo_configured
        or any(m.get("method") != "exact_id" for m in result.matched)
    )
    record_level_counting = bool(not has_compatible_ids)

    result.jaccard_similarity, result.jaccard_is_estimate, result.jaccard_explanation = \
        _compute_jaccard(
            result,
            fallback_count=fallback_a_count + fallback_b_count,
            approximate_used=approximate_used,
            record_level_counting=record_level_counting,
        )

    # === Stage 5: Attribute Conflict Detection ===
    if config.compare_columns:
        result.conflicts = _detect_conflicts(
            all_matches, norm_a, norm_b, raw_a, raw_b,
            config.compare_columns, cols_a, cols_b,
            dataset_a.source_name, dataset_b.source_name
        )

    return result


def _count_entities(norm_df, id_col, fuzzy_configured, unmatchable_indices):
    """
    Consistent entity counting policy:
    - If a compatible ID column is active:
      * Rows with usable IDs contribute 1 entity per distinct normalized key.
      * Rows without usable IDs are counted as 1 entity per row only if
        fallback matching (fuzzy) is enabled; otherwise they are unmatchable
        and excluded from matchable entity totals.
    - If no compatible ID column is active:
      * Each matchable row (not in unmatchable_indices) counts as 1 entity.
    """
    if norm_df.empty:
        return 0, 0

    if id_col and id_col in norm_df.columns:
        usable_mask = norm_df[id_col].apply(lambda x: not _is_missing(x))
        usable_keys = norm_df.loc[usable_mask, id_col].apply(normalize_business_key)
        distinct_id_entities = int(usable_keys.nunique())

        missing_id_indices = set(norm_df.index[~usable_mask])
        if fuzzy_configured:
            eligible_missing = missing_id_indices - unmatchable_indices
            return distinct_id_entities + len(eligible_missing), len(eligible_missing)
        return distinct_id_entities, 0

    matchable_rows = len(norm_df) - len(unmatchable_indices)
    return max(0, matchable_rows), 0


def _find_unmatchable_indices(norm_df, excluded_indices, use_exact, id_col,
                              use_fuzzy, name_col, use_geo, lat_col, lon_col):
    """
    Identify rows that cannot participate in ANY enabled matching stage.
    """
    unmatchable = set()
    for idx, row in norm_df.iterrows():
        if idx in excluded_indices:
            continue

        can_exact = use_exact and id_col and not _is_missing(row.get(id_col))
        can_name = use_fuzzy and name_col and not _is_missing(row.get(name_col))
        can_geo = False
        if use_geo and lat_col and lon_col:
            lat_v = _safe_finite_float(row.get(lat_col))
            lon_v = _safe_finite_float(row.get(lon_col))
            if lat_v is not None and lon_v is not None and -90 <= lat_v <= 90 and -180 <= lon_v <= 180:
                can_geo = True

        if use_fuzzy and use_geo:
            can_approx = can_name and can_geo
        elif use_fuzzy:
            can_approx = can_name
        elif use_geo:
            can_approx = can_geo
        else:
            can_approx = False

        if not (can_exact or can_approx):
            unmatchable.add(idx)

    return unmatchable


def _resolve(col_name, norm_cols):
    """Resolve column name case-insensitively."""
    if not col_name:
        return None
    return norm_cols.get(col_name.strip().lower())


def _is_missing(val):
    """Check if a value is missing."""
    if val is None:
        return True
    if isinstance(val, float) and np.isnan(val):
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    try:
        if pd.isna(val):
            return True
    except (ValueError, TypeError):
        pass
    return False


def _ids_conflict(norm_a, norm_b, a_idx, b_idx, id_col_a, id_col_b) -> bool:
    """
    Return True if both records have usable, compatible IDs that differ.
    """
    if not id_col_a or not id_col_b:
        return False
    val_a = norm_a.loc[a_idx, id_col_a]
    val_b = norm_b.loc[b_idx, id_col_b]
    if _is_missing(val_a) or _is_missing(val_b):
        return False
    return normalize_business_key(val_a) != normalize_business_key(val_b)


def _detect_within_source_duplicates(norm_df, raw_df, id_col, source_name,
                                     already_ambiguous, is_source_a=True):
    """
    Detect duplicate business keys within a single source independently of
    whether the key exists in the other source. Prevents multiple rows for
    the same counted entity from generating multiple confirmed matches.
    """
    ambiguous = []
    dup_indices = set()

    if norm_df.empty or not id_col or id_col not in norm_df.columns:
        return ambiguous, dup_indices

    usable_mask = norm_df[id_col].apply(lambda x: not _is_missing(x))
    if not usable_mask.any():
        return ambiguous, dup_indices

    id_series = norm_df.loc[usable_mask, id_col].apply(normalize_business_key)
    groups = id_series.groupby(id_series).apply(lambda s: list(s.index)).to_dict()

    for key, indices in sorted(groups.items()):
        if len(indices) <= 1:
            continue
        for idx in indices:
            dup_indices.add(idx)
            if idx in already_ambiguous:
                continue
            row_id = int(raw_df.loc[idx, "_original_row_id"])
            raw_id = str(norm_df.loc[idx, id_col])
            ambiguous.append({
                "id_a": raw_id if is_source_a else None,
                "id_b": None if is_source_a else raw_id,
                "row_id_a": row_id if is_source_a else None,
                "row_id_b": None if is_source_a else row_id,
                "index_a": idx if is_source_a else None,
                "index_b": None if is_source_a else idx,
                "method": "duplicate_id",
                "score": 100.0,
                "reason": (
                    f"Duplicate business key '{key}' within {source_name} "
                    f"({len(indices)} rows for 1 entity); unresolved."
                ),
                "source_a": source_name if is_source_a else "",
                "source_b": "" if is_source_a else source_name,
            })

    return ambiguous, dup_indices


def _exact_match(norm_a, norm_b, raw_a, raw_b, id_col_a, id_col_b,
                 source_a_name, source_b_name):
    """
    Exact identifier matching using canonical normalized business keys.
    Returns: (matches, ambiguous, a_used, b_used, amb_a, amb_b)
    """
    matches = []
    ambiguous = []
    a_used = set()
    b_used = set()
    amb_a = set()
    amb_b = set()

    if norm_a.empty or norm_b.empty:
        return matches, ambiguous, a_used, b_used, amb_a, amb_b

    a_ids = norm_a[[id_col_a]].copy()
    a_ids["_idx_a"] = norm_a.index
    a_ids = a_ids[a_ids[id_col_a].apply(lambda x: not _is_missing(x))]

    b_ids = norm_b[[id_col_b]].copy()
    b_ids["_idx_b"] = norm_b.index
    b_ids = b_ids[b_ids[id_col_b].apply(lambda x: not _is_missing(x))]

    if a_ids.empty or b_ids.empty:
        return matches, ambiguous, a_used, b_used, amb_a, amb_b

    a_ids["_match_key"] = a_ids[id_col_a].apply(normalize_business_key)
    b_ids["_match_key"] = b_ids[id_col_b].apply(normalize_business_key)

    a_groups = a_ids.groupby("_match_key")["_idx_a"].apply(list).to_dict()
    b_groups = b_ids.groupby("_match_key")["_idx_b"].apply(list).to_dict()

    shared_keys = sorted(set(a_groups.keys()) & set(b_groups.keys()))

    for key in shared_keys:
        a_indices = a_groups[key]
        b_indices = b_groups[key]

        if len(a_indices) == 1 and len(b_indices) == 1:
            a_idx = a_indices[0]
            b_idx = b_indices[0]
            matches.append({
                "id_a": str(norm_a.loc[a_idx, id_col_a]),
                "id_b": str(norm_b.loc[b_idx, id_col_b]),
                "row_id_a": int(raw_a.loc[a_idx, "_original_row_id"]),
                "row_id_b": int(raw_b.loc[b_idx, "_original_row_id"]),
                "index_a": a_idx,
                "index_b": b_idx,
                "method": "exact_id",
                "score": 100.0,
                "source_a": source_a_name,
                "source_b": source_b_name,
            })
            a_used.add(a_idx)
            b_used.add(b_idx)
        else:
            for a_idx in a_indices:
                amb_a.add(a_idx)
                for b_idx in b_indices:
                    amb_b.add(b_idx)
                    ambiguous.append({
                        "id_a": str(norm_a.loc[a_idx, id_col_a]),
                        "id_b": str(norm_b.loc[b_idx, id_col_b]),
                        "row_id_a": int(raw_a.loc[a_idx, "_original_row_id"]),
                        "row_id_b": int(raw_b.loc[b_idx, "_original_row_id"]),
                        "index_a": a_idx,
                        "index_b": b_idx,
                        "method": "exact_id",
                        "score": 100.0,
                        "reason": (
                            f"Identifier '{key}' has {len(a_indices)} "
                            f"occurrences in Source A and {len(b_indices)} "
                            f"in Source B (many-to-many)."
                        ),
                        "source_a": source_a_name,
                        "source_b": source_b_name,
                    })

    return matches, ambiguous, a_used, b_used, amb_a, amb_b


def _fuzzy_match(norm_a, norm_b, raw_a, raw_b, name_col_a, name_col_b,
                 threshold, margin, source_a_name, source_b_name,
                 id_col_a=None, id_col_b=None,
                 require_geo=False, lat_a=None, lon_a=None,
                 lat_b=None, lon_b=None, distance_threshold_m=500.0):
    """
    Ambiguity-aware fuzzy name matching (optionally combined with geo proximity).

    - Rejects pairs with conflicting trustworthy IDs.
    - If require_geo=True, a pair can only be confirmed if it ALSO satisfies
      distance_m <= distance_threshold_m; nearby pairs that fail fuzzy_threshold
      are reported separately as potential_geo_matches.
    - Ambiguity resolution: A match (a_idx, b_idx) is confirmed ONLY if it is
      mutually best on both sides AND beats every competing candidate on both
      sides by at least `margin`. Tied or near-tied candidates remain unresolved
      in `ambiguous`.
    """
    try:
        from rapidfuzz import fuzz
    except ImportError:
        logger.warning("RapidFuzz not installed. Fuzzy matching disabled.")
        return [], [], set(), set(), set(), set(), []

    matches = []
    ambiguous = []
    a_used = set()
    b_used = set()
    amb_a = set()
    amb_b = set()
    geo_only_candidates = []

    if norm_a.empty or norm_b.empty:
        return matches, ambiguous, a_used, b_used, amb_a, amb_b, geo_only_candidates

    a_rows = list(norm_a.index)
    b_rows = list(norm_b.index)

    candidates = []

    for a_idx in a_rows:
        a_name_raw = norm_a.loc[a_idx, name_col_a]
        a_name = None if _is_missing(a_name_raw) else str(a_name_raw).strip()

        a_lat = _safe_finite_float(norm_a.loc[a_idx, lat_a]) if require_geo and lat_a else None
        a_lon = _safe_finite_float(norm_a.loc[a_idx, lon_a]) if require_geo and lon_a else None
        a_geo_valid = (
            a_lat is not None and a_lon is not None
            and -90 <= a_lat <= 90 and -180 <= a_lon <= 180
        )

        for b_idx in b_rows:
            # Never override conflicting trustworthy IDs
            if _ids_conflict(norm_a, norm_b, a_idx, b_idx, id_col_a, id_col_b):
                continue

            b_name_raw = norm_b.loc[b_idx, name_col_b]
            b_name = None if _is_missing(b_name_raw) else str(b_name_raw).strip()

            dist_m = None
            geo_ok = True
            if require_geo:
                b_lat = _safe_finite_float(norm_b.loc[b_idx, lat_b]) if lat_b else None
                b_lon = _safe_finite_float(norm_b.loc[b_idx, lon_b]) if lon_b else None
                b_geo_valid = (
                    b_lat is not None and b_lon is not None
                    and -90 <= b_lat <= 90 and -180 <= b_lon <= 180
                )
                if not (a_geo_valid and b_geo_valid):
                    geo_ok = False
                else:
                    dist_m = haversine_distance(a_lat, a_lon, b_lat, b_lon)
                    geo_ok = dist_m <= distance_threshold_m

            if a_name is None or b_name is None:
                if require_geo and geo_ok and dist_m is not None:
                    geo_only_candidates.append(_make_geo_candidate(
                        raw_a, raw_b, a_idx, b_idx, dist_m,
                        source_a_name, source_b_name,
                        reason=f"Within {dist_m:.1f}m but missing name for confirmation."
                    ))
                    amb_a.add(a_idx)
                    amb_b.add(b_idx)
                continue

            score = float(fuzz.token_sort_ratio(a_name, b_name))

            if require_geo and not geo_ok:
                # Failed geographic constraint
                continue

            if score >= threshold:
                candidates.append({
                    "a_idx": a_idx,
                    "b_idx": b_idx,
                    "a_name": a_name,
                    "b_name": b_name,
                    "score": score,
                    "distance_m": dist_m,
                })
            elif require_geo and geo_ok and dist_m is not None:
                geo_only_candidates.append(_make_geo_candidate(
                    raw_a, raw_b, a_idx, b_idx, dist_m,
                    source_a_name, source_b_name,
                    id_a=a_name, id_b=b_name,
                    reason=(
                        f"Proximity-only candidate ({dist_m:.1f}m) with low "
                        f"name similarity ({score:.1f}% < {threshold}%)."
                    )
                ))
                amb_a.add(a_idx)
                amb_b.add(b_idx)

    if not candidates:
        return matches, ambiguous, a_used, b_used, amb_a, amb_b, geo_only_candidates

    # Group candidates by each side to check margin / ties
    by_a = {}
    by_b = {}
    for c in candidates:
        by_a.setdefault(c["a_idx"], []).append(c)
        by_b.setdefault(c["b_idx"], []).append(c)

    best_for_a = {}
    ambiguous_a_side = set()
    for a_idx, clist in by_a.items():
        clist_sorted = sorted(clist, key=lambda x: (-x["score"], x["b_idx"]))
        top = clist_sorted[0]
        if len(clist_sorted) > 1 and (top["score"] - clist_sorted[1]["score"]) < margin:
            ambiguous_a_side.add(a_idx)
        else:
            best_for_a[a_idx] = top["b_idx"]

    best_for_b = {}
    ambiguous_b_side = set()
    for b_idx, clist in by_b.items():
        clist_sorted = sorted(clist, key=lambda x: (-x["score"], x["a_idx"]))
        top = clist_sorted[0]
        if len(clist_sorted) > 1 and (top["score"] - clist_sorted[1]["score"]) < margin:
            ambiguous_b_side.add(b_idx)
        else:
            best_for_b[b_idx] = top["a_idx"]

    method_name = "fuzzy_geo" if require_geo else "fuzzy_name"

    for c in candidates:
        a_idx = c["a_idx"]
        b_idx = c["b_idx"]
        a_row_id = int(raw_a.loc[a_idx, "_original_row_id"])
        b_row_id = int(raw_b.loc[b_idx, "_original_row_id"])

        is_mutual_clear = (
            a_idx not in ambiguous_a_side
            and b_idx not in ambiguous_b_side
            and best_for_a.get(a_idx) == b_idx
            and best_for_b.get(b_idx) == a_idx
        )

        if is_mutual_clear:
            match_entry = {
                "id_a": c["a_name"],
                "id_b": c["b_name"],
                "row_id_a": a_row_id,
                "row_id_b": b_row_id,
                "index_a": a_idx,
                "index_b": b_idx,
                "method": method_name,
                "score": c["score"],
                "source_a": source_a_name,
                "source_b": source_b_name,
            }
            if c["distance_m"] is not None:
                match_entry["distance_m"] = round(c["distance_m"], 2)
            matches.append(match_entry)
            a_used.add(a_idx)
            b_used.add(b_idx)
        else:
            amb_a.add(a_idx)
            amb_b.add(b_idx)
            ambiguous.append({
                "id_a": c["a_name"],
                "id_b": c["b_name"],
                "row_id_a": a_row_id,
                "row_id_b": b_row_id,
                "index_a": a_idx,
                "index_b": b_idx,
                "method": method_name,
                "score": c["score"],
                "reason": (
                    f"Ambiguous candidate (score={c['score']:.1f}): tied, within "
                    f"margin ({margin}), or non-mutual best match."
                ),
                "source_a": source_a_name,
                "source_b": source_b_name,
            })

    return matches, ambiguous, a_used, b_used, amb_a, amb_b, geo_only_candidates


def _geo_proximity_candidates(norm_a, norm_b, raw_a, raw_b,
                              lat_a, lon_a, lat_b, lon_b,
                              threshold_m, source_a_name, source_b_name,
                              id_col_a=None, id_col_b=None):
    """
    Identify proximity-only candidates within threshold_m.
    Geographic proximity alone NEVER confirms entity identity; all pairs are
    returned as unresolved potential_geo_matches.
    """
    candidates = []
    amb_a = set()
    amb_b = set()

    if norm_a.empty or norm_b.empty:
        return candidates, amb_a, amb_b

    a_coords = []
    for idx in norm_a.index:
        lat_val = _safe_finite_float(norm_a.loc[idx, lat_a])
        lon_val = _safe_finite_float(norm_a.loc[idx, lon_a])
        if lat_val is not None and lon_val is not None and -90 <= lat_val <= 90 and -180 <= lon_val <= 180:
            a_coords.append((idx, lat_val, lon_val))

    b_coords = []
    for idx in norm_b.index:
        lat_val = _safe_finite_float(norm_b.loc[idx, lat_b])
        lon_val = _safe_finite_float(norm_b.loc[idx, lon_b])
        if lat_val is not None and lon_val is not None and -90 <= lat_val <= 90 and -180 <= lon_val <= 180:
            b_coords.append((idx, lat_val, lon_val))

    for a_idx, a_lat, a_lon in a_coords:
        for b_idx, b_lat, b_lon in b_coords:
            if _ids_conflict(norm_a, norm_b, a_idx, b_idx, id_col_a, id_col_b):
                continue
            dist = haversine_distance(a_lat, a_lon, b_lat, b_lon)
            if dist <= threshold_m:
                candidates.append(_make_geo_candidate(
                    raw_a, raw_b, a_idx, b_idx, dist,
                    source_a_name, source_b_name,
                    reason=(
                        f"Proximity-only candidate (distance={dist:.1f}m <= {threshold_m}m). "
                        f"Geographic proximity alone does not confirm entity identity."
                    )
                ))
                amb_a.add(a_idx)
                amb_b.add(b_idx)

    return candidates, amb_a, amb_b


def _make_geo_candidate(raw_a, raw_b, a_idx, b_idx, dist_m,
                        source_a_name, source_b_name,
                        id_a=None, id_b=None, reason=""):
    a_row_id = int(raw_a.loc[a_idx, "_original_row_id"])
    b_row_id = int(raw_b.loc[b_idx, "_original_row_id"])
    return {
        "id_a": id_a if id_a is not None else f"row_{a_row_id}",
        "id_b": id_b if id_b is not None else f"row_{b_row_id}",
        "row_id_a": a_row_id,
        "row_id_b": b_row_id,
        "index_a": a_idx,
        "index_b": b_idx,
        "method": "geo_proximity_only",
        "score": round(dist_m, 2),
        "reason": reason,
        "source_a": source_a_name,
        "source_b": source_b_name,
    }


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points on Earth
    using the Haversine formula (returns distance in metres).
    """
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_M * c


def _compute_jaccard(result, fallback_count=0, approximate_used=False,
                     record_level_counting=False):
    """
    Jaccard Similarity = |Confirmed Matches| / |Union of Unique Entities|

    Union = total_a + total_b - matched_count.
    Because each confirmed match is 1-to-1 between distinct entities counted in
    total_a and total_b, matched_count <= min(total_a, total_b) and
    0 <= jaccard <= 1 is guaranteed.
    """
    matched_count = len(result.matched)
    total_a = result.total_a
    total_b = result.total_b

    union_size = total_a + total_b - matched_count

    if union_size <= 0:
        return None, False, "Empty union: both sources have no matchable entities."

    jaccard = matched_count / union_size

    unmatchable_count = len(result.unmatchable_a) + len(result.unmatchable_b)
    is_estimate = bool(
        result.ambiguous or result.potential_geo_matches
        or unmatchable_count > 0 or fallback_count > 0
        or approximate_used or record_level_counting
    )

    label = "Estimated Jaccard" if is_estimate else "Jaccard"
    explanation = (
        f"Intersection (confirmed matches): {matched_count}. "
        f"Source A entities: {total_a}. "
        f"Source B entities: {total_b}. "
        f"Union: {union_size}. "
        f"{label} = {matched_count}/{union_size} = {jaccard:.4f}."
    )

    if is_estimate:
        notes = []
        if approximate_used:
            notes.append("approximate matching relied on for entity identity")
        if record_level_counting:
            notes.append("record-level entity counting used without compatible IDs")
        if result.ambiguous:
            notes.append(f"{len(result.ambiguous)} ambiguous/unresolved candidate pair(s) excluded from confirmed matches")
        if unmatchable_count > 0:
            notes.append(f"{unmatchable_count} unmatchable record(s) excluded from entity totals")
        if fallback_count > 0:
            notes.append(f"{fallback_count} record(s) without IDs evaluated via approximate matching")
        explanation += " Overlap is an estimate (" + "; ".join(notes) + ")."

    return jaccard, is_estimate, explanation


def _detect_conflicts(matches, norm_a, norm_b, raw_a, raw_b,
                      compare_columns, cols_a, cols_b,
                      source_a_name, source_b_name):
    """Compare attributes of matched entities and detect conflicts."""
    conflicts = []

    for match in matches:
        a_idx = match["index_a"]
        b_idx = match["index_b"]

        for col_pair in compare_columns:
            if isinstance(col_pair, (list, tuple)) and len(col_pair) == 2:
                col_a_name, col_b_name = col_pair
            else:
                col_a_name = col_b_name = col_pair

            actual_a = _resolve(col_a_name, cols_a)
            actual_b = _resolve(col_b_name, cols_b)

            if not actual_a or not actual_b:
                continue
            if actual_a not in norm_a.columns or actual_b not in norm_b.columns:
                continue

            val_a = norm_a.loc[a_idx, actual_a]
            val_b = norm_b.loc[b_idx, actual_b]

            a_missing = _is_missing(val_a)
            b_missing = _is_missing(val_b)

            raw_col_a = _find_raw_col(actual_a, raw_a.columns)
            raw_col_b = _find_raw_col(actual_b, raw_b.columns)
            raw_val_a = raw_a.loc[a_idx, raw_col_a] if raw_col_a else val_a
            raw_val_b = raw_b.loc[b_idx, raw_col_b] if raw_col_b else val_b

            if a_missing and b_missing:
                continue
            elif a_missing:
                conflict_type = "missing_in_a"
            elif b_missing:
                conflict_type = "missing_in_b"
            else:
                if _values_equal(val_a, val_b):
                    continue
                conflict_type = "conflict"

            conflicts.append({
                "entity_id": match.get("id_a", ""),
                "entity_name": match.get("id_a", ""),
                "attribute": col_a_name,
                "value_a": _safe_str(raw_val_a),
                "value_b": _safe_str(raw_val_b),
                "source_a": source_a_name,
                "source_b": source_b_name,
                "row_id_a": match["row_id_a"],
                "row_id_b": match["row_id_b"],
                "method": match["method"],
                "conflict_type": conflict_type,
            })

    return conflicts


def _values_equal(a, b):
    """Compare two values for equality, handling numeric types."""
    try:
        fa = float(a)
        fb = float(b)
        if math.isfinite(fa) and math.isfinite(fb):
            return math.isclose(fa, fb, rel_tol=1e-9)
    except (ValueError, TypeError):
        pass
    return str(a).strip().lower() == str(b).strip().lower()


def _safe_finite_float(val):
    """Safely convert to finite float, returning None on failure or non-finite."""
    if _is_missing(val):
        return None
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (ValueError, TypeError):
        return None


def _safe_str(val):
    """Safely convert to string."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    return str(val)


def _find_raw_col(norm_col, raw_columns):
    """Find matching raw column for a normalized column name."""
    for rc in raw_columns:
        if rc == "_original_row_id":
            continue
        if str(rc).strip().lower() == norm_col.strip().lower():
            return rc
    return None
