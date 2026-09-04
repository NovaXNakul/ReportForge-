# schema_config.py

"""
Configuration for Excel workbook schema mapping and dataset type detection.
Allows XToP & Web Scraper pipeline to dynamically adapt to different workbook structures.
"""

# Corporate Performance Workbook Schema (XTOP original)
WORKBOOK_SCHEMA = {
    "employees_sheet": "Employees",
    "revenue_sheet": "Monthly Revenue",
    "products_sheet": "Products",
    "regional_sheet": "Regional Performance",
}

# Column requirements for Corporate sheets
REQUIRED_COLUMNS = {
    "employees": ["Name", "Sales", "Target"],
    "revenue": ["Month", "Revenue"],
    "products": ["Product", "Revenue"],
    "regional": ["Region", "Revenue"],
}

# Scraped Books Dataset Schema
SCRAPED_BOOKS_COLUMNS = ["Title", "Price", "Rating", "Availability"]

def detect_dataset_type(df_dict):
    """
    Analyzes an uploaded or generated DataFrame dictionary and determines
    whether it matches Corporate Performance, Web Scraped Books, or Generic data.

    Returns:
        str: 'corporate', 'scraped_books', or 'generic'
    """
    if not isinstance(df_dict, dict):
        return "generic"

    sheet_names = list(df_dict.keys())
    
    # Check for Corporate Performance Schema
    corporate_count = 0
    for req_sheet in WORKBOOK_SCHEMA.values():
        if req_sheet in sheet_names:
            corporate_count += 1
            
    if corporate_count >= 3:
        return "corporate"
        
    # Check for Scraped Books Schema
    for sheet, df in df_dict.items():
        if hasattr(df, "columns"):
            cols = [str(c).strip().lower() for c in df.columns]
            if "price" in cols and ("rating" in cols or "title" in cols):
                return "scraped_books"
                
    return "generic"