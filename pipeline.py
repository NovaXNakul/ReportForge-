# pipeline.py

"""
Unified End-to-End Orchestrator Pipeline.
Connects: Web Scraper -> Excel Generator -> Excel Processing/Analysis -> PowerPoint Generator.
"""

import os
from scraper import scrape_books
from excel_generator import generate_excel
from excel_reader import read_excel
from ppt_generator import create_ppt
from config import DEFAULT_CSV_PATH, DEFAULT_EXCEL_PATH, DEFAULT_PPT_PATH

def run_web_scraping_pipeline(url="https://books.toscrape.com/", excel_path=DEFAULT_EXCEL_PATH, ppt_path=DEFAULT_PPT_PATH):
    """
    Executes full web scraping -> Excel generation -> PPT generation workflow.

    Returns:
        dict: Paths to generated CSV, Excel, and PPT files.
    """
    print("=" * 60)
    print("STEP 1: Executing Web Scraper...")
    print("=" * 60)
    df = scrape_books(url=url, output_csv=DEFAULT_CSV_PATH)
    if df is None or df.empty:
        raise RuntimeError("Web scraping failed or produced no data.")

    print("\n" + "=" * 60)
    print("STEP 2: Generating Formatted Excel Workbook...")
    print("=" * 60)
    generated_excel = generate_excel(df_or_path=df, output_path=excel_path)

    print("\n" + "=" * 60)
    print("STEP 3: Reading Excel Workbook & Detecting Schema...")
    print("=" * 60)
    data_dict = read_excel(generated_excel)

    print("\n" + "=" * 60)
    print("STEP 4: Generating PowerPoint Presentation Deck...")
    print("=" * 60)
    create_ppt(data_dict, output_path=ppt_path)

    print("\n" + "=" * 60)
    print("Pipeline Execution Completed Successfully!")
    print("=" * 60)

    return {
        "csv_path": DEFAULT_CSV_PATH,
        "excel_path": generated_excel,
        "ppt_path": ppt_path
    }

def run_excel_to_ppt_pipeline(excel_path, ppt_path=DEFAULT_PPT_PATH):
    """
    Executes direct Excel -> PPT generation (XTOP functionality).

    Returns:
        str: Path to generated PPT file.
    """
    print("=" * 60)
    print(f"Reading Excel file from '{excel_path}'...")
    print("=" * 60)
    data_dict = read_excel(excel_path)

    print("\n" + "=" * 60)
    print("Generating PowerPoint Presentation Deck...")
    print("=" * 60)
    create_ppt(data_dict, output_path=ppt_path)

    print("\n" + "=" * 60)
    print(f"PowerPoint generated successfully at '{ppt_path}'!")
    print("=" * 60)

    return ppt_path
