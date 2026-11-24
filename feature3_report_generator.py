# feature3_report_generator.py

"""
Excel and PowerPoint Report Generator for Feature 3:
Statistical/ML Anomaly Detection & Spatial Clustering.

Consumes a shared Feature3Bundle object ensuring identical metrics across
the Streamlit dashboard and exported reports.
"""

import os
import io
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.dml.color import RGBColor

from config import OUTPUT_DIR, COLOR_PRIMARY_HEX, PRIMARY_COLOR, WHITE_COLOR
from anomaly_detector import IQRColumnResult, ZScoreColumnResult, IsolationForestResult
from clustering_engine import ClusteringResult

logger = logging.getLogger(__name__)

# Shared Excel styling
HEADER_FILL = PatternFill(fill_type="solid", start_color=COLOR_PRIMARY_HEX)
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
CENTER_ALIGN = Alignment(horizontal="center", vertical="center")
THIN_BORDER = Border(
    left=Side(style="thin", color="CCCCCC"),
    right=Side(style="thin", color="CCCCCC"),
    top=Side(style="thin", color="CCCCCC"),
    bottom=Side(style="thin", color="CCCCCC"),
)


class Feature3Bundle:
    """
    Shared container holding all Feature 3 analytical results for a dataset.
    """

    def __init__(self,
                 dataset_name: str,
                 filename: str,
                 total_rows: int,
                 iqr_results: Optional[Dict[str, IQRColumnResult]] = None,
                 zscore_results: Optional[Dict[str, ZScoreColumnResult]] = None,
                 iforest_result: Optional[IsolationForestResult] = None,
                 clustering_result: Optional[ClusteringResult] = None,
                 config_summary: Optional[Dict[str, Any]] = None):
        self.dataset_name = dataset_name
        self.filename = filename
        self.total_rows = total_rows
        self.iqr_results = iqr_results or {}
        self.zscore_results = zscore_results or {}
        self.iforest_result = iforest_result
        self.clustering_result = clustering_result
        self.config_summary = config_summary or {}
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def generate_feature3_excel_report(bundle: Feature3Bundle,
                                    output_path: Optional[str] = None) -> str:
    """
    Generate a comprehensive multi-sheet Excel report from Feature3Bundle.
    """
    if output_path is None:
        output_path = os.path.join(OUTPUT_DIR, "anomaly_clustering_report.xlsx")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    wb = Workbook()

    # Sheet 1: Analysis Summary
    ws_sum = wb.active
    ws_sum.title = "Analysis Summary"
    _write_analysis_summary(ws_sum, bundle)

    # Sheet 2: IQR Results (if executed)
    if bundle.iqr_results:
        ws_iqr = wb.create_sheet("IQR Results")
        _write_iqr_sheet(ws_iqr, bundle.iqr_results)

    # Sheet 3: Z-score Results (if executed)
    if bundle.zscore_results:
        ws_z = wb.create_sheet("Z-score Results")
        _write_zscore_sheet(ws_z, bundle.zscore_results)

    # Sheet 4: Isolation Forest Results (if executed)
    if bundle.iforest_result and bundle.iforest_result.evaluated_records > 0:
        ws_if = wb.create_sheet("Isolation Forest")
        _write_iforest_sheet(ws_if, bundle.iforest_result)

    # Sheet 5: Spatial Clustering Results (if executed)
    if bundle.clustering_result and bundle.clustering_result.valid_records > 0:
        ws_clust = wb.create_sheet("Spatial Clustering")
        _write_clustering_sheet(ws_clust, bundle.clustering_result)

    # Sheet 6: Excluded Records
    ws_excl = wb.create_sheet("Excluded Records")
    _write_excluded_sheet(ws_excl, bundle)

    # Sheet 7: Analysis Configuration
    ws_cfg = wb.create_sheet("Configuration")
    _write_config_sheet(ws_cfg, bundle)

    wb.save(output_path)
    return output_path


def generate_feature3_excel_bytes(bundle: Feature3Bundle) -> bytes:
    """Generate Excel report and return as bytes for download button."""
    path = os.path.join(OUTPUT_DIR, "temp_feature3_report.xlsx")
    generate_feature3_excel_report(bundle, path)
    with open(path, "rb") as f:
        data = f.read()
    return data


