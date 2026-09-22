#!/usr/bin/env python3
"""Create selected token/cost charts styled like selected_correctness_charts.pdf."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from reportlab import rl_config
from reportlab.graphics import renderPDF, renderSVG
from reportlab.graphics.shapes import Circle, Drawing, Group, Line, Rect, String
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

rl_config.invariant = 1


ANALYSIS_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ANALYSIS_DIR / "grafici_token_costi_selezionati"
FIGURES_IT = OUTPUT_DIR / "figures"
FIGURES_EN = OUTPUT_DIR / "figures_en"
PDF_DIR = OUTPUT_DIR / "output" / "pdf"
RENDERED_IT = OUTPUT_DIR / "output" / "rendered"
RENDERED_EN = OUTPUT_DIR / "output" / "rendered_en"
SUMMARY_PATH = ANALYSIS_DIR / "tables" / "model_token_costs_17x60.csv"
RAW_PATH = ANALYSIS_DIR / "data" / "model_item_resources.csv"
DEEPSEEK_PATH = ANALYSIS_DIR / "tables" / "deepseek_flash_thinking_vs_no_thinking.csv"
METHODOLOGY_PATH = ANALYSIS_DIR / "README.md"
REFERENCE_PDF = ANALYSIS_DIR / "grafici_selezionati" / "output" / "pdf" / "selected_correctness_charts.pdf"

PAGE_W, PAGE_H = landscape(A4)
NAVY = HexColor("#17324D")
MUTED = HexColor("#5B6E82")
GRID = HexColor("#D6E0E8")
LIGHT_GRID = HexColor("#E8EEF2")
ROW_ALT = HexColor("#F7F9FA")
WHITE = HexColor("#FFFFFF")
INK = HexColor("#172534")
CREAM = HexColor("#F7F2E8")
RED = HexColor("#B23A3A")
GREEN = HexColor("#0F8A83")

PROVIDER_COLORS = {
    "openai": HexColor("#0F8A83"),
    "anthropic": HexColor("#B35A00"),
    "google": HexColor("#2C6ECB"),
    "deepseek": HexColor("#5A4BD6"),
    "xai": HexColor("#202124"),
    "mistral": HexColor("#F05A28"),
}
TOKEN_COLORS = {
    "input": HexColor("#2C6ECB"),
    "visible": HexColor("#0F8A83"),
    "reasoning": HexColor("#D97757"),
    "unseparated": HexColor("#7C5AC7"),
}

TEXT = {
    "it": {
        "pdf_title": "Grafici selezionati - token e costi",
        "pdf_subject": "Benchmark 17 x 60: token, reasoning e costi",
        "p1_title": "Classifica del costo medio",
        "p1_sub": "Costo API medio per risposta su 60 esercizi comuni | dall'alto: meno costoso -> piu costoso",
        "how": "COME LEGGERE",
        "p1_how": "Punto = costo medio; linea con estremi = intervallo di confidenza 95%",
        "rank": "POS.",
        "model": "MODELLO",
        "mean": "MEDIA",
        "total": "TOTALE 60",
        "p1_axis": "COSTO MEDIO PER RISPOSTA (USD) - PIU A SINISTRA = MENO COSTOSO",
        "p1_note": "Asse da zero. Gemma 4 31B IT usa la tariffa zero configurata per questa campagna; non e un prezzo universale.",
        "p2_title": "Composizione complessiva dei token",
        "p2_sub": "Token accumulati sui 60 esercizi comuni | ordinati dal volume minore al maggiore",
        "input": "Input",
        "visible": "Output visibile",
        "reasoning": "Reasoning",
        "unseparated": "Output + reasoning non separabili",
        "p2_axis": "TOKEN TOTALI NEL PANEL",
        "p2_note": "Claude Fable 5 non espone separatamente il thinking: la componente viola resta intenzionalmente non ripartita.",
        "p3_title": "Variabilita tra gli esercizi",
        "p3_sub": "Distribuzione per cella sui 60 esercizi | linea = min-max; box = Q1-Q3; tratto = mediana",
        "p3_left": "Output fatturabile per risposta",
        "p3_right": "Costo per risposta",
        "p3_note": "La dispersione mostra quanto esercizi diversi cambiano consumo e costo; le repliche sono macro-mediate per cella.",
        "p4_title": "Heatmap del costo per risposta",
        "p4_sub": "17 modelli x 60 esercizi comuni | colore su scala logaritmica per rendere visibili anche i costi bassi",
        "low": "Costo minore",
        "high": "Costo maggiore",
        "zero": "tariffa configurata = 0",
        "p4_note": "Verde = meno costoso | rosso = piu costoso. Le colonne A3 e F2 identificano materia, anno, appello ed esercizio.",
        "p5_title": "Perche il costo cambia: volume e tariffa effettiva",
        "p5_sub": "Ogni punto e un modello | dimensione del punto = costo medio per risposta",
        "p5_x": "TOKEN MEDI PER RISPOSTA",
        "p5_y": "USD EFFETTIVI PER 1M TOKEN ANALITICI",
        "p5_note": "In alto: tariffa effettiva maggiore. A destra: piu token consumati. Il costo finale combina entrambe le dimensioni.",
        "p6_title": "DeepSeek V4 Flash: effetto del thinking",
        "p6_sub": "Confronto appaiato thinking - no thinking sugli stessi 60 esercizi",
        "p6_card1": "TOKEN TOTALI",
        "p6_card2": "COSTO TOTALE",
        "p6_card3": "OUTPUT VISIBILE",
        "p6_left": "Delta token per esercizio",
        "p6_right": "Delta costo per esercizio (USD)",
        "p6_note": "Barra positiva = la versione thinking consuma o costa di piu. Tutti i confronti usano lo stesso esercizio.",
        "footer": "Panel comune: 60 esercizi, 17 modelli, 1.020 celle macro-mediate",
    },
    "en": {
        "pdf_title": "Selected token and cost charts",
        "pdf_subject": "17 x 60 benchmark: tokens, reasoning, and API cost",
        "p1_title": "Mean cost ranking",
        "p1_sub": "Mean API cost per response across 60 common exercises | top to bottom: cheaper -> more expensive",
        "how": "HOW TO READ",
        "p1_how": "Dot = mean cost; horizontal line with end caps = 95% confidence interval",
        "rank": "RANK",
        "model": "MODEL",
        "mean": "MEAN",
        "total": "TOTAL 60",
        "p1_axis": "MEAN COST PER RESPONSE (USD) - FARTHER LEFT = CHEAPER",
        "p1_note": "Axis starts at zero. Gemma 4 31B IT uses the campaign-configured zero rate; this is not a universal model price.",
        "p2_title": "Overall token composition",
        "p2_sub": "Tokens accumulated across 60 common exercises | ordered from lower to higher volume",
        "input": "Input",
        "visible": "Visible output",
        "reasoning": "Reasoning",
        "unseparated": "Unseparated output + reasoning",
        "p2_axis": "TOTAL TOKENS IN THE PANEL",
        "p2_note": "Claude Fable 5 does not report hidden thinking separately: the purple component is intentionally left unsplit.",
        "p3_title": "Variation across exercises",
        "p3_sub": "Per-cell distribution over 60 exercises | line = min-max; box = Q1-Q3; mark = median",
        "p3_left": "Billable output per response",
        "p3_right": "Cost per response",
        "p3_note": "The spread shows how exercises change usage and cost; repetitions are macro-averaged within each cell.",
        "p4_title": "Cost-per-response heatmap",
        "p4_sub": "17 models x 60 common exercises | logarithmic color scale keeps low costs visible",
        "low": "Lower cost",
        "high": "Higher cost",
        "zero": "configured rate = 0",
        "p4_note": "Green = cheaper | red = more expensive. A3 and F2 labels identify subject, year, exam session, and exercise.",
        "p5_title": "Why cost changes: token volume and effective rate",
        "p5_sub": "Each point is a model | point size = mean cost per response",
        "p5_x": "MEAN TOKENS PER RESPONSE",
        "p5_y": "EFFECTIVE USD PER 1M ANALYTICAL TOKENS",
        "p5_note": "Higher means a larger effective rate. Farther right means more tokens. Final cost combines both dimensions.",
        "p6_title": "DeepSeek V4 Flash: effect of thinking",
        "p6_sub": "Paired comparison of thinking minus no thinking on the same 60 exercises",
        "p6_card1": "TOTAL TOKENS",
        "p6_card2": "TOTAL COST",
        "p6_card3": "VISIBLE OUTPUT",
        "p6_left": "Token delta per exercise",
        "p6_right": "Cost delta per exercise (USD)",
        "p6_note": "A positive bar means the thinking version uses more tokens or costs more. Every comparison uses the same exercise.",
        "footer": "Common panel: 60 exercises, 17 models, 1,020 macro-averaged cells",
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentile(values: Iterable[float], p: float) -> float:
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * p
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def stats(values: Iterable[float]) -> tuple[float, float, float, float, float]:
    values = list(values)
    return min(values), percentile(values, 0.25), percentile(values, 0.5), percentile(values, 0.75), max(values)


def blend(color1: Any, color2: Any, amount: float) -> Any:
    amount = max(0.0, min(1.0, amount))
    return HexColor(
        "#{:02X}{:02X}{:02X}".format(
            round((color1.red * (1 - amount) + color2.red * amount) * 255),
            round((color1.green * (1 - amount) + color2.green * amount) * 255),
            round((color1.blue * (1 - amount) + color2.blue * amount) * 255),
        )
    )


def heat_color(value: float, minimum_positive: float, maximum: float) -> Any:
    if value <= 0:
        return HexColor("#E7ECEF")
    low = math.log10(minimum_positive)
    high = math.log10(maximum)
    t = 1.0 if high == low else (math.log10(value) - low) / (high - low)
    if t <= 0.5:
        return blend(GREEN, CREAM, t / 0.5)
    return blend(CREAM, RED, (t - 0.5) / 0.5)


def y_from_top(top: float) -> float:
    return PAGE_H - top


def add_text(
    drawing: Drawing,
    x: float,
    top: float,
    text: Any,
    size: float = 9,
    color: Any = INK,
    anchor: str = "start",
    font: str = "Helvetica",
    angle: float = 0,
) -> None:
    if not angle:
        drawing.add(
            String(
                x,
                y_from_top(top),
                str(text),
                fontName=font,
                fontSize=size,
                fillColor=color,
                textAnchor=anchor,
            )
        )
        return
    radians = math.radians(angle)
    group = Group(
        String(
            0,
            0,
            str(text),
            fontName=font,
            fontSize=size,
            fillColor=color,
            textAnchor=anchor,
        )
    )
    group.transform = (
        math.cos(radians),
        math.sin(radians),
        -math.sin(radians),
        math.cos(radians),
        x,
        y_from_top(top),
    )
    drawing.add(group)


def add_line(drawing: Drawing, x1: float, top1: float, x2: float, top2: float, color: Any = GRID, width: float = 1) -> None:
    drawing.add(Line(x1, y_from_top(top1), x2, y_from_top(top2), strokeColor=color, strokeWidth=width))


def add_rect(
    drawing: Drawing,
    x: float,
    top: float,
    width: float,
    height: float,
    fill: Any,
    stroke: Any | None = None,
    stroke_width: float = 0,
) -> None:
    drawing.add(
        Rect(
            x,
            y_from_top(top + height),
            width,
            height,
            fillColor=fill,
            strokeColor=stroke,
            strokeWidth=stroke_width,
        )
    )


def add_circle(drawing: Drawing, x: float, top: float, radius: float, fill: Any, stroke: Any = INK, width: float = 0.8) -> None:
    drawing.add(Circle(x, y_from_top(top), radius, fillColor=fill, strokeColor=stroke, strokeWidth=width))


def add_page_header(drawing: Drawing, title: str, subtitle: str) -> None:
    add_text(drawing, 44, 48, title, 24, NAVY)
    add_text(drawing, 44, 76, subtitle, 11, MUTED)


def add_provider_label(drawing: Drawing, rank: int, model: str, provider: str, row_top: float, row_height: float, show_rank: bool = True) -> None:
    if show_rank:
        add_text(drawing, 44, row_top + row_height * 0.60, f"{rank:02d}", 9, MUTED)
    add_rect(drawing, 68, row_top + 4, 3, row_height - 8, PROVIDER_COLORS[provider])
    add_text(drawing, 79, row_top + row_height * 0.53, model, 10.3, INK)
    add_text(drawing, 79, row_top + row_height * 0.82, provider.upper(), 5.8, MUTED)


def add_alternating_rows(drawing: Drawing, row_top: float, row_height: float, count: int, x: float = 40, width: float = 770) -> None:
    for index in range(count):
        if index % 2:
            add_rect(drawing, x, row_top + index * row_height, width, row_height, ROW_ALT)


def add_footer(drawing: Drawing, note: str, page_number: int, total_pages: int, footer: str) -> None:
    add_text(drawing, 44, 566, note, 7.2, MUTED)
    add_text(drawing, 44, 581, footer, 6.6, MUTED)
    add_text(drawing, 800, 581, f"{page_number}/{total_pages}", 6.6, MUTED, anchor="end")


def page_cost_ranking(summary: list[dict[str, str]], lang: str, total_pages: int = 6) -> Drawing:
    t = TEXT[lang]
    rows = sorted(summary, key=lambda row: float(row["cost_mean_usd"]))
    drawing = Drawing(PAGE_W, PAGE_H)
    add_page_header(drawing, t["p1_title"], t["p1_sub"])
    add_text(drawing, 44, 100, t["how"], 7.5, NAVY)
    add_line(drawing, 135, 96, 220, 96, HexColor("#40586B"), 2.2)
    add_line(drawing, 135, 90, 135, 102, HexColor("#40586B"), 2)
    add_line(drawing, 220, 90, 220, 102, HexColor("#40586B"), 2)
    add_circle(drawing, 178, 96, 6.2, GREEN)
    add_text(drawing, 234, 100, t["p1_how"], 8.5, INK)

    add_text(drawing, 44, 126, t["rank"], 8, MUTED)
    add_text(drawing, 79, 126, t["model"], 8, MUTED)
    add_text(drawing, 686, 126, t["mean"], 8, MUTED, anchor="end")
    add_text(drawing, 800, 126, t["total"], 8, MUTED, anchor="end")
    add_line(drawing, 44, 134, 804, 134, GRID, 1)

    row_top = 138
    row_height = min(23.7, 331.8 / max(len(rows), 1))
    add_alternating_rows(drawing, row_top, row_height, len(rows))
    plot_x0, plot_x1 = 285, 635
    maximum = max(float(row["cost_mean_ci95_high_usd"]) for row in rows)
    axis_max = math.ceil(maximum * 20) / 20
    for tick in range(6):
        value = axis_max * tick / 5
        x = plot_x0 + (plot_x1 - plot_x0) * tick / 5
        add_line(drawing, x, row_top, x, row_top + row_height * len(rows), GRID, 0.7)
        add_text(drawing, x, 493, f"${value:.2f}", 7.3, NAVY, anchor="middle")
    for index, row in enumerate(rows, start=1):
        top = row_top + (index - 1) * row_height
        provider = row["provider"]
        add_provider_label(drawing, index, row["model"], provider, top, row_height)
        mean = float(row["cost_mean_usd"])
        low = float(row["cost_mean_ci95_low_usd"])
        high = float(row["cost_mean_ci95_high_usd"])
        scale = lambda value: plot_x0 + (plot_x1 - plot_x0) * value / axis_max
        y = top + row_height * 0.53
        add_line(drawing, scale(low), y, scale(high), y, HexColor("#40586B"), 2.1)
        add_line(drawing, scale(low), y - 5, scale(low), y + 5, HexColor("#40586B"), 1.8)
        add_line(drawing, scale(high), y - 5, scale(high), y + 5, HexColor("#40586B"), 1.8)
        add_circle(drawing, scale(mean), y, 5.4, PROVIDER_COLORS[provider])
        add_text(drawing, 686, y + 3, f"${mean:.4f}", 8.8, INK, anchor="end")
        add_text(drawing, 800, y + 3, f"${float(row['cost_total_usd']):.4f}", 8.8, MUTED, anchor="end")
    add_line(drawing, plot_x0, 486, plot_x1, 486, NAVY, 1.3)
    add_text(drawing, (plot_x0 + plot_x1) / 2, 520, t["p1_axis"], 8.2, NAVY, anchor="middle")
    add_footer(drawing, t["p1_note"], 1, total_pages, t["footer"])
    return drawing


def page_token_composition(summary: list[dict[str, str]], lang: str, total_pages: int = 6) -> Drawing:
    t = TEXT[lang]
    rows = sorted(summary, key=lambda row: float(row["analytical_total_tokens_total"]))
    drawing = Drawing(PAGE_W, PAGE_H)
    add_page_header(drawing, t["p2_title"], t["p2_sub"])
    legend = [
        (t["input"], "input"),
        (t["visible"], "visible"),
        (t["reasoning"], "reasoning"),
        (t["unseparated"], "unseparated"),
    ]
    x = 44
    for label, key in legend:
        add_rect(drawing, x, 92, 11, 11, TOKEN_COLORS[key])
        add_text(drawing, x + 16, 101, label, 7.7, MUTED)
        x += 65 + len(label) * 4.2

    row_top = 116
    row_height = min(25.2, 352.8 / max(len(rows), 1))
    add_alternating_rows(drawing, row_top, row_height, len(rows))
    plot_x0, plot_x1 = 260, 733
    maximum = max(float(row["analytical_total_tokens_total"]) for row in rows)
    axis_max = math.ceil(maximum / 100000) * 100000
    for tick in range(7):
        value = axis_max * tick / 6
        x = plot_x0 + (plot_x1 - plot_x0) * tick / 6
        add_line(drawing, x, row_top, x, row_top + row_height * len(rows), GRID, 0.7)
        add_text(drawing, x, 490, f"{value/1000:.0f}k", 7.3, NAVY, anchor="middle")
    for index, row in enumerate(rows, start=1):
        top = row_top + (index - 1) * row_height
        provider = row["provider"]
        add_provider_label(drawing, index, row["model"], provider, top, row_height)
        values = [
            (float(row["input_tokens_total"]), "input"),
            (number(row["visible_output_tokens_total"]) or 0, "visible"),
            (number(row["reasoning_tokens_total"]) or 0, "reasoning"),
            (number(row["combined_output_unseparated_tokens_total"]) or 0, "unseparated"),
        ]
        x = plot_x0
        bar_top = top + 5
        for value, key in values:
            width = (plot_x1 - plot_x0) * value / axis_max
            if width > 0:
                add_rect(drawing, x, bar_top, width, row_height - 10, TOKEN_COLORS[key])
            x += width
        add_text(drawing, 800, top + row_height * 0.60, f"{float(row['analytical_total_tokens_total'])/1000:.1f}k", 8.5, INK, anchor="end")
    add_line(drawing, plot_x0, 483, plot_x1, 483, NAVY, 1.3)
    add_text(drawing, (plot_x0 + plot_x1) / 2, 518, t["p2_axis"], 8.2, NAVY, anchor="middle")
    add_footer(drawing, t["p2_note"], 2, total_pages, t["footer"])
    return drawing


def page_distributions(summary: list[dict[str, str]], raw: list[dict[str, str]], lang: str) -> Drawing:
    t = TEXT[lang]
    rows = sorted(summary, key=lambda row: float(row["cost_mean_usd"]))
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in raw:
        grouped[row["model"]].append(row)
    drawing = Drawing(PAGE_W, PAGE_H)
    add_page_header(drawing, t["p3_title"], t["p3_sub"])

    row_top = 116
    row_height = min(25.2, 352.8 / max(len(rows), 1))
    add_alternating_rows(drawing, row_top, row_height, len(rows))
    left_x0, left_x1 = 250, 490
    right_x0, right_x1 = 555, 800
    max_output = max(float(row["billed_output_tokens"]) for row in raw)
    output_axis_max = math.ceil(max_output / 10000) * 10000
    max_cost = max(float(row["cost_selected_usd"]) for row in raw)
    cost_axis_max = math.ceil(max_cost * 10) / 10
    add_text(drawing, (left_x0 + left_x1) / 2, 100, t["p3_left"], 9, NAVY, anchor="middle")
    add_text(drawing, (right_x0 + right_x1) / 2, 100, t["p3_right"], 9, NAVY, anchor="middle")
    for tick in range(5):
        x = left_x0 + (left_x1 - left_x0) * tick / 4
        add_line(drawing, x, row_top, x, row_top + row_height * len(rows), GRID, 0.7)
        add_text(drawing, x, 490, f"{output_axis_max*tick/4000:.0f}k", 7, NAVY, anchor="middle")
        x2 = right_x0 + (right_x1 - right_x0) * tick / 4
        add_line(drawing, x2, row_top, x2, row_top + row_height * len(rows), GRID, 0.7)
        add_text(drawing, x2, 490, f"${cost_axis_max*tick/4:.2f}", 7, NAVY, anchor="middle")
    for index, summary_row in enumerate(rows, start=1):
        top = row_top + (index - 1) * row_height
        model = summary_row["model"]
        provider = summary_row["provider"]
        add_provider_label(drawing, index, model, provider, top, row_height)
        datasets = [
            ([float(row["billed_output_tokens"]) for row in grouped[model]], left_x0, left_x1, output_axis_max),
            ([float(row["cost_selected_usd"]) for row in grouped[model]], right_x0, right_x1, cost_axis_max),
        ]
        for values, x0, x1, maximum in datasets:
            minimum, q1, median, q3, maximum_value = stats(values)
            scale = lambda value: x0 + (x1 - x0) * value / maximum
            y = top + row_height * 0.55
            color = PROVIDER_COLORS[provider]
            add_line(drawing, scale(minimum), y, scale(maximum_value), y, color, 1.6)
            add_line(drawing, scale(minimum), y - 4, scale(minimum), y + 4, color, 1.2)
            add_line(drawing, scale(maximum_value), y - 4, scale(maximum_value), y + 4, color, 1.2)
            add_rect(drawing, scale(q1), y - 6, max(1.2, scale(q3) - scale(q1)), 12, blend(color, WHITE, 0.62), color, 1)
            add_line(drawing, scale(median), y - 7, scale(median), y + 7, color, 2.1)
    add_line(drawing, left_x0, 483, left_x1, 483, NAVY, 1.2)
    add_line(drawing, right_x0, 483, right_x1, 483, NAVY, 1.2)
    add_footer(drawing, t["p3_note"], 3, 6, t["footer"])
    return drawing


def page_heatmap(summary: list[dict[str, str]], raw: list[dict[str, str]], lang: str) -> Drawing:
    t = TEXT[lang]
    rows = sorted(summary, key=lambda row: float(row["cost_mean_usd"]))
    items = list(dict.fromkeys(row["item_key"] for row in raw))
    item_labels = {row["item_key"]: row["item_label"] for row in raw}
    values = {(row["model"], row["item_key"]): float(row["cost_selected_usd"]) for row in raw}
    positives = [value for value in values.values() if value > 0]
    minimum_positive, maximum = min(positives), max(positives)
    drawing = Drawing(PAGE_W, PAGE_H)
    add_page_header(drawing, t["p4_title"], t["p4_sub"])

    left, right = 228, 810
    cell_h = min(11.6, 162.4 / max(len(rows), 1))
    panels = [
        ("analysis_3", 105, "ANALISI 3" if lang == "it" else "ANALYSIS 3"),
        ("physics_2", 320, "FISICA 2" if lang == "it" else "PHYSICS 2"),
    ]
    for subject, header_top, panel_label in panels:
        panel_items = [item for item in items if item.startswith(subject + "|")]
        cell_w = (right - left) / len(panel_items)
        grid_top = header_top + 34
        add_text(drawing, 44, header_top + 12, panel_label, 8.5, NAVY, font="Helvetica-Bold")
        for column, item in enumerate(panel_items):
            x = left + column * cell_w + cell_w * 0.58
            add_text(drawing, x, header_top + 27, item_labels[item], 5.5, MUTED, anchor="start", angle=60)
        for row_index, row in enumerate(rows, start=1):
            top = grid_top + (row_index - 1) * cell_h
            provider = row["provider"]
            if row_index % 2 == 0:
                add_rect(drawing, 40, top, 770, cell_h, ROW_ALT)
            add_text(drawing, 44, top + cell_h * 0.66, f"{row_index:02d}", 6.2, MUTED)
            add_rect(drawing, 67, top + 2, 3, cell_h - 4, PROVIDER_COLORS[provider])
            label_size = 6.0 if len(row["model"]) > 23 else 6.8
            add_text(drawing, 78, top + cell_h * 0.66, row["model"], label_size, INK)
            for column, item in enumerate(panel_items):
                value = values[(row["model"], item)]
                add_rect(drawing, left + column * cell_w, top + 0.5, cell_w - 0.4, cell_h - 1.0, heat_color(value, minimum_positive, maximum), WHITE, 0.3)
    legend_x, legend_top, legend_w = 228, 526, 360
    for step in range(120):
        ratio = step / 119
        if ratio <= 0.5:
            color = blend(GREEN, CREAM, ratio / 0.5)
        else:
            color = blend(CREAM, RED, (ratio - 0.5) / 0.5)
        add_rect(drawing, legend_x + legend_w * ratio, legend_top, legend_w / 119 + 0.4, 10, color)
    add_text(drawing, legend_x, 550, t["low"], 8.2, NAVY, font="Helvetica-Bold")
    add_text(drawing, legend_x + legend_w, 550, t["high"], 8.2, NAVY, anchor="end", font="Helvetica-Bold")
    add_rect(drawing, 640, legend_top, 13, 10, HexColor("#E7ECEF"))
    add_text(drawing, 660, 534, t["zero"], 8.0, MUTED)
    add_footer(drawing, t["p4_note"], 4, 6, t["footer"])
    return drawing


def page_cost_drivers(summary: list[dict[str, str]], lang: str) -> Drawing:
    t = TEXT[lang]
    rows = sorted(summary, key=lambda row: float(row["cost_mean_usd"]))
    drawing = Drawing(PAGE_W, PAGE_H)
    add_page_header(drawing, t["p5_title"], t["p5_sub"])
    x0, x1, top, bottom = 92, 600, 112, 500
    x_values = [float(row["analytical_total_tokens_mean"]) for row in rows]
    effective_rates = [
        float(row["cost_total_usd"]) / float(row["analytical_total_tokens_total"]) * 1_000_000
        if float(row["analytical_total_tokens_total"]) else 0
        for row in rows
    ]
    x_max = math.ceil(max(x_values) / 5000) * 5000
    y_max = math.ceil(max(effective_rates) / 10) * 10
    for tick in range(6):
        x = x0 + (x1 - x0) * tick / 5
        value = x_max * tick / 5
        add_line(drawing, x, top, x, bottom, GRID, 0.7)
        add_text(drawing, x, 519, f"{value/1000:.0f}k", 7.4, NAVY, anchor="middle")
        y_top = bottom - (bottom - top) * tick / 5
        y_value = y_max * tick / 5
        add_line(drawing, x0, y_top, x1, y_top, GRID, 0.7)
        add_text(drawing, x0 - 10, y_top + 3, f"${y_value:.0f}", 7.4, NAVY, anchor="end")
    add_line(drawing, x0, bottom, x1, bottom, NAVY, 1.2)
    add_line(drawing, x0, top, x0, bottom, NAVY, 1.2)
    add_text(drawing, (x0 + x1) / 2, 545, t["p5_x"], 8.2, NAVY, anchor="middle")
    add_text(drawing, 44, (top + bottom) / 2, t["p5_y"], 8.2, NAVY, anchor="middle", angle=90)

    max_cost = max(float(row["cost_mean_usd"]) for row in rows)
    for index, (row, effective_rate) in enumerate(zip(rows, effective_rates), start=1):
        x = x0 + (x1 - x0) * float(row["analytical_total_tokens_mean"]) / x_max
        y = bottom - (bottom - top) * effective_rate / y_max
        radius = 4 + 7 * math.sqrt(float(row["cost_mean_usd"]) / max_cost if max_cost else 0)
        color = PROVIDER_COLORS[row["provider"]]
        add_circle(drawing, x, y, radius, color, WHITE, 1)
        add_text(drawing, x, y + 2.5, f"{index}", 5.5, WHITE, anchor="middle", font="Helvetica-Bold")

    list_x, list_top = 628, 116
    list_height = min(27, 378 / max(len(rows), 1))
    add_text(drawing, list_x, 101, t["rank"], 7.2, MUTED)
    add_text(drawing, list_x + 30, 101, t["model"], 7.2, MUTED)
    for index, row in enumerate(rows, start=1):
        top_row = list_top + (index - 1) * list_height
        if index % 2 == 0:
            add_rect(drawing, list_x - 6, top_row - 12, 178, list_height, ROW_ALT)
        add_text(drawing, list_x, top_row, f"{index:02d}", 7.4, MUTED)
        add_rect(drawing, list_x + 28, top_row - 10, 3, 15, PROVIDER_COLORS[row["provider"]])
        add_text(drawing, list_x + 37, top_row, row["model"], 7.6, INK)
    add_footer(drawing, t["p5_note"], 5, 6, t["footer"])
    return drawing


def page_deepseek(deepseek: list[dict[str, str]], lang: str) -> Drawing:
    t = TEXT[lang]
    rows = sorted(deepseek, key=lambda row: float(row["delta_total_tokens"]))
    drawing = Drawing(PAGE_W, PAGE_H)
    add_page_header(drawing, t["p6_title"], t["p6_sub"])

    total_thinking = sum(float(row["total_tokens_thinking"]) for row in rows)
    total_no = sum(float(row["total_tokens_no_thinking"]) for row in rows)
    cost_thinking = sum(float(row["cost_usd_thinking"]) for row in rows)
    cost_no = sum(float(row["cost_usd_no_thinking"]) for row in rows)
    visible_thinking = sum(float(row["visible_output_tokens_thinking"]) for row in rows)
    visible_no = sum(float(row["visible_output_tokens_no_thinking"]) for row in rows)
    cards = [
        (t["p6_card1"], total_thinking / total_no - 1, TOKEN_COLORS["reasoning"]),
        (t["p6_card2"], cost_thinking / cost_no - 1, RED),
        (t["p6_card3"], visible_thinking / visible_no - 1, GREEN),
    ]
    for index, (label, value, color) in enumerate(cards):
        x = 44 + index * 235
        add_rect(drawing, x, 90, 210, 50, ROW_ALT, GRID, 0.8)
        add_text(drawing, x + 12, 108, label, 7.5, MUTED)
        add_text(drawing, x + 198, 126, f"{value:+.1%}", 18, color, anchor="end", font="Helvetica-Bold")

    x0, x1, top, bottom = 100, 610, 175, 500
    x_values = [float(row["delta_total_tokens"]) for row in rows]
    y_values = [float(row["delta_cost_usd"]) for row in rows]
    x_min, x_max = min(0.0, min(x_values)), max(x_values)
    y_min, y_max = min(0.0, min(y_values)), max(y_values)
    x_pad = max((x_max - x_min) * 0.08, 1.0)
    y_pad = max((y_max - y_min) * 0.10, 0.0001)
    x_min, x_max = x_min - x_pad, x_max + x_pad
    y_min, y_max = y_min - y_pad, y_max + y_pad
    sx = lambda value: x0 + (x1 - x0) * (value - x_min) / (x_max - x_min)
    sy = lambda value: bottom - (bottom - top) * (value - y_min) / (y_max - y_min)
    for tick in range(6):
        x_value = x_min + (x_max - x_min) * tick / 5
        x = sx(x_value)
        add_line(drawing, x, top, x, bottom, GRID, 0.65)
        add_text(drawing, x, 520, f"{x_value/1000:.1f}k", 7.4, NAVY, anchor="middle")
        y_value = y_min + (y_max - y_min) * tick / 5
        y = sy(y_value)
        add_line(drawing, x0, y, x1, y, GRID, 0.65)
        add_text(drawing, x0 - 10, y + 3, f"${y_value:.3f}", 7.2, NAVY, anchor="end")
    if x_min <= 0 <= x_max:
        add_line(drawing, sx(0), top, sx(0), bottom, NAVY, 1.1)
    if y_min <= 0 <= y_max:
        add_line(drawing, x0, sy(0), x1, sy(0), NAVY, 1.1)
    add_line(drawing, x0, bottom, x1, bottom, NAVY, 1.2)
    add_line(drawing, x0, top, x0, bottom, NAVY, 1.2)
    subject_colors = {"analysis_3": TOKEN_COLORS["input"], "physics_2": TOKEN_COLORS["unseparated"]}
    for row in rows:
        add_circle(drawing, sx(float(row["delta_total_tokens"])), sy(float(row["delta_cost_usd"])), 4.1, subject_colors[row["subject"]], WHITE, 0.8)
    add_text(drawing, (x0 + x1) / 2, 548, t["p6_left"], 8.7, NAVY, anchor="middle", font="Helvetica-Bold")
    add_text(drawing, 42, (top + bottom) / 2, t["p6_right"], 8.7, NAVY, anchor="middle", angle=90, font="Helvetica-Bold")

    legend_x = 646
    labels = (("analysis_3", "Analisi 3" if lang == "it" else "Analysis 3"), ("physics_2", "Fisica 2" if lang == "it" else "Physics 2"))
    add_text(drawing, legend_x, 182, "LEGENDA" if lang == "it" else "LEGEND", 8.3, NAVY, font="Helvetica-Bold")
    for index, (subject, label) in enumerate(labels):
        y = 204 + index * 24
        add_circle(drawing, legend_x + 5, y, 5, subject_colors[subject], WHITE, 0.8)
        add_text(drawing, legend_x + 18, y + 3, label, 8.2, INK, font="Helvetica-Bold")
        selected = [row for row in rows if row["subject"] == subject]
        add_text(drawing, legend_x, y + 19, f"n={len(selected)}", 6.8, MUTED)
    add_text(drawing, legend_x, 286, "MEDIANE" if lang == "it" else "MEDIANS", 8.3, NAVY, font="Helvetica-Bold")
    for index, (subject, label) in enumerate(labels):
        selected = [row for row in rows if row["subject"] == subject]
        token_median = statistics.median(float(row["delta_total_tokens"]) for row in selected)
        cost_median = statistics.median(float(row["delta_cost_usd"]) for row in selected)
        y = 309 + index * 54
        add_text(drawing, legend_x, y, label, 7.6, INK, font="Helvetica-Bold")
        add_text(drawing, legend_x, y + 16, f"token: {token_median:+,.0f}", 7.2, MUTED)
        add_text(drawing, legend_x, y + 31, f"costo: ${cost_median:+.4f}" if lang == "it" else f"cost: ${cost_median:+.4f}", 7.2, MUTED)
    add_footer(drawing, t["p6_note"], 6, 6, t["footer"])
    return drawing


def build_drawings(lang: str, summary: list[dict[str, str]], raw: list[dict[str, str]], deepseek: list[dict[str, str]]) -> list[Drawing]:
    return [
        page_cost_ranking(summary, lang),
        page_token_composition(summary, lang),
        page_distributions(summary, raw, lang),
        page_heatmap(summary, raw, lang),
        page_cost_drivers(summary, lang),
        page_deepseek(deepseek, lang),
    ]


def export_set(lang: str, drawings: list[Drawing]) -> dict[str, Any]:
    english = lang == "en"
    figure_dir = FIGURES_EN if english else FIGURES_IT
    rendered_dir = RENDERED_EN if english else RENDERED_IT
    pdf_name = "selected_token_cost_charts.pdf" if english else "grafici_token_costi_selezionati.pdf"
    prefix_names = [
        "01_cost_ranking" if english else "01_classifica_costi",
        "02_token_composition" if english else "02_composizione_token",
        "03_distributions" if english else "03_distribuzioni",
        "04_cost_heatmap" if english else "04_heatmap_costi",
        "05_cost_drivers" if english else "05_driver_costo",
        "06_thinking_comparison" if english else "06_confronto_thinking",
    ]
    figure_dir.mkdir(parents=True, exist_ok=True)
    rendered_dir.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    for drawing, name in zip(drawings, prefix_names):
        renderSVG.drawToFile(drawing, str(figure_dir / f"{name}.svg"))
    pdf_path = PDF_DIR / pdf_name
    pdf = canvas.Canvas(str(pdf_path), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    pdf.setTitle(TEXT[lang]["pdf_title"])
    pdf.setSubject(TEXT[lang]["pdf_subject"])
    pdf.setAuthor("Francesco Bortot")
    pdf.setCreator("UniAIBench figure generator")
    for drawing in drawings:
        renderPDF.draw(drawing, pdf, 0, 0)
        pdf.showPage()
    pdf.save()
    return {
        "pdf": pdf_path,
        "figures": [figure_dir / f"{name}.svg" for name in prefix_names],
        "rendered_dir": rendered_dir,
    }


def write_analysis(summary: list[dict[str, str]], deepseek: list[dict[str, str]]) -> Path:
    by_model = {row["model"]: row for row in summary}
    total_cost = sum(float(row["cost_total_usd"]) for row in summary)
    total_tokens = sum(float(row["analytical_total_tokens_total"]) for row in summary)
    provider_cost_rows = sum(int(float(row["provider_reported_cost_rows"])) for row in summary)
    reconstructed_cost_rows = sum(int(float(row["reconstructed_cost_rows"])) for row in summary)
    retry_rows = sum(int(float(row["retry_rows"])) for row in summary)
    top_two = float(by_model["GPT-5.6 Sol"]["cost_total_usd"]) + float(by_model["Claude Fable 5"]["cost_total_usd"])
    thinking_tokens = sum(float(row["total_tokens_thinking"]) for row in deepseek)
    no_tokens = sum(float(row["total_tokens_no_thinking"]) for row in deepseek)
    thinking_cost = sum(float(row["cost_usd_thinking"]) for row in deepseek)
    no_cost = sum(float(row["cost_usd_no_thinking"]) for row in deepseek)
    visible_thinking = sum(float(row["visible_output_tokens_thinking"]) for row in deepseek)
    visible_no = sum(float(row["visible_output_tokens_no_thinking"]) for row in deepseek)
    path = OUTPUT_DIR / "ANALISI.md"
    path.write_text(
        f"""# Analisi grafica - token e costi del panel 17 x 60

