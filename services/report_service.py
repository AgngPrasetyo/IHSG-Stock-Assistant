"""Build offline PDF reports from an existing analysis payload."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from io import BytesIO
import math
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.graphics.shapes import Drawing, Line, PolyLine, String
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
POST_SIGNAL_STATUS_LABELS = {
    "MATCH": "Sesuai arah",
    "NOT_MATCH": "Tidak sesuai arah",
    "NOT_MATCH_FLAT": "Harga tidak berubah",
    "NOT_EVALUATED_HOLD": "Tidak dievaluasi",
    "UNAVAILABLE": "Data belum tersedia",
}
POST_SIGNAL_VALIDATION_DESCRIPTION = (
    "Validasi ini membandingkan sinyal terbaru dengan arah harga pada T+1, T+3, "
    "T+5, dan T+10 hari perdagangan bursa saham. Validasi ini tidak digunakan "
    "untuk mengubah indikator terbaik, sinyal utama, atau hasil evaluasi "
    "Walk-Forward Analysis."
)
INVALID_PDF_TEXT_CHARS = str.maketrans("", "", "■□�")

def _format_user_friendly_condition(analysis: dict[str, Any]) -> str:
    signal = str(analysis.get("latest_signal") or "HOLD").upper()
    indicator = analysis.get("best_indicator") or "indikator terbaik"
    latest_date = analysis.get("latest_date") or "tanggal terakhir"

    if signal == "HOLD":
        return (
            f"Sinyal saat ini adalah HOLD pada {latest_date}. "
            f"Belum ada sinyal BUY atau SELL baru berdasarkan {indicator} pada data terakhir."
        )

    return (
        f"Sinyal saat ini adalah {signal} pada {latest_date} berdasarkan {indicator}."
    )

def _comparison_zero_notes(comparison: list[dict[str, Any]]) -> list[str]:
        notes = []
        for item in comparison:
            try:
                active = int(float(item.get("total_active_signals", 0)))
            except (TypeError, ValueError):
                active = 0

            if active == 0:
                indicator = item.get("indicator") or "Indikator"
                notes.append(
                    f"{indicator} tidak menjadi indikator terpilih pada window WFA sektor ini, "
                    "sehingga tidak memiliki nilai evaluasi final pada rangkuman perbandingan."
                )
        return notes


        

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
        ("Sinyal Aktif Terakhir", _format_last_active_signal(analysis.get("last_active_signal"))),
        ("Indikator Terbaik", analysis.get("best_indicator")),
        ("Harga Penutupan Terakhir", _format_rupiah(analysis.get("latest_close"))),
        ("Kondisi Teknikal", _format_user_friendly_condition(analysis)),
    ], styles),
]))

    metrics = analysis.get("metrics") or {}
    story.append(_section_block(styles, "Metrik Evaluasi", [
    Paragraph(
    "Indikator terbaik dipilih dari hasil gabungan pengujian Out-of-Sample "
    "pada window WFA ketika indikator tersebut terpilih dari In-Sample. "
    "Directional Accuracy digunakan sebagai dasar pemilihan indikator terbaik "
    "dan dihitung berdasarkan kecocokan arah sinyal BUY/SELL terhadap Average "
    "Forward Return pada T+1, T+3, T+5, dan T+10 hari perdagangan bursa saham. "
    "Hit Rate, Total Active Signals, dan Correct Signals digunakan sebagai "
    "metrik pendukung untuk membaca rata-rata keberhasilan dan jumlah sinyal.",
    styles["BodyRelaxed"],
    ),
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

    
    chart_section = _price_chart_section(analysis.get("chart_data"), styles)
    if chart_section is not None:
        story.append(chart_section)

    _add_section(story, styles, "Perbandingan Indikator")
    story.append(Paragraph(
    "Tabel ini menampilkan hasil evaluasi final indikator pada sektor saham terkait. "
    "Indikator terbaik dipilih berdasarkan Directional Accuracy tertinggi dari hasil "
    "gabungan pengujian Out-of-Sample pada window WFA ketika indikator tersebut "
    "terpilih dari In-Sample. Hit Rate, Active, dan Correct digunakan sebagai "
    "metrik pendukung.",
    styles["BodyRelaxed"],
))

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

    zero_notes = _comparison_zero_notes(analysis.get("indicator_comparison") or [])
    if zero_notes:
        story.append(Paragraph(" ".join(zero_notes), styles["BodyRelaxed"]))

    post_signal_validation = analysis.get("post_signal_validation")
    if isinstance(post_signal_validation, list) and post_signal_validation:
        story.append(_post_signal_validation_section(post_signal_validation, styles))


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
        Paragraph(_clean_text("Metrik Evaluasi"), styles["Subtle"]),
        _data_table(metric_hint_rows, styles, col_widths=[4.2 * cm, 11.0 * cm]),
    ]))

    _add_section(story, styles, "Disclaimer")
    story.append(_disclaimer_box(analysis.get("disclaimer") or DISCLAIMER, styles))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def _header(styles: dict[str, ParagraphStyle]) -> list[Any]:
    """Build the fixed report heading without reading external state."""
    return [
        Paragraph(_clean_text("Stock Decision Assistant"), styles["TitleSmall"]),
        Paragraph(_clean_text("Laporan Hasil Analisis Teknikal Saham"), styles["Heading1"]),
        Paragraph(_clean_text(f"Dicetak pada: {date.today().isoformat()}"), styles["Subtle"]),
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
    return KeepTogether([Spacer(1, 0.08 * cm), Paragraph(_clean_text(title), styles["Heading2"]), *flowables])


def _add_section(story: list[Any], styles: dict[str, ParagraphStyle], title: str) -> None:
    """Append a standalone section heading to the report story."""
    story.append(Spacer(1, 0.12 * cm))
    story.append(Paragraph(_clean_text(title), styles["Heading2"]))


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

def _price_chart_section(chart_data: Any, styles: dict[str, ParagraphStyle]) -> KeepTogether | None:
    """Render a simple closing-price chart from frontend chart_data."""
    if not isinstance(chart_data, list):
        return None

    points = []
    for item in chart_data[-120:]:
        if not isinstance(item, dict):
            continue

        date_value = item.get("date")
        close_value = item.get("close")

        try:
            close = float(close_value)
        except (TypeError, ValueError):
            continue

        if not math.isfinite(close):
            continue

        points.append(
            {
                "date": str(date_value or ""),
                "close": close,
            }
        )

    if len(points) < 2:
        return None

    drawing = _build_price_chart_drawing(points)

    return _section_block(styles, "Grafik Harga Penutupan", [
        Paragraph(
            "Grafik ini menampilkan pergerakan harga penutupan terbaru berdasarkan data historis yang digunakan pada dashboard.",
            styles["BodyRelaxed"],
        ),
        drawing,
    ])

def _build_price_chart_drawing(points: list[dict[str, Any]]) -> Drawing:
    """Build a compact line chart drawing for closing prices."""
    width = 15.2 * cm
    height = 5.2 * cm
    left_pad = 1.05 * cm
    right_pad = 0.45 * cm
    top_pad = 0.35 * cm
    bottom_pad = 0.75 * cm

    chart_width = width - left_pad - right_pad
    chart_height = height - top_pad - bottom_pad

    closes = [float(point["close"]) for point in points]
    min_close = min(closes)
    max_close = max(closes)
    value_range = max_close - min_close or 1.0

    drawing = Drawing(width, height)

    axis_color = colors.HexColor("#E2E8F0")
    text_color = colors.HexColor("#728196")
    line_color = colors.HexColor("#2F5BEA")

    x0 = left_pad
    y0 = bottom_pad
    x1 = left_pad + chart_width
    y1 = bottom_pad + chart_height

    drawing.add(Line(x0, y0, x1, y0, strokeColor=axis_color, strokeWidth=0.8))
    drawing.add(Line(x0, y0, x0, y1, strokeColor=axis_color, strokeWidth=0.8))

    coordinates: list[float] = []
    denominator = max(len(points) - 1, 1)

    for index, point in enumerate(points):
        x = left_pad + (index / denominator) * chart_width
        y = bottom_pad + ((float(point["close"]) - min_close) / value_range) * chart_height
        coordinates.extend([x, y])

    drawing.add(PolyLine(coordinates, strokeColor=line_color, strokeWidth=1.6))

    first_date = points[0].get("date") or "-"
    last_date = points[-1].get("date") or "-"

    drawing.add(String(x0, y1 + 3, _format_number(max_close, 0), fontSize=7.5, fillColor=text_color))
    drawing.add(String(x0, y0 - 12, _format_number(min_close, 0), fontSize=7.5, fillColor=text_color))
    drawing.add(String(x0, y0 - 25, first_date, fontSize=7.2, fillColor=text_color))
    drawing.add(String(x1 - 52, y0 - 25, last_date, fontSize=7.2, fillColor=text_color))

    return drawing

def _post_signal_validation_section(
    validations: list[Any],
    styles: dict[str, ParagraphStyle],
) -> KeepTogether:
    """Render latest-signal validation rows already present in the payload."""
    rows = [[
        "Horizon",
        "Sinyal",
        "Tgl. Sinyal",
        "Tgl. Target",
        "Status",
        "Return",
        "Keterangan",
    ]]
    for raw_item in validations:
        item = raw_item if isinstance(raw_item, dict) else {}
        status = str(item.get("status") or "").strip().upper()
        is_hold = status == "NOT_EVALUATED_HOLD"
        rows.append([
            _format_horizon(item),
            item.get("signal"),
            _format_optional_text(item.get("signal_date")),
            "-" if is_hold else _format_optional_text(item.get("target_date")),
            POST_SIGNAL_STATUS_LABELS.get(status, _format_optional_text(status)),
            "-" if is_hold else _format_percent(item.get("return_pct")),
            item.get("message") or item.get("keterangan"),
        ])

    return _section_block(styles, "Validasi Lanjutan Sinyal Terbaru", [
        Paragraph(POST_SIGNAL_VALIDATION_DESCRIPTION, styles["BodyRelaxed"]),
        _data_table(
    rows,
    styles,
        col_widths=[
        1.60 * cm,  # Horizon
        1.45 * cm,  # Sinyal
        2.25 * cm,  # Tgl. Sinyal
        2.25 * cm,  # Tgl. Target
        2.10 * cm,  # Status
        1.55 * cm,  # Return
        4.00 * cm,  # Keterangan
    ],
    align_right_cols={5},
    ),
])

def _format_last_active_signal(value: Any) -> str:
    """Format the latest historical BUY/SELL signal for the PDF report."""
    if not isinstance(value, dict):
        return "Belum ada sinyal aktif BUY/SELL pada periode data yang tersedia."

    signal = str(value.get("signal") or "").strip().upper()
    signal_date = value.get("date")

    if signal not in {"BUY", "SELL"} or not signal_date:
        return "Belum ada sinyal aktif BUY/SELL pada periode data yang tersedia."

    return f"{signal} pada {signal_date}"

def _format_horizon(item: dict[str, Any]) -> str:
    """Format validation horizon without recalculating anything from price data."""
    label = _format_optional_text(item.get("label"))
    if label != "-":
        return label
    horizon = item.get("horizon")
    try:
        return f"T+{int(horizon)}"
    except (TypeError, ValueError):
        return "-"


def _format_optional_text(value: Any) -> str:
    """Return a clean placeholder for optional payload text fields."""
    text = sanitize_pdf_text(value)
    return "-" if text.casefold() in {"none", "null", "undefined", "nan"} else text


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


def sanitize_pdf_text(value: Any) -> str:
    """Normalize and remove characters that render as invalid boxes in PDFs."""
    if isinstance(value, float) and math.isnan(value):
        value = None

    text = "-" if value is None else str(value)
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(INVALID_PDF_TEXT_CHARS)
    cleaned_chars = []
    for char in text:
        category = unicodedata.category(char)
        if category.startswith("C") and char not in {"\n", "\t"}:
            continue
        cleaned_chars.append(char)

    text = "".join(cleaned_chars)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    text = text.replace(", menghasilkan", ", indikator tersebut menghasilkan")
    if text.casefold() in {"", "none", "null", "undefined", "nan"}:
        return "-"
    return text


def _clean_text(value: Any) -> str:
    """Escape sanitized user-facing text for ReportLab Paragraph markup."""
    return escape(sanitize_pdf_text(value)).replace("\n", "<br/>")


def _format_number(value: Any, decimals: int = 2) -> str:
    """Format numeric values for report tables with a safe fallback."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "-"
    if not math.isfinite(numeric):
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
