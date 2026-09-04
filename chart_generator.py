# chart_generator.py

import os
import matplotlib.pyplot as plt
import pandas as pd
from config import OUTPUT_DIR

# Set aesthetic style
plt.style.use("ggplot")

def create_revenue_chart(revenue_df):
    plt.figure(figsize=(8, 4))
    plt.plot(
        revenue_df["Month"],
        revenue_df["Revenue"],
        marker="o",
        linewidth=3,
        color="#1F4E78"
    )
    plt.title("Monthly Revenue Trend", fontsize=14, fontweight="bold")
    plt.xlabel("Month", fontsize=11)
    plt.ylabel("Revenue ($)", fontsize=11)
    plt.grid(True, linestyle="--", alpha=0.6)

    chart_path = os.path.join(OUTPUT_DIR, "revenue_chart.png")
    plt.savefig(chart_path, bbox_inches="tight", dpi=150)
    plt.close()
    return chart_path

def create_region_chart(regional_df):
    plt.figure(figsize=(6, 6))
    colors = ["#1F4E78", "#2E75B6", "#5B9BD5", "#A5A5A5", "#ED7D31"]
    plt.pie(
        regional_df["Revenue"],
        labels=regional_df["Region"],
        autopct="%1.1f%%",
        colors=colors[:len(regional_df)],
        startangle=140
    )
    plt.title("Regional Revenue Distribution", fontsize=14, fontweight="bold")

    chart_path = os.path.join(OUTPUT_DIR, "region_chart.png")
    plt.savefig(chart_path, bbox_inches="tight", dpi=150)
    plt.close()
    return chart_path

def create_product_chart(products_df):
    plt.figure(figsize=(8, 4))
    plt.bar(
        products_df["Product"],
        products_df["Revenue"],
        color="#2E75B6",
        edgecolor="#1F4E78"
    )
    plt.title("Product Revenue Analysis", fontsize=14, fontweight="bold")
    plt.xlabel("Product", fontsize=11)
    plt.ylabel("Revenue ($)", fontsize=11)

    chart_path = os.path.join(OUTPUT_DIR, "product_chart.png")
    plt.savefig(chart_path, bbox_inches="tight", dpi=150)
    plt.close()
    return chart_path

def create_price_distribution_chart(books_df):
    """
    Generates a price distribution histogram for scraped books data.
    """
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
    else:
        df["Price_Clean"] = 0.0

    plt.figure(figsize=(8, 4))
    plt.hist(
        df["Price_Clean"].dropna(),
        bins=10,
        color="#2E75B6",
        edgecolor="white"
    )
    plt.title("Book Price Distribution", fontsize=14, fontweight="bold")
    plt.xlabel("Price (£)", fontsize=11)
    plt.ylabel("Number of Books", fontsize=11)

    chart_path = os.path.join(OUTPUT_DIR, "price_distribution.png")
    plt.savefig(chart_path, bbox_inches="tight", dpi=150)
    plt.close()
    return chart_path

def create_rating_distribution_chart(books_df):
    """
    Generates a bar chart of book ratings.
    """
    if "Rating" not in books_df.columns:
        return None

    counts = books_df["Rating"].value_counts()

    plt.figure(figsize=(7, 4))
    counts.plot(kind="bar", color="#1F4E78", edgecolor="none")
    plt.title("Book Ratings Distribution", fontsize=14, fontweight="bold")
    plt.xlabel("Rating Level", fontsize=11)
    plt.ylabel("Count", fontsize=11)
    plt.xticks(rotation=0)

    chart_path = os.path.join(OUTPUT_DIR, "rating_distribution.png")
    plt.savefig(chart_path, bbox_inches="tight", dpi=150)
    plt.close()
    return chart_path