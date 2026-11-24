# dq_report_generator.py

"""
Data Quality & Source Comparison Report Generator for ReportForge 2.0.

Generates Excel and PowerPoint reports from shared analysis result objects
(QualityResult, ComparisonResult). Uses the same result objects as the
Streamlit dashboard to ensure consistency.

Does NOT independently recalculate any metrics.
"""

import os
import io
import logging
from datetime import datetime
from typing import Optional

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.dml.color import RGBColor

from config import OUTPUT_DIR, COLOR_PRIMARY_HEX, PRIMARY_COLOR, WHITE_COLOR

logger = logging.getLogger(__name__)

# Shared styles
HEADER_FILL = PatternFill(fill_type="solid", start_color=COLOR_PRIMARY_HEX)
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
CENTER_ALIGN = Alignment(horizontal="center", vertical="center")
WRAP_ALIGN = Alignment(horizontal="left", vertical="top", wrap_text=True)
THIN_BORDER = Border(
    left=Side(style="thin", color="CCCCCC"),
    right=Side(style="thin", color="CCCCCC"),
    top=Side(style="thin", color="CCCCCC"),
    bottom=Side(style="thin", color="CCCCCC"),
)


class AnalysisBundle:
    """
    Shared analysis result container passed to both dashboard and report generators.

    Attributes:
        quality_results: List of QualityResult objects.
        comparison_result: Optional ComparisonResult object.
        datasets: List of IngestedDataset objects.
        config_summary: Dict describing analysis configuration.
        timestamp: When the analysis was performed.
    """

    def __init__(self, quality_results=None, comparison_result=None,
                 datasets=None, config_summary=None):
        self.quality_results = quality_results or []
        self.comparison_result = comparison_result
        self.datasets = datasets or []
        self.config_summary = config_summary or {}
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def generate_dq_excel_report(bundle: AnalysisBundle,
                              output_path: Optional[str] = None) -> str:
    """
    Generate a comprehensive Excel report from the analysis bundle.

    Sheets:
    1. Quality Summary — per-source quality metrics.
    2. Data Quality Issues — full issue table.
    3. Source Comparison — match summary (if comparison was run).
    4. Matched Entities — confirmed matches.
    5. Exclusive Entities — entities unique to each source.
    6. Ambiguous Matches — unresolved candidates.
    7. Attribute Conflicts — conflicting attributes.
    8. Analysis Configuration — parameters used.

    Returns:
        Path to the generated Excel file.
    """
    if output_path is None:
        output_path = os.path.join(OUTPUT_DIR, "data_quality_report.xlsx")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    wb = Workbook()

    # === Sheet 1: Quality Summary ===
    ws = wb.active
    ws.title = "Quality Summary"
    _write_quality_summary(ws, bundle.quality_results)

    # === Sheet 2: Data Quality Issues ===
    ws_issues = wb.create_sheet("Data Quality Issues")
    _write_issues_sheet(ws_issues, bundle.quality_results)

    # === Sheets 3-7: Source Comparison (if available) ===
    if bundle.comparison_result:
        cr = bundle.comparison_result

        ws_comp = wb.create_sheet("Source Comparison")
        _write_comparison_summary(ws_comp, cr)

        ws_matched = wb.create_sheet("Matched Entities")
        _write_matched_sheet(ws_matched, cr)

        ws_exclusive = wb.create_sheet("Exclusive Entities")
        _write_exclusive_sheet(ws_exclusive, cr)

        ws_ambiguous = wb.create_sheet("Ambiguous Matches")
        _write_ambiguous_sheet(ws_ambiguous, cr)

        ws_conflicts = wb.create_sheet("Attribute Conflicts")
        _write_conflicts_sheet(ws_conflicts, cr)

    # === Sheet 8: Analysis Configuration ===
    ws_config = wb.create_sheet("Analysis Configuration")
    _write_config_sheet(ws_config, bundle)

    wb.save(output_path)
    logger.info(f"Data quality Excel report saved at '{output_path}'")
    return output_path