def generate_feature3_ppt_report(bundle: Feature3Bundle,
                                   output_path: Optional[str] = None) -> str:
    """
    Generate a PowerPoint presentation deck from Feature3Bundle.
    """
    if output_path is None:
        output_path = os.path.join(OUTPUT_DIR, "anomaly_clustering_report.pptx")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    ppt = Presentation()

    # Slide 1: Cover Page
    slide = ppt.slides.add_slide(ppt.slide_layouts[0])
    slide.shapes.title.text = "Anomaly Detection & Spatial Clustering Report"
    slide.placeholders[1].text = (
        f"Statistical Analysis, Isolation Forest & DBSCAN Spatial Clustering\n"
        f"Dataset: {bundle.dataset_name} ({bundle.filename})\n"
        f"Generated by ReportForge 2.0 | {bundle.timestamp}"
    )

    # Slide 2: Executive Summary & Overview
    slide = ppt.slides.add_slide(ppt.slide_layouts[1])
    slide.shapes.title.text = "Executive Summary"
    overview_lines = [
        f"• Dataset: {bundle.dataset_name} ({bundle.filename}) with {bundle.total_rows} total rows.",
    ]
    if bundle.iqr_results:
        total_iqr_anom = sum(len(r.anomalies) for r in bundle.iqr_results.values())
        overview_lines.append(f"• IQR Anomaly Detection: Evaluated {len(bundle.iqr_results)} column(s); identified {total_iqr_anom} anomalous value(s).")
    if bundle.zscore_results:
        total_z_anom = sum(len(r.anomalies) for r in bundle.zscore_results.values())
        overview_lines.append(f"• Z-Score Anomaly Detection: Evaluated {len(bundle.zscore_results)} column(s); identified {total_z_anom} anomalous value(s).")
    if bundle.iforest_result:
        if_res = bundle.iforest_result
        overview_lines.append(
            f"• Isolation Forest: Evaluated {if_res.evaluated_records} complete records on {len(if_res.features)} features; "
            f"flagged {if_res.anomaly_count} multivariate outlier(s) ({if_res.anomaly_percentage:.1f}%)."
        )
    if bundle.clustering_result:
        c_res = bundle.clustering_result
        overview_lines.append(
            f"• DBSCAN Spatial Clustering: Grouped {c_res.valid_records} valid coordinates into {c_res.cluster_count} dense cluster(s); "
            f"identified {c_res.noise_count} isolated noise point(s) ({c_res.noise_percentage:.1f}%)."
        )
    slide.placeholders[1].text = "\n\n".join(overview_lines)

    # Slide 3: Statistical Anomaly Detection (IQR & Z-score)
    if bundle.iqr_results or bundle.zscore_results:
        slide = ppt.slides.add_slide(ppt.slide_layouts[1])
        slide.shapes.title.text = "Statistical Anomaly Detection"
        stat_lines = []
        if bundle.iqr_results:
            stat_lines.append("IQR Univariate Analysis (Q1 - 1.5*IQR to Q3 + 1.5*IQR):")
            for col, r in bundle.iqr_results.items():
                stat_lines.append(
                    f"  - Column '{col}': {len(r.anomalies)} anomalies "
                    f"[{r.lower_bound:.2f} to {r.upper_bound:.2f}] (Q1={r.q1:.2f}, Q3={r.q3:.2f}, IQR={r.iqr:.2f})"
                )
        if bundle.zscore_results:
            stat_lines.append("\nZ-Score Univariate Analysis (|Z| > threshold):")
            for col, r in bundle.zscore_results.items():
                stat_lines.append(
                    f"  - Column '{col}': {len(r.anomalies)} anomalies "
                    f"(mean={r.mean:.2f}, std={r.std:.2f}, threshold=±{r.threshold:.1f})"
                )
        slide.placeholders[1].text = "\n".join(stat_lines)

    # Slide 4: Isolation Forest Multivariate Anomaly Detection
    if bundle.iforest_result:
        if_res = bundle.iforest_result
        slide = ppt.slides.add_slide(ppt.slide_layouts[1])
        slide.shapes.title.text = "Isolation Forest Multivariate Analysis"
        if_lines = [
            f"• Selected Features: {', '.join(if_res.features)}",
            f"• Evaluated Records: {if_res.evaluated_records} (Complete Cases)",
            f"• Excluded Incomplete Records: {if_res.excluded_records}",
            f"• Contamination Parameter: {if_res.contamination}",
            f"• Number of Estimators: {if_res.n_estimators} (Random State: {if_res.random_state})",
            f"• Flagged Multivariate Outliers: {if_res.anomaly_count} ({if_res.anomaly_percentage:.1f}%)",
            "\nKey Principles:",
            "  - Unsupervised algorithm isolating anomalies using randomized orthogonal partitions.",
            "  - Anomalies are isolated near tree roots (shorter average path lengths).",
            "  - Decision score < 0 signifies an outlier; lower scores denote stronger anomalies.",
        ]
        slide.placeholders[1].text = "\n".join(if_lines)

    # Slide 5: DBSCAN Spatial Clustering
    if bundle.clustering_result:
        c_res = bundle.clustering_result
        slide = ppt.slides.add_slide(ppt.slide_layouts[1])
        slide.shapes.title.text = "DBSCAN Spatial Clustering"
        c_lines = [
            f"• Distance Threshold (Epsilon): {c_res.eps_km:.2f} km ({c_res.eps_radians:.6f} radians)",
            f"• Minimum Core Samples: {c_res.min_samples}",
            f"• Total Valid Coordinates: {c_res.valid_records} (Excluded: {c_res.excluded_records})",
            f"• Dense Clusters Identified: {c_res.cluster_count}",
            f"• Geographically Isolated Noise Points: {c_res.noise_count} ({c_res.noise_percentage:.1f}%)",
            "\nCluster Sizes Distribution:",
        ]
        for cid, size in sorted(c_res.cluster_sizes.items()):
            c_lines.append(f"  - Cluster {cid}: {size} records")
        c_lines.append("\nOperational Context:")
        c_lines.append("  - DBSCAN noise (-1) indicates spatial isolation, NOT erroneous data.")
        slide.placeholders[1].text = "\n".join(c_lines)

    # Slide 6: Findings & Limitations
    slide = ppt.slides.add_slide(ppt.slide_layouts[1])
    slide.shapes.title.text = "Findings & Operational Limitations"
    finding_lines = [
        "1. Investigation Trigger, Not Proof of Error:",
        "   - Anomaly flags indicate unexpected statistical properties requiring domain review.",
        "2. Univariate vs Multivariate Strengths:",
        "   - IQR and Z-score quickly detect extreme individual values.",
        "   - Isolation Forest reveals conflicting attribute combinations (e.g., massive beds but minimal staff).",
        "3. Spatial Density vs Geographic Errors:",
        "   - DBSCAN noise isolates remote facilities (e.g., rural hospitals) rather than flawed coordinates.",
        "4. Algorithmic Limitations:",
        "   - Z-score assumes roughly unimodal distributions and is sensitive to extreme values.",
        "   - Isolation Forest requires careful contamination selection when unlabeled.",
        "   - DBSCAN uses global epsilon, which may struggle with drastically varying density regimes.",
    ]
    slide.placeholders[1].text = "\n".join(finding_lines)

    ppt.save(output_path)
    return output_path


