# excel_reader.py

import pandas as pd
from schema_config import WORKBOOK_SCHEMA, REQUIRED_COLUMNS, detect_dataset_type

def read_excel(file_path):
    """
    Reads an Excel file and returns a dictionary of DataFrames along with dataset metadata.
    
    Supports:
    - Corporate Performance multi-sheet workbooks
    - Web Scraped workbooks (Books Data + Summary)
    - Generic single/multi-sheet workbooks

    Returns:
        dict: Sheet name -> DataFrame
    """
    # Read all sheets from Excel file
    try:
        all_sheets = pd.read_excel(file_path, sheet_name=None)
    except Exception as e:
        raise ValueError(f"Unable to read Excel file: {str(e)}")

    if not all_sheets:
        raise ValueError("Excel file is empty.")

    # Determine schema type
    dataset_type = detect_dataset_type(all_sheets)

    if dataset_type == "corporate":
        # Validate required corporate sheets
        missing_sheets = [
            sheet for sheet in WORKBOOK_SCHEMA.values() if sheet not in all_sheets
        ]
        if missing_sheets:
            raise KeyError(
                f"Missing required sheet(s): {missing_sheets}. "
                f"Expected sheets: {list(WORKBOOK_SCHEMA.values())}"
            )
        
        # Map to standardized corporate dict
        result_dict = {
            "Employees": all_sheets[WORKBOOK_SCHEMA["employees_sheet"]],
            "Monthly Revenue": all_sheets[WORKBOOK_SCHEMA["revenue_sheet"]],
            "Products": all_sheets[WORKBOOK_SCHEMA["products_sheet"]],
            "Regional Performance": all_sheets[WORKBOOK_SCHEMA["regional_sheet"]],
        }

        # Validate columns
        dfs_to_check = {
            "employees": result_dict["Employees"],
            "revenue": result_dict["Monthly Revenue"],
            "products": result_dict["Products"],
            "regional": result_dict["Regional Performance"],
        }

        for sheet_key, df in dfs_to_check.items():
            missing_cols = set(REQUIRED_COLUMNS[sheet_key]) - set(df.columns)
            if missing_cols:
                raise ValueError(
                    f"Sheet '{sheet_key}' missing column(s): {missing_cols}. "
                    f"Expected: {REQUIRED_COLUMNS[sheet_key]}"
                )
        return result_dict

    elif dataset_type == "scraped_books":
        # Return all sheets, prioritizing main data sheet
        main_sheet_name = None
        for name in all_sheets.keys():
            cols = [str(c).strip().lower() for c in all_sheets[name].columns]
            if "price" in cols or "title" in cols:
                main_sheet_name = name
                break
        
        if not main_sheet_name:
            main_sheet_name = list(all_sheets.keys())[0]

        return {
            "Books Data": all_sheets[main_sheet_name],
            "Summary": all_sheets.get("Summary", pd.DataFrame())
        }

    else:
        # Generic Excel workbook
        return all_sheets