def generate_dq_excel_bytes(bundle: AnalysisBundle) -> bytes:
    """Generate Excel report and return as bytes for Streamlit download."""
    output_path = os.path.join(OUTPUT_DIR, "data_quality_report.xlsx")
    generate_dq_excel_report(bundle, output_path)
    with open(output_path, "rb") as f:
        return f.read()


def generate_dq_ppt_report(bundle: AnalysisBundle,
                            output_path: Optional[str] = None) -> str:
    """
    Generate a PowerPoint presentation from the analysis bundle.

    Slides:
    1. Report Overview.
    2. Source Descriptions.
    3. Data Quality Summary.
    4. Quality Comparison Chart.
    5. Source Overlap & Jaccard Similarity (if comparison).
    6. Important Quality Issues.
    7. Attribute Conflict Summary (if comparison).
    8. Findings & Limitations.

    Returns:
        Path to the generated PPT file.
    """
    if output_path is None:
        output_path = os.path.join(OUTPUT_DIR, "data_quality_report.pptx")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    ppt = Presentation()

    # Slide 1: Report Overview
    slide = ppt.slides.add_slide(ppt.slide_layouts[0])
    slide.shapes.title.text = "Data Intelligence Report"
    slide.placeholders[1].text = (
        f"Data Quality & Source Comparison Analysis\n"
        f"Generated by ReportForge 2.0\n"
        f"Analysis Date: {bundle.timestamp}"
    )

    # Slide 2: Source Descriptions
    slide = ppt.slides.add_slide(ppt.slide_layouts[1])
    slide.shapes.title.text = "Data Sources"
    source_lines = []
    for ds in bundle.datasets:
        line = f"• {ds.source_name}: {ds.filename}"
        if ds.sheet_name:
            line += f" (Sheet: {ds.sheet_name})"
        line += f" — {len(ds.raw_df)} records, {len(ds.raw_df.columns) - 1} columns"
        source_lines.append(line)
    slide.placeholders[1].text = "\n\n".join(source_lines) if source_lines else "No datasets loaded."

    # Slide 3: Data Quality Summary
    slide = ppt.slides.add_slide(ppt.slide_layouts[1])
    slide.shapes.title.text = "Data Quality Summary"
    quality_lines = []
    for qr in bundle.quality_results:
        s = qr.to_summary_dict()
        quality_lines.append(
            f"Source: {s['source_name']}\n"
            f"  Records: {s['total_records']}  |  "
            f"Completeness: {s['completeness']}  |  "
            f"Validity: {s['validity']}\n"
            f"  Uniqueness: {s['uniqueness']}  |  "
            f"Freshness: {s['freshness']}  |  "
            f"Timestamp Coverage: {s['timestamp_coverage']}"
        )
    slide.placeholders[1].text = "\n\n".join(quality_lines) if quality_lines else "No quality analysis performed."

    # Slide 4: Quality Metric Comparison (KPI cards)
    if len(bundle.quality_results) >= 1:
        slide = ppt.slides.add_slide(ppt.slide_layouts[5])
        slide.shapes.title.text = "Quality Metrics Overview"

        for i, qr in enumerate(bundle.quality_results[:2]):
            s = qr.to_summary_dict()
            x_offset = 0.5 + i * 4.8
            y_start = 1.5

            cards = [
                ("Completeness", s["completeness"]),
                ("Validity", s["validity"]),
                ("Uniqueness", s["uniqueness"]),
                ("Freshness", s["freshness"]),
            ]

            # Source label
            label = slide.shapes.add_textbox(
                Inches(x_offset), Inches(1.2), Inches(4.3), Inches(0.3)
            )
            label.text_frame.text = s["source_name"]
            label.text_frame.paragraphs[0].font.bold = True
            label.text_frame.paragraphs[0].font.size = Pt(12)

            for j, (metric, val) in enumerate(cards):
                left = Inches(x_offset)
                top = Inches(y_start + j * 1.3)
                card = slide.shapes.add_shape(
                    MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
                    left, top, Inches(4.3), Inches(1.1)
                )
                card.fill.solid()
                card.fill.fore_color.rgb = PRIMARY_COLOR
                tf = card.text_frame
                tf.text = f"{metric}\n{val}"
                for para in tf.paragraphs:
                    para.font.color.rgb = WHITE_COLOR
                    para.font.size = Pt(11)

    # Slide 5: Source Overlap & Jaccard Similarity
    if bundle.comparison_result:
        cr = bundle.comparison_result
        slide = ppt.slides.add_slide(ppt.slide_layouts[1])
        slide.shapes.title.text = "Source Overlap Analysis"

        summary = cr.to_summary_dict()
        jaccard_pct = (
            f"{summary['jaccard_similarity'] * 100:.1f}%"
            if summary['jaccard_similarity'] is not None else "N/A"
        )

        slide.placeholders[1].text = (
            f"• Source A ({summary['source_a']}): {summary['total_a']} unique entities\n"
            f"• Source B ({summary['source_b']}): {summary['total_b']} unique entities\n\n"
            f"• Confirmed Matches: {summary['matched_count']}\n"
            f"• Exclusive to A: {summary['exclusive_a_count']}\n"
            f"• Exclusive to B: {summary['exclusive_b_count']}\n"
            f"• Ambiguous Candidates: {summary['ambiguous_count']}\n\n"
            f"• Jaccard Similarity: {jaccard_pct}\n\n"
            f"• Attribute Conflicts: {summary['conflict_count']}"
        )

    # Slide 6: Important Quality Issues
    all_issues = []
    for qr in bundle.quality_results:
        all_issues.extend(qr.issues)

    if all_issues:
        slide = ppt.slides.add_slide(ppt.slide_layouts[1])
        slide.shapes.title.text = "Key Data Quality Issues"

        # Summarize by issue type
        issue_counts = {}
        for issue in all_issues:
            itype = issue["issue_type"]
            issue_counts[itype] = issue_counts.get(itype, 0) + 1

        issue_lines = []
        for itype, count in sorted(issue_counts.items(), key=lambda x: -x[1]):
            issue_lines.append(f"• {itype}: {count} occurrences")

        slide.placeholders[1].text = (
            f"Total Issues Found: {len(all_issues)}\n\n" +
            "\n".join(issue_lines[:10])
        )

    # Slide 7: Attribute Conflicts
    if bundle.comparison_result and bundle.comparison_result.conflicts:
        slide = ppt.slides.add_slide(ppt.slide_layouts[1])
        slide.shapes.title.text = "Attribute Conflicts"

        conflict_lines = []
        for c in bundle.comparison_result.conflicts[:8]:
            conflict_lines.append(
                f"• {c['entity_id']} — {c['attribute']}: "
                f"'{c['value_a']}' ({c['source_a']}) vs "
                f"'{c['value_b']}' ({c['source_b']})"
            )

        total_conflicts = len(bundle.comparison_result.conflicts)
        showing = min(8, total_conflicts)
        slide.placeholders[1].text = (
            f"Showing {showing} of {total_conflicts} conflicts:\n\n" +
            "\n".join(conflict_lines)
        )

    # Slide 8: Findings & Limitations
    slide = ppt.slides.add_slide(ppt.slide_layouts[1])
    slide.shapes.title.text = "Findings & Limitations"

    findings = []
    for qr in bundle.quality_results:
        s = qr.to_summary_dict()
        if s["completeness_value"] is not None and s["completeness_value"] < 90:
            findings.append(f"• {s['source_name']} has low completeness ({s['completeness']}).")
        if s["uniqueness_value"] is not None and s["uniqueness_value"] < 100:
            findings.append(f"• {s['source_name']} contains duplicate identifiers ({s['uniqueness']}).")

    findings.append("")
    findings.append("Limitations:")
    findings.append("• Fuzzy matching uses O(n×m) pairwise comparison — may be slow for large datasets.")
    findings.append("• Geographic proximity matching assumes spherical Earth (Haversine).")
    findings.append("• Ambiguous matches require manual review for confirmation.")
    findings.append("• This tool evaluates data quality but does not determine which source is authoritative.")

    slide.placeholders[1].text = "\n".join(findings)

    ppt.save(output_path)
    logger.info(f"Data quality PPT report saved at '{output_path}'")
    return output_path