def generate_feature3_ppt_bytes(bundle: Feature3Bundle) -> bytes:
    """Generate PPT report and return as bytes for download button."""
    path = os.path.join(OUTPUT_DIR, "temp_feature3_report.pptx")
    generate_feature3_ppt_report(bundle, path)
    with open(path, "rb") as f:
        data = f.read()
    return data


# ==============================================================================
# Excel Sheet Writers
# ==============================================================================

def _write_analysis_summary(ws, bundle: Feature3Bundle):
    headers = ["Metric / Parameter", "Value"]
    _write_headers(ws, headers)

    rows = [
        ("Dataset Name", bundle.dataset_name),
        ("Filename", bundle.filename),
        ("Total Records", bundle.total_rows),
        ("Analysis Timestamp", bundle.timestamp),
    ]

    if bundle.iqr_results:
        tot_iqr_anom = sum(len(r.anomalies) for r in bundle.iqr_results.values())
        rows.append(("IQR Columns Evaluated", len(bundle.iqr_results)))
        rows.append(("IQR Anomalies Flagged", tot_iqr_anom))

    if bundle.zscore_results:
        tot_z_anom = sum(len(r.anomalies) for r in bundle.zscore_results.values())
        rows.append(("Z-Score Columns Evaluated", len(bundle.zscore_results)))
        rows.append(("Z-Score Anomalies Flagged", tot_z_anom))

    if bundle.iforest_result:
        rows.append(("Isolation Forest Features", ", ".join(bundle.iforest_result.features)))
        rows.append(("Isolation Forest Evaluated Records", bundle.iforest_result.evaluated_records))
        rows.append(("Isolation Forest Anomalies Flagged", bundle.iforest_result.anomaly_count))
        rows.append(("Isolation Forest Anomaly %", f"{bundle.iforest_result.anomaly_percentage:.2f}%"))

    if bundle.clustering_result:
        rows.append(("DBSCAN Valid Coordinates", bundle.clustering_result.valid_records))
        rows.append(("DBSCAN Dense Clusters", bundle.clustering_result.cluster_count))
        rows.append(("DBSCAN Spatial Noise Points", bundle.clustering_result.noise_count))
        rows.append(("DBSCAN Noise %", f"{bundle.clustering_result.noise_percentage:.2f}%"))

    for r_idx, (k, v) in enumerate(rows, start=2):
        ws.cell(row=r_idx, column=1, value=str(k))
        ws.cell(row=r_idx, column=2, value=str(v))

    _auto_width(ws)
    _apply_borders(ws)


