# insights_generator.py

import pandas as pd

def generate_insights(employees_df, revenue_df, products_df, regional_df):
    """
    Generates text bullet point insights for Corporate Performance data.
    """
    insights = []

    # Revenue Growth
    if revenue_df is not None and not revenue_df.empty and "Revenue" in revenue_df.columns:
        start_revenue = revenue_df.iloc[0]["Revenue"]
        end_revenue = revenue_df.iloc[-1]["Revenue"]
        if start_revenue != 0:
            growth = ((end_revenue - start_revenue) / start_revenue) * 100
            insights.append(
                f"Revenue grew by {growth:.1f}% from {revenue_df.iloc[0]['Month']} to {revenue_df.iloc[-1]['Month']}."
            )

    # Top Performer
    if employees_df is not None and not employees_df.empty and "Sales" in employees_df.columns:
        top_employee = employees_df.loc[employees_df["Sales"].idxmax()]
        insights.append(
            f"{top_employee['Name']} is the top performer with sales of {top_employee['Sales']:,}."
        )

    # Best Region
    if regional_df is not None and not regional_df.empty and "Revenue" in regional_df.columns:
        top_region = regional_df.loc[regional_df["Revenue"].idxmax()]
        insights.append(
            f"{top_region['Region']} region generated the highest revenue."
        )

    # Best Product
    if products_df is not None and not products_df.empty and "Revenue" in products_df.columns:
        top_product = products_df.loc[products_df["Revenue"].idxmax()]
        insights.append(
            f"{top_product['Product']} contributes the highest product revenue."
        )

    return insights

def generate_scraped_insights(books_df):
    """
    Generates text bullet point insights for Web Scraped Books data.
    """
    if books_df is None or books_df.empty:
        return ["No scraped data available for insight generation."]

    df = books_df.copy()
    if "Price" in df.columns:
        df["Price_Clean"] = (
            df["Price"]
            .astype(str)
            .str.replace("£", "", regex=False)
            .str.replace("Â", "", regex=False)
            .str.strip()
        )
        df["Price_Clean"] = pd.to_numeric(df["Price_Clean"], errors="coerce")

    insights = []
    total_count = len(df)
    insights.append(f"A total of {total_count} items were successfully scraped from the target website.")

    if "Price_Clean" in df.columns and not df["Price_Clean"].dropna().empty:
        avg_price = df["Price_Clean"].mean()
        max_item = df.loc[df["Price_Clean"].idxmax()]
        min_item = df.loc[df["Price_Clean"].idxmin()]
        insights.append(f"Average item price is £{avg_price:.2f}.")
        insights.append(f"Highest priced item: '{max_item.get('Title', 'N/A')}' at £{max_item['Price_Clean']:.2f}.")
        insights.append(f"Lowest priced item: '{min_item.get('Title', 'N/A')}' at £{min_item['Price_Clean']:.2f}.")

    if "Rating" in df.columns:
        rating_counts = df["Rating"].value_counts()
        most_common_rating = rating_counts.idxmax()
        insights.append(f"The most common rating across scraped catalog is '{most_common_rating}' ({rating_counts[most_common_rating]} items).")

    if "Availability" in df.columns:
        in_stock = int(df["Availability"].astype(str).str.contains("In stock", case=False, na=False).sum())
        stock_pct = (in_stock / total_count) * 100 if total_count > 0 else 0
        insights.append(f"{in_stock} out of {total_count} items ({stock_pct:.1f}%) are currently in stock.")

    return insights

def generate_generic_insights(df_dict):
    """
    Fallback insight generator for arbitrary uploaded Excel workbooks.
    """
    insights = []
    for sheet_name, df in df_dict.items():
        if isinstance(df, pd.DataFrame) and not df.empty:
            insights.append(f"Sheet '{sheet_name}' contains {len(df)} rows and {len(df.columns)} columns.")
    return insights