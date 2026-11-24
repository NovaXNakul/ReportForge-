# tests/conftest.py

"""
Shared pytest fixtures for ReportForge 2.0 tests.

All synthetic test datasets are created programmatically here.
These are SYNTHETIC datasets created solely for testing purposes.
"""

import os
os.environ.setdefault("MPLBACKEND", "Agg")
import json
import tempfile
from datetime import datetime, timedelta

import pandas as pd
import pytest


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def synthetic_hospitals_a(tmp_dir):
    """
    SYNTHETIC hospital dataset A (CSV).
    10 records with known quality issues:
    - Row 3: missing name
    - Row 5: duplicate ID (H102)
    - Row 6: invalid latitude (999)
    - Row 7: missing beds
    - Row 8: future timestamp
    - Row 9: stale timestamp
    - Row 10: invalid timestamp string
    """
    data = {
        "HospitalID": ["H101", "H102", "H103", "H104", "H102",
                        "H106", "H107", "H108", "H109", "H110"],
        "Name": ["City Hospital", "Metro Clinic", "", "Green Valley Hospital",
                 "Metro Clinic Copy", "Sunrise Medical", "Care Plus",
                 "East Side Hospital", "West Wing", "North Star"],
        "Beds": [100, 200, 150, 50, 200, 300, None, 120, 80, 250],
        "Latitude": [19.076, 19.082, 19.065, 19.100, 19.082,
                     999.0, 19.055, 19.040, 19.030, 19.020],
        "Longitude": [72.877, 72.880, 72.870, 72.900, 72.880,
                      72.860, 72.850, 72.840, 72.830, 72.820],
        "LastUpdated": [
            "2026-11-01", "2026-11-10", "2026-10-15", "2026-11-20",
            "2026-11-10", "2026-09-01", "2026-11-05", "2027-01-01",
            "2025-01-01", "not-a-date"
        ],
    }
    filepath = os.path.join(tmp_dir, "hospitals_a.csv")
    pd.DataFrame(data).to_csv(filepath, index=False)
    return filepath


@pytest.fixture
def synthetic_hospitals_b(tmp_dir):
    """
    SYNTHETIC hospital dataset B (CSV).
    8 records for comparison testing:
    - H101, H102, H104 shared with A
    - H201, H202 exclusive to B
    - H102 has different Beds value (conflict)
    - Fuzzy match candidate: "City Hosp" ~ "City Hospital"
    """
    data = {
        "HospitalID": ["H101", "H102", "H104", "H201", "H202",
                        "H203", "H204", "H205"],
        "Name": ["City Hosp", "Metro Clinic", "Green Valley Hospital",
                 "River Side Hospital", "Mountain View Clinic",
                 "Ocean Hospital", "Lake View", "Desert Medical"],
        "Beds": [100, 250, 50, 180, 90, 110, 70, 200],
        "Latitude": [19.076, 19.082, 19.100, 19.150, 19.200,
                     19.250, 19.300, 19.350],
        "Longitude": [72.877, 72.880, 72.900, 72.950, 73.000,
                      73.050, 73.100, 73.150],
        "LastUpdated": [
            "2026-11-05", "2026-11-15", "2026-11-20", "2026-10-01",
            "2026-11-18", "2026-11-01", "2026-10-15", "2026-11-10"
        ],
    }
    filepath = os.path.join(tmp_dir, "hospitals_b.csv")
    pd.DataFrame(data).to_csv(filepath, index=False)
    return filepath


@pytest.fixture
def synthetic_excel(tmp_dir):
    """
    SYNTHETIC Excel workbook with two sheets for testing.
    """
    filepath = os.path.join(tmp_dir, "test_data.xlsx")
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df_sheet1 = pd.DataFrame({
            "ID": ["001", "002", "003"],
            "Value": [10, 20, 30],
            "Category": ["A", "B", "C"],
        })
        df_sheet1.to_excel(writer, sheet_name="Sheet1", index=False)

        df_sheet2 = pd.DataFrame({
            "Code": ["X1", "X2"],
            "Score": [95.5, 88.0],
        })
        df_sheet2.to_excel(writer, sheet_name="Sheet2", index=False)

    return filepath


