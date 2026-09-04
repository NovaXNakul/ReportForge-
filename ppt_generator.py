# ppt_generator.py

import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.dml.color import RGBColor

from schema_config import detect_dataset_type
from performance_analyzer import analyze_performance, analyze_scraped_data
from insights_generator import generate_insights, generate_scraped_insights, generate_generic_insights
from chart_generator import (
    create_revenue_chart,
    create_region_chart,
    create_product_chart,
    create_price_distribution_chart,
    create_rating_distribution_chart
)
from config import DEFAULT_PPT_PATH, PRIMARY_COLOR, SECONDARY_COLOR, WHITE_COLOR

def create_ppt(data_dict, output_path=DEFAULT_PPT_PATH):
    """
    Generates a professionally styled PowerPoint presentation based on dataset structure.
    
    Supports:
    - Corporate Performance datasets (Employees, Monthly Revenue, Products, Regional Performance)
    - Web Scraped datasets (Books Data, Summary)
    - Generic datasets
    """
    dataset_type = detect_dataset_type(data_dict)

    if dataset_type == "corporate":
        return _create_corporate_ppt(data_dict, output_path)
    elif dataset_type == "scraped_books":
        return _create_scraped_books_ppt(data_dict, output_path)
    else:
        return _create_generic_ppt(data_dict, output_path)

def _create_corporate_ppt(data_dict, output_path):
    employees_df = data_dict["Employees"]
    revenue_df = data_dict["Monthly Revenue"]
    products_df = data_dict["Products"]
    regional_df = data_dict["Regional Performance"]

    performance_df = analyze_performance(employees_df)
    total_employees = len(employees_df)
    total_sales = employees_df["Sales"].sum()
    top_performer = employees_df.loc[employees_df["Sales"].idxmax(), "Name"]
    best_region = regional_df.loc[regional_df["Revenue"].idxmax(), "Region"]
    total_product_revenue = products_df["Revenue"].sum()

    insights = generate_insights(employees_df, revenue_df, products_df, regional_df)

    revenue_chart = create_revenue_chart(revenue_df)
    region_chart = create_region_chart(regional_df)
    product_chart = create_product_chart(products_df)

    ppt = Presentation()

    # Slide 1: Cover Page
    slide = ppt.slides.add_slide(ppt.slide_layouts[0])
    slide.shapes.title.text = "Company Performance Report"
    slide.placeholders[1].text = "Generated Automatically via XToP Suite"

    # Slide 2: Executive Summary
    slide = ppt.slides.add_slide(ppt.slide_layouts[1])
    slide.shapes.title.text = "Executive Summary"
    slide.placeholders[1].text = (
        f"• Total Employees: {total_employees}\n"
        f"• Total Sales Volume: ${total_sales:,}\n"
        f"• Top Performer: {top_performer}\n"
        f"• Best Performing Region: {best_region}\n"
        f"• Total Product Revenue: ${total_product_revenue:,}"
    )

    # Slide 3: KPI Dashboard
    slide = ppt.slides.add_slide(ppt.slide_layouts[5])
    slide.shapes.title.text = "KPI Dashboard"
    kpis = [
        ("Total Employees", str(total_employees)),
        ("Total Sales", f"${total_sales:,}"),
        ("Top Performer", top_performer),
        ("Top Region", best_region)
    ]
    positions = [(0.8, 1.8), (5.2, 1.8), (0.8, 4.0), (5.2, 4.0)]

    for i in range(4):
        left, top = Inches(positions[i][0]), Inches(positions[i][1])
        card = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, left, top, Inches(4.0), Inches(1.8)
        )
        card.fill.solid()
        card.fill.fore_color.rgb = PRIMARY_COLOR
        card.text = f"{kpis[i][0]}\n\n{kpis[i][1]}"

    # Slide 4: Performance Table
    slide = ppt.slides.add_slide(ppt.slide_layouts[5])
    slide.shapes.title.text = "Employee Performance Analysis"
    rows, cols = len(performance_df) + 1, 4
    table = slide.shapes.add_table(rows, cols, Inches(0.8), Inches(1.5), Inches(8.4), Inches(4.5)).table
    
    headers = ["Employee Name", "Sales ($)", "Target ($)", "Achievement %"]
    for col_idx, h in enumerate(headers):
        cell = table.cell(0, col_idx)
        cell.text = h
        cell.fill.solid()
        cell.fill.fore_color.rgb = PRIMARY_COLOR

    for i, (_, row) in enumerate(performance_df.iterrows(), start=1):
        table.cell(i, 0).text = str(row["Name"])
        table.cell(i, 1).text = f"{row['Sales']:,}"
        table.cell(i, 2).text = f"{row['Target']:,}"
        table.cell(i, 3).text = f"{row['Achievement %']:.1f}%"

    # Slide 5: Revenue Trend
    slide = ppt.slides.add_slide(ppt.slide_layouts[5])
    slide.shapes.title.text = "Revenue Trend Analysis"
    slide.shapes.add_picture(revenue_chart, Inches(1.0), Inches(1.5), width=Inches(8.0))

    # Slide 6: Regional Distribution
    slide = ppt.slides.add_slide(ppt.slide_layouts[5])
    slide.shapes.title.text = "Regional Revenue Distribution"
    slide.shapes.add_picture(region_chart, Inches(1.5), Inches(1.5), width=Inches(7.0))

    # Slide 7: Product Revenue
    slide = ppt.slides.add_slide(ppt.slide_layouts[5])
    slide.shapes.title.text = "Product Revenue Analysis"
    slide.shapes.add_picture(product_chart, Inches(1.0), Inches(1.5), width=Inches(8.0))

    # Slide 8: Key Insights
    slide = ppt.slides.add_slide(ppt.slide_layouts[1])
    slide.shapes.title.text = "Strategic Insights"
    slide.placeholders[1].text = "\n\n".join([f"• {insight}" for insight in insights])

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    ppt.save(output_path)
    print(f"Corporate Presentation saved at '{output_path}'")
    return ppt

