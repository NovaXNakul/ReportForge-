# main.py

"""
CLI Entry point for XToP & Web Scraper Automation System.
Usage:
    python main.py                              # Runs full web scrape -> Excel -> PPT pipeline
    python main.py --mode full                  # Explicit full web scrape -> Excel -> PPT pipeline
    python main.py --mode convert --input file  # Converts specified Excel file to PPT
"""

import sys
import argparse
import os

from pipeline import run_web_scraping_pipeline, run_excel_to_ppt_pipeline
from config import DEFAULT_EXCEL_PATH, DEFAULT_PPT_PATH

def main():
    parser = argparse.ArgumentParser(
        description="XToP & Web Scraper Automation System - Integrated CLI"
    )
    parser.add_argument(
        "--mode",
        choices=["full", "scrape", "convert"],
        default="full",
        help="Operation mode: 'full' (Scrape -> Excel -> PPT), 'scrape' (Scrape -> Excel), 'convert' (Excel -> PPT)"
    )
    parser.add_argument(
        "--input",
        type=str,
        default=DEFAULT_EXCEL_PATH,
        help="Input Excel file path for 'convert' mode."
    )
    parser.add_argument(
        "--output-ppt",
        type=str,
        default=DEFAULT_PPT_PATH,
        help="Output path for generated PowerPoint deck."
    )

    args = parser.parse_args()

    print("=" * 60)
    print("XToP & Web Scraper Integration Suite")
    print("=" * 60)

    if args.mode in ["full", "scrape"]:
        print("\n[INFO] Mode: Web Scraping Pipeline")
        results = run_web_scraping_pipeline(ppt_path=args.output_ppt)
        print(f"\n[SUCCESS] Excel generated: {results['excel_path']}")
        print(f"[SUCCESS] PPT generated:   {results['ppt_path']}")

    elif args.mode == "convert":
        if not os.path.exists(args.input):
            print(f"[ERROR] Input Excel file not found at '{args.input}'")
            sys.exit(1)

        print(f"\n[INFO] Mode: Excel to PPT Conversion")
        out_ppt = run_excel_to_ppt_pipeline(excel_path=args.input, ppt_path=args.output_ppt)
        print(f"\n[SUCCESS] PPT generated: {out_ppt}")

if __name__ == "__main__":
    main()