def _write_iqr_sheet(ws, iqr_results: Dict[str, IQRColumnResult]):
    headers = [
        "Row ID", "Column", "Value", "Raw Value", "Boundary Violated",
        "Bound Value", "Deviation", "Explanation"
    ]
    _write_headers(ws, headers)

    curr_row = 2
    for col, r in iqr_results.items():
        for anom in r.anomalies:
            ws.cell(row=curr_row, column=1, value=anom["row_id"])
            ws.cell(row=curr_row, column=2, value=anom["column"])
            ws.cell(row=curr_row, column=3, value=anom["value"])
            ws.cell(row=curr_row, column=4, value=anom["raw_value"])
            ws.cell(row=curr_row, column=5, value=anom["boundary_violated"])
            ws.cell(row=curr_row, column=6, value=round(anom["bound_value"], 4))
            ws.cell(row=curr_row, column=7, value=round(anom["deviation"], 4))
            ws.cell(row=curr_row, column=8, value=anom["explanation"])
            curr_row += 1

    _auto_width(ws)
    _apply_borders(ws)


def _write_zscore_sheet(ws, zscore_results: Dict[str, ZScoreColumnResult]):
    headers = [
        "Row ID", "Column", "Value", "Raw Value", "Z-Score", "Deviation from Mean", "Explanation"
    ]
    _write_headers(ws, headers)

    curr_row = 2
    for col, r in zscore_results.items():
        for anom in r.anomalies:
            ws.cell(row=curr_row, column=1, value=anom["row_id"])
            ws.cell(row=curr_row, column=2, value=anom["column"])
            ws.cell(row=curr_row, column=3, value=anom["value"])
            ws.cell(row=curr_row, column=4, value=anom["raw_value"])
            ws.cell(row=curr_row, column=5, value=anom["z_score"])
            ws.cell(row=curr_row, column=6, value=round(anom["deviation_from_mean"], 4))
            ws.cell(row=curr_row, column=7, value=anom["explanation"])
            curr_row += 1

    _auto_width(ws)
    _apply_borders(ws)


def _write_iforest_sheet(ws, if_result: IsolationForestResult):
    headers = ["Row ID", "Decision Score", "Prediction", "Is Anomaly"] + if_result.features
    _write_headers(ws, headers)

    for r_idx, row in enumerate(if_result.evaluated_rows, start=2):
        ws.cell(row=r_idx, column=1, value=row["row_id"])
        ws.cell(row=r_idx, column=2, value=row["decision_score"])
        ws.cell(row=r_idx, column=3, value="Outlier (-1)" if row["prediction"] == -1 else "Inlier (1)")
        ws.cell(row=r_idx, column=4, value="YES" if row["is_anomaly"] else "No")
        for f_idx, feat in enumerate(if_result.features, start=5):
            ws.cell(row=r_idx, column=f_idx, value=row["features"].get(feat))

    _auto_width(ws)
    _apply_borders(ws)