def _create_scraped_books_ppt(data_dict, output_path):
    main_df = data_dict.get("Books Data")
    if main_df is None or main_df.empty:
        main_df = list(data_dict.values())[0]

    kpi_metrics = analyze_scraped_data(main_df)
    insights = generate_scraped_insights(main_df)

    price_chart = create_price_distribution_chart(main_df)
    rating_chart = create_rating_distribution_chart(main_df)

    ppt = Presentation()

    # Slide 1: Cover
    slide = ppt.slides.add_slide(ppt.slide_layouts[0])
    slide.shapes.title.text = "Web Scraping Intelligence Report"
    slide.placeholders[1].text = "Automated E-Commerce & Book Data Analysis"

    # Slide 2: Executive Summary
    slide = ppt.slides.add_slide(ppt.slide_layouts[1])
    slide.shapes.title.text = "Scraped Market Summary"
    slide.placeholders[1].text = (
        f"• Total Items Scraped: {kpi_metrics.get('Total Books', 0)}\n"
        f"• Average Catalog Price: £{kpi_metrics.get('Average Price', 0.0):.2f}\n"
        f"• Highest Priced Item: £{kpi_metrics.get('Highest Price', 0.0):.2f}\n"
        f"• Lowest Priced Item: £{kpi_metrics.get('Lowest Price', 0.0):.2f}\n"
        f"• In-Stock Items: {kpi_metrics.get('Available Books', 0)}"
    )

    # Slide 3: KPI Dashboard
    slide = ppt.slides.add_slide(ppt.slide_layouts[5])
    slide.shapes.title.text = "Catalog Analytics Dashboard"
    cards = [
        ("Total Items", str(kpi_metrics.get("Total Books", 0))),
        ("Avg Price", f"£{kpi_metrics.get('Average Price', 0.0):.2f}"),
        ("Highest Price", f"£{kpi_metrics.get('Highest Price', 0.0):.2f}"),
        ("Available Items", str(kpi_metrics.get("Available Books", 0)))
    ]
    positions = [(0.8, 1.8), (5.2, 1.8), (0.8, 4.0), (5.2, 4.0)]
    for i in range(4):
        left, top = Inches(positions[i][0]), Inches(positions[i][1])
        card = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, left, top, Inches(4.0), Inches(1.8))
        card.fill.solid()
        card.fill.fore_color.rgb = PRIMARY_COLOR
        card.text = f"{cards[i][0]}\n\n{cards[i][1]}"

    # Slide 4: Data Preview Table
    slide = ppt.slides.add_slide(ppt.slide_layouts[5])
    slide.shapes.title.text = "Scraped Catalog Sample"
    sample_df = main_df.head(8)
    rows, cols = len(sample_df) + 1, min(len(sample_df.columns), 4)
    table = slide.shapes.add_table(rows, cols, Inches(0.8), Inches(1.5), Inches(8.4), Inches(4.5)).table

    for col_idx in range(cols):
        cell = table.cell(0, col_idx)
        cell.text = str(sample_df.columns[col_idx])
        cell.fill.solid()
        cell.fill.fore_color.rgb = PRIMARY_COLOR

    for r_idx, (_, row) in enumerate(sample_df.iterrows(), start=1):
        for c_idx in range(cols):
            table.cell(r_idx, c_idx).text = str(row.iloc[c_idx])[:30]

    # Slide 5: Price Distribution Chart
    if price_chart and os.path.exists(price_chart):
        slide = ppt.slides.add_slide(ppt.slide_layouts[5])
        slide.shapes.title.text = "Price Distribution Analysis"
        slide.shapes.add_picture(price_chart, Inches(1.0), Inches(1.5), width=Inches(8.0))

    # Slide 6: Rating Distribution Chart
    if rating_chart and os.path.exists(rating_chart):
        slide = ppt.slides.add_slide(ppt.slide_layouts[5])
        slide.shapes.title.text = "Catalog Ratings Overview"
        slide.shapes.add_picture(rating_chart, Inches(1.2), Inches(1.5), width=Inches(7.5))

    # Slide 7: Generated Insights
    slide = ppt.slides.add_slide(ppt.slide_layouts[1])
    slide.shapes.title.text = "Automated Insights"
    slide.placeholders[1].text = "\n\n".join([f"• {insight}" for insight in insights])

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    ppt.save(output_path)
    print(f"Scraped Data Presentation saved at '{output_path}'")
    return ppt

def _create_generic_ppt(data_dict, output_path):
    ppt = Presentation()
    slide = ppt.slides.add_slide(ppt.slide_layouts[0])
    slide.shapes.title.text = "Data Report Presentation"
    slide.placeholders[1].text = "Generated by XToP Suite"

    insights = generate_generic_insights(data_dict)
    
    slide = ppt.slides.add_slide(ppt.slide_layouts[1])
    slide.shapes.title.text = "Workbook Summary"
    slide.placeholders[1].text = "\n\n".join([f"• {i}" for i in insights])

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    ppt.save(output_path)
    return ppt