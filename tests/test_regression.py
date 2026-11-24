# tests/test_regression.py

"""
Regression tests for existing ReportForge functionality.

Ensures that the original web scraping, Excel generation, Excel reading,
and PowerPoint generation workflows remain operational after Feature 1
modifications.
"""

import os
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from schema_config import detect_dataset_type
from excel_reader import read_excel
from ppt_generator import create_ppt


class TestSchemaDetection:
    """Test that existing schema detection still works."""

    def test_corporate_detection(self, corporate_excel):
        """Corporate Performance workbooks are correctly detected."""
        data_dict = read_excel(corporate_excel)
        dataset_type = detect_dataset_type(data_dict)
        assert dataset_type == "corporate"

    def test_books_detection(self, books_excel):
        """Scraped Books workbooks are correctly detected."""
        data_dict = read_excel(books_excel)
        dataset_type = detect_dataset_type(data_dict)
        assert dataset_type == "scraped_books"

    def test_generic_detection(self, synthetic_excel):
        """Generic workbooks are detected as 'generic'."""
        data_dict = read_excel(synthetic_excel)
        dataset_type = detect_dataset_type(data_dict)
        assert dataset_type == "generic"


class TestExcelReader:
    """Test existing Excel reader functionality."""

    def test_corporate_excel_reading(self, corporate_excel):
        """Corporate Excel files are read with correct sheet mapping."""
        data_dict = read_excel(corporate_excel)
        assert "Employees" in data_dict
        assert "Monthly Revenue" in data_dict
        assert "Products" in data_dict
        assert "Regional Performance" in data_dict

        # Verify column structure
        assert "Name" in data_dict["Employees"].columns
        assert "Sales" in data_dict["Employees"].columns
        assert "Target" in data_dict["Employees"].columns

    def test_books_excel_reading(self, books_excel):
        """Books Excel files are read correctly."""
        data_dict = read_excel(books_excel)
        assert "Books Data" in data_dict
        assert "Summary" in data_dict

    def test_generic_excel_reading(self, synthetic_excel):
        """Generic Excel files return all sheets."""
        data_dict = read_excel(synthetic_excel)
        assert len(data_dict) == 2


class TestPptGeneration:
    """Test existing PowerPoint generation workflows."""

    def test_corporate_ppt_generation(self, corporate_excel, tmp_dir):
        """Corporate PPT generation completes without errors."""
        data_dict = read_excel(corporate_excel)
        output_path = os.path.join(tmp_dir, "corporate.pptx")
        result = create_ppt(data_dict, output_path=output_path)
        assert os.path.exists(output_path)

    def test_books_ppt_generation(self, books_excel, tmp_dir):
        """Books PPT generation completes without errors."""
        data_dict = read_excel(books_excel)
        output_path = os.path.join(tmp_dir, "books.pptx")
        result = create_ppt(data_dict, output_path=output_path)
        assert os.path.exists(output_path)

    def test_generic_ppt_generation(self, synthetic_excel, tmp_dir):
        """Generic PPT generation completes without errors."""
        data_dict = read_excel(synthetic_excel)
        output_path = os.path.join(tmp_dir, "generic.pptx")
        result = create_ppt(data_dict, output_path=output_path)
        assert os.path.exists(output_path)


class TestScraperNetworkFailure:
    """Test scraper behavior on network failures."""

    @patch("scraper.requests.get")
    def test_scraper_connection_error(self, mock_get):
        """Scraper handles ConnectionError gracefully."""
        from scraper import scrape_books
        mock_get.side_effect = ConnectionError("Network unreachable")
        result = scrape_books(url="https://books.toscrape.com/")
        assert result is None

    @patch("scraper.requests.get")
    def test_scraper_timeout(self, mock_get):
        """Scraper handles Timeout errors gracefully."""
        from scraper import scrape_books
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")
        result = scrape_books(url="https://books.toscrape.com/")
        assert result is None

    @patch("scraper.requests.get")
    def test_scraper_http_error(self, mock_get):
        """Scraper handles HTTP error status codes."""
        from scraper import scrape_books
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        result = scrape_books(url="https://books.toscrape.com/")
        assert result is None


class TestReportConsistency:
    """Test that dashboard and report results use the same data."""

    def test_quality_result_summary_dict(self, synthetic_hospitals_a):
        """QualityResult.to_summary_dict() returns consistent values."""
        from data_ingestion import ingest_file
        from data_quality_analyzer import QualityConfig, analyze_quality

        datasets = ingest_file(synthetic_hospitals_a, source_name="Test")
        ds = datasets[0]

        config = QualityConfig(
            required_columns=["Name", "Beds"],
            identifier_column="HospitalID",
        )
        result = analyze_quality(ds, config)
        summary = result.to_summary_dict()

        # Summary dict should match the result object
        assert summary["completeness_value"] == result.completeness
        assert summary["validity_value"] == result.validity
        assert summary["uniqueness_value"] == result.uniqueness
        assert summary["freshness_value"] == result.freshness
        assert summary["total_records"] == result.total_records

    def test_report_generation_from_bundle(self, synthetic_hospitals_a,
                                            synthetic_hospitals_b, tmp_dir):
        """Excel and PPT reports can be generated from an AnalysisBundle."""
        from data_ingestion import ingest_file
        from data_quality_analyzer import QualityConfig, analyze_quality
        from source_comparator import ComparisonConfig, compare_sources
        from dq_report_generator import (
            AnalysisBundle, generate_dq_excel_report, generate_dq_ppt_report
        )

        ds_a = ingest_file(synthetic_hospitals_a, source_name="A")[0]
        ds_b = ingest_file(synthetic_hospitals_b, source_name="B")[0]

        qr_a = analyze_quality(ds_a, QualityConfig(
            required_columns=["Name"], identifier_column="HospitalID"
        ))
        qr_b = analyze_quality(ds_b, QualityConfig(
            required_columns=["Name"], identifier_column="HospitalID"
        ))

        cr = compare_sources(ds_a, ds_b, ComparisonConfig(
            id_column_a="HospitalID", id_column_b="HospitalID",
            use_exact=True,
            compare_columns=[("Beds", "Beds")],
        ))

        bundle = AnalysisBundle(
            quality_results=[qr_a, qr_b],
            comparison_result=cr,
            datasets=[ds_a, ds_b],
        )

        excel_path = os.path.join(tmp_dir, "test_report.xlsx")
        ppt_path = os.path.join(tmp_dir, "test_report.pptx")

        generate_dq_excel_report(bundle, excel_path)
        generate_dq_ppt_report(bundle, ppt_path)

        assert os.path.exists(excel_path)
        assert os.path.exists(ppt_path)
        assert os.path.getsize(excel_path) > 0
        assert os.path.getsize(ppt_path) > 0