@pytest.fixture
def synthetic_geojson(tmp_dir):
    """
    SYNTHETIC GeoJSON file with Point features for testing.
    """
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [72.877, 19.076]},
                "properties": {"id": "G001", "name": "GeoPoint A", "value": 42}
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [72.880, 19.082]},
                "properties": {"id": "G002", "name": "GeoPoint B", "value": 55}
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [72.870, 19.065]},
                "properties": {"id": "G003", "name": "GeoPoint C", "value": None}
            },
        ]
    }
    filepath = os.path.join(tmp_dir, "test_points.geojson")
    with open(filepath, "w") as f:
        json.dump(geojson, f)
    return filepath


@pytest.fixture
def empty_csv(tmp_dir):
    """An empty CSV file (headers only, no data rows)."""
    filepath = os.path.join(tmp_dir, "empty.csv")
    with open(filepath, "w") as f:
        f.write("ID,Name,Value\n")
    return filepath


@pytest.fixture
def truly_empty_file(tmp_dir):
    """A completely empty file."""
    filepath = os.path.join(tmp_dir, "truly_empty.csv")
    with open(filepath, "w") as f:
        f.write("")
    return filepath


@pytest.fixture
def leading_zeros_csv(tmp_dir):
    """CSV with identifier columns that have leading zeros."""
    data = {
        "ZipCode": ["00501", "01001", "10001", "90210"],
        "Name": ["Holtsville", "Agawam", "New York", "Beverly Hills"],
        "State": ["NY", "MA", "NY", "CA"],
    }
    filepath = os.path.join(tmp_dir, "zipcodes.csv")
    pd.DataFrame(data).to_csv(filepath, index=False)
    return filepath


@pytest.fixture
def reference_time():
    """Fixed reference time for deterministic freshness tests."""
    return datetime(2026, 11, 24, 12, 0, 0)


@pytest.fixture
def corporate_excel(tmp_dir):
    """SYNTHETIC corporate performance Excel workbook for regression testing."""
    filepath = os.path.join(tmp_dir, "corporate_report.xlsx")
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        pd.DataFrame({
            "Name": ["Alice", "Bob", "Charlie"],
            "Sales": [50000, 65000, 45000],
            "Target": [55000, 60000, 50000],
        }).to_excel(writer, sheet_name="Employees", index=False)

        pd.DataFrame({
            "Month": ["Jan", "Feb", "Mar"],
            "Revenue": [100000, 120000, 115000],
        }).to_excel(writer, sheet_name="Monthly Revenue", index=False)

        pd.DataFrame({
            "Product": ["Widget A", "Widget B"],
            "Revenue": [80000, 95000],
        }).to_excel(writer, sheet_name="Products", index=False)

        pd.DataFrame({
            "Region": ["North", "South", "East", "West"],
            "Revenue": [50000, 60000, 45000, 70000],
        }).to_excel(writer, sheet_name="Regional Performance", index=False)

    return filepath


@pytest.fixture
def books_excel(tmp_dir):
    """SYNTHETIC books workbook for regression testing."""
    filepath = os.path.join(tmp_dir, "books_report.xlsx")
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        pd.DataFrame({
            "Title": ["Book One", "Book Two", "Book Three"],
            "Price": ["£10.99", "£25.50", "£7.00"],
            "Rating": ["Three", "Five", "One"],
            "Availability": ["In stock", "In stock", "Out of stock"],
        }).to_excel(writer, sheet_name="Books Data", index=False)

        pd.DataFrame({
            "Metric": ["Total Books", "Average Price"],
            "Value": [3, 14.50],
        }).to_excel(writer, sheet_name="Summary", index=False)

    return filepath
