#!/usr/bin/env python3
"""Build focused response-time charts for the balanced 14 x 60 panel."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.graphics import renderPDF, renderSVG
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

import build_selected_token_cost_charts as base
import build_speed_correctness_alternatives as correlation_chart


ANALYSIS_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ANALYSIS_DIR / "grafici_tempo_risposta_focus"
FIGURES_IT = OUTPUT_DIR / "figures"
FIGURES_EN = OUTPUT_DIR / "figures_en"
PDF_DIR = OUTPUT_DIR / "output" / "pdf"
RENDERED_IT = OUTPUT_DIR / "output" / "rendered"
RENDERED_EN = OUTPUT_DIR / "output" / "rendered_en"
TABLE_DIR = OUTPUT_DIR / "tables"

RAW_PATH = ANALYSIS_DIR / "data" / "model_item_resources.csv"
QUALITY_PATH = ANALYSIS_DIR / "tables" / "main_ranking_overall.csv"
SOURCE_MANIFEST = ANALYSIS_DIR / "README.md"
REFERENCE_PDF = ANALYSIS_DIR / "grafici_token_costi_focus" / "output" / "pdf" / "focused_token_cost_charts.pdf"
TOKEN_FOCUS_MANIFEST = ANALYSIS_DIR / "grafici_token_costi_focus" / "MANIFEST.json"

LOW = HexColor("#0F8A83")
HIGH = HexColor("#B23A3A")
RETRY = HexColor("#D1495B")

TEXT = {
    "it": {
        "pdf_title": "Grafici focus - tempo di risposta",
        "pdf_subject": "Benchmark 14 x 60: tempo, token e correttezza",
        "p1_title": "Classifica del tempo tipico",
        "p1_sub": "Tempo end-to-end su 60 esercizi comuni | ordinamento per mediana crescente",
        "how": "COME LEGGERE",
        "p1_how": "Punto = mediana; linea con estremi = intervallo Q1-Q3",
        "rank": "POS.",
        "model": "MODELLO",
        "median": "MEDIANA",
        "mean": "MEDIA",
        "p90": "P90",
        "total": "TOTALE 60",
        "p1_axis": "TEMPO DI RISPOSTA (SECONDI) - PIU A SINISTRA = PIU VELOCE",
        "p1_note": "Il tempo esclude la coda locale prima del dispatch; include chiamata API, generazione e gli eventuali retry.",
        "p2_title": "Dove cambiano i tempi",
        "p2_sub": "Heatmap modello x esercizio | intestazioni raggruppate per materia, appello ed esercizio",
        "faster": "Piu veloce",
        "same": "Mediana esercizio",
        "slower": "Piu lento",
        "retry": "retry",
        "p2_note": "0,5 = meta del tempo tipico dell'esercizio; 2,0 = il doppio. Il colore controlla la diversa difficolta degli esercizi.",
        "p3_title": "Come si forma il tempo medio",
        "p3_sub": "Volume di token e intensita temporale effettiva spiegano insieme il tempo osservato",
        "formula": "TEMPO MEDIO = TOKEN MEDI x SECONDI EFFETTIVI PER 1K / 1.000",
        "p3_x": "TOKEN ANALITICI MEDI PER RISPOSTA",
        "p3_y": "SECONDI EFFETTIVI PER 1K TOKEN ANALITICI",
        "few_low": "POCHI TOKEN\nBASSA INTENSITA",
        "few_high": "POCHI TOKEN\nALTA INTENSITA",
        "many_low": "MOLTI TOKEN\nBASSA INTENSITA",
        "many_high": "MOLTI TOKEN\nALTA INTENSITA",
        "bubble": "DIMENSIONE BOLLA = TEMPO MEDIO",
        "p3_note": "I secondi per 1K sono un rapporto operativo: includono latenza, generazione e retry, non una velocita pura del provider.",
        "p4_title": "Velocita e correttezza",
        "p4_sub": "Accuratezza media e risposte tipiche per ora sugli stessi 60 esercizi | piu in alto e a destra e meglio",
        "p4_x": "ACCURATEZZA MEDIA (%)",
        "p4_y": "RISPOSTE TIPICHE PER ORA",
        "accuracy": "ACC.",
        "speed": "RISP./H",
        "time": "SEC.",
        "desired": "PIU CORRETTO E PIU VELOCE",
        "p4_note": "Risposte/ora = 3.600 diviso il tempo mediano. E una velocita tipica teorica per richieste eseguite in sequenza.",
        "footer": "Panel comune: 60 esercizi (33 Analisi 3, 27 Fisica 2), 14 modelli, 840 celle macro-mediate",
    },
    "en": {
        "pdf_title": "Focused response-time charts",
        "pdf_subject": "14 x 60 benchmark: response time, tokens, and correctness",
        "p1_title": "Typical response-time ranking",
        "p1_sub": "End-to-end time across 60 common exercises | ordered by increasing median",
        "how": "HOW TO READ",
        "p1_how": "Dot = median; horizontal line with end caps = Q1-Q3 interval",
        "rank": "RANK",
        "model": "MODEL",
        "median": "MEDIAN",
        "mean": "MEAN",
        "p90": "P90",
        "total": "TOTAL 60",
        "p1_axis": "RESPONSE TIME (SECONDS) - FARTHER LEFT = FASTER",
        "p1_note": "Time excludes the local queue before dispatch; it includes the API call, generation, and any retries.",
        "p2_title": "Where response times differ",
        "p2_sub": "Model-by-exercise heatmap | headers grouped by subject, exam session, and exercise",
        "faster": "Faster",
        "same": "Exercise median",
        "slower": "Slower",
        "retry": "retry",
        "p2_note": "0.5 means half the exercise's typical time; 2.0 means twice as long. Normalization controls exercise difficulty.",
        "p3_title": "How mean response time is formed",
        "p3_sub": "Token volume and effective time intensity jointly explain observed response time",
        "formula": "MEAN TIME = MEAN TOKENS x EFFECTIVE SECONDS PER 1K / 1,000",
        "p3_x": "MEAN ANALYTICAL TOKENS PER RESPONSE",
        "p3_y": "EFFECTIVE SECONDS PER 1K ANALYTICAL TOKENS",
        "few_low": "FEWER TOKENS\nLOW INTENSITY",
        "few_high": "FEWER TOKENS\nHIGH INTENSITY",
        "many_low": "MORE TOKENS\nLOW INTENSITY",
        "many_high": "MORE TOKENS\nHIGH INTENSITY",
        "bubble": "BUBBLE SIZE = MEAN RESPONSE TIME",
        "p3_note": "Seconds per 1K is an operational ratio: it includes latency, generation, and retries, not pure provider throughput.",
        "p4_title": "Speed and correctness",
        "p4_sub": "Mean accuracy and typical responses per hour on the same 60 exercises | higher and right is better",
        "p4_x": "MEAN ACCURACY (%)",
        "p4_y": "TYPICAL RESPONSES PER HOUR",
        "accuracy": "ACC.",
        "speed": "RESP./H",
        "time": "SEC.",
        "desired": "MORE CORRECT AND FASTER",
        "p4_note": "Responses/hour = 3,600 divided by median time. It is a theoretical typical rate for sequential requests.",
        "footer": "Common panel: 60 exercises (33 Analysis 3, 27 Physics 2), 14 models, 840 macro-averaged cells",
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def short_number(value: float) -> str:
    if value >= 3600:
        return f"{value / 3600:.1f}h"
    return f"{value / 60:.1f}m"


def item_order(item_key: str) -> tuple[int, int, int, int]:
    subject, year, session, exercise = item_key.split("|")
    session_order = {
        "primoapp_tema_a": 1,
        "primoapp_tema_b": 2,
        "secondoapp_tema_a": 3,
        "secondoapp_tema_b": 4,
        "primoapp": 1,
        "secondoapp": 2,
        "terzoapp": 5,
        "quartoapp": 6,
        "quintoapp": 7,
    }
    return (0 if subject == "analysis_3" else 1, int(year), session_order[session], int(exercise[1:]))


def validate(raw: list[dict[str, str]], quality: list[dict[str, str]]) -> list[dict[str, str]]:
    models = {row["model"] for row in raw}
    items = {row["item_key"] for row in raw}
    cells = Counter((row["model"], row["item_key"]) for row in raw)
    if len(raw) != 840 or len(models) != 14 or len(items) != 60:
        raise RuntimeError("Balanced panel is not 14 x 60")
    if any(value != 1 for value in cells.values()):
        raise RuntimeError("Model-item cells are not one-to-one")
    if any(not row["elapsed_seconds"] for row in raw):
        raise RuntimeError("Missing elapsed_seconds")
    selected = [row for row in quality if row["ranking_type"] == "matched_common_items" and row["scope"] == "overall"]
    if len(selected) != 14 or {row["model"] for row in selected} != models:
        raise RuntimeError("Quality rows do not match the 14-model panel")
    return selected


def summarize(raw: list[dict[str, str]], quality: list[dict[str, str]]) -> list[dict[str, Any]]:
    quality_by_model = {row["model"]: row for row in quality}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in raw:
        grouped[row["model"]].append(row)
    result: list[dict[str, Any]] = []
    for model, rows in grouped.items():
        times = [float(row["elapsed_seconds"]) for row in rows]
        tokens = [float(row["analytical_total_tokens"]) for row in rows]
        q = quality_by_model[model]
        total_time = sum(times)
        total_tokens = sum(tokens)
        result.append(
            {
                "model": model,
                "provider": rows[0]["provider"],
                "n": len(rows),
                "median_seconds": base.percentile(times, 0.5),
                "mean_seconds": statistics.mean(times),
                "q1_seconds": base.percentile(times, 0.25),
                "q3_seconds": base.percentile(times, 0.75),
                "p90_seconds": base.percentile(times, 0.90),
                "min_seconds": min(times),
                "max_seconds": max(times),
                "total_seconds": total_time,
                "retry_rows": sum(float(row["retry_count"] or 0) > 0 for row in rows),
                "analytical_tokens_mean": statistics.mean(tokens),
                "analytical_tokens_total": total_tokens,
                "effective_seconds_per_1k_tokens": total_time / total_tokens * 1000,
                "typical_responses_per_hour": 3600 / base.percentile(times, 0.5),
                "accuracy_mean": float(q["accuracy_mean"]),
                "accuracy_ci95_low": float(q["accuracy_ci95_low"]),
                "accuracy_ci95_high": float(q["accuracy_ci95_high"]),
            }
        )
    result.sort(key=lambda row: (row["median_seconds"], row["model"]))
    for rank, row in enumerate(result, 1):
        row["time_rank"] = rank
    return result


def add_multiline(drawing: Drawing, x: float, top: float, value: str, color: Any, anchor: str) -> None:
    for index, line in enumerate(value.split("\n")):
        base.add_text(drawing, x, top + index * 9, line, 6.1, color, anchor=anchor, font="Helvetica-Bold")


def page_time_ranking(summary: list[dict[str, Any]], lang: str) -> Drawing:
    t = TEXT[lang]
    rows = summary
    drawing = Drawing(base.PAGE_W, base.PAGE_H)
    base.add_page_header(drawing, t["p1_title"], t["p1_sub"])
    base.add_text(drawing, 44, 100, t["how"], 7.5, base.NAVY)
    base.add_line(drawing, 135, 96, 220, 96, HexColor("#40586B"), 2.2)
    base.add_line(drawing, 135, 90, 135, 102, HexColor("#40586B"), 2)
    base.add_line(drawing, 220, 90, 220, 102, HexColor("#40586B"), 2)
    base.add_circle(drawing, 178, 96, 6.2, base.GREEN)
    base.add_text(drawing, 234, 100, t["p1_how"], 8.5, base.INK)

    headers = [(44, t["rank"], "start"), (79, t["model"], "start"), (590, t["median"], "end"),
               (655, t["mean"], "end"), (720, t["p90"], "end"), (800, t["total"], "end")]
    for x, label, anchor in headers:
        base.add_text(drawing, x, 126, label, 7.5, base.MUTED, anchor=anchor)
    base.add_line(drawing, 44, 134, 804, 134, base.GRID, 1)

    row_top, row_height = 138, 23.7
    base.add_alternating_rows(drawing, row_top, row_height, len(rows))
    plot_x0, plot_x1 = 285, 540
    axis_max = math.ceil(max(row["q3_seconds"] for row in rows) / 100) * 100
    for tick in range(6):
        value = axis_max * tick / 5
        x = plot_x0 + (plot_x1 - plot_x0) * tick / 5
        base.add_line(drawing, x, row_top, x, row_top + row_height * len(rows), base.GRID, 0.7)
        base.add_text(drawing, x, 493, f"{value:.0f}", 7.2, base.NAVY, anchor="middle")
    for index, row in enumerate(rows, 1):
        top = row_top + (index - 1) * row_height
        base.add_provider_label(drawing, index, row["model"], row["provider"], top, row_height)
        scale = lambda value: plot_x0 + (plot_x1 - plot_x0) * value / axis_max
        y = top + row_height * 0.53
        low, median, high = scale(row["q1_seconds"]), scale(row["median_seconds"]), scale(row["q3_seconds"])
        base.add_line(drawing, low, y, high, y, HexColor("#40586B"), 2.0)
        base.add_line(drawing, low, y - 6, low, y + 6, HexColor("#40586B"), 1.8)
        base.add_line(drawing, high, y - 6, high, y + 6, HexColor("#40586B"), 1.8)
        base.add_circle(drawing, median, y, 5.5, base.PROVIDER_COLORS[row["provider"]])
        base.add_text(drawing, 590, y + 3, f"{row['median_seconds']:.1f}", 8.1, base.INK, anchor="end")
        base.add_text(drawing, 655, y + 3, f"{row['mean_seconds']:.1f}", 8.1, base.INK, anchor="end")
        base.add_text(drawing, 720, y + 3, f"{row['p90_seconds']:.1f}", 8.1, base.INK, anchor="end")
        base.add_text(drawing, 800, y + 3, short_number(row["total_seconds"]), 8.1, base.MUTED, anchor="end")
    base.add_line(drawing, plot_x0, 486, plot_x1, 486, base.NAVY, 1.3)
    base.add_text(drawing, (plot_x0 + plot_x1) / 2, 522, t["p1_axis"], 8.0, base.NAVY, anchor="middle")
    base.add_footer(drawing, t["p1_note"], 1, 4, t["footer"])
    return drawing


def ratio_color(ratio: float) -> Any:
    value = max(-2.0, min(2.0, math.log2(ratio)))
    if value < 0:
        return base.blend(LOW, base.CREAM, (value + 2) / 2)
    return base.blend(base.CREAM, HIGH, value / 2)


def page_heatmap(raw: list[dict[str, str]], summary: list[dict[str, Any]], lang: str) -> Drawing:
    t = TEXT[lang]
    drawing = Drawing(base.PAGE_W, base.PAGE_H)
    base.add_page_header(drawing, t["p2_title"], t["p2_sub"])
    items = sorted({row["item_key"] for row in raw}, key=item_order)
    by_cell = {(row["model"], row["item_key"]): row for row in raw}
    item_medians = {
        item: statistics.median(float(row["elapsed_seconds"]) for row in raw if row["item_key"] == item)
        for item in items
    }

    legend_x = 466
    for index, (ratio, label) in enumerate(((0.5, t["faster"]), (1.0, t["same"]), (2.0, t["slower"]))):
        x = legend_x + index * 92
        base.add_rect(drawing, x, 91, 18, 12, ratio_color(ratio), base.WHITE, 0.5)
        base.add_text(drawing, x + 24, 101, label, 6.8, base.MUTED)
    base.add_rect(drawing, 742, 91, 18, 12, base.WHITE, RETRY, 1.5)
    base.add_text(drawing, 766, 101, t["retry"], 6.8, base.MUTED)

    x0, x1, row_h = 230, 804, 11.8
    session_codes = {
        "primoapp": "P1", "secondoapp": "P2", "terzoapp": "P3", "quartoapp": "P4", "quintoapp": "P5",
        "primoapp_tema_a": "P1A", "primoapp_tema_b": "P1B", "secondoapp_tema_a": "P2A", "secondoapp_tema_b": "P2B",
    }
    panels = [
        ("analysis_3", 112, "ANALISI 3" if lang == "it" else "ANALYSIS 3"),
        ("physics_2", 337, "FISICA 2" if lang == "it" else "PHYSICS 2"),
    ]
    for subject, header_top, subject_label in panels:
        panel_items = [item for item in items if item.startswith(subject + "|")]
        cell_w = (x1 - x0) / len(panel_items)
        row_top_start = header_top + 45
        base.add_text(drawing, 44, header_top + 12, subject_label, 8.5, base.NAVY, font="Helvetica-Bold")
        for group_start in range(0, len(panel_items), 3):
            _, year, session, _ = panel_items[group_start].split("|")
            fill = HexColor("#F3F7F9") if (group_start // 3) % 2 == 0 else HexColor("#EAF0F4")
            base.add_rect(drawing, x0 + group_start * cell_w, header_top, 3 * cell_w, 20, fill, base.WHITE, 0.7)
            base.add_text(drawing, x0 + (group_start + 1.5) * cell_w, header_top + 13, f"{year[-2:]} {session_codes[session]}", 6.3, base.MUTED, anchor="middle", font="Helvetica-Bold")
            for exercise in range(3):
                column = group_start + exercise
                base.add_text(drawing, x0 + (column + 0.5) * cell_w, header_top + 35, f"E{exercise + 1}", 6.2, base.NAVY, anchor="middle", font="Helvetica-Bold")
        for index, model_row in enumerate(summary, 1):
            row_top = row_top_start + (index - 1) * row_h
            if index % 2 == 0:
                base.add_rect(drawing, 40, row_top, 764, row_h, base.ROW_ALT)
            base.add_text(drawing, 44, row_top + row_h * 0.65, f"{index:02d}", 6.4, base.MUTED)
            base.add_rect(drawing, 67, row_top + 2, 3, row_h - 4, base.PROVIDER_COLORS[model_row["provider"]])
            label_size = 6.2 if len(model_row["model"]) > 23 else 7.1
            base.add_text(drawing, 78, row_top + row_h * 0.65, model_row["model"], label_size, base.INK)
            for column, item in enumerate(panel_items):
                row = by_cell[(model_row["model"], item)]
                ratio = float(row["elapsed_seconds"]) / item_medians[item]
                color = ratio_color(ratio)
                retry = float(row["retry_count"] or 0) > 0
                base.add_rect(drawing, x0 + column * cell_w, row_top + 0.7, cell_w - 0.4, row_h - 1.4, color, RETRY if retry else base.WHITE, 1.2 if retry else 0.35)
                text_color = base.WHITE if abs(math.log2(ratio)) > 1.35 else base.INK
                base.add_text(drawing, x0 + (column + 0.5) * cell_w, row_top + row_h * 0.67, f"{ratio:.1f}", 4.8, text_color, anchor="middle", font="Helvetica-Bold")
        for boundary in range(0, len(panel_items) + 1, 3):
            x = x0 + boundary * cell_w
            base.add_line(drawing, x, header_top, x, row_top_start + len(summary) * row_h, base.WHITE, 1.0)
    base.add_footer(drawing, t["p2_note"], 2, 4, t["footer"])
    return drawing


def page_time_drivers(summary: list[dict[str, Any]], lang: str) -> Drawing:
    t = TEXT[lang]
    drawing = Drawing(base.PAGE_W, base.PAGE_H)
    base.add_page_header(drawing, t["p3_title"], t["p3_sub"])
    base.add_rect(drawing, 44, 90, 760, 31, HexColor("#F3F7F9"), base.GRID, 0.7)
    base.add_text(drawing, 292, 110, t["formula"], 8.5, base.NAVY, anchor="middle", font="Helvetica-Bold")
    base.add_line(drawing, 548, 94, 548, 117, base.GRID, 0.9)
    base.add_circle(drawing, 575, 106, 4.2, base.GREEN, base.WHITE, 0.8)
    base.add_circle(drawing, 594, 106, 8.0, base.GREEN, base.WHITE, 0.8)
    base.add_text(drawing, 612, 109, t["bubble"], 6.8, base.NAVY, font="Helvetica-Bold")

    x0, x1, top, bottom = 92, 600, 153, 502
    x_values = [row["analytical_tokens_mean"] for row in summary]
    y_values = [row["effective_seconds_per_1k_tokens"] for row in summary]
    x_max = math.ceil(max(x_values) / 5000) * 5000
    y_max = math.ceil(max(y_values) / 10) * 10
    x_mid, y_mid = statistics.median(x_values), statistics.median(y_values)
    sx = lambda value: x0 + (x1 - x0) * value / x_max
    sy = lambda value: bottom - (bottom - top) * value / y_max
    mid_x, mid_y = sx(x_mid), sy(y_mid)

    base.add_rect(drawing, x0, top, mid_x - x0, mid_y - top, HexColor("#FCF4EF"))
    base.add_rect(drawing, mid_x, top, x1 - mid_x, mid_y - top, HexColor("#F8ECE9"))
    base.add_rect(drawing, x0, mid_y, mid_x - x0, bottom - mid_y, HexColor("#EDF7F5"))
    base.add_rect(drawing, mid_x, mid_y, x1 - mid_x, bottom - mid_y, HexColor("#F2F7F6"))
    for tick in range(6):
        x = x0 + (x1 - x0) * tick / 5
        y = bottom - (bottom - top) * tick / 5
        base.add_line(drawing, x, top, x, bottom, base.GRID, 0.65)
        base.add_line(drawing, x0, y, x1, y, base.GRID, 0.65)
        base.add_text(drawing, x, 520, f"{x_max * tick / 5000:.0f}k", 7.2, base.NAVY, anchor="middle")
        base.add_text(drawing, x0 - 10, y + 3, f"{y_max * tick / 5:.0f}", 7.2, base.NAVY, anchor="end")
    base.add_line(drawing, mid_x, top, mid_x, bottom, base.MUTED, 1.0)
    base.add_line(drawing, x0, mid_y, x1, mid_y, base.MUTED, 1.0)
    base.add_line(drawing, x0, bottom, x1, bottom, base.NAVY, 1.2)
    base.add_line(drawing, x0, top, x0, bottom, base.NAVY, 1.2)
    add_multiline(drawing, x0 + 8, top + 14, t["few_high"], base.RED, "start")
    add_multiline(drawing, x1 - 8, top + 14, t["many_high"], base.RED, "end")
    add_multiline(drawing, x0 + 8, bottom - 28, t["few_low"], base.GREEN, "start")
    add_multiline(drawing, x1 - 8, bottom - 28, t["many_low"], base.GREEN, "end")

    max_time = max(row["mean_seconds"] for row in summary)
    for row in summary:
        x, y = sx(row["analytical_tokens_mean"]), sy(row["effective_seconds_per_1k_tokens"])
        radius = 4.2 + 6.5 * math.sqrt(row["mean_seconds"] / max_time)
        base.add_circle(drawing, x, y, radius, base.PROVIDER_COLORS[row["provider"]], base.WHITE, 1)
        base.add_text(drawing, x, y + 2.2, str(row["time_rank"]), 5.2, base.WHITE,
                      anchor="middle", font="Helvetica-Bold")
    base.add_text(drawing, (x0 + x1) / 2, 546, t["p3_x"], 8.1, base.NAVY, anchor="middle")
    base.add_text(drawing, 44, (top + bottom) / 2, t["p3_y"], 8.0, base.NAVY, anchor="middle", angle=90)

    list_x, list_top, list_height = 628, 155, 24.7
    base.add_text(drawing, list_x, 140, t["rank"], 7.0, base.MUTED)
    base.add_text(drawing, list_x + 30, 140, t["model"], 7.0, base.MUTED)
    for row in summary:
        index = row["time_rank"]
        row_top = list_top + (index - 1) * list_height
        if index % 2 == 0:
            base.add_rect(drawing, list_x - 6, row_top - 12, 178, list_height, base.ROW_ALT)
        base.add_text(drawing, list_x, row_top, f"{index:02d}", 7.2, base.MUTED)
        base.add_rect(drawing, list_x + 28, row_top - 10, 3, 15, base.PROVIDER_COLORS[row["provider"]])
        base.add_text(drawing, list_x + 37, row_top, row["model"], 7.1, base.INK)
    base.add_footer(drawing, t["p3_note"], 3, 4, t["footer"])
    return drawing


def page_speed_accuracy(summary: list[dict[str, Any]], lang: str) -> Drawing:
    t = TEXT[lang]
    drawing = Drawing(base.PAGE_W, base.PAGE_H)
    base.add_page_header(drawing, t["p4_title"], t["p4_sub"])
    x0, x1, top, bottom = 92, 600, 142, 502
    x_min, x_max = 60.0, 100.0
    y_max = math.ceil(max(row["typical_responses_per_hour"] for row in summary) / 25) * 25
    sx = lambda value: x0 + (x1 - x0) * (value - x_min) / (x_max - x_min)
    sy = lambda value: bottom - (bottom - top) * value / y_max

    accuracy_mid = statistics.median(row["accuracy_mean"] for row in summary)
    speed_mid = statistics.median(row["typical_responses_per_hour"] for row in summary)
    base.add_rect(drawing, sx(accuracy_mid), top, x1 - sx(accuracy_mid), sy(speed_mid) - top,
                  HexColor("#EDF7F5"))

    for tick in range(6):
        x_value = x_min + (x_max - x_min) * tick / 5
        x = sx(x_value)
        base.add_line(drawing, x, top, x, bottom, base.GRID, 0.7)
        base.add_text(drawing, x, 520, f"{x_value:.0f}", 7.2, base.NAVY, anchor="middle")
        y_value = y_max * tick / 5
        y = sy(y_value)
        base.add_line(drawing, x0, y, x1, y, base.GRID, 0.7)
        base.add_text(drawing, x0 - 10, y + 3, f"{y_value:.0f}", 7.2, base.NAVY, anchor="end")
    base.add_line(drawing, x0, bottom, x1, bottom, base.NAVY, 1.2)
    base.add_line(drawing, x0, top, x0, bottom, base.NAVY, 1.2)
    base.add_line(drawing, sx(accuracy_mid), top, sx(accuracy_mid), bottom, base.MUTED, 1.0)
    base.add_line(drawing, x0, sy(speed_mid), x1, sy(speed_mid), base.MUTED, 1.0)
    base.add_text(drawing, x1 - 8, top + 17, t["desired"], 6.8, base.GREEN,
                  anchor="end", font="Helvetica-Bold")
    for row in summary:
        x, y = sx(row["accuracy_mean"]), sy(row["typical_responses_per_hour"])
        base.add_circle(drawing, x, y, 7.0, base.PROVIDER_COLORS[row["provider"]], base.WHITE, 1)
        base.add_text(drawing, x, y + 2.2, str(row["time_rank"]), 5.3, base.WHITE,
                      anchor="middle", font="Helvetica-Bold")
    base.add_text(drawing, (x0 + x1) / 2, 546, t["p4_x"], 8.1, base.NAVY, anchor="middle")
    base.add_text(drawing, 44, (top + bottom) / 2, t["p4_y"], 8.0, base.NAVY, anchor="middle", angle=90)

    list_x, list_top, list_height = 615, 148, 25.0
    base.add_text(drawing, list_x, 132, t["rank"], 6.8, base.MUTED)
    base.add_text(drawing, list_x + 28, 132, t["model"], 6.8, base.MUTED)
    base.add_text(drawing, 748, 132, t["accuracy"], 6.4, base.MUTED, anchor="end")
    base.add_text(drawing, 782, 132, t["speed"], 6.4, base.MUTED, anchor="end")
    base.add_text(drawing, 808, 132, t["time"], 6.4, base.MUTED, anchor="end")
    for row in summary:
        index = row["time_rank"]
        row_top = list_top + (index - 1) * list_height
        if index % 2 == 0:
            base.add_rect(drawing, list_x - 6, row_top - 12, 195, list_height, base.ROW_ALT)
        base.add_text(drawing, list_x, row_top, f"{index:02d}", 6.9, base.MUTED)
        base.add_rect(drawing, list_x + 25, row_top - 10, 3, 15, base.PROVIDER_COLORS[row["provider"]])
        font_size = 5.7 if len(row["model"]) > 23 else 6.6
        base.add_text(drawing, list_x + 34, row_top, row["model"], font_size, base.INK)
        base.add_text(drawing, 748, row_top, f"{row['accuracy_mean']:.1f}", 6.6, base.INK, anchor="end")
        base.add_text(drawing, 782, row_top, f"{row['typical_responses_per_hour']:.0f}", 6.6, base.INK, anchor="end")
        base.add_text(drawing, 808, row_top, f"{row['median_seconds']:.1f}", 6.6, base.INK, anchor="end")
    base.add_footer(drawing, t["p4_note"], 4, 4, t["footer"])
    return drawing


def write_tables(raw: list[dict[str, str]], summary: list[dict[str, Any]]) -> list[Path]:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = TABLE_DIR / "tempi_modelli_14x60.csv"
    fields = list(summary[0].keys())
    with summary_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary)

    normalized_path = TABLE_DIR / "tempi_normalizzati_modello_esercizio_14x60.csv"
    medians = {
        item: statistics.median(float(row["elapsed_seconds"]) for row in raw if row["item_key"] == item)
        for item in {row["item_key"] for row in raw}
    }
    normalized = []
    for row in raw:
        normalized.append(
            {
                "model": row["model"],
                "provider": row["provider"],
                "subject": row["subject"],
                "year": row["year"],
                "session": row["session"],
                "exercise": row["exercise"],
                "item_key": row["item_key"],
                "item_label": row["item_label"],
                "elapsed_seconds": row["elapsed_seconds"],
                "item_median_seconds": medians[row["item_key"]],
                "time_ratio_to_item_median": float(row["elapsed_seconds"]) / medians[row["item_key"]],
                "attempt_count": row["attempt_count"],
                "retry_count": row["retry_count"],
            }
        )
    with normalized_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(normalized[0].keys()))
        writer.writeheader()
        writer.writerows(normalized)
    return [summary_path, normalized_path]


def export_set(lang: str, drawings: list[Drawing]) -> dict[str, Any]:
    english = lang == "en"
    figure_dir = FIGURES_EN if english else FIGURES_IT
    rendered_dir = RENDERED_EN if english else RENDERED_IT
    pdf_name = "focused_response_time_charts.pdf" if english else "grafici_tempo_risposta_focus.pdf"
    names = (
        ["01_response_time_ranking", "02_model_exercise_heatmap", "03_time_drivers", "04_response_time_accuracy_correlation"]
        if english
        else ["01_classifica_tempi", "02_heatmap_modelli_esercizi", "03_driver_tempo", "04_correttezza_velocita"]
    )
    figure_dir.mkdir(parents=True, exist_ok=True)
    rendered_dir.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    for drawing, name in zip(drawings, names):
        renderSVG.drawToFile(drawing, str(figure_dir / f"{name}.svg"))
    pdf_path = PDF_DIR / pdf_name
    pdf = canvas.Canvas(str(pdf_path), pagesize=(base.PAGE_W, base.PAGE_H), pageCompression=1)
    pdf.setTitle(TEXT[lang]["pdf_title"])
    pdf.setSubject(TEXT[lang]["pdf_subject"])
    pdf.setAuthor("Francesco Bortot")
    pdf.setCreator("UniAIBench figure generator")
    for drawing in drawings:
        renderPDF.draw(drawing, pdf, 0, 0)
        pdf.showPage()
    pdf.save()
    return {"pdf": pdf_path, "figures": [figure_dir / f"{name}.svg" for name in names], "rendered": rendered_dir}


def write_methodology(summary: list[dict[str, Any]]) -> Path:
    path = OUTPUT_DIR / "METODOLOGIA.md"
    path.write_text(
        """# Metodologia - tempo di risposta 14 x 60

