# app.py

import os
import hashlib
import json
import streamlit as st
import pandas as pd
from excel_reader import read_excel
from ppt_generator import create_ppt
from pipeline import run_web_scraping_pipeline, run_excel_to_ppt_pipeline
from config import DEFAULT_EXCEL_PATH, DEFAULT_PPT_PATH

# --- Feature 1 imports ---
from data_ingestion import ingest_file, IngestedDataset, IngestionError
from data_quality_analyzer import (
    QualityConfig, QualityResult, analyze_quality, enrich_issues_with_business_id
)
from source_comparator import ComparisonConfig, ComparisonResult, compare_sources
from dq_report_generator import (
    AnalysisBundle, generate_dq_excel_bytes, generate_dq_ppt_bytes
)

# --- Feature 3 imports ---
from feature3_ui import render_feature3_tab

# Page Config
st.set_page_config(
    page_title="ReportForge — Data Intelligence Platform",
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

st.markdown('<div class="main-title">📊 ReportForge — Data Intelligence Platform</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Web Scraping, Excel Reports, PowerPoint Decks, Data Quality & Anomaly Analytics</div>', unsafe_allow_html=True)

# Tabs Navigation
tab1, tab2, tab3, tab4 = st.tabs([
    "🌐 Web Scraper -> Excel & PPT",
    "📄 XTOP: Excel -> PPT Generator",
    "🔍 Data Intelligence — Quality & Source Comparison",
    "🎯 Anomaly Detection & Spatial Clustering"
])

# ==============================================================================
# TAB 1: WEB SCRAPER PIPELINE (unchanged)
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
# TAB 2: XTOP EXCEL TO PPT GENERATOR (unchanged)
# ==============================================================================
with tab2:
    st.header("XTOP: Excel to PowerPoint Presentation Generator")
    st.write("Upload an Excel file (Corporate Performance report or Scraped dataset) to convert it directly into an automated PowerPoint deck.")

    uploaded_file = st.file_uploader(
        "Upload Excel Workbook (.xlsx)",
        type=["xlsx"],
        key="tab2_uploader"
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

# ==============================================================================
# TAB 3: DATA INTELLIGENCE — QUALITY & SOURCE COMPARISON
# ==============================================================================
with tab3:
    st.header("🔍 Data Intelligence — Quality & Source Comparison")
    st.write(
        "Upload multiple datasets to evaluate their quality, compare their contents, "
        "identify shared and unique entities, and detect conflicting information."
    )

    # Initialize session state
    if "dq_datasets" not in st.session_state:
        st.session_state.dq_datasets = []
    if "dq_analysis_bundle" not in st.session_state:
        st.session_state.dq_analysis_bundle = None
    if "dq_analysis_signature" not in st.session_state:
        st.session_state.dq_analysis_signature = None

    # =============================================
    # SECTION 1: Dataset Upload & Configuration
    # =============================================
    st.subheader("📁 Section 1: Dataset Upload & Configuration")

    uploaded_files = st.file_uploader(
        "Upload datasets (CSV, XLSX, or GeoJSON)",
        type=["csv", "xlsx", "geojson"],
        accept_multiple_files=True,
        key="dq_file_uploader"
    )

    if not uploaded_files:
        st.session_state.dq_datasets = []
        st.session_state.dq_analysis_bundle = None
        st.session_state.dq_analysis_signature = None
    else:
        st.markdown("---")
        st.markdown("**Configure each dataset:**")

        ingested_datasets = []
        upload_fingerprints = []

        for i, ufile in enumerate(uploaded_files):
            file_bytes = ufile.getvalue()
            content_hash = hashlib.sha256(file_bytes).hexdigest()

            with st.expander(f"📄 {ufile.name}", expanded=(i < 2)):
                col_a, col_b = st.columns(2)
                with col_a:
                    source_name = st.text_input(
                        "Source Name", value=f"Source {i+1}",
                        key=f"src_name_{i}"
                    )
                with col_b:
                    sheet_name = None
                    if ufile.name.lower().endswith(".xlsx"):
                        sheet_name = st.text_input(
                            "Sheet Name (leave blank for all)",
                            value="", key=f"sheet_{i}"
                        )
                        sheet_name = sheet_name.strip() if sheet_name.strip() else None

                upload_fingerprints.append((ufile.name, content_hash, source_name, sheet_name))

                # Save file temporarily
                os.makedirs("output", exist_ok=True)
                temp_path = os.path.join("output", f"dq_upload_{i}_{ufile.name}")
                with open(temp_path, "wb") as f:
                    f.write(file_bytes)

                try:
                    datasets = ingest_file(
                        filepath=temp_path,
                        source_name=source_name,
                        sheet_name=sheet_name,
                        original_filename=ufile.name,
                    )
                    for ds in datasets:
                        ingested_datasets.append(ds)
                        st.write(f"✅ Loaded: **{len(ds.raw_df)}** records, "
                                 f"**{len(ds.raw_df.columns) - 1}** columns")
                        st.dataframe(ds.raw_df.head(5), use_container_width=True)

                        if ds.ingestion_warnings:
                            for w in ds.ingestion_warnings:
                                st.warning(f"⚠️ {w}")

                except IngestionError as e:
                    st.error(f"❌ {str(e)}")
                except Exception as e:
                    st.error(f"❌ Failed to load: {str(e)}")

        st.session_state.dq_datasets = ingested_datasets

        if ingested_datasets:
            st.markdown("---")
            st.markdown("**Quality Analysis Configuration:**")

            # Let user select columns for each dataset
            quality_configs = []

            for ds in ingested_datasets:
                available_cols = [c for c in ds.normalized_df.columns if c != "_original_row_id"]

                with st.expander(f"⚙️ Config: {ds.source_name} ({ds.filename})", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        req_cols = st.multiselect(
                            "Required Columns (for completeness)",
                            options=available_cols,
                            key=f"req_{ds.source_name}_{ds.filename}_{ds.sheet_name}"
                        )
                        id_col = st.selectbox(
                            "Identifier Column (for uniqueness)",
                            options=["(None)"] + available_cols,
                            key=f"id_{ds.source_name}_{ds.filename}_{ds.sheet_name}"
                        )
                        id_col = None if id_col == "(None)" else id_col

                    with col2:
                        ts_col = st.selectbox(
                            "Timestamp Column (for freshness)",
                            options=["(None)"] + available_cols,
                            key=f"ts_{ds.source_name}_{ds.filename}_{ds.sheet_name}"
                        )
                        ts_col = None if ts_col == "(None)" else ts_col

                        freshness_days = st.number_input(
                            "Freshness Threshold (days)",
                            min_value=1, value=30,
                            key=f"fresh_{ds.source_name}_{ds.filename}_{ds.sheet_name}"
                        )

                    # Validation rules
                    st.markdown("**Validation Rules** (optional):")
                    validation_rules = {}

                    val_cols = st.multiselect(
                        "Columns to validate",
                        options=available_cols,
                        key=f"val_cols_{ds.source_name}_{ds.filename}_{ds.sheet_name}"
                    )

                    for vc in val_cols:
                        rule_type = st.selectbox(
                            f"Rule type for '{vc}'",
                            options=["numeric", "non_negative", "range",
                                     "latitude", "longitude", "date", "categorical"],
                            key=f"rule_{vc}_{ds.source_name}_{ds.filename}_{ds.sheet_name}"
                        )
                        rule = {"type": rule_type}

                        if rule_type == "range":
                            rc1, rc2 = st.columns(2)
                            with rc1:
                                rule["min"] = st.number_input(
                                    f"Min for '{vc}'", value=0.0,
                                    key=f"min_{vc}_{ds.source_name}_{ds.filename}_{ds.sheet_name}"
                                )
                            with rc2:
                                rule["max"] = st.number_input(
                                    f"Max for '{vc}'", value=100.0,
                                    key=f"max_{vc}_{ds.source_name}_{ds.filename}_{ds.sheet_name}"
                                )
                        elif rule_type == "categorical":
                            allowed_str = st.text_input(
                                f"Allowed values for '{vc}' (comma-separated)",
                                key=f"cat_{vc}_{ds.source_name}_{ds.filename}_{ds.sheet_name}"
                            )
                            rule["values"] = [v.strip() for v in allowed_str.split(",") if v.strip()]

                        validation_rules[vc] = [rule]

                    qc = QualityConfig(
                        required_columns=req_cols,
                        identifier_column=id_col,
                        timestamp_column=ts_col,
                        freshness_threshold_days=int(freshness_days),
                        validation_rules=validation_rules,
                    )
                    quality_configs.append((ds, qc))

            # Comparison configuration
            comp_config = None
            if len(ingested_datasets) >= 2:
                st.markdown("---")
                st.markdown("**Source Comparison Configuration:**")

                col_s1, col_s2 = st.columns(2)
                ds_names = [f"{ds.source_name} ({ds.filename})" for ds in ingested_datasets]

                with col_s1:
                    ds_a_idx = st.selectbox("Source A", range(len(ds_names)),
                                            format_func=lambda x: ds_names[x],
                                            key="comp_ds_a")
                with col_s2:
                    ds_b_idx = st.selectbox("Source B", range(len(ds_names)),
                                            index=min(1, len(ds_names) - 1),
                                            format_func=lambda x: ds_names[x],
                                            key="comp_ds_b")

                if ds_a_idx != ds_b_idx:
                    ds_a = ingested_datasets[ds_a_idx]
                    ds_b = ingested_datasets[ds_b_idx]

                    avail_a = [c for c in ds_a.normalized_df.columns if c != "_original_row_id"]
                    avail_b = [c for c in ds_b.normalized_df.columns if c != "_original_row_id"]

                    with st.expander("🔗 Matching Configuration", expanded=True):
                        use_exact = st.checkbox("Enable Exact ID Matching", value=True,
                                                key="use_exact")
                        compatible_ids = st.checkbox(
                            "Identifiers from both sources are compatible",
                            value=True, key="compatible_ids"
                        )
                        id_a = id_b = None
                        if use_exact or compatible_ids:
                            mc1, mc2 = st.columns(2)
                            with mc1:
                                id_a = st.selectbox("ID Column (Source A)",
                                                    ["(None)"] + avail_a,
                                                    key="id_col_a")
                                id_a = None if id_a == "(None)" else id_a
                            with mc2:
                                id_b = st.selectbox("ID Column (Source B)",
                                                    ["(None)"] + avail_b,
                                                    key="id_col_b")
                                id_b = None if id_b == "(None)" else id_b

                        use_fuzzy = st.checkbox("Enable Fuzzy Name Matching",
                                                value=False, key="use_fuzzy")
                        name_a = name_b = None
                        fuzzy_threshold = 80.0
                        fuzzy_margin = 5.0
                        if use_fuzzy:
                            fc1, fc2, fc3, fc4 = st.columns(4)
                            with fc1:
                                name_a = st.selectbox("Name Column (Source A)",
                                                      ["(None)"] + avail_a,
                                                      key="name_col_a")
                                name_a = None if name_a == "(None)" else name_a
                            with fc2:
                                name_b = st.selectbox("Name Column (Source B)",
                                                      ["(None)"] + avail_b,
                                                      key="name_col_b")
                                name_b = None if name_b == "(None)" else name_b
                            with fc3:
                                fuzzy_threshold = st.slider(
                                    "Similarity Threshold (%)",
                                    50, 100, 80, key="fuzzy_thresh"
                                )
                            with fc4:
                                fuzzy_margin = st.number_input(
                                    "Ambiguity Margin (%)",
                                    min_value=0.0, max_value=50.0, value=5.0,
                                    key="fuzzy_margin"
                                )

                        use_geo = st.checkbox("Enable Geographic Proximity Matching",
                                              value=False, key="use_geo")
                        lat_a = lon_a = lat_b = lon_b = None
                        distance_threshold = 500.0
                        if use_geo:
                            gc1, gc2 = st.columns(2)
                            with gc1:
                                lat_a = st.selectbox("Latitude (Source A)",
                                                     ["(None)"] + avail_a, key="lat_a")
                                lon_a = st.selectbox("Longitude (Source A)",
                                                     ["(None)"] + avail_a, key="lon_a")
                                lat_a = None if lat_a == "(None)" else lat_a
                                lon_a = None if lon_a == "(None)" else lon_a
                            with gc2:
                                lat_b = st.selectbox("Latitude (Source B)",
                                                     ["(None)"] + avail_b, key="lat_b")
                                lon_b = st.selectbox("Longitude (Source B)",
                                                     ["(None)"] + avail_b, key="lon_b")
                                lat_b = None if lat_b == "(None)" else lat_b
                                lon_b = None if lon_b == "(None)" else lon_b
                            distance_threshold = st.number_input(
                                "Distance Threshold (metres)",
                                min_value=1.0, value=500.0, key="dist_thresh"
                            )

                    # Attribute comparison columns
                    with st.expander("📊 Attribute Comparison", expanded=False):
                        st.write("Select columns to compare between matched entities:")
                        compare_cols = []
                        common_cols = set(avail_a) & set(avail_b)
                        if common_cols:
                            selected_compare = st.multiselect(
                                "Common columns to compare",
                                options=sorted(common_cols),
                                key="compare_cols"
                            )
                            compare_cols = [(c, c) for c in selected_compare]
                        else:
                            st.info("No common column names found. Add custom mappings below.")

                        custom_comp = st.text_area(
                            "Custom column mappings (one per line, format: col_a=col_b)",
                            key="custom_compare"
                        )
                        if custom_comp.strip():
                            for line in custom_comp.strip().split("\n"):
                                if "=" in line:
                                    parts = line.split("=", 1)
                                    compare_cols.append((parts[0].strip(), parts[1].strip()))

                    comp_config = ComparisonConfig(
                        id_column_a=id_a,
                        id_column_b=id_b,
                        name_column_a=name_a,
                        name_column_b=name_b,
                        lat_column_a=lat_a,
                        lon_column_a=lon_a,
                        lat_column_b=lat_b,
                        lon_column_b=lon_b,
                        fuzzy_threshold=fuzzy_threshold,
                        fuzzy_margin=float(fuzzy_margin),
                        distance_threshold_m=distance_threshold,
                        compare_columns=compare_cols,
                        use_exact=use_exact,
                        use_fuzzy=use_fuzzy,
                        use_geo=use_geo,
                        compatible_ids=compatible_ids,
                    )

            # Build deterministic signature covering file contents + all settings
            sig_payload = {
                "uploads": upload_fingerprints,
                "quality": [
                    {
                        "source": ds.source_name,
                        "req": qc.required_columns,
                        "id": qc.identifier_column,
                        "ts": qc.timestamp_column,
                        "fresh_days": qc.freshness_threshold_days,
                        "rules": qc.validation_rules,
                    }
                    for ds, qc in quality_configs
                ],
                "comparison": {
                    "ds_a": ds_a_idx if len(ingested_datasets) >= 2 else None,
                    "ds_b": ds_b_idx if len(ingested_datasets) >= 2 else None,
                    "use_exact": comp_config.use_exact,
                    "compatible_ids": comp_config.compatible_ids,
                    "id_a": comp_config.id_column_a,
                    "id_b": comp_config.id_column_b,
                    "use_fuzzy": comp_config.use_fuzzy,
                    "name_a": comp_config.name_column_a,
                    "name_b": comp_config.name_column_b,
                    "fuzzy_thresh": comp_config.fuzzy_threshold,
                    "fuzzy_margin": comp_config.fuzzy_margin,
                    "use_geo": comp_config.use_geo,
                    "lat_a": comp_config.lat_column_a,
                    "lon_a": comp_config.lon_column_a,
                    "lat_b": comp_config.lat_column_b,
                    "lon_b": comp_config.lon_column_b,
                    "dist": comp_config.distance_threshold_m,
                    "compare": comp_config.compare_columns,
                } if comp_config else None,
            }
            current_signature = hashlib.sha256(
                json.dumps(sig_payload, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()

            if (
                st.session_state.dq_analysis_bundle is not None
                and st.session_state.dq_analysis_signature != current_signature
            ):
                st.session_state.dq_analysis_bundle = None
                st.info("ℹ️ Inputs or analysis settings changed. Click 'Run Data Quality Analysis' to refresh results.")

            # =============================================
            # RUN ANALYSIS
            # =============================================
            st.markdown("---")
            if st.button("🚀 Run Data Quality Analysis", type="primary",
                         use_container_width=True):
                with st.spinner("Analyzing data quality and comparing sources..."):
                    try:
                        # Run quality analysis
                        quality_results = []
                        for ds, qc in quality_configs:
                            qr = analyze_quality(ds, qc)
                            norm_cols = {c.lower(): c for c in ds.normalized_df.columns}
                            resolved_id = norm_cols.get(
                                qc.identifier_column.lower()
                            ) if qc.identifier_column else None
                            enrich_issues_with_business_id(qr, ds.normalized_df, resolved_id)
                            quality_results.append(qr)

                        # Run comparison
                        comparison_result = None
                        if comp_config and len(ingested_datasets) >= 2 and ds_a_idx != ds_b_idx:
                            comparison_result = compare_sources(
                                ingested_datasets[ds_a_idx],
                                ingested_datasets[ds_b_idx],
                                comp_config
                            )

                        # Build config summary
                        config_summary = {}
                        for ds, qc in quality_configs:
                            prefix = ds.source_name
                            config_summary[f"{prefix} - Required Columns"] = str(qc.required_columns)
                            config_summary[f"{prefix} - Identifier Column"] = str(qc.identifier_column)
                            config_summary[f"{prefix} - Timestamp Column"] = str(qc.timestamp_column)
                            config_summary[f"{prefix} - Freshness Threshold"] = f"{qc.freshness_threshold_days} days"

                        if comp_config:
                            config_summary["Comparison - Exact Matching"] = str(comp_config.use_exact)
                            config_summary["Comparison - Compatible IDs"] = str(comp_config.compatible_ids)
                            config_summary["Comparison - Fuzzy Matching"] = str(comp_config.use_fuzzy)
                            config_summary["Comparison - Fuzzy Threshold"] = f"{comp_config.fuzzy_threshold}%"
                            config_summary["Comparison - Fuzzy Margin"] = f"{comp_config.fuzzy_margin}%"
                            config_summary["Comparison - Geo Matching"] = str(comp_config.use_geo)

                        bundle = AnalysisBundle(
                            quality_results=quality_results,
                            comparison_result=comparison_result,
                            datasets=ingested_datasets,
                            config_summary=config_summary,
                        )
                        st.session_state.dq_analysis_bundle = bundle
                        st.session_state.dq_analysis_signature = current_signature

                        st.success("✅ Analysis completed successfully!")

                    except Exception as e:
                        st.error(f"❌ Analysis Error: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc())

    # =============================================
    # DISPLAY RESULTS (from session state)
    # =============================================
    bundle = st.session_state.dq_analysis_bundle

    if bundle:
        # =============================================
        # SECTION 2: Data Quality Dashboard
        # =============================================
        st.markdown("---")
        st.subheader("📊 Section 2: Data Quality Dashboard")

        for qr in bundle.quality_results:
            s = qr.to_summary_dict()
            st.markdown(f"### {s['source_name']} — {s['filename']}")

            mc1, mc2, mc3, mc4, mc5 = st.columns(5)
            mc1.metric("Total Records", s["total_records"])
            mc2.metric("Completeness", s["completeness"])
            mc3.metric("Validity", s["validity"])
            mc4.metric("Uniqueness", s["uniqueness"])
            mc5.metric("Freshness", s["freshness"])

            mc6, mc7, mc8, mc9, mc10 = st.columns(5)
            mc6.metric("Timestamp Coverage", s["timestamp_coverage"])
            mc7.metric("Missing Values", s["missing_values"])
            mc8.metric("Duplicates", s["duplicate_identifiers"])
            mc9.metric("Invalid Records", s["invalid_records"])
            mc10.metric("Stale Records", s["stale_records"])

        # Comparison bar chart if multiple sources
        if len(bundle.quality_results) >= 2:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            st.markdown("#### Quality Metrics Comparison")
            metric_names = ["Completeness", "Validity", "Uniqueness", "Freshness"]
            fig, ax = plt.subplots(figsize=(10, 4))

            x = range(len(metric_names))
            width = 0.35
            colors = ["#1F4E78", "#2E75B6", "#5B9BD5", "#ED7D31"]

            for i, qr in enumerate(bundle.quality_results[:4]):
                s = qr.to_summary_dict()
                values = [
                    s["completeness_value"] if s["completeness_value"] is not None else 0,
                    s["validity_value"] if s["validity_value"] is not None else 0,
                    s["uniqueness_value"] if s["uniqueness_value"] is not None else 0,
                    s["freshness_value"] if s["freshness_value"] is not None else 0,
                ]
                offset = (i - len(bundle.quality_results[:4]) / 2 + 0.5) * width
                bars = ax.bar([xi + offset for xi in x], values, width,
                              label=s["source_name"],
                              color=colors[i % len(colors)])

            ax.set_ylabel("Percentage (%)")
            ax.set_title("Data Quality Comparison")
            ax.set_xticks(list(x))
            ax.set_xticklabels(metric_names)
            ax.legend()
            ax.set_ylim(0, 110)
            plt.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

        # =============================================
        # SECTION 3: Data Quality Issues
        # =============================================
        st.markdown("---")
        st.subheader("⚠️ Section 3: Data Quality Issues")

        all_issues = []
        for qr in bundle.quality_results:
            all_issues.extend(qr.issues)

        if all_issues:
            issues_df = pd.DataFrame(all_issues)

            # Filters
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                filter_source = st.multiselect(
                    "Filter by Source",
                    options=issues_df["source_name"].unique().tolist(),
                    default=issues_df["source_name"].unique().tolist(),
                    key="issue_filter_source"
                )
            with fc2:
                filter_type = st.multiselect(
                    "Filter by Issue Type",
                    options=issues_df["issue_type"].unique().tolist(),
                    default=issues_df["issue_type"].unique().tolist(),
                    key="issue_filter_type"
                )
            with fc3:
                filter_col = st.multiselect(
                    "Filter by Column",
                    options=issues_df["column"].unique().tolist(),
                    default=issues_df["column"].unique().tolist(),
                    key="issue_filter_col"
                )

            filtered_df = issues_df[
                issues_df["source_name"].isin(filter_source) &
                issues_df["issue_type"].isin(filter_type) &
                issues_df["column"].isin(filter_col)
            ]

            st.write(f"Showing **{len(filtered_df)}** of **{len(issues_df)}** issues")
            st.dataframe(filtered_df, use_container_width=True, height=400)
        else:
            st.info("No data quality issues found.")

        # =============================================
        # SECTION 4: Source Comparison
        # =============================================
        if bundle.comparison_result:
            cr = bundle.comparison_result
            summary = cr.to_summary_dict()

            st.markdown("---")
            st.subheader("🔗 Section 4: Source Comparison")

            cc1, cc2, cc3, cc4 = st.columns(4)
            cc1.metric("Confirmed Matches", summary["matched_count"])
            cc2.metric(f"Exclusive to {summary['source_a']}", summary["exclusive_a_count"])
            cc3.metric(f"Exclusive to {summary['source_b']}", summary["exclusive_b_count"])

            jaccard_pct = (
                f"{summary['jaccard_similarity'] * 100:.1f}%"
                if summary['jaccard_similarity'] is not None else "N/A"
            )
            jaccard_label = (
                "Jaccard Similarity (Estimate)"
                if summary.get("jaccard_is_estimate") else "Jaccard Similarity"
            )
            cc4.metric(jaccard_label, jaccard_pct)

            cc5, cc6, cc7, cc8 = st.columns(4)
            cc5.metric("Ambiguous / Unresolved", summary["ambiguous_count"])
            cc6.metric(f"Unmatchable ({summary['source_a']})", summary["unmatchable_a_count"])
            cc7.metric(f"Unmatchable ({summary['source_b']})", summary["unmatchable_b_count"])
            cc8.metric("Attribute Conflicts", summary["conflict_count"])

            st.info(f"ℹ️ {summary['jaccard_explanation']}")

            # Matched entities
            if cr.matched:
                with st.expander(f"✅ Confirmed Matches ({len(cr.matched)})", expanded=False):
                    matched_df = pd.DataFrame(cr.matched)
                    display_cols = ["id_a", "id_b", "row_id_a", "row_id_b",
                                    "method", "score"]
                    display_cols = [c for c in display_cols if c in matched_df.columns]
                    st.dataframe(matched_df[display_cols], use_container_width=True)

            # Exclusive entities
            if not cr.exclusive_a.empty:
                with st.expander(f"🔵 Exclusive to {summary['source_a']} ({len(cr.exclusive_a)})",
                                 expanded=False):
                    st.dataframe(cr.exclusive_a, use_container_width=True)

            if not cr.exclusive_b.empty:
                with st.expander(f"🟠 Exclusive to {summary['source_b']} ({len(cr.exclusive_b)})",
                                 expanded=False):
                    st.dataframe(cr.exclusive_b, use_container_width=True)

            # Ambiguous matches
            if cr.ambiguous:
                with st.expander(f"⚠️ Ambiguous Matches ({len(cr.ambiguous)})", expanded=False):
                    amb_df = pd.DataFrame(cr.ambiguous)
                    display_cols = ["id_a", "id_b", "row_id_a", "row_id_b",
                                    "method", "score", "reason"]
                    display_cols = [c for c in display_cols if c in amb_df.columns]
                    st.dataframe(amb_df[display_cols], use_container_width=True)

            # =============================================
            # SECTION 5: Attribute Conflicts
            # =============================================
            if cr.conflicts:
                st.markdown("---")
                st.subheader("⚔️ Section 5: Attribute Conflicts")

                conflicts_df = pd.DataFrame(cr.conflicts)
                st.write(f"Found **{len(conflicts_df)}** attribute conflicts")
                st.dataframe(conflicts_df, use_container_width=True, height=400)

        # =============================================
        # SECTION 6: Report Downloads
        # =============================================
        st.markdown("---")
        st.subheader("📥 Section 6: Report Downloads")

        dl1, dl2 = st.columns(2)
        with dl1:
            try:
                excel_bytes = generate_dq_excel_bytes(bundle)
                st.download_button(
                    label="📥 Download Excel Report (.xlsx)",
                    data=excel_bytes,
                    file_name="data_quality_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"Failed to generate Excel report: {e}")

        with dl2:
            try:
                ppt_bytes = generate_dq_ppt_bytes(bundle)
                st.download_button(
                    label="📥 Download PowerPoint Report (.pptx)",
                    data=ppt_bytes,
                    file_name="data_quality_report.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"Failed to generate PPT report: {e}")

# ==============================================================================
# TAB 4: ANOMALY DETECTION & SPATIAL CLUSTERING (Feature 3)
# ==============================================================================
with tab4:
    render_feature3_tab()

