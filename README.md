# 📊 XToP & Web Scraper Automation System

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.20+-FF4B4B.svg)](https://streamlit.io/)
[![OpenPyXL](https://img.shields.io/badge/OpenPyXL-3.0+-green.svg)](https://openpyxl.readthedocs.io/)
[![python-pptx](https://img.shields.io/badge/python--pptx-0.6+-orange.svg)](https://python-pptx.readthedocs.io/)

A powerful, unified Python application that combines **Automated Web Scraping to Formatted Excel Reports** and **XTOP (Excel to Automated PowerPoint Presentation Generator)** into a single, cohesive reporting suite.

Whether you need to scrape online market catalogs and generate dynamic executive slide decks, or convert internal corporate Excel spreadsheets directly into PowerPoint presentations, this platform handles the entire pipeline end-to-end.

---

## 🌟 Key Features

- 🌐 **Automated Web Scraping Engine**: Extract catalog items, pricing, star ratings, and stock availability automatically using BeautifulSoup4 and Requests.
- 📈 **OpenPyXL Formatted Excel Generator**: Auto-generates multi-sheet Excel workbooks (`Data` and `Summary Analytics`) complete with styled headers, thin cell borders, aligned text, currency formatting (`£#,##0.00`), and auto-fitted column widths.
- 🎨 **Dynamic PowerPoint Deck Builder**: Automatically compiles multi-slide PowerPoint presentation decks featuring Cover Pages, Executive Summaries, KPI Cards, Data Sample Tables, High-Resolution Charts (matplotlib), and Natural Language Strategic Insights.
- 🔄 **Smart Schema Detector**: Intelligent schema ingestion that automatically adapts slide layouts for **Corporate Performance Reports** (Employees, Revenue, Products, Regions) or **Web Scraped Datasets** (Books, E-commerce, Catalog items).
- 🖥️ **Interactive Streamlit Web Dashboard**: User-friendly web UI featuring live scraping, interactive data tables, sheet selectors, and 1-click downloads for `.xlsx` and `.pptx` files.
- 💻 **Integrated Command-Line Interface (CLI)**: Full support for automated batch processing, headless scraping, and offline file conversions.

---

## 🏗️ System Architecture & Data Flow

```text
               ┌──────────────────────────────┐
               │    1. Web Scraper Engine     │
               │         (scraper.py)         │
               └──────────────┬───────────────┘
                              │
                              ▼
 ┌───────────────────┐  ┌─────────────────────────────┐
 │  User Excel File  │  │  2. Excel Generator Engine  │
 │   (.xlsx Upload)  │  │     (excel_generator.py)    │
 └─────────┬─────────┘  └──────────────┬──────────────┘
           │                           │
           └──────────────┬────────────┘
                          │
                          ▼
           ┌─────────────────────────────┐
           │ 3. Excel Reader & Validator │
           │     (excel_reader.py &      │
           │      schema_config.py)      │
           └──────────────┬──────────────┘
                          │
                          ▼
           ┌─────────────────────────────┐
           │ 4. Analytics & Insights     │
           │ (performance_analyzer.py,   │
           │  insights_generator.py,     │
           │  ranking_generator.py)      │
           └──────────────┬──────────────┘
                          │
                          ▼
           ┌─────────────────────────────┐
           │ 5. Chart Generator Engine   │
           │    (chart_generator.py)     │
           └──────────────┬──────────────┘
                          │
                          ▼
           ┌─────────────────────────────┐
           │ 6. PPT Presentation Engine  │
           │      (ppt_generator.py)     │
           └──────────────┬──────────────┘
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
  ┌───────────────────┐       ┌───────────────────┐
  │  Streamlit Web UI │       │  CLI Pipeline     │
  │     (app.py)      │       │     (main.py)     │
  └───────────────────┘       └───────────────────┘
```

---

## 📁 Repository Structure

```text
Combine_Project/
│
├── app.py                      # Streamlit Web Application Interface
├── main.py                     # CLI Entry Point
├── pipeline.py                 # End-to-End Orchestrator Pipeline
├── config.py                   # Global Styling Tokens, Colors & Path Settings
├── schema_config.py            # Excel Schema Definitions & Detection Engine
│
├── scraper.py                  # Web Scraping Engine (BeautifulSoup4 + Requests)
├── excel_generator.py          # Excel Report Builder (OpenPyXL)
├── excel_reader.py             # Excel Workbook Ingestion & Schema Validator
│
├── performance_analyzer.py     # Corporate & Catalog Metric Calculators
├── insights_generator.py       # Natural Language Strategic Insights Engine
├── ranking_generator.py        # Item & Employee Ranking Utilities
├── chart_generator.py          # Matplotlib Visualizations Engine
├── ppt_generator.py            # Automated PowerPoint Deck Builder (python-pptx)
│
├── requirements.txt            # Python Package Dependencies
├── .gitignore                  # Git Ignore Rules
└── README.md                   # Project Documentation
```

---

## ⚡ Quick Start & Installation

### 1. Prerequisites
Ensure you have Python 3.8 or higher installed on your system.

### 2. Clone Repository & Install Dependencies
```bash
# Clone the repository
git clone https://github.com/your-username/Combine_Project.git
cd Combine_Project

# Install required dependencies
pip install -r requirements.txt
```

---

## 🚀 Usage Guide

### 1. Running the Streamlit Web Application
Launch the interactive dashboard with a single command:
```bash
streamlit run app.py
```
The web dashboard provides two primary modes:
- **Tab 1: 🌐 Web Scraper -> Excel & PPT**: Enter target URL, run full scraping, preview metrics/data tables, and download `.xlsx` & `.pptx` files.
- **Tab 2: 📄 XTOP: Excel -> PPT Generator**: Drag and drop any Excel workbook, preview sheets, validate schema, and generate PowerPoint presentation decks.

### 2. Running via Command Line Interface (CLI)

- **Full Pipeline Mode** *(Scrape Web -> Generate Excel -> Build PPT)*:
  ```bash
  python main.py --mode full
  ```

- **Scrape Only Mode** *(Scrape Web -> Generate Excel)*:
  ```bash
  python main.py --mode scrape
  ```

- **XTOP Conversion Mode** *(Convert Existing Excel to PPT)*:
  ```bash
  python main.py --mode convert --input data/report.xlsx --output-ppt output/presentation.pptx
  ```

---

## 📊 Supported Workbook Schemas

### 1. Corporate Performance Schema (XTOP Original)
Requires sheets:
- `Employees` (Columns: `Name`, `Sales`, `Target`)
- `Monthly Revenue` (Columns: `Month`, `Revenue`)
- `Products` (Columns: `Product`, `Revenue`)
- `Regional Performance` (Columns: `Region`, `Revenue`)

### 2. Web Scraped / Catalog Schema
Requires columns:
- `Title` / Item Name
- `Price` (auto-cleaned and formatted)
- `Rating`
- `Availability`

---

## 🛠️ Tech Stack

- **Frontend**: [Streamlit](https://streamlit.io/)
- **Data Scraping**: [Requests](https://requests.readthedocs.io/) & [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/)
- **Data Processing**: [Pandas](https://pandas.pydata.org/)
- **Excel Formatting**: [OpenPyXL](https://openpyxl.readthedocs.io/)
- **Visualization**: [Matplotlib](https://matplotlib.org/)
- **PowerPoint Generation**: [python-pptx](https://python-pptx.readthedocs.io/)

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check out the issues page or submit a pull request.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