def generate_dq_ppt_bytes(bundle: AnalysisBundle) -> bytes:
    """Generate PPT report and return as bytes for Streamlit download."""
    output_path = os.path.join(OUTPUT_DIR, "data_quality_report.pptx")
    generate_dq_ppt_report(bundle, output_path)
    with open(output_path, "rb") as f:
        return f.read()


# ============================================================
# Excel Sheet Writers
# ============================================================

def _write_quality_summary(ws, quality_results):
    """Write quality summary sheet."""
    headers = [
        "Source Name", "Filename", "Sheet", "Total Records",
        "Completeness", "Validity", "Uniqueness", "Freshness",
        "Timestamp Coverage", "Missing Values", "Duplicates",
        "Invalid Records", "Stale Records"
    ]
    _write_headers(ws, headers)

    for row_idx, qr in enumerate(quality_results, start=2):
        s = qr.to_summary_dict()
        ws.cell(row=row_idx, column=1, value=s["source_name"])
        ws.cell(row=row_idx, column=2, value=s["filename"])
        ws.cell(row=row_idx, column=3, value=s["sheet_name"])
        ws.cell(row=row_idx, column=4, value=s["total_records"])
        ws.cell(row=row_idx, column=5, value=s["completeness"])
        ws.cell(row=row_idx, column=6, value=s["validity"])
        ws.cell(row=row_idx, column=7, value=s["uniqueness"])
        ws.cell(row=row_idx, column=8, value=s["freshness"])
        ws.cell(row=row_idx, column=9, value=s["timestamp_coverage"])
        ws.cell(row=row_idx, column=10, value=s["missing_values"])
        ws.cell(row=row_idx, column=11, value=s["duplicate_identifiers"])
        ws.cell(row=row_idx, column=12, value=s["invalid_records"])
        ws.cell(row=row_idx, column=13, value=s["stale_records"])

    _auto_width(ws)
    _apply_borders(ws)


