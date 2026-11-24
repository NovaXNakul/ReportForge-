# 📊 ReportForge 2.0 — Data Intelligence & Geospatial Analytics Platform

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.20+-FF4B4B.svg)](https://streamlit.io/)
[![OpenPyXL](https://img.shields.io/badge/OpenPyXL-3.0+-green.svg)](https://openpyxl.readthedocs.io/)
[![python-pptx](https://img.shields.io/badge/python--pptx-0.6+-orange.svg)](https://python-pptx.readthedocs.io/)
[![Scikit-Learn](https://img.shields.io/badge/scikit--learn-1.2+-F7931E.svg)](https://scikit-learn.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**ReportForge 2.0** is an enterprise data intelligence, automated reporting, and geospatial analytics platform. Originally developed for automated web scraping and Microsoft Office document synthesis (Excel & PowerPoint), ReportForge 2.0 has been upgraded with rigorous multi-source data ingestion, comprehensive data quality validation, fuzzy/spatial entity resolution, statistical and machine learning anomaly detection, and density-based spatial clustering.

---

## 📌 Problem Statement

Organizations dealing with multi-vendor geospatial feeds, tabular business registries, and external catalogs frequently encounter:
1. **Source Discrepancies & Coverage Gaps**: Inconsistent identifiers, schema divergence, typographical variance, and conflicting attributes across disparate data providers.
2. **Data Quality Degradation**: Missing required fields, invalid coordinates outside geographic ranges, non-unique business keys, and stale timestamps.
3. **Statistical & Multivariate Outliers**: Incomplete or erroneous numerical values that distort operational reporting and regional decision-making.
4. **Spatial Density Blindspots**: Inability to systematically cluster geographic point-of-interest (POI) networks or isolate remote entities without introducing flat Cartesian distortion.
5. **Disconnected Reporting Workflows**: Manual, error-prone translation of statistical analysis into executive-ready presentation decks and auditable spreadsheets.

ReportForge 2.0 bridges raw data ingestion with executive intelligence by combining rigorous data quality dimensions, deterministic entity resolution, unsupervised machine learning, and automated multi-sheet Excel and multi-slide PowerPoint report generation.

---

## 🛠️ Technology Stack

- **Core & Data Processing**: Python 3.8+, Pandas, NumPy
- **Machine Learning & Spatial Algorithms**: Scikit-Learn (`IsolationForest`, `DBSCAN`, `BallTree`), RapidFuzz (Levenshtein token sorting)
- **Web Scraping**: BeautifulSoup4, Requests
- **Presentation & Office Automation**: OpenPyXL (Excel styling, conditional formatting, borders), python-pptx (Shape builders, PowerPoint slides)
- **Web UI & Visualization**: Streamlit (Reactive component architecture), Matplotlib (Seaborn-styled distribution plots and geospatial scatter)
- **Quality Assurance**: Pytest (Deterministic synthetic fixtures and regression test suites)

---

## 🌟 Core Functionalities

### 1. Data Quality & Multi-Source Comparison (Feature 1)
- **Multi-Format Ingestion (`data_ingestion.py`)**:
  - Ingests **CSV**, **Excel (.xlsx)** with sheet selection, and **GeoJSON** (`Feature` / `FeatureCollection` with Point geometries). Legacy `.xls` is safely rejected.
  - Preserves leading zeros in identifiers (read initially as text), retains source provenance (`source_name`, `filename`, `sheet_name`), maintains 1-based original row tracking (`_original_row_id`), and disambiguates colliding normalized column headers.
- **Four Quality Dimensions (`data_quality_analyzer.py`)**:
  - **Completeness**: `(Non-missing required cells / Total expected required cells) × 100`. Missing required columns penalize completeness rather than silently disappearing.
  - **Validity**: `(Passing validation checks / Total applicable checks) × 100`. Validates ranges, non-negative constraints, categories, dates, and geographic bounds (latitude $[-90, 90]^\circ$, longitude $[-180, 180]^\circ$).
  - **Uniqueness**: `(Distinct business keys / Total rows with usable keys) × 100`.
  - **Freshness**: `(Records within freshness window / Valid timestamp records) × 100`. Future timestamps are flagged as invalid anomalies.
- **Multi-Source Entity Resolution (`source_comparator.py`)**:
  - **Exact Matching**: Canonical normalized key matching (`strip().lower()`) with strict one-to-one mapping.
  - **Fuzzy Name Matching**: RapidFuzz `token_sort_ratio` with configurable similarity thresholds and ambiguity margins (`fuzzy_margin`).
  - **Geographic Proximity Matching**: Haversine distance in metres. Proximity serves as a candidate filter or combines with name matching; it never overrides conflicting reliable business IDs.
  - **Jaccard Similarity**: Mathematical Jaccard coefficient $|A \cap B| / |A \cup B|$ strictly bounded in $[0, 1]$, labeled as estimated when approximate matching is used, and returning `N/A` on empty unions.
  - **Mutually Exclusive Classification**: Every row is strictly categorized into `matched`, `ambiguous`, `unmatchable`, or `exclusive`.

### 2. Statistical/ML Anomaly Detection & Spatial Clustering (Feature 3)
- **Univariate Statistical Detection (`anomaly_detector.py`)**:
  - **Interquartile Range (IQR)**: Linear-interpolated order statistics ($Q_1$, $Q_3$, $\text{IQR} = Q_3 - Q_1$). Flags values outside $[Q_1 - k \times \text{IQR},\; Q_3 + k \times \text{IQR}]$ with configurable $k$ (default 1.5). Zero IQR and constant columns are safely handled without division by zero or false positives.
  - **Z-Score**: Population standard deviation ($\text{ddof}=0$) with user threshold (default 3.0). Zero-variance constant columns are assigned $Z = 0.0$ safely.
- **Multivariate Unsupervised ML (`anomaly_detector.py`)**:
  - **Isolation Forest**: Scikit-Learn tree ensemble (`n_estimators=100`, configurable contamination $\in (0, 0.5]$ or `'auto'`, fixed `random_state=42`).
  - Evaluates complete cases across selected feature dimensions; incomplete rows are tracked in `excluded_details`.
  - Calculates continuous anomaly scores via `decision_function()` where negative scores indicate higher abnormality.
- **Spatial Density Clustering (`clustering_engine.py`)**:
  - **DBSCAN with Haversine Metric**: Clusters geographic coordinates using spherical great-circle distance ($R = 6371.0\text{ km}$).
  - Converts degree coordinates to radians in `[latitude, longitude]` order. Epsilon threshold is converted via $\varepsilon_{\text{radians}} = \varepsilon_{\text{km}} / 6371.0$.
  - Distinguishes between **excluded invalid coordinates** (e.g. out-of-range latitude or missing values) and **algorithmic noise points** (`-1`, valid coordinates that are geographically isolated).
  - Tracks core points using `dbscan.core_sample_indices_`.

### 3. Unified Automated Reporting & Interactive Dashboard
- **Shared Architecture (`AnalysisBundle` & `Feature3Bundle`)**: Decouples analytical engines from presentation. UI charts, Excel workbooks, and PowerPoint decks consume the exact same bundled result objects, eliminating discrepancies.
- **Multi-Sheet Excel Reports**: Auto-generated 7-sheet workbooks with professional navy headers, auto-adjusted column widths, and cell borders.
- **Executive PowerPoint Decks**: Formatted 6-slide presentations with KPI stat cards, findings callouts, and structured tables.
- **Streamlit Interactive UI (`app.py`)**: Modular 4-tab interface with session-state invalidation (via SHA-256 parameter hashing) ensuring stale results cannot be downloaded.

### 4. Preserved Original Workflows
- **Automated Web Scraping Engine (`scraper.py`)**: Scrapes e-commerce/catalog data into structured datasets.
- **XTOP Engine (`excel_reader.py`, `ppt_generator.py`)**: Auto-converts Corporate Performance and catalog workbooks into PowerPoint presentations.

---

## 🏗️ System Architecture

```text
Multiple Dataset Ingestion (.csv, .xlsx, .geojson)
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│ 1. Data Ingestion & Preprocessing (data_ingestion.py)  │
│    Raw Preservation + Normalization + Provenance       │
└────────────────────────────┬───────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────┐
│ 2. Data Quality │ │ 3. Multi-Source │ │ 4. Feature 3 Analytics  │
│    Analyzer     │ │    Comparator   │ │    (anomaly_detector.py │
│ (data_quality_  │ │ (source_compa-  │ │     clustering_engine)  │
│  analyzer.py)   │ │  rator.py)      │ │   IQR, Z-Score, iForest,│
│ Completeness,   │ │ Exact, Fuzzy,   │ │   DBSCAN (Haversine km) │
│ Validity, Keys  │ │ Geo, Jaccard    │ └────────────┬────────────┘
└────────┬────────┘ └────────┬────────┘              │
         │                   │                       │
         └─────────┬─────────┘                       │
                   ▼                                 ▼
       ┌────────────────────────┐        ┌────────────────────────┐
       │ Shared AnalysisBundle  │        │  Shared Feature3Bundle │
       │ (dq_report_generator)  │        │(feature3_report_gene-) │
       └───────────┬────────────┘        └───────────┬────────────┘
                   │                                 │
     ┌─────────────┼─────────────┐     ┌─────────────┼─────────────┐
     ▼             ▼             ▼     ▼             ▼             ▼
Streamlit UI  Excel Report   PPT Deck Streamlit UI  Excel Report   PPT Deck
 (Tab 3)       (6 Sheets)    (5 Slides)(Tab 4)       (7 Sheets)    (6 Slides)
```

---

## 📁 Repository Structure

```text
ReportForge-/
├── app.py                         # Streamlit Web Application (Tabs 1, 2, 3 & 4)
├── main.py                        # Headless CLI entry point (original workflows)
├── pipeline.py                    # Scraper and XTOP pipeline orchestrator
├── config.py                      # Theme colors, styling tokens, and default paths
├── schema_config.py               # Excel workbook schema definitions & detection
├── scraper.py                     # Web scraping engine (BeautifulSoup4 + Requests)
├── excel_generator.py             # Formatted Excel report builder (OpenPyXL)
├── excel_reader.py                # Excel workbook ingestion & schema validator
├── performance_analyzer.py        # Catalog and corporate metric calculations
├── insights_generator.py          # Strategic natural language insights engine
├── ranking_generator.py           # Item and employee ranking utilities
├── chart_generator.py             # Matplotlib visual chart generation engine
├── ppt_generator.py               # Automated PowerPoint deck builder (python-pptx)
│
├── data_ingestion.py              # Feature 1: CSV, XLSX & GeoJSON ingestion
├── data_quality_analyzer.py       # Feature 1: Completeness, validity, uniqueness, freshness
├── source_comparator.py           # Feature 1: Exact, fuzzy, geo entity matching & Jaccard
├── dq_report_generator.py         # Feature 1: Shared AnalysisBundle -> Excel & PPT reports
│
├── anomaly_detector.py            # Feature 3: Univariate (IQR, Z-Score) & Multivariate (iForest)
├── clustering_engine.py           # Feature 3: DBSCAN spatial clustering (Haversine km)
├── feature3_report_generator.py    # Feature 3: Feature3Bundle -> Excel & PPT reports
├── feature3_ui.py                 # Feature 3: Modular Streamlit Tab 4 component
│
├── data/                          # Sample and demonstration datasets
│   ├── books_data.csv             # Sample scraped catalog data
│   ├── report.xlsx                # Sample corporate performance workbook
│   ├── uploaded_report.xlsx       # Sample evaluation workbook
│   └── sample_hospitals_anomaly.csv # Feature 3: Synthetic hospital dataset (40 POIs)
│
├── tests/                         # Pytest automated test suite (113 deterministic tests)
│   ├── conftest.py                # Synthetic dataset fixtures
│   ├── test_data_ingestion.py     # Ingestion & normalization tests
│   ├── test_data_quality.py       # Quality dimension metrics & rules
│   ├── test_source_comparator.py  # Exact, fuzzy, geo matching & Jaccard tests
│   ├── test_audit_bugs.py         # Regression tests for adversarial edge cases
│   ├── test_anomaly_detector.py   # IQR, Z-Score & Isolation Forest unit tests
│   ├── test_clustering_engine.py  # DBSCAN spatial clustering unit tests
│   ├── test_feature3_reports.py   # Feature 3 Excel & PPT bundle integration tests
│   └── test_regression.py         # Original scraper and XTOP regression tests
│
├── requirements.txt               # Project dependencies
├── .gitignore                     # Git exclusion rules
└── README.md                      # Platform documentation
```

---

## ⚡ Installation & Setup

### Prerequisites
- Python 3.8 or higher (Tested on Python 3.10, 3.11, 3.12, 3.14)
- Git

### Installation Steps
```powershell
# 1. Clone repository
git clone https://github.com/NovaXNakul/ReportForge-.git
cd ReportForge-

# 2. Checkout the development branch
git checkout feature/reportforge-v2

# 3. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 4. Install dependencies
pip install -r requirements.txt
```

---

## 🚀 Usage Guide

### 1. Launching the Interactive Web Application
```powershell
streamlit run app.py
```
The application opens in your browser with four modular tabs:
- **Tab 1: `🌐 Web Scraper -> Excel & PPT`**: Execute automated web scraping from online catalogs into formatted Excel reports and PowerPoint presentations.
- **Tab 2: `📄 XTOP: Excel -> PPT Generator`**: Upload corporate Excel workbooks and generate styled slide decks.
- **Tab 3: `🔍 Data Intelligence — Quality & Source Comparison`**: Ingest multiple datasets (CSV, XLSX, GeoJSON), configure quality validation rules, execute entity resolution (exact, fuzzy, spatial), analyze attribute conflicts, and export reports.
- **Tab 4: `🎯 Anomaly Detection & Spatial Clustering`**: Load uploaded files or the built-in demonstration dataset, execute statistical and ML anomaly detection, run DBSCAN spatial clustering, inspect interactive visualizations, and download multi-sheet Excel workbooks and executive slide decks.

### 2. Demonstration Dataset Walkthrough
To test Feature 3 immediately:
1. In Tab 4, select **"Use Sample Hospital Dataset (40 records with known outliers & clusters)"**.
2. Select numerical columns: `bed_count`, `icu_beds`, `daily_admissions`, `er_wait_time_min`.
3. Select spatial coordinates: Latitude = `latitude`, Longitude = `longitude`.
4. Run analysis with default parameters ($k=1.5$, $Z=3.0$, contamination $=0.05$, $\varepsilon=5.0\text{ km}$, $\text{min\_samples}=3$).
5. The platform correctly detects:
   - **Univariate Outliers**: Hospital `H031` (1,500 beds) and `H032` (240 min ER wait time).
   - **Multivariate Outliers**: Hospital `H033` (500 beds with only 8 ICU beds) and `H034` (35 beds with 30 ICU beds).
   - **Spatial Density**: 2 distinct spatial clusters (Central Mumbai and South Mumbai) and 4 isolated noise points (Pune, Nashik, Alibaug, Matheran).
   - **Data Governance**: Hospital `H039` (missing bed count) and `H040` (latitude $95^\circ > 90^\circ$) are logged in excluded audit records rather than crashing the models or distorting clusters.

### 3. Command-Line Workflows (Original Functionality)
```powershell
# Run full scraping and presentation pipeline
python main.py --mode full

# Run scraping only
python main.py --mode scrape

# Convert an existing Excel workbook to PowerPoint
python main.py --mode convert --input data/report.xlsx --output-ppt output/presentation.pptx
```

---

## 🧪 Automated Testing

ReportForge 2.0 includes a deterministic Pytest test suite with **113 automated tests** covering all data quality dimensions, adversarial matching edge cases, statistical formulas, ML models, and report generators.

To execute the test suite:
```powershell
python -m pytest tests/ -v
```

For a compact execution summary:
```powershell
python -m pytest tests/ -q
```
*Expected result: 113 passed in under 10 seconds.*

---

## ⚠️ Known Limitations

1. **Quadratic Match Complexity**: Pairwise fuzzy string matching (`fuzz.token_sort_ratio`) and brute-force spatial candidate pairing operate in $O(n \times m)$ time. For production workloads exceeding 50,000 records per source, spatial indexing (e.g. H3 discrete global grid or R-tree) and string blocking should be applied.
2. **GeoJSON Geometry Support**: GeoJSON ingestion extracts coordinates directly for `Point` geometries. Complex geometries (`Polygon`, `LineString`) ingest feature properties with `None` coordinates; `GeometryCollection` is rejected.
3. **Spherical Earth Assumption**: DBSCAN spatial clustering applies Haversine distance on a spherical Earth with mean radius $R = 6371.0\text{ km}$. Ellipsoidal geodesic formulas (e.g., Vincenty or Karney) are not used, which introduces an acceptable error margin of $< 0.5\%$ for local and regional clustering.
4. **Timezone Assumptions**: Timestamps default to UTC-naive normalization; mixed-timezone datasets are converted to UTC-naive representations for uniform comparison.

---

## 🔮 Future Enhancements (Planned Feature 2)

- **Geospatial Coverage & Analytics Dashboard (Feature 2)**:
  - Integration of interactive slippy map layers (Folium/Leaflet) for visual POI exploration.
  - Hexagonal spatial indexing (Uber H3) for regional coverage density heatmaps.
  - Administrative boundary polygon aggregation and geographic gap identification across data sources.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
