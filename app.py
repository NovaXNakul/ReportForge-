# app.py

import os
import streamlit as st
import pandas as pd
from excel_reader import read_excel
from ppt_generator import create_ppt
from pipeline import run_web_scraping_pipeline, run_excel_to_ppt_pipeline
from config import DEFAULT_EXCEL_PATH, DEFAULT_PPT_PATH

# Page Config
st.set_page_config(
    page_title="XToP & Web Scraper Automation Suite",
    page_icon="📊",
    layout="wide"
)

# Custom Styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.3rem;
        color: #1F4E78;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.1rem;
        color: #595959;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F2F4F7;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #1F4E78;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📊 XToP & Web Scraper Automation Suite</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Combined Platform for Web Scraping, Excel Report Generation & Automated PowerPoint Decks</div>', unsafe_allow_html=True)

# Tabs Navigation
tab1, tab2 = st.tabs(["🌐 Web Scraper -> Excel & PPT", "📄 XTOP: Excel -> PPT Generator"])

# ==============================================================================
# TAB 1: WEB SCRAPER PIPELINE
# ==============================================================================
with tab1:
    st.header("Automated Web Scraping to Excel & PPT")
    st.write("Scrape online data (e.g. Books to Scrape catalog), structure into a formatted Excel report, and auto-generate a PowerPoint presentation deck.")

    col1, col2 = st.columns([3, 1])
    with col1:
        target_url = st.text_input("Target Scraping URL", value="https://books.toscrape.com/")
    with col2:
        st.write("")
        st.write("")
        run_scrape_btn = st.button("🚀 Run Full Pipeline", type="primary", use_container_width=True)

    if run_scrape_btn:
        with st.spinner("Scraping web data, generating Excel report, and compiling PPT deck..."):
            try:
                res = run_web_scraping_pipeline(url=target_url)
                st.success("✅ Full pipeline completed successfully!")

                # Preview Data
                if os.path.exists(res["csv_path"]):
                    df_preview = pd.read_csv(res["csv_path"])
                    
                    st.subheader("Data Overview & Metrics")
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Total Items", len(df_preview))
                    m2.metric("Unique Ratings", df_preview["Rating"].nunique() if "Rating" in df_preview.columns else "N/A")
                    
                    if "Price" in df_preview.columns:
                        clean_p = pd.to_numeric(df_preview["Price"].astype(str).str.replace("£", "").str.replace("Â", "").str.strip(), errors="coerce")
                        m3.metric("Avg Price", f"£{clean_p.mean():.2f}")
                        m4.metric("Max Price", f"£{clean_p.max():.2f}")

                    st.subheader("Scraped Dataset Preview")
                    st.dataframe(df_preview.head(10), use_container_width=True)

                st.subheader("Generated Deliverables")
                d_col1, d_col2 = st.columns(2)

                if os.path.exists(res["excel_path"]):
                    with d_col1:
                        with open(res["excel_path"], "rb") as f:
                            st.download_button(
                                label="📥 Download Excel Report (.xlsx)",
                                data=f.read(),
                                file_name="books_report.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )

                if os.path.exists(res["ppt_path"]):
                    with d_col2:
                        with open(res["ppt_path"], "rb") as f:
                            st.download_button(
                                label="📥 Download PowerPoint Deck (.pptx)",
                                data=f.read(),
                                file_name="report.pptx",
                                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                use_container_width=True
                            )

            except Exception as e:
                st.error(f"❌ Pipeline Execution Error: {str(e)}")

# ==============================================================================
# TAB 2: XTOP EXCEL TO PPT GENERATOR
# ==============================================================================
with tab2:
    st.header("XTOP: Excel to PowerPoint Presentation Generator")
    st.write("Upload an Excel file (Corporate Performance report or Scraped dataset) to convert it directly into an automated PowerPoint deck.")

    uploaded_file = st.file_uploader(
        "Upload Excel Workbook (.xlsx)",
        type=["xlsx"]
    )

    if uploaded_file:
        try:
            # Save uploaded file temporarily
            os.makedirs("output", exist_ok=True)
            temp_excel_path = os.path.join("output", "uploaded_report.xlsx")
            with open(temp_excel_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            # Read Excel
            data_dict = read_excel(temp_excel_path)

            st.success("✅ Workbook loaded and validated successfully!")
            
            # Show Sheet Previews
            st.subheader("Workbook Sheets Preview")
            sheet_names = list(data_dict.keys())
            selected_sheet = st.selectbox("Select Sheet to View", sheet_names)
            st.dataframe(data_dict[selected_sheet].head(10), use_container_width=True)

            if st.button("📊 Generate PowerPoint Presentation Deck", type="primary"):
                with st.spinner("Generating slides, charts, and executive insights..."):
                    out_ppt = os.path.join("output", "generated_report.pptx")
                    create_ppt(data_dict, output_path=out_ppt)

                    st.success("🎉 PowerPoint Deck generated successfully!")

                    with open(out_ppt, "rb") as f:
                        st.download_button(
                            label="📥 Download Presentation Deck (.pptx)",
                            data=f.read(),
                            file_name="generated_report.pptx",
                            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                            use_container_width=True
                        )

        except KeyError as e:
            st.error(f"❌ Sheet structure error: {e}")
            st.info("Supported formats: Corporate Performance workbook (Employees, Monthly Revenue, Products, Regional Performance) OR Web Scraped workbook (Books Data, Summary).")

        except ValueError as e:
            st.error(f"❌ Column schema error: {e}")

        except Exception as e:
            st.error(f"❌ Unexpected Error: {e}")