- Panel: 14 modelli x 60 esercizi comuni = 840 celle modello-esercizio.
- Composizione: 33 esercizi di Analisi 3 e 27 di Fisica 2, anni 2025-2026.
- Tempo: `timing.elapsed_seconds` della run attiva selezionata dall'indice autorevole.
- Semantica: il cronometro parte al primo dispatch, esclude l'attesa del semaforo locale e include chiamata API, generazione, backoff e retry.
- Classifica: mediana crescente; dispersione principale Q1-Q3; media, P90 e totale restano visibili.
- Heatmap: tempo della cella / mediana dei 14 modelli sullo stesso esercizio.
- Driver: `tempo medio = token analitici medi x secondi effettivi per 1K / 1.000`.
- Correttezza: macro-media sui medesimi 60 esercizi e giudizi attivi.
- Velocita nel grafico congiunto: `risposte tipiche/ora = 3.600 / tempo mediano in secondi`.

I secondi effettivi per 1K token sono un rapporto operativo e non una stima pura della velocita di generazione del provider.
""",
        encoding="utf-8",
    )
    return path


def main() -> None:
    raw = read_csv(RAW_PATH)
    quality_all = read_csv(QUALITY_PATH)
    quality = validate(raw, quality_all)
    summary = summarize(raw, quality)
    tables = write_tables(raw, summary)
    methodology = write_methodology(summary)

    outputs: dict[str, Any] = {}
    for lang in ("it", "en"):
        fourth_page = (
            correlation_chart.page_correlation_outliers(summary, main_report=True)
            if lang == "en"
            else page_speed_accuracy(summary, lang)
        )
        drawings = [
            page_time_ranking(summary, lang),
            page_heatmap(raw, summary, lang),
            page_time_drivers(summary, lang),
            fourth_page,
        ]
        outputs[lang] = export_set(lang, drawings)

    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sources": {
            str(RAW_PATH.relative_to(ANALYSIS_DIR)): sha256_file(RAW_PATH),
            str(QUALITY_PATH.relative_to(ANALYSIS_DIR)): sha256_file(QUALITY_PATH),
            str(SOURCE_MANIFEST.relative_to(ANALYSIS_DIR)): sha256_file(SOURCE_MANIFEST),
            str(TOKEN_FOCUS_MANIFEST.relative_to(ANALYSIS_DIR)): sha256_file(TOKEN_FOCUS_MANIFEST),
            str(REFERENCE_PDF.relative_to(ANALYSIS_DIR)): sha256_file(REFERENCE_PDF),
        },
        "counts": {
            "models": 14,
            "common_items": 60,
            "analysis_3_items": 33,
            "physics_2_items": 27,
            "model_item_cells": 840,
            "retry_rows": sum(float(row["retry_count"] or 0) > 0 for row in raw),
            "pages_per_pdf": 4,
        },
        "quality_checks": {
            "balanced_14x60": True,
            "elapsed_complete": True,
            "quality_panel_matches": True,
            "active_source_manifest": str(SOURCE_MANIFEST.relative_to(ANALYSIS_DIR)),
        },
        "outputs": {},
    }
    for path in tables + [methodology]:
        manifest["outputs"][str(path.relative_to(OUTPUT_DIR))] = sha256_file(path)
    for result in outputs.values():
        manifest["outputs"][str(result["pdf"].relative_to(OUTPUT_DIR))] = sha256_file(result["pdf"])
        for path in result["figures"]:
            manifest["outputs"][str(path.relative_to(OUTPUT_DIR))] = sha256_file(path)
    manifest_path = OUTPUT_DIR / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(OUTPUT_DIR), "manifest": str(manifest_path)}, indent=2))


if __name__ == "__main__":
    main()