## Evidenze principali

- Il costo complessivo del panel e **{total_cost:.4f} USD** per **{total_tokens:,.0f} token analitici**.
- GPT-5.6 Sol (**{float(by_model['GPT-5.6 Sol']['cost_total_usd']):.4f} USD**) e Claude Fable 5 (**{float(by_model['Claude Fable 5']['cost_total_usd']):.4f} USD**) assorbono insieme il **{top_two / total_cost:.1%}** del costo totale.
- Il minor costo non nullo e DeepSeek V4 Flash senza thinking: **{float(by_model['DeepSeek V4 Flash (no thinking)']['cost_total_usd']):.4f} USD** sui 60 esercizi.
- Il maggior volume di token appartiene a DeepSeek V4 Flash con thinking: **{float(by_model['DeepSeek V4 Flash']['analytical_total_tokens_total']):,.0f} token**, in gran parte reasoning.
- Claude Sonnet 4.5 usa il minor volume complessivo (**{float(by_model['Claude Sonnet 4.5']['analytical_total_tokens_total']):,.0f} token**) ma non e il modello meno costoso: il prezzo per token resta determinante.
- Nel confronto appaiato DeepSeek, il thinking aumenta i token del **{thinking_tokens / no_tokens - 1:.1%}** e il costo del **{thinking_cost / no_cost - 1:.1%}**, mentre riduce l'output visibile del **{1 - visible_thinking / visible_no:.1%}**.

