"""Build offline PDF reports from an existing analysis payload."""

from __future__ import annotations

import re
from datetime import date
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


DISCLAIMER = "Hasil ini merupakan sinyal analisis teknikal, bukan rekomendasi investasi final."
TEXT = colors.HexColor("#141827")
MUTED = colors.HexColor("#536171")
BORDER = colors.HexColor("#E4DED3")
HEADER_BG = colors.HexColor("#F2E6D6")
LABEL_BG = colors.HexColor("#FBFAF7")
DISCLAIMER_BG = colors.HexColor("#FFF7ED")
TEAL = colors.HexColor("#0D8A83")


def build_analysis_pdf(payload: dict[str, Any]) -> bytes:
    """Build a PDF report from an already available frontend analysis payload."""
    if not isinstance(payload, dict):
        raise ValueError("Payload laporan tidak valid.")

    analysis = payload.get("analysis")
    if not isinstance(analysis, dict) or analysis.get("success") is not True:
        raise ValueError("Payload laporan tidak valid.")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.7 * cm,
        title="Laporan Hasil Analisis Teknikal Saham",
        pageCompression=0,
    )
    styles = _styles()
    story: list[Any] = []

    story.extend(_header(styles))
    story.append(_section_block(styles, "Informasi Saham", [
        _key_value_table([
            ("Ticker", analysis.get("ticker")),
            ("Nama Saham", analysis.get("stock_name") or "-"),
            ("Sektor", analysis.get("sector")),
            ("Tanggal Data Terakhir", analysis.get("latest_date")),
        ], styles),
    ]))

    story.append(_section_block(styles, "Ringkasan Hasil", [
        _key_value_table([
            ("Sinyal Teknis Saat Ini", analysis.get("latest_signal")),
            ("Indikator Terbaik", analysis.get("best_indicator")),
            ("Harga Penutupan Terakhir", _format_rupiah(analysis.get("latest_close"))),
            ("Kondisi Teknikal", analysis.get("latest_condition")),
        ], styles),
    ]))

    metrics = analysis.get("metrics") or {}
    story.append(_section_block(styles, "Metrik Evaluasi", [
        _data_table([
            ["Metrik", "Nilai"],
            ["Directional Accuracy", _format_percent(metrics.get("directional_accuracy"))],
            ["Hit Rate", _format_percent(metrics.get("hit_rate"))],
            ["Total Active Signals", _format_number(metrics.get("total_active_signals"), 0)],
            ["Correct Signals", _format_number(metrics.get("correct_signals"), 0)],
        ], styles, col_widths=[10.2 * cm, 5.0 * cm], align_right_cols={1}),
    ]))

    _add_section(story, styles, "Penjelasan Asisten")
    story.append(Paragraph(_clean_text(payload.get("explanation") or "Penjelasan belum tersedia."), styles["BodyRelaxed"]))

    _add_section(story, styles, "Perbandingan Indikator")
    comparison_rows = [["Indikator", "Directional Accuracy", "Hit Rate", "Active", "Correct"]]
    for item in analysis.get("indicator_comparison") or []:
        comparison_rows.append([
            item.get("indicator"),
            _format_percent(item.get("directional_accuracy")),
            _format_percent(item.get("hit_rate")),
            _format_number(item.get("total_active_signals"), 0),
            _format_number(item.get("correct_signals"), 0),
        ])
    if len(comparison_rows) == 1:
        comparison_rows.append(["-", "-", "-", "-", "-"])
    story.append(_data_table(
        comparison_rows,
        styles,
        col_widths=[4.4 * cm, 3.5 * cm, 2.8 * cm, 2.2 * cm, 2.3 * cm],
        align_right_cols={1, 2, 3, 4},
    ))

    hint = analysis.get("technical_hint") or {}
    hint_rows = [["Istilah", "Penjelasan"]]
    for item in hint.get("items") or []:
        hint_rows.append([item.get("term"), item.get("description")])
    if len(hint_rows) == 1:
        hint_rows.append(["-", "-"])

    metric_hint_rows = [["Metrik", "Penjelasan"]]
    for item in hint.get("metric_items") or []:
        metric_hint_rows.append([item.get("term"), item.get("description")])
    if len(metric_hint_rows) == 1:
        metric_hint_rows.append(["-", "-"])

    story.append(_section_block(styles, "Hint Istilah Teknikal", [
        Paragraph(_clean_text(hint.get("title") or "Hint istilah teknikal"), styles["Subtle"]),
        _data_table(hint_rows, styles, col_widths=[4.2 * cm, 11.0 * cm]),
        Spacer(1, 0.12 * cm),
        Paragraph("Metrik Evaluasi", styles["Subtle"]),
        _data_table(metric_hint_rows, styles, col_widths=[4.2 * cm, 11.0 * cm]),
    ]))

    _add_section(story, styles, "Disclaimer")
    story.append(_disclaimer_box(analysis.get("disclaimer") or DISCLAIMER, styles))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def _header(styles: dict[str, ParagraphStyle]) -> list[Any]:
    """Build the fixed report heading without reading external state."""
    return [
        Paragraph("Stock Decision Assistant", styles["TitleSmall"]),
        Paragraph("Laporan Hasil Analisis Teknikal Saham", styles["Heading1"]),
        Paragraph(f"Dicetak pada: {date.today().isoformat()}", styles["Subtle"]),
        Spacer(1, 0.12 * cm),
        HRFlowable(width="100%", thickness=0.6, color=BORDER, spaceBefore=4, spaceAfter=12),
    ]


