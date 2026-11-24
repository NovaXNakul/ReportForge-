# data_ingestion.py

"""
Multi-Source Data Ingestion Module for ReportForge 2.0.

Supports CSV, Excel (.xlsx), and GeoJSON file ingestion with configurable
normalization, provenance tracking, and robust error handling.

Assumptions & Policies:
- CSV files are initially read as raw text (dtype=str) to preserve exact
  formatting such as leading zeros in identifiers before any downstream
  type coercion.
- Excel (.xlsx) files are read with dtype=str where cells are stored as text;
  however, Excel numeric cells that only display leading zeros via number
  formatting cannot be recovered as zero-padded text by standard readers.
- Legacy .xls files are not supported (use .xlsx).
- Date formats: Attempts ISO 8601 first, then common formats (MM/DD/YYYY,
  DD/MM/YYYY, YYYY-MM-DD). Ambiguous dates default to dayfirst=False (US format).
- Timezones: Mixed or timezone-aware timestamps are converted to UTC and stored
  as timezone-naive UTC timestamps for consistent comparison. Naive timestamps
  are treated as-is without implicit timezone conversion.
- GeoJSON: Supports Point, MultiPoint, LineString, MultiLineString, Polygon,
  MultiPolygon geometries. GeometryCollection is flagged as unsupported.
  Only Feature and FeatureCollection GeoJSON types are ingested.
- Reserved metadata columns: '_original_row_id' is reserved for provenance.
"""

import os
import json
import logging
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Supported GeoJSON geometry types
SUPPORTED_GEOJSON_GEOMETRIES = {
    "Point", "MultiPoint", "LineString", "MultiLineString",
    "Polygon", "MultiPolygon",
}

RESERVED_COLUMNS = {"_original_row_id"}


def _is_raw_missing(val) -> bool:
    """Check whether a raw cell value is missing (None, NaN, empty/whitespace)."""
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


class IngestionError(Exception):
    """Raised when a file cannot be ingested."""
    pass


class IngestedDataset:
    """
    Container for an ingested dataset, preserving both raw and normalized data
    along with provenance metadata.

    Attributes:
        source_name: User-provided name for this data source.
        filename: Original filename (preserved separately from temp paths).
        sheet_name: Excel sheet name (None for CSV/GeoJSON).
        raw_df: Original data as-is (text-preserved for CSV/XLSX).
        normalized_df: Cleaned/normalized copy for comparison.
        row_id_column: Name of the stable original row identifier column added.
        geo_columns: Dict mapping 'latitude' and 'longitude' to column names, if detected.
        ingestion_warnings: List of non-fatal warnings encountered during ingestion.
        normalization_failures: Dict mapping (row_index, norm_col) -> failure metadata
            for originally populated values that failed numeric or date coercion.
    """

    def __init__(self, source_name: str, filename: str, sheet_name: Optional[str],
                 raw_df: pd.DataFrame, normalized_df: pd.DataFrame,
                 row_id_column: str = "_original_row_id",
                 geo_columns: Optional[dict] = None,
                 ingestion_warnings: Optional[list] = None,
                 normalization_failures: Optional[dict] = None):
        self.source_name = source_name
        self.filename = filename
        self.sheet_name = sheet_name
        self.raw_df = raw_df
        self.normalized_df = normalized_df
        self.row_id_column = row_id_column
        self.geo_columns = geo_columns or {}
        self.ingestion_warnings = ingestion_warnings or []
        self.normalization_failures = normalization_failures or {}

    def __repr__(self):
        return (f"IngestedDataset(source='{self.source_name}', file='{self.filename}', "
                f"sheet='{self.sheet_name}', rows={len(self.raw_df)}, "
                f"cols={len(self.raw_df.columns)})")


