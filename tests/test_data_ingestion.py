# tests/test_data_ingestion.py

"""Tests for the data_ingestion module."""

import os
import json
import pytest
import pandas as pd

from data_ingestion import ingest_file, IngestedDataset, IngestionError


class TestCSVIngestion:
    """Test CSV file ingestion."""

    def test_basic_csv_ingestion(self, synthetic_hospitals_a):
        """Test that a valid CSV is ingested correctly."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="Test Source")
        assert len(datasets) == 1
        ds = datasets[0]
        assert isinstance(ds, IngestedDataset)
        assert ds.source_name == "Test Source"
        assert ds.filename == "hospitals_a.csv"
        assert ds.sheet_name is None
        assert len(ds.raw_df) == 10
        assert "_original_row_id" in ds.raw_df.columns
        assert ds.raw_df["_original_row_id"].tolist() == list(range(1, 11))

    def test_empty_csv(self, empty_csv):
        """Test that empty CSV (headers only) produces an empty dataset."""
        datasets = ingest_file(empty_csv, source_name="Empty")
        assert len(datasets) == 1
        ds = datasets[0]
        assert len(ds.raw_df) == 0
        assert "id" in ds.normalized_df.columns or "ID" in ds.raw_df.columns

    def test_truly_empty_file(self, truly_empty_file):
        """Test that a completely empty file raises IngestionError."""
        with pytest.raises(IngestionError):
            ingest_file(truly_empty_file, source_name="Empty")

    def test_unsupported_format(self, tmp_dir):
        """Test that unsupported file formats raise IngestionError."""
        filepath = os.path.join(tmp_dir, "test.pdf")
        with open(filepath, "w") as f:
            f.write("not a pdf")
        with pytest.raises(IngestionError, match="Unsupported file format"):
            ingest_file(filepath, source_name="PDF")

    def test_file_not_found(self):
        """Test that missing files raise IngestionError."""
        with pytest.raises(IngestionError, match="File not found"):
            ingest_file("/nonexistent/file.csv", source_name="Missing")

    def test_identifier_preservation(self, leading_zeros_csv):
        """Test that leading zeros are preserved in identifier columns."""
        datasets = ingest_file(
            leading_zeros_csv,
            source_name="ZipCodes",
            identifier_columns=["ZipCode"]
        )
        ds = datasets[0]
        # Check raw data preserves leading zeros
        raw_zips = ds.raw_df["ZipCode"].tolist()
        assert "00501" in raw_zips
        assert "01001" in raw_zips

        # Normalized data should also preserve identifiers as strings
        norm_col = "zipcode"  # normalized column name
        assert norm_col in ds.normalized_df.columns
        norm_zips = ds.normalized_df[norm_col].tolist()
        assert "00501" in norm_zips
        assert "01001" in norm_zips

    def test_provenance_preserved(self, synthetic_hospitals_a):
        """Test that source provenance metadata is preserved."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="Hospital Source A")
        ds = datasets[0]
        assert ds.source_name == "Hospital Source A"
        assert ds.filename == "hospitals_a.csv"
        assert ds.sheet_name is None

    def test_normalization_column_names(self, synthetic_hospitals_a):
        """Test that column names are normalized (lowercased, stripped)."""
        datasets = ingest_file(synthetic_hospitals_a, source_name="Test")
        ds = datasets[0]
        norm_cols = list(ds.normalized_df.columns)
        assert "hospitalid" in norm_cols
        assert "name" in norm_cols
        assert "beds" in norm_cols


class TestExcelIngestion:
    """Test Excel file ingestion."""

    def test_excel_all_sheets(self, synthetic_excel):
        """Test that all sheets are ingested when no sheet is specified."""
        datasets = ingest_file(synthetic_excel, source_name="Excel Test")
        assert len(datasets) == 2
        sheet_names = {ds.sheet_name for ds in datasets}
        assert "Sheet1" in sheet_names
        assert "Sheet2" in sheet_names

    def test_excel_specific_sheet(self, synthetic_excel):
        """Test ingestion of a specific sheet."""
        datasets = ingest_file(
            synthetic_excel, source_name="Excel Test",
            sheet_name="Sheet1"
        )
        assert len(datasets) == 1
        assert datasets[0].sheet_name == "Sheet1"
        assert len(datasets[0].raw_df) == 3

    def test_excel_identifier_preservation(self, synthetic_excel):
        """Test that identifiers are preserved as strings in Excel."""
        datasets = ingest_file(
            synthetic_excel, source_name="Excel Test",
            sheet_name="Sheet1",
            identifier_columns=["ID"]
        )
        ds = datasets[0]
        # Raw df should have ID values as strings
        assert all(isinstance(v, str) for v in ds.raw_df["ID"].tolist())


class TestGeoJSONIngestion:
    """Test GeoJSON file ingestion."""

    def test_geojson_basic(self, synthetic_geojson):
        """Test basic GeoJSON ingestion."""
        datasets = ingest_file(synthetic_geojson, source_name="GeoTest")
        assert len(datasets) == 1
        ds = datasets[0]
        assert len(ds.raw_df) == 3
        assert "_geojson_latitude" in ds.raw_df.columns
        assert "_geojson_longitude" in ds.raw_df.columns
        assert ds.geo_columns.get("latitude") is not None

    def test_geojson_coordinates(self, synthetic_geojson):
        """Test that Point coordinates are correctly extracted."""
        datasets = ingest_file(synthetic_geojson, source_name="GeoTest")
        ds = datasets[0]
        # First point: [72.877, 19.076] -> lat=19.076, lon=72.877
        assert ds.raw_df.iloc[0]["_geojson_latitude"] == 19.076
        assert ds.raw_df.iloc[0]["_geojson_longitude"] == 72.877

    def test_geojson_invalid(self, tmp_dir):
        """Test that invalid GeoJSON raises IngestionError."""
        filepath = os.path.join(tmp_dir, "bad.geojson")
        with open(filepath, "w") as f:
            f.write("{not valid json")
        with pytest.raises(IngestionError):
            ingest_file(filepath, source_name="Bad")

    def test_geojson_unsupported_type(self, tmp_dir):
        """Test that unsupported GeoJSON types raise IngestionError."""
        filepath = os.path.join(tmp_dir, "topo.geojson")
        with open(filepath, "w") as f:
            json.dump({"type": "Topology", "objects": {}}, f)
        with pytest.raises(IngestionError, match="Unsupported GeoJSON type"):
            ingest_file(filepath, source_name="Topo")

    def test_geojson_empty_features(self, tmp_dir):
        """Test that GeoJSON with no features raises IngestionError."""
        filepath = os.path.join(tmp_dir, "empty.geojson")
        with open(filepath, "w") as f:
            json.dump({"type": "FeatureCollection", "features": []}, f)
        with pytest.raises(IngestionError, match="no features"):
            ingest_file(filepath, source_name="Empty")
