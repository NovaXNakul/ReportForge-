# ranking_generator.py

import pandas as pd

def get_employee_ranking(employees_df):
    """
    Ranks employees by Sales in descending order.
    """
    if "Sales" in employees_df.columns:
        return employees_df.sort_values(by="Sales", ascending=False)
    return employees_df

def get_top_products(products_df, top_n=5):
    """
    Returns top N products by Revenue.
    """
    if "Revenue" in products_df.columns:
        return products_df.sort_values(by="Revenue", ascending=False).head(top_n)
    return products_df.head(top_n)

def get_top_books(books_df, top_n=5, sort_by="Price"):
    """
    Returns top N books sorted by Price or Rating.
    """
    df = books_df.copy()
    if sort_by == "Price" and "Price" in df.columns:
        df["Price_Clean"] = (
            df["Price"]
            .astype(str)
            .str.replace("£", "", regex=False)
            .str.replace("Â", "", regex=False)
            .str.strip()
        )
        df["Price_Clean"] = pd.to_numeric(df["Price_Clean"], errors="coerce")
        return df.sort_values(by="Price_Clean", ascending=False).head(top_n)
    return df.head(top_n)