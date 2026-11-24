# feature3_ui.py

"""
Streamlit UI Workspace for Feature 3:
Statistical/ML Anomaly Detection & Spatial Clustering.

Kept modular to maintain high maintainability and clean integration with app.py.
"""

import os
import hashlib
import json
import logging
from typing import Optional, List, Dict, Any

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from data_ingestion import ingest_file, IngestedDataset, IngestionError
from anomaly_detector import (
    AnomalyConfig,
    detect_iqr_anomalies,
    detect_zscore_anomalies,
    detect_isolation_forest_anomalies,
)
from clustering_engine import ClusteringConfig, run_spatial_clustering
from feature3_report_generator import (
    Feature3Bundle,
    generate_feature3_excel_bytes,
    generate_feature3_ppt_bytes,
)

logger = logging.getLogger(__name__)


def render_feature3_tab():
    """Renders the Feature 3 Anomaly Detection & Spatial Clustering UI in Streamlit."""
    st.header("🎯 Anomaly Detection & Spatial Clustering")
    st.write(
        "Detect statistical univariate outliers (IQR, Z-Score), multivariate abnormal combinations "
        "(Isolation Forest), and spatial concentrations/isolated noise points (DBSCAN Clustering)."
    )

    if "f3_analysis_bundle" not in st.session_state:
        st.session_state.f3_analysis_bundle = None
    if "f3_analysis_signature" not in st.session_state:
        st.session_state.f3_analysis_signature = None

    # ==============================================================================
    # SECTION 1: Dataset Selection
    # ==============================================================================
    st.subheader("📁 Section 1: Dataset Selection")

    loaded_datasets: List[IngestedDataset] = st.session_state.get("dq_datasets", [])
    dataset_options = ["Upload New Dataset"]
    if loaded_datasets:
        dataset_options = [f"Loaded: {ds.source_name} ({ds.filename})" for ds in loaded_datasets] + dataset_options

    selected_option = st.selectbox(
        "Choose Data Source for Analysis",
        options=dataset_options,
        key="f3_source_selector"
    )

    active_dataset: Optional[IngestedDataset] = None

    if selected_option.startswith("Loaded:"):
        idx = dataset_options.index(selected_option)
        active_dataset = loaded_datasets[idx]
    else:
        uploaded_file = st.file_uploader(
            "Upload Dataset (.csv, .xlsx, or .geojson)",
            type=["csv", "xlsx", "geojson"],
            key="f3_file_uploader"
        )
        if uploaded_file:
            os.makedirs("output", exist_ok=True)
            temp_path = os.path.join("output", f"f3_upload_{uploaded_file.name}")
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getvalue())

            try:
                ingested = ingest_file(
                    filepath=temp_path,
                    source_name="Uploaded Dataset",
                    original_filename=uploaded_file.name,
                )
                if ingested:
                    active_dataset = ingested[0]
            except IngestionError as e:
                st.error(f"❌ Ingestion Error: {e}")
            except Exception as e:
                st.error(f"❌ Unexpected Error: {e}")

    if not active_dataset:
        st.info("Please select or upload a dataset to begin anomaly detection and spatial clustering.")
        return

    st.write(
        f"✅ Active Dataset: **{active_dataset.source_name}** (`{active_dataset.filename}`) — "
        f"**{len(active_dataset.raw_df)}** records, **{len(active_dataset.raw_df.columns) - 1}** columns"
    )
    with st.expander("👀 Dataset Preview", expanded=False):
        st.dataframe(active_dataset.raw_df.head(10), use_container_width=True)

    df_eval = active_dataset.normalized_df
    all_cols = [c for c in df_eval.columns if c != "_original_row_id"]

    # Filter potential numerical columns
    numeric_candidate_cols = []
    for c in all_cols:
        series_clean = pd.to_numeric(df_eval[c], errors="coerce").dropna()
        if len(series_clean) > 0 and (len(series_clean) / len(df_eval)) >= 0.5:
            numeric_candidate_cols.append(c)

    # Detect geo columns
    geo_cols = active_dataset.geo_columns
    default_lat_idx = 0
    default_lon_idx = 0
    if "latitude" in geo_cols and geo_cols["latitude"] in all_cols:
        default_lat_idx = all_cols.index(geo_cols["latitude"]) + 1
    if "longitude" in geo_cols and geo_cols["longitude"] in all_cols:
        default_lon_idx = all_cols.index(geo_cols["longitude"]) + 1

    # ==============================================================================
    # CONFIGURATION EXPANDERS
    # ==============================================================================
    st.markdown("---")
    st.markdown("### ⚙️ Analytical Configuration")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### 1. Univariate Statistical Anomalies (IQR & Z-Score)")
        run_iqr = st.checkbox("Run IQR Anomaly Detection", value=True, key="f3_run_iqr")
        iqr_selected_cols = []
        iqr_k = 1.5
        if run_iqr:
            iqr_selected_cols = st.multiselect(
                "Columns for IQR Analysis",
                options=numeric_candidate_cols,
                default=numeric_candidate_cols[:min(2, len(numeric_candidate_cols))],
                key="f3_iqr_cols"
            )
            iqr_k = st.number_input("IQR Multiplier (k)", min_value=0.1, max_value=10.0, value=1.5, step=0.1, key="f3_iqr_k")

        run_zscore = st.checkbox("Run Z-Score Anomaly Detection", value=True, key="f3_run_zscore")
        zscore_selected_cols = []
        zscore_thresh = 3.0
        if run_zscore:
            zscore_selected_cols = st.multiselect(
                "Columns for Z-Score Analysis",
                options=numeric_candidate_cols,
                default=numeric_candidate_cols[:min(2, len(numeric_candidate_cols))],
                key="f3_zscore_cols"
            )
            zscore_thresh = st.number_input("Z-Score Absolute Threshold (|Z|)", min_value=0.5, max_value=10.0, value=3.0, step=0.5, key="f3_zscore_thresh")

    with c2:
        st.markdown("#### 2. Isolation Forest (Multivariate ML)")
        run_iforest = st.checkbox("Run Isolation Forest", value=True, key="f3_run_iforest")
        iforest_features = []
        iforest_n_est = 100
        iforest_contam = 0.05
        iforest_seed = 42
        if run_iforest:
            iforest_features = st.multiselect(
                "Numerical Features for Isolation Forest",
                options=numeric_candidate_cols,
                default=numeric_candidate_cols[:min(3, len(numeric_candidate_cols))],
                key="f3_iforest_features"
            )
            if1, if2, if3 = st.columns(3)
            with if1:
                iforest_n_est = st.number_input("Estimators (trees)", min_value=10, max_value=500, value=100, step=10, key="f3_iforest_nest")
            with if2:
                iforest_contam = st.number_input("Contamination", min_value=0.01, max_value=0.5, value=0.05, step=0.01, key="f3_iforest_contam")
            with if3:
                iforest_seed = st.number_input("Random Seed", min_value=0, max_value=99999, value=42, key="f3_iforest_seed")

        st.markdown("#### 3. DBSCAN Spatial Clustering")
        run_clustering = st.checkbox("Run DBSCAN Clustering", value=bool(default_lat_idx and default_lon_idx), key="f3_run_dbscan")
        selected_lat = None
        selected_lon = None
        dbscan_eps_km = 0.5
        dbscan_min_samples = 5
        if run_clustering:
            cl1, cl2 = st.columns(2)
            with cl1:
                lat_choice = st.selectbox("Latitude Column", options=["(None)"] + all_cols, index=default_lat_idx, key="f3_lat_col")
                selected_lat = None if lat_choice == "(None)" else lat_choice
            with cl2:
                lon_choice = st.selectbox("Longitude Column", options=["(None)"] + all_cols, index=default_lon_idx, key="f3_lon_col")
                selected_lon = None if lon_choice == "(None)" else lon_choice

            cl3, cl4 = st.columns(2)
            with cl3:
                dbscan_eps_km = st.number_input("Epsilon Distance (km)", min_value=0.01, max_value=500.0, value=0.5, step=0.1, key="f3_dbscan_eps")
            with cl4:
                dbscan_min_samples = st.number_input("Min Samples", min_value=1, max_value=100, value=5, step=1, key="f3_dbscan_min_samples")

    # Construct Signature for Caching / Invalidation
    sig_payload = {
        "dataset_name": active_dataset.source_name,
        "filename": active_dataset.filename,
        "rows": len(active_dataset.raw_df),
        "run_iqr": run_iqr,
        "iqr_cols": iqr_selected_cols,
        "iqr_k": iqr_k,
        "run_zscore": run_zscore,
        "zscore_cols": zscore_selected_cols,
        "zscore_thresh": zscore_thresh,
        "run_iforest": run_iforest,
        "iforest_features": iforest_features,
        "iforest_n_est": iforest_n_est,
        "iforest_contam": iforest_contam,
        "iforest_seed": iforest_seed,
        "run_clustering": run_clustering,
        "lat": selected_lat,
        "lon": selected_lon,
        "eps_km": dbscan_eps_km,
        "min_samples": dbscan_min_samples,
    }
    current_sig = hashlib.sha256(json.dumps(sig_payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()

    if (st.session_state.f3_analysis_bundle is not None
            and st.session_state.f3_analysis_signature != current_sig):
        st.session_state.f3_analysis_bundle = None
        st.info("ℹ️ Settings or data changed. Click 'Run Analysis' to compute updated results.")

    # ==============================================================================
    # RUN BUTTON
    # ==============================================================================
    st.markdown("---")
    if st.button("🚀 Run Anomaly Detection & Spatial Clustering", type="primary", use_container_width=True):
        with st.spinner("Executing statistical, machine learning, and spatial clustering algorithms..."):
            try:
                iqr_res = {}
                if run_iqr and iqr_selected_cols:
                    iqr_res = detect_iqr_anomalies(df_eval, iqr_selected_cols, k=iqr_k, source_name=active_dataset.source_name)

                z_res = {}
                if run_zscore and zscore_selected_cols:
                    z_res = detect_zscore_anomalies(df_eval, zscore_selected_cols, threshold=zscore_thresh, source_name=active_dataset.source_name)

                if_res = None
                if run_iforest and iforest_features:
                    if_res = detect_isolation_forest_anomalies(
                        df_eval,
                        features=iforest_features,
                        n_estimators=int(iforest_n_est),
                        contamination=iforest_contam,
                        random_state=int(iforest_seed),
                        source_name=active_dataset.source_name,
                    )

                c_res = None
                if run_clustering and selected_lat and selected_lon:
                    c_res = run_spatial_clustering(
                        df_eval,
                        lat_column=selected_lat,
                        lon_column=selected_lon,
                        eps_km=float(dbscan_eps_km),
                        min_samples=int(dbscan_min_samples),
                        source_name=active_dataset.source_name,
                    )

                config_summary = {
                    "Dataset": f"{active_dataset.source_name} ({active_dataset.filename})",
                    "Total Rows": len(active_dataset.raw_df),
                    "IQR Multiplier (k)": iqr_k if run_iqr else "Not Executed",
                    "Z-Score Threshold": zscore_thresh if run_zscore else "Not Executed",
                    "Isolation Forest Features": ", ".join(iforest_features) if (run_iforest and if_res) else "Not Executed",
                    "Isolation Forest Contamination": iforest_contam if run_iforest else "Not Executed",
                    "DBSCAN Epsilon (km)": dbscan_eps_km if run_clustering else "Not Executed",
                    "DBSCAN Min Samples": dbscan_min_samples if run_clustering else "Not Executed",
                }

                bundle = Feature3Bundle(
                    dataset_name=active_dataset.source_name,
                    filename=active_dataset.filename,
                    total_rows=len(active_dataset.raw_df),
                    iqr_results=iqr_res,
                    zscore_results=z_res,
                    iforest_result=if_res,
                    clustering_result=c_res,
                    config_summary=config_summary,
                )

                st.session_state.f3_analysis_bundle = bundle
                st.session_state.f3_analysis_signature = current_sig
                st.success("✅ Analysis completed successfully!")

            except Exception as e:
                st.error(f"❌ Execution Error: {e}")
                logger.exception("Feature 3 analysis failed")

    # ==============================================================================
    # DISPLAY RESULTS
    # ==============================================================================
    bundle: Optional[Feature3Bundle] = st.session_state.f3_analysis_bundle
    if not bundle:
        return

    # Section 2: Statistical Anomaly Detection
    st.markdown("---")
    st.subheader("📊 Section 2: Statistical Anomaly Detection (IQR & Z-Score)")

    stat_tab1, stat_tab2 = st.tabs(["📦 Interquartile Range (IQR)", "📈 Z-Score Analysis"])

    with stat_tab1:
        if bundle.iqr_results:
            for col, r in bundle.iqr_results.items():
                st.markdown(f"##### Column: `{col}`")
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Evaluated Records", r.evaluated_records)
                m2.metric("Q1 (25%)", f"{r.q1:.2f}" if r.q1 is not None else "N/A")
                m3.metric("Q3 (75%)", f"{r.q3:.2f}" if r.q3 is not None else "N/A")
                m4.metric("IQR", f"{r.iqr:.2f}" if r.iqr is not None else "N/A")
                m5.metric("Anomalies Flagged", len(r.anomalies))

                st.write(f"Boundaries: `[{r.lower_bound:.2f}, {r.upper_bound:.2f}]` (k={r.k})")

                # Box plot visualization
                valid_vals = pd.to_numeric(df_eval[col], errors="coerce").dropna()
                if len(valid_vals) > 0:
                    fig, ax = plt.subplots(figsize=(8, 2.5))
                    ax.boxplot(valid_vals, vert=False, patch_artist=True, boxprops=dict(facecolor="#2E75B6", color="#1F4E78"))
                    ax.set_title(f"IQR Boxplot — {col} (Anomalies: {len(r.anomalies)})", fontsize=11, fontweight="bold")
                    ax.set_xlabel(col)
                    st.pyplot(fig)
                    plt.close(fig)

                if r.anomalies:
                    with st.expander(f"⚠️ Flagged IQR Outliers ({len(r.anomalies)})"):
                        st.dataframe(pd.DataFrame(r.anomalies), use_container_width=True)
                else:
                    st.info(f"No statistical IQR outliers detected in `{col}`.")
        else:
            st.info("IQR analysis was not configured or executed.")

    with stat_tab2:
        if bundle.zscore_results:
            for col, r in bundle.zscore_results.items():
                st.markdown(f"##### Column: `{col}`")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Evaluated Records", r.evaluated_records)
                m2.metric("Mean (μ)", f"{r.mean:.2f}" if r.mean is not None else "N/A")
                m3.metric("Std Dev (σ, ddof=0)", f"{r.std:.2f}" if r.std is not None else "N/A")
                m4.metric("Anomalies Flagged", len(r.anomalies))

                # Histogram / Distribution visualization
                valid_vals = pd.to_numeric(df_eval[col], errors="coerce").dropna()
                if len(valid_vals) > 0 and r.std and r.std > 0:
                    fig, ax = plt.subplots(figsize=(8, 2.5))
                    ax.hist(valid_vals, bins=15, color="#5B9BD5", edgecolor="white", alpha=0.8)
                    ax.axvline(r.mean - r.threshold * r.std, color="#ED7D31", linestyle="--", label=f"-{r.threshold}σ Threshold")
                    ax.axvline(r.mean + r.threshold * r.std, color="#ED7D31", linestyle="--", label=f"+{r.threshold}σ Threshold")
                    ax.axvline(r.mean, color="#1F4E78", linestyle="-", label="Mean (μ)")
                    ax.set_title(f"Z-Score Distribution — {col}", fontsize=11, fontweight="bold")
                    ax.legend(fontsize=8)
                    st.pyplot(fig)
                    plt.close(fig)

                if r.anomalies:
                    with st.expander(f"⚠️ Flagged Z-Score Outliers ({len(r.anomalies)})"):
                        st.dataframe(pd.DataFrame(r.anomalies), use_container_width=True)
                else:
                    st.info(f"No statistical Z-score outliers detected in `{col}`.")
        else:
            st.info("Z-score analysis was not configured or executed.")

    # Section 3: Isolation Forest
    st.markdown("---")
    st.subheader("🌲 Section 3: Isolation Forest (Multivariate Anomaly Detection)")
    if bundle.iforest_result:
        if_res = bundle.iforest_result
        if if_res.evaluated_records > 0:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Evaluated Complete Cases", if_res.evaluated_records)
            m2.metric("Excluded Incomplete Rows", if_res.excluded_records)
            m3.metric("Multivariate Anomalies", if_res.anomaly_count)
            m4.metric("Anomaly Proportion", f"{if_res.anomaly_percentage:.1f}%")

            # Score distribution visualization
            scores = [row["decision_score"] for row in if_res.evaluated_rows]
            fig, ax = plt.subplots(figsize=(8, 2.5))
            ax.hist(scores, bins=15, color="#1F4E78", edgecolor="white")
            ax.axvline(0.0, color="#ED7D31", linestyle="--", label="Decision Boundary (0.0)")
            ax.set_title("Isolation Forest Decision Score Distribution (Scores < 0 are Anomalies)", fontsize=11, fontweight="bold")
            ax.set_xlabel("Decision Function Score")
            ax.legend(fontsize=8)
            st.pyplot(fig)
            plt.close(fig)

            # Optional 2D scatter plot if exactly 2 features chosen
            if len(if_res.features) == 2:
                feat_x, feat_y = if_res.features[0], if_res.features[1]
                fig, ax = plt.subplots(figsize=(8, 4))
                inlier_x = [r["features"][feat_x] for r in if_res.evaluated_rows if not r["is_anomaly"]]
                inlier_y = [r["features"][feat_y] for r in if_res.evaluated_rows if not r["is_anomaly"]]
                anom_x = [r["features"][feat_x] for r in if_res.evaluated_rows if r["is_anomaly"]]
                anom_y = [r["features"][feat_y] for r in if_res.evaluated_rows if r["is_anomaly"]]

                ax.scatter(inlier_x, inlier_y, color="#2E75B6", label="Inliers (Prediction 1)", alpha=0.7)
                ax.scatter(anom_x, anom_y, color="#ED7D31", marker="x", s=80, label="Anomalies (Prediction -1)", linewidths=2)
                ax.set_xlabel(feat_x, fontsize=10)
                ax.set_ylabel(feat_y, fontsize=10)
                ax.set_title(f"Multivariate Inliers vs Outliers ({feat_x} vs {feat_y})", fontsize=11, fontweight="bold")
                ax.legend()
                st.pyplot(fig)
                plt.close(fig)

            if if_res.anomalies:
                with st.expander(f"⚠️ Flagged Isolation Forest Outliers ({len(if_res.anomalies)})", expanded=True):
                    flat_anom = []
                    for a in if_res.anomalies:
                        entry = {"row_id": a["row_id"], "decision_score": a["decision_score"]}
                        entry.update(a["features"])
                        flat_anom.append(entry)
                    st.dataframe(pd.DataFrame(flat_anom), use_container_width=True)
            else:
                st.info("No records flagged as multivariate outliers by Isolation Forest.")
        else:
            st.warning(f"Isolation Forest did not evaluate records: {if_res.notes}")
    else:
        st.info("Isolation Forest was not configured or executed.")

    # Section 4: Spatial Clustering
    st.markdown("---")
    st.subheader("🗺️ Section 4: Spatial Clustering (DBSCAN)")
    if bundle.clustering_result:
        c_res = bundle.clustering_result
        if c_res.valid_records > 0:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Valid Coordinates", c_res.valid_records)
            m2.metric("Excluded Bad Coords", c_res.excluded_records)
            m3.metric("Dense Clusters Formed", c_res.cluster_count)
            m4.metric("Spatial Noise (-1)", f"{c_res.noise_count} ({c_res.noise_percentage:.1f}%)")

            # Scatter Plot: Longitude vs Latitude
            fig, ax = plt.subplots(figsize=(8, 5))
            colors = plt.cm.tab10.colors
            unique_labels = sorted(list({r["cluster_label"] for r in c_res.evaluated_rows}))

            for lbl in unique_labels:
                lbl_rows = [r for r in c_res.evaluated_rows if r["cluster_label"] == lbl]
                lons = [r["longitude"] for r in lbl_rows]
                lats = [r["latitude"] for r in lbl_rows]

                if lbl == -1:
                    ax.scatter(lons, lats, color="#595959", marker="x", s=70, label=f"Noise / Isolated (-1) [{len(lons)}]", zorder=2)
                else:
                    c = colors[lbl % len(colors)]
                    ax.scatter(lons, lats, color=c, marker="o", s=50, label=f"Cluster {lbl} [{len(lons)}]", alpha=0.8, zorder=3)

            ax.set_xlabel("Longitude (°)", fontsize=10)
            ax.set_ylabel("Latitude (°)", fontsize=10)
            ax.set_title(f"DBSCAN Spatial Clusters (eps={c_res.eps_km:.2f} km, min_samples={c_res.min_samples})", fontsize=11, fontweight="bold")
            ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
            plt.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

            with st.expander(f"📍 Cluster Membership Table ({c_res.valid_records} records)", expanded=False):
                st.dataframe(pd.DataFrame(c_res.evaluated_rows), use_container_width=True)
        else:
            st.warning(f"DBSCAN did not run: {c_res.notes}")
    else:
        st.info("DBSCAN spatial clustering was not configured or executed.")

    # Section 5: Report Downloads
    st.markdown("---")
    st.subheader("📥 Section 5: Report Downloads")

    dl1, dl2 = st.columns(2)
    with dl1:
        try:
            excel_bytes = generate_feature3_excel_bytes(bundle)
            st.download_button(
                label="📥 Download Analytical Excel Report (.xlsx)",
                data=excel_bytes,
                file_name=f"anomaly_clustering_report_{active_dataset.filename}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Failed to generate Excel report: {e}")

    with dl2:
        try:
            ppt_bytes = generate_feature3_ppt_bytes(bundle)
            st.download_button(
                label="📥 Download Analytical PowerPoint Deck (.pptx)",
                data=ppt_bytes,
                file_name=f"anomaly_clustering_report_{active_dataset.filename}.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Failed to generate PPT report: {e}")
