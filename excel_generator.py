# excel_generator.py

import os
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from config import DEFAULT_CSV_PATH, DEFAULT_EXCEL_PATH, COLOR_PRIMARY_HEX

def generate_excel(df_or_path=None, output_path=DEFAULT_EXCEL_PATH):
    """
    Generates a professionally formatted multi-sheet Excel workbook from a DataFrame or CSV file.
    
    Sheets:
    1. Main Data Sheet (formatted table, auto-width, borders, price styling)
    2. Summary Analytics Dashboard Sheet

    Args:
        df_or_path: pandas DataFrame or path to CSV file. Defaults to data/books_data.csv.
        output_path: Path where generated .xlsx file will be saved.

    Returns:
        str: Absolute path to the generated Excel file.
    """
    # Load DataFrame
    if df_or_path is None or (isinstance(df_or_path, str) and df_or_path == DEFAULT_CSV_PATH):
        if not os.path.exists(DEFAULT_CSV_PATH):
            raise FileNotFoundError(f"Source CSV data not found at '{DEFAULT_CSV_PATH}'")
        df = pd.read_csv(DEFAULT_CSV_PATH)
    elif isinstance(df_or_path, str):
        df = pd.read_csv(df_or_path)
    elif isinstance(df_or_path, pd.DataFrame):
        df = df_or_path.copy()
    else:
        raise ValueError("Invalid argument for df_or_path. Provide a DataFrame or CSV path.")

    # Clean Price Column if present
    if "Price" in df.columns:
        df["Price_Clean"] = (
            df["Price"]
            .astype(str)
            .str.replace("£", "", regex=False)
            .str.replace("Â", "", regex=False)
            .str.strip()
        )
        df["Price_Clean"] = pd.to_numeric(df["Price_Clean"], errors="coerce")

    # Create Workbook
    workbook = Workbook()

    # ==========================
    # Sheet 1: Main Data
    # ==========================
    sheet = workbook.active
    sheet.title = "Books Data"

    headers = list(df.columns)

    # Header Formatting
    header_fill = PatternFill(fill_type="solid", start_color=COLOR_PRIMARY_HEX)
    header_font = Font(bold=True, color="FFFFFF", size=11)
    center_align = Alignment(horizontal="center", vertical="center")

    for col_num, header in enumerate(headers, start=1):
        cell = sheet.cell(row=1, column=col_num)
        cell.value = header
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    # Data Rows Insertion
    for row_num, row_values in enumerate(df.values, start=2):
        for col_num, val in enumerate(row_values, start=1):
            sheet.cell(row=row_num, column=col_num).value = val

    # Thin Border Styling
    thin_border = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC")
    )

    for row in sheet.iter_rows():
        for cell in row:
            cell.border = thin_border

    # Format Price Column
    if "Price" in headers:
        price_col_idx = headers.index("Price") + 1
        for r in range(2, len(df) + 2):
            cell = sheet.cell(row=r, column=price_col_idx)
            if isinstance(cell.value, (int, float)):
                cell.number_format = "£#,##0.00"

    # Auto Column Widths
    for column in sheet.columns:
        max_length = 0
        col_letter = column[0].column_letter
        for cell in column:
            if cell.value is not None:
                max_length = max(max_length, len(str(cell.value)))
        sheet.column_dimensions[col_letter].width = max(max_length + 4, 12)

    # ==========================
    # Sheet 2: Summary Analytics
    # ==========================
    summary = workbook.create_sheet("Summary")

    summary["A1"] = "Metric"
    summary["B1"] = "Value"
    summary["A1"].font = Font(bold=True, color="FFFFFF")
    summary["B1"].font = Font(bold=True, color="FFFFFF")
    summary["A1"].fill = header_fill
    summary["B1"].fill = header_fill

    summary["A2"] = "Total Books"
    summary["B2"] = len(df)

    summary["A3"] = "Unique Ratings"
    summary["B3"] = df["Rating"].nunique() if "Rating" in df.columns else 0

    summary["A4"] = "Available Books"
    if "Availability" in df.columns:
        summary["B4"] = int(df["Availability"].astype(str).str.contains("In stock", case=False, na=False).sum())
    else:
        summary["B4"] = len(df)

    if "Price_Clean" in df.columns and not df["Price_Clean"].dropna().empty:
        summary["A5"] = "Average Price (£)"
        summary["B5"] = round(df["Price_Clean"].mean(), 2)

        summary["A6"] = "Highest Price (£)"
        summary["B6"] = round(df["Price_Clean"].max(), 2)

        summary["A7"] = "Lowest Price (£)"
        summary["B7"] = round(df["Price_Clean"].min(), 2)

    for row_idx in range(1, 8):
        for col_idx in [1, 2]:
            cell = summary.cell(row=row_idx, column=col_idx)
            cell.border = thin_border

    for col in summary.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        summary.column_dimensions[col[0].column_letter].width = max(max_len + 5, 15)

    # Save Workbook
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    workbook.save(output_path)
    print(f"Excel report generated successfully at '{output_path}'")
    return output_path