def ingest_file(filepath: str, source_name: str,
                sheet_name: Optional[str] = None,
                identifier_columns: Optional[list] = None,
                normalize_config: Optional[dict] = None,
                original_filename: Optional[str] = None) -> list:
    """
    Ingest a single file and return a list of IngestedDataset objects.

    For Excel (.xlsx) files, if sheet_name is None, all sheets are ingested (one
    IngestedDataset per sheet). For CSV and GeoJSON, one IngestedDataset
    is returned.

    Args:
        filepath: Path to the file on disk.
        source_name: User-defined source label.
        sheet_name: Specific Excel sheet to read (None = all sheets).
        identifier_columns: Columns to preserve as strings (leading zeros).
        normalize_config: Dict with normalization options:
            - strip_whitespace (bool): Strip leading/trailing whitespace. Default True.
            - lowercase_text (bool): Lowercase text columns. Default False.
            - normalize_column_names (bool): Lowercase and strip column names. Default True.
            - coerce_numeric (list): Column names to coerce to numeric.
            - parse_dates (list): Column names to parse as dates.
            - missing_values (list): Additional strings to treat as missing.
        original_filename: Original user filename when filepath is a temporary path.

    Returns:
        List of IngestedDataset objects.

    Raises:
        IngestionError: If the file cannot be read or is unsupported.
    """
    if not os.path.exists(filepath):
        raise IngestionError(f"File not found: '{filepath}'")

    filename = original_filename or os.path.basename(filepath)
    ext = os.path.splitext(filename)[1].lower()

    if normalize_config is None:
        normalize_config = {}

    if identifier_columns is None:
        identifier_columns = []

    try:
        if ext == ".csv":
            return _ingest_csv(filepath, source_name, filename,
                               identifier_columns, normalize_config)
        elif ext == ".xlsx":
            return _ingest_excel(filepath, source_name, filename,
                                 sheet_name, identifier_columns, normalize_config)
        elif ext == ".geojson":
            return _ingest_geojson(filepath, source_name, filename,
                                   identifier_columns, normalize_config)
        else:
            raise IngestionError(
                f"Unsupported file format: '{ext}'. "
                f"Supported formats: .csv, .xlsx, .geojson"
            )
    except IngestionError:
        raise
    except Exception as e:
        raise IngestionError(f"Failed to read '{filename}': {str(e)}")


def _ingest_csv(filepath, source_name, filename,
                identifier_columns, normalize_config):
    """
    Ingest a CSV file using lossless initial text parsing (dtype=str)
    so leading zeros and raw representations are preserved before normalization.
    """
    try:
        df = pd.read_csv(filepath, dtype=str, keep_default_na=True)
    except pd.errors.EmptyDataError:
        raise IngestionError(f"File '{filename}' is empty.")
    except pd.errors.ParserError as e:
        raise IngestionError(f"File '{filename}' is malformed or corrupted: {e}")

    if df.empty and len(df.columns) == 0:
        raise IngestionError(f"File '{filename}' is empty (no columns detected).")

    warnings_list = _check_duplicate_columns(df, filename)
    _check_reserved_columns(df, filename)
    raw_df = _add_row_ids(df.copy())
    normalized_df, norm_failures = _normalize_dataframe(
        raw_df.copy(), identifier_columns, normalize_config, warnings_list
    )

    return [IngestedDataset(
        source_name=source_name,
        filename=filename,
        sheet_name=None,
        raw_df=raw_df,
        normalized_df=normalized_df,
        geo_columns=_detect_geo_columns(normalized_df),
        ingestion_warnings=warnings_list,
        normalization_failures=norm_failures,
    )]


def _ingest_excel(filepath, source_name, filename,
                  sheet_name, identifier_columns, normalize_config):
    """Ingest an Excel (.xlsx) file (one or more sheets)."""
    try:
        sheets = pd.read_excel(filepath, sheet_name=sheet_name,
                               dtype=str, keep_default_na=True, engine="openpyxl")
    except Exception as e:
        raise IngestionError(f"Cannot read Excel file '{filename}': {e}")

    if isinstance(sheets, pd.DataFrame):
        sheets = {sheet_name or "Sheet1": sheets}

    datasets = []
    for sname, df in sheets.items():
        if df.empty and len(df.columns) == 0:
            logger.warning(f"Sheet '{sname}' in '{filename}' is empty, skipping.")
            continue

        warnings_list = _check_duplicate_columns(df, filename, sname)
        _check_reserved_columns(df, filename, sname)
        raw_df = _add_row_ids(df.copy())
        normalized_df, norm_failures = _normalize_dataframe(
            raw_df.copy(), identifier_columns, normalize_config, warnings_list
        )

        datasets.append(IngestedDataset(
            source_name=source_name,
            filename=filename,
            sheet_name=str(sname),
            raw_df=raw_df,
            normalized_df=normalized_df,
            geo_columns=_detect_geo_columns(normalized_df),
            ingestion_warnings=warnings_list,
            normalization_failures=norm_failures,
        ))

    if not datasets:
        raise IngestionError(f"Excel file '{filename}' contains no readable sheets.")

    return datasets


