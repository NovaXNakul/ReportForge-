# performance_analyzer.py

import pandas as pd

def analyze_performance(employees_df):
    """
    Calculates Sales Target Achievement % for Corporate Employees dataframe.
    """
    result = employees_df.copy()
    if "Sales" in result.columns and "Target" in result.columns:
        result["Achievement %"] = (result["Sales"] / result["Target"]) * 100
    return result

def analyze_scraped_data(books_df):
    """
    Analyzes scraped books DataFrame to produce aggregate KPI metrics.
    """
    if books_df is None or books_df.empty:
        return {}

    df = books_df.copy()

    # Ensure numeric price
    if "Price" in df.columns:
        df["Price_Clean"] = (
            df["Price"]
            .astype(str)
            .str.replace("£", "", regex=False)
            .str.replace("Â", "", regex=False)
            .str.strip()
        )
        df["Price_Clean"] = pd.to_numeric(df["Price_Clean"], errors="coerce")
    else:
        df["Price_Clean"] = 0.0

    total_books = len(df)
    avg_price = df["Price_Clean"].mean() if "Price_Clean" in df.columns else 0.0
    max_price = df["Price_Clean"].max() if "Price_Clean" in df.columns else 0.0
    min_price = df["Price_Clean"].min() if "Price_Clean" in df.columns else 0.0
    unique_ratings = df["Rating"].nunique() if "Rating" in df.columns else 0

    in_stock_count = total_books
    if "Availability" in df.columns:
        in_stock_count = int(
            df["Availability"].astype(str).str.contains("In stock", case=False, na=False).sum()
        )

    return {
        "Total Books": total_books,
        "Average Price": round(avg_price, 2),
        "Highest Price": round(max_price, 2),
        "Lowest Price": round(min_price, 2),
        "Unique Ratings": unique_ratings,
        "Available Books": in_stock_count,
    }