def _write_issues_sheet(ws, quality_results):
    """Write issues detail sheet."""
    headers = [
        "Source", "Filename", "Sheet", "Row ID", "Business ID",
        "Column", "Issue Type", "Original Value", "Explanation"
    ]
    _write_headers(ws, headers)

    row_idx = 2
    for qr in quality_results:
        for issue in qr.issues:
            ws.cell(row=row_idx, column=1, value=issue.get("source_name", ""))
            ws.cell(row=row_idx, column=2, value=issue.get("filename", ""))
            ws.cell(row=row_idx, column=3, value=issue.get("sheet_name", ""))
            ws.cell(row=row_idx, column=4, value=issue.get("row_id", ""))
            ws.cell(row=row_idx, column=5, value=issue.get("business_id", ""))
            ws.cell(row=row_idx, column=6, value=issue.get("column", ""))
            ws.cell(row=row_idx, column=7, value=issue.get("issue_type", ""))
            ws.cell(row=row_idx, column=8, value=issue.get("original_value", ""))
            ws.cell(row=row_idx, column=9, value=issue.get("explanation", ""))
            row_idx += 1

    _auto_width(ws)
    _apply_borders(ws)


def _write_comparison_summary(ws, cr):
    """Write comparison summary sheet."""
    summary = cr.to_summary_dict()

    headers = ["Metric", "Value"]
    _write_headers(ws, headers)

    metrics = [
        ("Source A", summary["source_a"]),
        ("Source B", summary["source_b"]),
        ("Total Unique in A", summary["total_a"]),
        ("Total Unique in B", summary["total_b"]),
        ("Confirmed Matches", summary["matched_count"]),
        ("Exclusive to A", summary["exclusive_a_count"]),
        ("Exclusive to B", summary["exclusive_b_count"]),
        ("Ambiguous / Unresolved Candidates", summary["ambiguous_count"]),
        ("Proximity-Only Candidates", summary.get("potential_geo_count", 0)),
        ("Unmatchable in A", summary["unmatchable_a_count"]),
        ("Unmatchable in B", summary["unmatchable_b_count"]),
        ("Jaccard Similarity" + (" (Estimate)" if summary.get("jaccard_is_estimate") else ""), (
            f"{summary['jaccard_similarity']:.4f}"
            if summary['jaccard_similarity'] is not None else "N/A"
        )),
        ("Attribute Conflicts", summary["conflict_count"]),
    ]

    for row_idx, (metric, val) in enumerate(metrics, start=2):
        ws.cell(row=row_idx, column=1, value=metric)
        ws.cell(row=row_idx, column=2, value=str(val))

    # Add Jaccard explanation
    exp_row = len(metrics) + 3
    ws.cell(row=exp_row, column=1, value="Jaccard Explanation")
    ws.cell(row=exp_row, column=1).font = Font(bold=True)
    ws.cell(row=exp_row + 1, column=1, value=summary.get("jaccard_explanation", ""))

    _auto_width(ws)
    _apply_borders(ws)


