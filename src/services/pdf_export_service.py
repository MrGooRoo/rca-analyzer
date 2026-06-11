"""
PDF Export Service — генерация PDF-отчёта по результату RCA-анализа.

Зеркалит структуру DOCX-экспорта (export_service.generate_docx):
заголовок + мета, резюме, причинные секции (или bowtie-секции),
таблица рекомендаций, техническая информация.

Используется fpdf2 (чистый Python, без системных зависимостей).
Кириллица обеспечивается встроенными TTF-шрифтами DejaVuSans
(src/services/fonts/), поэтому работает и в Docker без системных шрифтов.

Зависимость: fpdf2 (см. pyproject.toml).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fpdf import FPDF

from src.domain.models import MethodologyType, RCAResult

# ---------------------------------------------------------------------------
# Шрифты
# ---------------------------------------------------------------------------

_FONTS_DIR = Path(__file__).parent / "fonts"
_FONT_REGULAR = _FONTS_DIR / "DejaVuSans.ttf"
_FONT_BOLD = _FONTS_DIR / "DejaVuSans-Bold.ttf"
_FONT_FAMILY = "DejaVu"

# ---------------------------------------------------------------------------
# Цветовая палитра (RGB-кортежи) — совпадает с DOCX-экспортом
# ---------------------------------------------------------------------------

_C_TITLE = (0x1A, 0x1A, 0x2E)
_C_PRIMARY = (0x01, 0x69, 0x6F)
_C_RED = (0xF7, 0x6F, 0x6F)
_C_ORANGE = (0xF7, 0xB9, 0x55)
_C_BLUE = (0x4F, 0x8E, 0xF7)
_C_GREEN = (0x3E, 0xCF, 0x8E)
_C_MUTED = (0x7A, 0x79, 0x74)
_C_HEADER_BG = (0xF0, 0xF0, 0xF4)

_PRIORITY_COLORS = {
    "high": _C_RED,
    "medium": _C_ORANGE,
    "low": _C_GREEN,
}

METHODOLOGY_LABELS = {
    MethodologyType.FIVE_WHY: "5 Почему",
    MethodologyType.ISHIKAWA: "Ishikawa (Рыбья кость)",
    MethodologyType.FTA: "FTA (Дерево отказов)",
    MethodologyType.RCA_SYSTEMIC: "RCA Системный",
    MethodologyType.BOWTIE: "Bowtie (Бабочка)",
}

_PAGE_MARGIN = 18  # мм


class _RCAPdf(FPDF):
    """FPDF с футером-нумерацией страниц."""

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font(_FONT_FAMILY, "", 8)
        self.set_text_color(*_C_MUTED)
        self.cell(0, 8, f"Страница {self.page_no()}", align="C")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_pdf(result: RCAResult) -> bytes:
    """Генерирует PDF-документ и возвращает его как bytes (для FastAPI Response)."""
    pdf = _RCAPdf(orientation="P", unit="mm", format="A4")
    pdf.set_margins(_PAGE_MARGIN, _PAGE_MARGIN, _PAGE_MARGIN)
    pdf.set_auto_page_break(auto=True, margin=18)

    pdf.add_font(_FONT_FAMILY, "", str(_FONT_REGULAR))
    pdf.add_font(_FONT_FAMILY, "B", str(_FONT_BOLD))

    pdf.add_page()

    _add_header(pdf, result)
    _add_summary(pdf, result)

    if result.methodology == MethodologyType.BOWTIE:
        _add_bowtie_section(pdf, result)
    else:
        _add_causal_sections(pdf, result)

    _add_recommendations(pdf, result)
    _add_meta(pdf, result)

    out = pdf.output()
    return bytes(out)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _epw(pdf: FPDF) -> float:
    """Эффективная ширина страницы (с учётом полей)."""
    return pdf.w - pdf.l_margin - pdf.r_margin


def _heading(pdf: FPDF, text: str, color: tuple[int, int, int], size: int = 13) -> None:
    pdf.ln(2)
    pdf.set_font(_FONT_FAMILY, "B", size)
    pdf.set_text_color(*color)
    pdf.multi_cell(_epw(pdf), 7, text)
    pdf.ln(1)


def _bullet(pdf: FPDF, text: str, meta: str) -> None:
    """Маркированный пункт: основной текст + приглушённая мета."""
    pdf.set_font(_FONT_FAMILY, "", 10.5)
    pdf.set_text_color(*_C_TITLE)
    bullet_indent = 5
    x_start = pdf.get_x()
    pdf.cell(bullet_indent, 5.5, "•")
    pdf.set_x(x_start + bullet_indent)
    pdf.multi_cell(_epw(pdf) - bullet_indent, 5.5, text)
    if meta:
        pdf.set_x(x_start + bullet_indent)
        pdf.set_font(_FONT_FAMILY, "", 8)
        pdf.set_text_color(*_C_MUTED)
        pdf.multi_cell(_epw(pdf) - bullet_indent, 4.5, meta)
    pdf.ln(0.5)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _add_header(pdf: FPDF, result: RCAResult) -> None:
    label = METHODOLOGY_LABELS.get(result.methodology, result.methodology.value)
    created = result.created_at.strftime("%d.%m.%Y %H:%M UTC")

    pdf.set_font(_FONT_FAMILY, "B", 18)
    pdf.set_text_color(*_C_TITLE)
    pdf.multi_cell(_epw(pdf), 9, f"Отчёт RCA — {label}")
    pdf.ln(1)

    meta = (
        f"ID: {result.result_id}  |  Дата: {created}  |  "
        f"Модель: {result.model_used}  |  Токены: {result.tokens_used}  |  "
        f"Уверенность: {result.confidence_avg * 100:.0f}%"
    )
    pdf.set_font(_FONT_FAMILY, "", 8.5)
    pdf.set_text_color(*_C_MUTED)
    pdf.multi_cell(_epw(pdf), 5, meta)

    # Разделительная линия
    pdf.ln(1)
    pdf.set_draw_color(*_C_MUTED)
    y = pdf.get_y()
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(3)


def _add_summary(pdf: FPDF, result: RCAResult) -> None:
    _heading(pdf, "Резюме", _C_PRIMARY)
    pdf.set_font(_FONT_FAMILY, "", 11)
    pdf.set_text_color(*_C_TITLE)
    pdf.multi_cell(_epw(pdf), 6, result.summary or "—")
    pdf.ln(2)


def _add_causal_sections(pdf: FPDF, result: RCAResult) -> None:
    """Универсальные секции для ishikawa / five_why / fta / rca_systemic."""
    sections = [
        ("Корневые причины", result.root_causes, _C_RED),
        ("Способствующие факторы", result.contributing_causes, _C_ORANGE),
        ("Непосредственные причины", result.immediate_causes, _C_BLUE),
    ]
    for title, nodes, color in sections:
        if not nodes:
            continue
        _heading(pdf, title, color)
        for node in nodes:
            meta = f"[{node.category}  {node.confidence * 100:.0f}%]"
            _bullet(pdf, node.text, meta)
        pdf.ln(1)


def _add_bowtie_section(pdf: FPDF, result: RCAResult) -> None:
    """Bowtie-специфичные секции, разделённые по category (BOWTIE:*)."""
    all_nodes = result.causal_tree

    def _by_cat(prefix: str) -> list:
        return [n for n in all_nodes if n.category.upper().startswith(f"BOWTIE:{prefix}")]

    hazards = _by_cat("HAZARD")
    top_events = _by_cat("TOP_EVENT")
    threats = _by_cat("THREAT")
    prev_bars = _by_cat("PREVENTION")
    consequences = _by_cat("CONSEQUENCE")
    miti_bars = _by_cat("MITIGATION")

    # Fallback: category не проставлен → стандартное отображение
    if not any([hazards, top_events, threats, prev_bars, consequences, miti_bars]):
        _add_causal_sections(pdf, result)
        return

    bowtie_sections = [
        ("Опасный фактор (Hazard)", hazards, _C_MUTED),
        ("Топ-событие", top_events, _C_RED),
        ("Угрозы", threats, _C_RED),
        ("Барьеры предотвращения", prev_bars, _C_ORANGE),
        ("Последствия", consequences, _C_BLUE),
        ("Барьеры смягчения последствий", miti_bars, _C_GREEN),
    ]
    for title, nodes, color in bowtie_sections:
        if not nodes:
            continue
        _heading(pdf, title, color)
        for node in nodes:
            degraded = node.confidence <= 0.3 and "BARRIER" in node.category.upper()
            suffix = "  ⚠ деградирован" if degraded else ""
            meta = f"[{node.confidence * 100:.0f}%{suffix}]"
            _bullet(pdf, node.text, meta)
        pdf.ln(1)


def _add_recommendations(pdf: FPDF, result: RCAResult) -> None:
    if not result.recommendations:
        return

    _heading(pdf, f"Рекомендации ({len(result.recommendations)})", _C_GREEN)

    # Ширины колонок: №, Приоритет, Категория, Ответственный, Рекомендация
    epw = _epw(pdf)
    widths = [8, 24, 28, 32, epw - 92]
    headers = ["№", "Приоритет", "Категория", "Ответственный", "Рекомендация"]

    # Шапка таблицы
    pdf.set_font(_FONT_FAMILY, "B", 8.5)
    pdf.set_text_color(*_C_TITLE)
    pdf.set_fill_color(*_C_HEADER_BG)
    pdf.set_draw_color(*_C_MUTED)
    line_h = 6
    for w, label in zip(widths, headers, strict=True):
        pdf.cell(w, line_h, label, border=1, align="C", fill=True)
    pdf.ln(line_h)

    # Строки (с переносом текста рекомендации через multi_cell)
    pdf.set_font(_FONT_FAMILY, "", 8.5)
    for idx, rec in enumerate(result.recommendations, start=1):
        cells = [
            str(idx),
            rec.priority.upper(),
            rec.category,
            rec.responsible or "—",
            rec.text,
        ]
        _table_row(pdf, widths, cells, rec.priority)

    pdf.ln(2)


def _table_row(pdf: FPDF, widths: list[float], cells: list[str], priority: str) -> None:
    """Строка таблицы с автоматической высотой по самой длинной ячейке."""
    line_h = 4.6

    # Рассчитываем высоту строки по числу строк в каждой ячейке
    pdf.set_font(_FONT_FAMILY, "", 8.5)
    max_lines = 1
    for w, text in zip(widths, cells, strict=True):
        n = len(pdf.multi_cell(w, line_h, text, dry_run=True, output="LINES"))
        max_lines = max(max_lines, n)
    row_h = max_lines * line_h

    # Перенос страницы, если строка не помещается
    if pdf.get_y() + row_h > pdf.h - pdf.b_margin:
        pdf.add_page()

    x0 = pdf.get_x()
    y0 = pdf.get_y()
    pdf.set_draw_color(*_C_MUTED)

    for i, (w, text) in enumerate(zip(widths, cells, strict=True)):
        x = pdf.get_x()
        y = pdf.get_y()
        # Рамка ячейки на полную высоту строки
        pdf.rect(x, y, w, row_h)
        # Цвет приоритета во второй колонке
        if i == 1:
            pdf.set_text_color(*_PRIORITY_COLORS.get(priority, _C_MUTED))
            pdf.set_font(_FONT_FAMILY, "B", 8.5)
        else:
            pdf.set_text_color(*_C_TITLE)
            pdf.set_font(_FONT_FAMILY, "", 8.5)
        align = "C" if i in (0, 1) else "L"
        pdf.multi_cell(w, line_h, text, align=align, new_x="RIGHT", new_y="TOP")
        pdf.set_xy(x + w, y)

    pdf.set_xy(x0, y0 + row_h)


def _add_meta(pdf: FPDF, result: RCAResult) -> None:
    _heading(pdf, "Техническая информация", _C_MUTED)

    rows = [
        ("result_id", result.result_id),
        ("incident_id", result.incident_id),
        ("methodology", result.methodology.value),
        ("model_used", result.model_used),
        ("tokens_used", str(result.tokens_used)),
        ("confidence_avg", f"{result.confidence_avg:.3f}"),
        ("created_at", result.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")),
        ("exported_at", datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")),
    ]

    epw = _epw(pdf)
    key_w = 42
    val_w = epw - key_w
    line_h = 5.2
    pdf.set_draw_color(*_C_MUTED)

    for k, v in rows:
        if pdf.get_y() + line_h > pdf.h - pdf.b_margin:
            pdf.add_page()
        pdf.set_font(_FONT_FAMILY, "B", 8)
        pdf.set_text_color(*_C_MUTED)
        pdf.cell(key_w, line_h, k, border=1)
        pdf.set_font(_FONT_FAMILY, "", 8)
        pdf.set_text_color(*_C_TITLE)
        pdf.cell(val_w, line_h, v, border=1)
        pdf.ln(line_h)