## Lettura delle sei figure

1. **Classifica costi:** confronta costo medio, incertezza fra esercizi e costo totale del panel.
2. **Composizione token:** separa input, output visibile, reasoning e componente non separabile di Claude Fable 5.
3. **Distribuzioni:** mostra quanto consumo e costo cambiano da un esercizio all'altro.
4. **Heatmap:** individua combinazioni modello-esercizio particolarmente costose.
5. **Driver del costo:** distingue l'effetto del numero di token dall'effetto della tariffa.
6. **Thinking/no-thinking:** misura direttamente l'impatto della modalita di ragionamento sullo stesso modello.

## Limiti da mantenere visibili

- {provider_cost_rows} costi di cella sono dichiarati dal provider; {reconstructed_cost_rows} sono ricostruiti dalle tariffe versionate.
- Claude Fable 5 non separa il thinking nascosto dall'output fatturabile.
- Le celle con retry sono {retry_rows}; token e costo descrivono la risposta finale riuscita e le repliche sono macro-mediate.
- La tariffa zero di Gemma 4 31B IT e specifica della configurazione della campagna.
""",
        encoding="utf-8",
    )
    return path


def main() -> int:
    summary = read_csv(SUMMARY_PATH)
    raw = read_csv(RAW_PATH)
    deepseek = read_csv(DEEPSEEK_PATH)
    if len(summary) != 17 or len(raw) != 1020 or len(deepseek) != 60:
        raise RuntimeError("Unexpected source dimensions for selected charts")
    outputs = {}
    for lang in ("it", "en"):
        drawings = build_drawings(lang, summary, raw, deepseek)
        outputs[lang] = export_set(lang, drawings)
    analysis_path = write_analysis(summary, deepseek)
    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "style_reference": str(REFERENCE_PDF.relative_to(ANALYSIS_DIR)),
        "style_reference_sha256": sha256_file(REFERENCE_PDF),
        "sources": {
            str(path.relative_to(ANALYSIS_DIR)): sha256_file(path)
            for path in (SUMMARY_PATH, RAW_PATH, DEEPSEEK_PATH, METHODOLOGY_PATH)
        },
        "counts": {"pages_per_pdf": 6, "models": 17, "common_items": 60, "model_item_cells": 1020},
        "outputs": {},
    }
    for output in outputs.values():
        paths = [output["pdf"], *output["figures"]]
        for path in paths:
            manifest["outputs"][str(path.relative_to(OUTPUT_DIR))] = sha256_file(path)
    manifest["outputs"][str(analysis_path.relative_to(OUTPUT_DIR))] = sha256_file(analysis_path)
    manifest_path = OUTPUT_DIR / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pdfs": [str(outputs[lang]["pdf"]) for lang in ("it", "en")], "manifest": str(manifest_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