def _write_matched_sheet(ws, cr):
    """Write matched entities sheet."""
    headers = [
        "ID (Source A)", "ID (Source B)", "Row A", "Row B",
        "Method", "Score/Distance", "Source A", "Source B"
    ]
    _write_headers(ws, headers)

    for row_idx, m in enumerate(cr.matched, start=2):
        ws.cell(row=row_idx, column=1, value=str(m.get("id_a", "")))
        ws.cell(row=row_idx, column=2, value=str(m.get("id_b", "")))
        ws.cell(row=row_idx, column=3, value=m.get("row_id_a", ""))
        ws.cell(row=row_idx, column=4, value=m.get("row_id_b", ""))
        ws.cell(row=row_idx, column=5, value=m.get("method", ""))
        ws.cell(row=row_idx, column=6, value=m.get("score", ""))
        ws.cell(row=row_idx, column=7, value=m.get("source_a", ""))
        ws.cell(row=row_idx, column=8, value=m.get("source_b", ""))

    _auto_width(ws)
    _apply_borders(ws)


def _write_exclusive_sheet(ws, cr):
    """Write exclusive entities sheet."""
    ws.cell(row=1, column=1, value=f"Exclusive to {cr.source_a_name}")
    ws.cell(row=1, column=1).font = Font(bold=True, size=12)

    start_row = 3
    if not cr.exclusive_a.empty:
        for col_idx, col in enumerate(cr.exclusive_a.columns, start=1):
            cell = ws.cell(row=start_row, column=col_idx, value=str(col))
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL

        for r_idx, (_, row) in enumerate(cr.exclusive_a.iterrows(), start=start_row + 1):
            for c_idx, val in enumerate(row.values, start=1):
                ws.cell(row=r_idx, column=c_idx, value=str(val) if pd.notna(val) else "")

    separator_row = start_row + len(cr.exclusive_a) + 3
    ws.cell(row=separator_row, column=1, value=f"Exclusive to {cr.source_b_name}")
    ws.cell(row=separator_row, column=1).font = Font(bold=True, size=12)

    b_start = separator_row + 2
    if not cr.exclusive_b.empty:
        for col_idx, col in enumerate(cr.exclusive_b.columns, start=1):
            cell = ws.cell(row=b_start, column=col_idx, value=str(col))
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL

        for r_idx, (_, row) in enumerate(cr.exclusive_b.iterrows(), start=b_start + 1):
            for c_idx, val in enumerate(row.values, start=1):
                ws.cell(row=r_idx, column=c_idx, value=str(val) if pd.notna(val) else "")

    _auto_width(ws)
    _apply_borders(ws)