def _styles() -> dict[str, ParagraphStyle]:
    """Create all ReportLab paragraph styles used by the PDF layout."""
    base = getSampleStyleSheet()
    return {
        "TitleSmall": ParagraphStyle(
            "TitleSmall",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=TEAL,
            spaceAfter=4,
        ),
        "Heading1": ParagraphStyle(
            "Heading1Custom",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=23,
            textColor=TEXT,
            spaceAfter=4,
        ),
        "Heading2": ParagraphStyle(
            "Heading2Custom",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=TEXT,
            spaceBefore=8,
            spaceAfter=6,
        ),
        "Body": ParagraphStyle(
            "BodyCustom",
            parent=base["BodyText"],
            fontSize=9,
            leading=12.5,
            textColor=colors.HexColor("#344054"),
            spaceAfter=4,
        ),
        "BodyRight": ParagraphStyle(
            "BodyRightCustom",
            parent=base["BodyText"],
            fontSize=9,
            leading=12.5,
            alignment=2,
            textColor=colors.HexColor("#344054"),
            spaceAfter=4,
        ),
        "TableHeader": ParagraphStyle(
            "TableHeaderCustom",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.6,
            leading=11.5,
            textColor=TEXT,
            spaceAfter=0,
        ),
        "TableHeaderRight": ParagraphStyle(
            "TableHeaderRightCustom",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.6,
            leading=11.5,
            alignment=2,
            textColor=TEXT,
            spaceAfter=0,
        ),
        "Label": ParagraphStyle(
            "LabelCustom",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12.5,
            textColor=TEXT,
            spaceAfter=0,
        ),
        "Subtle": ParagraphStyle(
            "SubtleCustom",
            parent=base["BodyText"],
            fontSize=9,
            leading=12,
            textColor=MUTED,
            spaceAfter=5,
        ),
        "BodyRelaxed": ParagraphStyle(
            "BodyRelaxedCustom",
            parent=base["BodyText"],
            fontSize=9.2,
            leading=14.2,
            textColor=colors.HexColor("#344054"),
            spaceAfter=8,
        ),
    }


def _section_block(styles: dict[str, ParagraphStyle], title: str, flowables: list[Any]) -> KeepTogether:
    """Keep short sections together so they do not split awkwardly across pages."""
    return KeepTogether([Spacer(1, 0.08 * cm), Paragraph(title, styles["Heading2"]), *flowables])


def _add_section(story: list[Any], styles: dict[str, ParagraphStyle], title: str) -> None:
    """Append a standalone section heading to the report story."""
    story.append(Spacer(1, 0.12 * cm))
    story.append(Paragraph(title, styles["Heading2"]))


def _key_value_table(rows: list[tuple[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    """Render label/value rows without converting Paragraph cells to strings."""
    data = [
        [Paragraph(f"<b>{_clean_text(label)}</b>", styles["Label"]), Paragraph(_clean_text(value), styles["Body"])]
        for label, value in rows
    ]
    table = Table(data, colWidths=[5.0 * cm, 10.2 * cm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("BACKGROUND", (0, 0), (0, -1), LABEL_BG),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _data_table(
    rows: list[list[Any]],
    styles: dict[str, ParagraphStyle],
    col_widths: list[float] | None = None,
    align_right_cols: set[int] | None = None,
) -> Table:
    """Render a formal grid table with optional right-aligned numeric columns."""
    align_right_cols = align_right_cols or set()
    data = []
    for row_index, row in enumerate(rows):
        cells = []
        for col_index, cell in enumerate(row):
            if row_index == 0:
                style = styles["TableHeaderRight"] if col_index in align_right_cols else styles["TableHeader"]
            else:
                style = styles["BodyRight"] if col_index in align_right_cols else styles["Body"]
            cells.append(_table_cell(cell, style))
        data.append(cells)

    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _disclaimer_box(text: Any, styles: dict[str, ParagraphStyle]) -> Table:
    """Render the investment-safety disclaimer as a highlighted single-cell box."""
    table = Table([[Paragraph(_clean_text(text), styles["Body"])]], colWidths=[15.2 * cm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor("#E7D1B9")),
        ("BACKGROUND", (0, 0), (-1, -1), DISCLAIMER_BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def _table_cell(value: Any, style: ParagraphStyle) -> Any:
    """Return flowables unchanged; wrap plain values for table cell text wrapping."""
    if isinstance(value, Paragraph):
        return value
    return Paragraph(_clean_text(value), style)


def _clean_text(value: Any) -> str:
    """Escape user-facing text for ReportLab Paragraph markup."""
    text = "-" if value is None or value == "" else str(value)
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    return escape(text).replace("\n", "<br/>")


def _format_number(value: Any, decimals: int = 2) -> str:
    """Format numeric values for report tables with a safe fallback."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"{numeric:.{decimals}f}"


def _format_rupiah(value: Any) -> str:
    """Format a numeric price as a compact Indonesian Rupiah string."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"Rp {numeric:,.0f}".replace(",", ".")


def _format_percent(value: Any) -> str:
    """Format percentage metrics using two decimal places."""
    formatted = _format_number(value, 2)
    return "-" if formatted == "-" else f"{formatted}%"


def _footer(canvas: Any, doc: SimpleDocTemplate) -> None:
    """Draw the static compliance footer on every PDF page."""
    canvas.saveState()
    width, _height = A4
    y = 1.05 * cm
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.4)
    canvas.line(doc.leftMargin, y + 0.28 * cm, width - doc.rightMargin, y + 0.28 * cm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(doc.leftMargin, y, "Stock Decision Assistant")
    canvas.drawCentredString(width / 2, y, "Bukan rekomendasi investasi final")
    canvas.drawRightString(width - doc.rightMargin, y, f"Halaman {doc.page}")
    canvas.restoreState()