def _write_clustering_sheet(ws, c_result: ClusteringResult):
    headers = ["Row ID", "Latitude", "Longitude", "Cluster Label", "Is Noise (-1)", "Is Core Point"]
    _write_headers(ws, headers)

    for r_idx, row in enumerate(c_result.evaluated_rows, start=2):
        ws.cell(row=r_idx, column=1, value=row["row_id"])
        ws.cell(row=r_idx, column=2, value=row["latitude"])
        ws.cell(row=r_idx, column=3, value=row["longitude"])
        ws.cell(row=r_idx, column=4, value=row["cluster_label"])
        ws.cell(row=r_idx, column=5, value="YES" if row["is_noise"] else "No")
        ws.cell(row=r_idx, column=6, value="YES" if row["is_core_point"] else "No")

    _auto_width(ws)
    _apply_borders(ws)


def _write_excluded_sheet(ws, bundle: Feature3Bundle):
    headers = ["Module / Algorithm", "Row ID", "Reason", "Details"]
    _write_headers(ws, headers)

    curr_row = 2

    # IQR Excluded
    for col, r in bundle.iqr_results.items():
        for exc in r.excluded_details:
            ws.cell(row=curr_row, column=1, value=f"IQR ({col})")
            ws.cell(row=curr_row, column=2, value=exc["row_id"])
            ws.cell(row=curr_row, column=3, value=exc["reason"])
            ws.cell(row=curr_row, column=4, value=f"Raw: {exc.get('raw_value', '')}")
            curr_row += 1

    # Z-Score Excluded
    for col, r in bundle.zscore_results.items():
        for exc in r.excluded_details:
            ws.cell(row=curr_row, column=1, value=f"Z-Score ({col})")
            ws.cell(row=curr_row, column=2, value=exc["row_id"])
            ws.cell(row=curr_row, column=3, value=exc["reason"])
            ws.cell(row=curr_row, column=4, value=f"Raw: {exc.get('raw_value', '')}")
            curr_row += 1

    # Isolation Forest Excluded
    if bundle.iforest_result:
        for exc in bundle.iforest_result.excluded_details:
            ws.cell(row=curr_row, column=1, value="Isolation Forest")
            ws.cell(row=curr_row, column=2, value=exc["row_id"])
            ws.cell(row=curr_row, column=3, value=exc["reason"])
            ws.cell(row=curr_row, column=4, value="")
            curr_row += 1

    # Spatial Clustering Excluded
    if bundle.clustering_result:
        for exc in bundle.clustering_result.excluded_details:
            ws.cell(row=curr_row, column=1, value="DBSCAN Spatial")
            ws.cell(row=curr_row, column=2, value=exc["row_id"])
            ws.cell(row=curr_row, column=3, value=exc["reason"])
            ws.cell(row=curr_row, column=4, value=f"Lat: {exc.get('raw_latitude', '')}, Lon: {exc.get('raw_longitude', '')}")
            curr_row += 1

    _auto_width(ws)
    _apply_borders(ws)


def _write_config_sheet(ws, bundle: Feature3Bundle):
    headers = ["Parameter", "Configured Value"]
    _write_headers(ws, headers)

    curr_row = 2
    for k, v in bundle.config_summary.items():
        ws.cell(row=curr_row, column=1, value=str(k))
        ws.cell(row=curr_row, column=2, value=str(v))
        curr_row += 1

    _auto_width(ws)
    _apply_borders(ws)


def _write_headers(ws, headers: List[str]):
    for col_idx, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=col_idx, value=h)
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.alignment = CENTER_ALIGN


def _auto_width(ws):
    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            if cell.value is not None:
                max_len = max(max_len, min(len(str(cell.value)), 60))
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)


def _apply_borders(ws):
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                cell.border = THIN_BORDER