def _write_ambiguous_sheet(ws, cr):
    """Write ambiguous matches sheet."""
    headers = [
        "ID (Source A)", "ID (Source B)", "Row A", "Row B",
        "Method", "Score/Distance", "Reason"
    ]
    _write_headers(ws, headers)

    for row_idx, a in enumerate(cr.ambiguous, start=2):
        ws.cell(row=row_idx, column=1, value=str(a.get("id_a", "")))
        ws.cell(row=row_idx, column=2, value=str(a.get("id_b", "")))
        ws.cell(row=row_idx, column=3, value=a.get("row_id_a", ""))
        ws.cell(row=row_idx, column=4, value=a.get("row_id_b", ""))
        ws.cell(row=row_idx, column=5, value=a.get("method", ""))
        ws.cell(row=row_idx, column=6, value=a.get("score", ""))
        ws.cell(row=row_idx, column=7, value=a.get("reason", ""))
        row_idx += 1

    _auto_width(ws)
    _apply_borders(ws)


def _write_conflicts_sheet(ws, cr):
    """Write attribute conflicts sheet."""
    headers = [
        "Entity ID", "Entity Name", "Attribute", "Value (Source A)",
        "Value (Source B)", "Source A", "Source B",
        "Row A", "Row B", "Match Method", "Conflict Type"
    ]
    _write_headers(ws, headers)

    for row_idx, c in enumerate(cr.conflicts, start=2):
        ws.cell(row=row_idx, column=1, value=c.get("entity_id", ""))
        ws.cell(row=row_idx, column=2, value=c.get("entity_name", ""))
        ws.cell(row=row_idx, column=3, value=c.get("attribute", ""))
        ws.cell(row=row_idx, column=4, value=c.get("value_a", ""))
        ws.cell(row=row_idx, column=5, value=c.get("value_b", ""))
        ws.cell(row=row_idx, column=6, value=c.get("source_a", ""))
        ws.cell(row=row_idx, column=7, value=c.get("source_b", ""))
        ws.cell(row=row_idx, column=8, value=c.get("row_id_a", ""))
        ws.cell(row=row_idx, column=9, value=c.get("row_id_b", ""))
        ws.cell(row=row_idx, column=10, value=c.get("method", ""))
        ws.cell(row=row_idx, column=11, value=c.get("conflict_type", ""))

    _auto_width(ws)
    _apply_borders(ws)


def _write_config_sheet(ws, bundle):
    """Write analysis configuration sheet."""
    headers = ["Parameter", "Value"]
    _write_headers(ws, headers)

    row_idx = 2
    ws.cell(row=row_idx, column=1, value="Analysis Timestamp")
    ws.cell(row=row_idx, column=2, value=bundle.timestamp)
    row_idx += 1

    ws.cell(row=row_idx, column=1, value="Number of Datasets")
    ws.cell(row=row_idx, column=2, value=len(bundle.datasets))
    row_idx += 1

    for key, val in bundle.config_summary.items():
        ws.cell(row=row_idx, column=1, value=str(key))
        ws.cell(row=row_idx, column=2, value=str(val))
        row_idx += 1

    _auto_width(ws)
    _apply_borders(ws)


# ============================================================
# Utility Functions
# ============================================================

def _write_headers(ws, headers):
    """Write styled header row."""
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER_ALIGN


def _auto_width(ws):
    """Auto-fit column widths."""
    for column in ws.columns:
        max_length = 0
        col_letter = column[0].column_letter
        for cell in column:
            if cell.value is not None:
                max_length = max(max_length, min(len(str(cell.value)), 50))
        ws.column_dimensions[col_letter].width = max(max_length + 3, 12)


def _apply_borders(ws):
    """Apply thin borders to all cells with data."""
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                cell.border = THIN_BORDER