def _ingest_geojson(filepath, source_name, filename,
                    identifier_columns, normalize_config):
    """
    Ingest a GeoJSON file by extracting feature properties into a DataFrame
    and adding latitude/longitude columns for Point geometries.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            geojson = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise IngestionError(f"File '{filename}' is not valid JSON/GeoJSON: {e}")

    if not isinstance(geojson, dict):
        raise IngestionError(f"File '{filename}' is not a valid GeoJSON object.")

    geojson_type = geojson.get("type", "")

    if geojson_type == "FeatureCollection":
        features = geojson.get("features", [])
    elif geojson_type == "Feature":
        features = [geojson]
    else:
        raise IngestionError(
            f"Unsupported GeoJSON type '{geojson_type}' in '{filename}'. "
            f"Expected 'Feature' or 'FeatureCollection'."
        )

    if not features:
        raise IngestionError(f"GeoJSON file '{filename}' contains no features.")

    rows = []
    warnings_list = []

    for idx, feature in enumerate(features):
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            warnings_list.append(
                f"Item at index {idx} is not a valid GeoJSON Feature, skipping."
            )
            continue

        props = feature.get("properties") or {}
        row = dict(props)

        if "_geojson_latitude" in row or "_geojson_longitude" in row:
            warnings_list.append(
                f"Feature at index {idx}: property collides with reserved "
                f"'_geojson_latitude'/'_geojson_longitude' column."
            )

        geometry = feature.get("geometry")
        if geometry and isinstance(geometry, dict):
            geom_type = geometry.get("type", "")
            coords = geometry.get("coordinates")

            if geom_type not in SUPPORTED_GEOJSON_GEOMETRIES:
                warnings_list.append(
                    f"Feature at index {idx}: unsupported geometry type '{geom_type}'."
                )
                row["_geojson_geometry_type"] = geom_type
                row["_geojson_latitude"] = None
                row["_geojson_longitude"] = None
            elif geom_type == "Point" and isinstance(coords, (list, tuple)) and len(coords) >= 2:
                # GeoJSON coordinates are [longitude, latitude]
                row["_geojson_geometry_type"] = "Point"
                row["_geojson_longitude"] = coords[0]
                row["_geojson_latitude"] = coords[1]
            else:
                # Non-Point geometries: preserve geometry type, store None for point lat/lon
                row["_geojson_geometry_type"] = geom_type
                row["_geojson_latitude"] = None
                row["_geojson_longitude"] = None
        else:
            row["_geojson_geometry_type"] = None
            row["_geojson_latitude"] = None
            row["_geojson_longitude"] = None

        rows.append(row)

    if not rows:
        raise IngestionError(f"GeoJSON file '{filename}' produced no valid features.")

    df = pd.DataFrame(rows)

    for col in identifier_columns:
        if col in df.columns:
            df[col] = df[col].map(lambda x: str(x) if not _is_raw_missing(x) else x)

    _check_reserved_columns(df, filename)
    raw_df = _add_row_ids(df.copy())
    normalized_df, norm_failures = _normalize_dataframe(
        raw_df.copy(), identifier_columns, normalize_config, warnings_list
    )

    geo_cols = {}
    if "_geojson_latitude" in normalized_df.columns:
        geo_cols["latitude"] = "_geojson_latitude"
        geo_cols["longitude"] = "_geojson_longitude"

    return [IngestedDataset(
        source_name=source_name,
        filename=filename,
        sheet_name=None,
        raw_df=raw_df,
        normalized_df=normalized_df,
        geo_columns=geo_cols,
        ingestion_warnings=warnings_list,
        normalization_failures=norm_failures,
    )]


def _check_reserved_columns(df: pd.DataFrame, filename: str, sheet_name: Optional[str] = None):
    """Raise IngestionError if input data contains reserved metadata column names."""
    collisions = [c for c in df.columns if str(c).strip() in RESERVED_COLUMNS]
    if collisions:
        loc = f"'{filename}'" + (f" sheet '{sheet_name}'" if sheet_name else "")
        raise IngestionError(
            f"Reserved metadata column collision in {loc}: {collisions}. "
            f"Please rename these columns before ingestion."
        )


def _add_row_ids(df: pd.DataFrame, col_name: str = "_original_row_id") -> pd.DataFrame:
    """Add a stable 1-based row identifier column."""
    df.insert(0, col_name, range(1, len(df) + 1))
    return df


def _check_duplicate_columns(df, filename, sheet_name=None):
    """Check for duplicate column names and return warnings."""
    warnings_list = []
    cols = list(df.columns)
    seen = {}
    for c in cols:
        seen[c] = seen.get(c, 0) + 1
    dupes = {k: v for k, v in seen.items() if v > 1}
    if dupes:
        loc = f"'{filename}'" + (f" sheet '{sheet_name}'" if sheet_name else "")
        warnings_list.append(
            f"Duplicate column names in {loc}: {dupes}."
        )
    return warnings_list


def _normalize_dataframe(df, identifier_columns, config, warnings_list):
    """
    Apply configurable normalization to a DataFrame while tracking
    originally populated values that fail numeric/date coercion.

    Returns:
        (normalized_df, normalization_failures)
    """
    norm_failures = {}

    # Step 1: Normalize column names and detect collisions
    if config.get("normalize_column_names", True):
        new_cols = []
        seen_norm = {}
        collisions = []
        for c in df.columns:
            if c == "_original_row_id":
                new_cols.append(c)
                continue
            norm_c = str(c).strip().lower().replace("  ", " ")
            if norm_c in seen_norm:
                seen_norm[norm_c] += 1
                disambiguated = f"{norm_c}_{seen_norm[norm_c]}"
                collisions.append((str(c), norm_c, disambiguated))
                new_cols.append(disambiguated)
            else:
                seen_norm[norm_c] = 1
                new_cols.append(norm_c)
        df.columns = new_cols
        if collisions:
            warnings_list.append(
                f"Normalized column name collision(s) detected and disambiguated: {collisions}."
            )

    id_cols_lower = [c.strip().lower() for c in identifier_columns]

    # Step 2: Handle additional missing value markers
    extra_missing = config.get("missing_values", [])
    if extra_missing:
        df = df.replace(extra_missing, np.nan)

    # Step 3: Strip whitespace from string columns
    if config.get("strip_whitespace", True):
        for col in df.columns:
            if col == "_original_row_id":
                continue
            if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
                df[col] = df[col].map(
                    lambda x: x.strip() if isinstance(x, str) else x
                )

    # Step 4: Optionally lowercase text columns (not identifiers)
    if config.get("lowercase_text", False):
        for col in df.columns:
            if col == "_original_row_id":
                continue
            if col.strip().lower() in id_cols_lower:
                continue
            if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
                df[col] = df[col].map(
                    lambda x: x.lower() if isinstance(x, str) else x
                )

    # Step 5: Coerce specified columns to numeric (tracking failures)
    coerce_numeric = config.get("coerce_numeric", [])
    for col_name in coerce_numeric:
        matched = [c for c in df.columns
                   if c.strip().lower() == col_name.strip().lower()
                   and c != "_original_row_id"]
        for mc in matched:
            pre_vals = df[mc].copy()
            converted = pd.to_numeric(pre_vals, errors="coerce")
            for idx in df.index:
                orig_v = pre_vals.loc[idx]
                conv_v = converted.loc[idx]
                if not _is_raw_missing(orig_v):
                    if pd.isna(conv_v) or (isinstance(conv_v, (int, float)) and not np.isfinite(conv_v)):
                        norm_failures[(idx, mc)] = {
                            "type": "numeric",
                            "raw_value": orig_v,
                        }
                        if not pd.isna(conv_v):
                            converted.loc[idx] = np.nan
            df[mc] = converted

    # Step 6: Parse specified columns as dates (tracking failures, UTC-naive normalization)
    parse_dates = config.get("parse_dates", [])
    for col_name in parse_dates:
        matched = [c for c in df.columns
                   if c.strip().lower() == col_name.strip().lower()
                   and c != "_original_row_id"]
        for mc in matched:
            pre_vals = df[mc].copy()
            converted = _parse_timestamps_consistent(pre_vals)
            for idx in df.index:
                orig_v = pre_vals.loc[idx]
                conv_v = converted.loc[idx]
                if not _is_raw_missing(orig_v) and pd.isna(conv_v):
                    norm_failures[(idx, mc)] = {
                        "type": "date",
                        "raw_value": orig_v,
                    }
            df[mc] = converted

    # Step 7: Preserve identifier columns as strings
    for id_col in identifier_columns:
        matched = [c for c in df.columns
                   if c.strip().lower() == id_col.strip().lower()
                   and c != "_original_row_id"]
        for mc in matched:
            df[mc] = df[mc].map(
                lambda x: str(x) if not _is_raw_missing(x) else x
            )

    return df, norm_failures


def _parse_timestamps_consistent(series: pd.Series) -> pd.Series:
    """
    Parse a Series of timestamps consistently.
    - Converts timezone-aware timestamps to UTC and strips tzinfo (UTC-naive).
    - Leaves timezone-naive timestamps as naive.
    """
    out = []
    for val in series:
        if _is_raw_missing(val):
            out.append(pd.NaT)
            continue
        try:
            ts = pd.to_datetime(val, dayfirst=False)
            if pd.isna(ts):
                out.append(pd.NaT)
            else:
                if ts.tzinfo is not None:
                    ts = ts.tz_convert("UTC").tz_localize(None)
                out.append(ts)
        except Exception:
            out.append(pd.NaT)
    return pd.Series(out, index=series.index)


def _detect_geo_columns(df):
    """
    Auto-detect geographic coordinate columns by common naming conventions.
    Returns dict with 'latitude' and 'longitude' keys if found.
    """
    lat_names = {"latitude", "lat", "_geojson_latitude"}
    lon_names = {"longitude", "lon", "lng", "_geojson_longitude"}

    geo = {}
    cols_lower = {c.lower(): c for c in df.columns}

    for name in lat_names:
        if name in cols_lower:
            geo["latitude"] = cols_lower[name]
            break

    for name in lon_names:
        if name in cols_lower:
            geo["longitude"] = cols_lower[name]
            break

    if "latitude" in geo and "longitude" in geo:
        return geo
    return {}
