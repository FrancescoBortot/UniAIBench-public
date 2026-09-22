#!/usr/bin/env python3
"""Build four separate English speed/correctness chart alternatives."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.graphics import renderPDF, renderSVG
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

import build_selected_token_cost_charts as base


ANALYSIS_DIR = Path(__file__).resolve().parents[1]
TIME_DIR = ANALYSIS_DIR / "grafici_tempo_risposta_focus"
OUTPUT_DIR = TIME_DIR / "alternatives_en"
FIGURE_DIR = OUTPUT_DIR / "figures"
PDF_DIR = OUTPUT_DIR / "output" / "pdf"
RENDERED_DIR = OUTPUT_DIR / "output" / "rendered"
SUMMARY_PATH = TIME_DIR / "tables" / "tempi_modelli_17x60.csv"
SOURCE_MANIFEST = TIME_DIR / "MANIFEST.json"

FOOTER = "Common panel: 60 exercises, 17 models, 1,020 macro-averaged cells | English alternatives"
TIME_MIN, TIME_MAX = 15.0, 500.0

SHORT_NAMES = {
    "Claude Fable 5": "Fable",
    "Claude Haiku 4.5": "Haiku",
    "Claude Sonnet 4.5": "Sonnet",
    "DeepSeek V4 Flash": "DS Flash",
    "DeepSeek V4 Flash (no thinking)": "DS Flash NT",
    "DeepSeek V4 Pro": "DS Pro",
    "DeepSeek V4.1 Flash": "DS 4.1 Flash",
    "GPT-5.6 Sol": "GPT-5.6",
    "Gemini 3.1 Pro Preview": "Gemini Pro",
    "Gemini 3.5 Flash": "Gemini Flash",
    "Gemma 4 31B IT": "Gemma",
    "Grok 4.3": "Grok 4.3",
    "Grok 4.5": "Grok 4.5",
    "OpenAI GPT-4.1": "GPT-4.1",
    "OpenAI o3": "o3",
    "Mistral Medium 3.5": "Mistral Med.",
    "Mistral Small 4": "Mistral Small",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_summary() -> list[dict[str, Any]]:
    rows = read_csv(SUMMARY_PATH)
    numeric = {
        "median_seconds", "mean_seconds", "q1_seconds", "q3_seconds", "p90_seconds",
        "typical_responses_per_hour", "accuracy_mean", "accuracy_ci95_low", "accuracy_ci95_high",
    }
    result: list[dict[str, Any]] = []
    for source in rows:
        row: dict[str, Any] = dict(source)
        for key in numeric:
            row[key] = float(row[key])
        row["time_rank"] = int(row["time_rank"])
        result.append(row)
    if len(result) != 17 or len({row["model"] for row in result}) != 17:
        raise RuntimeError("Expected exactly 17 models")
    return result


def average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        average = (start + 1 + end) / 2.0
        for index in order[start:end]:
            ranks[index] = average
        start = end
    return ranks


def pearson(values_x: list[float], values_y: list[float]) -> float:
    mean_x = sum(values_x) / len(values_x)
    mean_y = sum(values_y) / len(values_y)
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(values_x, values_y))
    spread_x = sum((x - mean_x) ** 2 for x in values_x)
    spread_y = sum((y - mean_y) ** 2 for y in values_y)
    return covariance / math.sqrt(spread_x * spread_y)


def correlation_diagnostics(summary: list[dict[str, Any]]) -> dict[str, Any]:
    log_times = [math.log10(row["median_seconds"]) for row in summary]
    accuracies = [row["accuracy_mean"] for row in summary]
    minimum_time = min(row["median_seconds"] for row in summary)
    deficits = [100.0 - value for value in accuracies]
    best: tuple[float, float, float, list[float]] | None = None
    for index in range(20001):
        exponent = 0.01 + index * (5.0 - 0.01) / 20000
        weights = [(row["median_seconds"] / minimum_time) ** (-exponent) for row in summary]
        amplitude = sum(weight * deficit for weight, deficit in zip(weights, deficits)) / sum(weight * weight for weight in weights)
        predictions = [100.0 - amplitude * weight for weight in weights]
        sse = sum((actual - predicted) ** 2 for actual, predicted in zip(accuracies, predictions))
        if best is None or sse < best[0]:
            best = (sse, amplitude, exponent, predictions)
    assert best is not None
    sse, amplitude, exponent, predictions = best
    residuals = [actual - predicted for actual, predicted in zip(accuracies, predictions)]
    diagnostics = []
    for row, predicted, residual in zip(summary, predictions, residuals):
        diagnostics.append({**row, "trend_accuracy": predicted, "residual_pp": residual})
    correlation = pearson(log_times, accuracies)
    spearman = pearson(average_ranks(log_times), average_ranks(accuracies))
    total_variation = sum((value - sum(accuracies) / len(accuracies)) ** 2 for value in accuracies)
    return {
        "curve_amplitude": amplitude,
        "curve_exponent": exponent,
        "minimum_time": minimum_time,
        "pearson_log_time": correlation,
        "spearman": spearman,
        "trend_r_squared": 1.0 - sse / total_variation,
        "rows": diagnostics,
    }


def log_scale(value: float, minimum: float, maximum: float, x0: float, x1: float) -> float:
    return x0 + (x1 - x0) * (math.log(value) - math.log(minimum)) / (math.log(maximum) - math.log(minimum))


def accuracy_color(accuracy: float) -> Any:
    amount = max(0.0, min(1.0, (accuracy - 60.0) / 40.0))
    if amount <= 0.5:
        return base.blend(base.RED, base.CREAM, amount / 0.5)
    return base.blend(base.CREAM, base.GREEN, (amount - 0.5) / 0.5)


def add_standard_footer(drawing: Drawing, note: str) -> None:
    base.add_text(drawing, 44, 566, note, 7.1, base.MUTED)
    base.add_text(drawing, 44, 581, FOOTER, 6.6, base.MUTED)


def page_dual_ranking(summary: list[dict[str, Any]]) -> Drawing:
    rows = sorted(summary, key=lambda row: (-row["accuracy_mean"], row["median_seconds"]))
    drawing = Drawing(base.PAGE_W, base.PAGE_H)
    base.add_page_header(
        drawing,
        "Option 1 - Aligned correctness and response-time rankings",
        "One shared model order, with accuracy uncertainty on the left and typical-time variability on the right",
    )

    base.add_text(drawing, 44, 118, "ACC. RANK", 6.8, base.MUTED)
    base.add_text(drawing, 92, 118, "MODEL", 6.8, base.MUTED)
    base.add_text(drawing, 390, 108, "MEAN ACCURACY (%)", 8.0, base.NAVY, anchor="middle", font="Helvetica-Bold")
    base.add_text(drawing, 681, 108, "MEDIAN RESPONSE TIME (S, LOG SCALE)", 8.0, base.NAVY,
                  anchor="middle", font="Helvetica-Bold")
    base.add_text(drawing, 390, 121, "farther right = more correct", 6.5, base.MUTED, anchor="middle")
    base.add_text(drawing, 681, 121, "farther left = faster", 6.5, base.MUTED, anchor="middle")

    row_top, row_h = 132, 25.0
    base.add_alternating_rows(drawing, row_top, row_h, len(rows), x=40, width=770)
    acc_x0, acc_x1 = 285, 495
    time_x0, time_x1 = 575, 765
    for value in (60, 70, 80, 90, 100):
        x = acc_x0 + (acc_x1 - acc_x0) * (value - 60) / 40
        base.add_line(drawing, x, row_top, x, row_top + row_h * len(rows), base.GRID, 0.65)
        base.add_text(drawing, x, 497, str(value), 6.9, base.NAVY, anchor="middle")
    for value in (20, 40, 80, 160, 320):
        x = log_scale(value, TIME_MIN, TIME_MAX, time_x0, time_x1)
        base.add_line(drawing, x, row_top, x, row_top + row_h * len(rows), base.GRID, 0.65)
        base.add_text(drawing, x, 497, str(value), 6.9, base.NAVY, anchor="middle")

    for rank, row in enumerate(rows, 1):
        top = row_top + (rank - 1) * row_h
        y = top + row_h * 0.55
        base.add_text(drawing, 44, y + 3, f"{rank:02d}", 8.3, base.MUTED)
        base.add_rect(drawing, 78, top + 4, 3, row_h - 8, base.PROVIDER_COLORS[row["provider"]])
        base.add_text(drawing, 90, top + row_h * 0.50, row["model"], 8.7, base.INK)
        base.add_text(drawing, 90, top + row_h * 0.79, row["provider"].upper(), 5.2, base.MUTED)

        acc = row["accuracy_mean"]
        acc_low = max(60.0, row["accuracy_ci95_low"])
        acc_high = min(100.0, row["accuracy_ci95_high"])
        acc_scale = lambda value: acc_x0 + (acc_x1 - acc_x0) * (value - 60) / 40
        base.add_line(drawing, acc_scale(acc_low), y, acc_scale(acc_high), y, HexColor("#62798C"), 1.6)
        base.add_line(drawing, acc_scale(acc_low), y - 4, acc_scale(acc_low), y + 4, HexColor("#62798C"), 1.0)
        base.add_line(drawing, acc_scale(acc_high), y - 4, acc_scale(acc_high), y + 4, HexColor("#62798C"), 1.0)
        base.add_circle(drawing, acc_scale(acc), y, 4.8, base.PROVIDER_COLORS[row["provider"]], base.WHITE, 0.8)
        base.add_text(drawing, 535, y + 3, f"{acc:.1f}", 7.5, base.INK, anchor="end")

        q1 = log_scale(max(TIME_MIN, row["q1_seconds"]), TIME_MIN, TIME_MAX, time_x0, time_x1)
        median = log_scale(row["median_seconds"], TIME_MIN, TIME_MAX, time_x0, time_x1)
        q3 = log_scale(min(TIME_MAX, row["q3_seconds"]), TIME_MIN, TIME_MAX, time_x0, time_x1)
        base.add_line(drawing, q1, y, q3, y, HexColor("#62798C"), 1.6)
        base.add_line(drawing, q1, y - 4, q1, y + 4, HexColor("#62798C"), 1.0)
        base.add_line(drawing, q3, y - 4, q3, y + 4, HexColor("#62798C"), 1.0)
        base.add_circle(drawing, median, y, 4.8, base.PROVIDER_COLORS[row["provider"]], base.WHITE, 0.8)
        base.add_text(drawing, 806, y + 3, f"{row['median_seconds']:.1f}", 7.5, base.INK, anchor="end")
    base.add_line(drawing, acc_x0, 490, acc_x1, 490, base.NAVY, 1.1)
    base.add_line(drawing, time_x0, 490, time_x1, 490, base.NAVY, 1.1)
    add_standard_footer(drawing, "Intervals: 95% confidence interval for accuracy; Q1-Q3 for response time.")
    return drawing


def page_speed_bars(summary: list[dict[str, Any]]) -> Drawing:
    rows = sorted(summary, key=lambda row: (-row["typical_responses_per_hour"], -row["accuracy_mean"]))
    drawing = Drawing(base.PAGE_W, base.PAGE_H)
    base.add_page_header(
        drawing,
        "Option 2 - Speed bars colored by correctness",
        "Bar length shows typical responses per hour; bar color and the ACC. column show mean accuracy",
    )

    base.add_text(drawing, 44, 119, "SPEED RANK", 6.8, base.MUTED)
    base.add_text(drawing, 96, 119, "MODEL", 6.8, base.MUTED)
    base.add_text(drawing, 465, 108, "TYPICAL RESPONSES PER HOUR", 8.0, base.NAVY, anchor="middle", font="Helvetica-Bold")
    base.add_text(drawing, 710, 119, "ACC.", 6.8, base.MUTED, anchor="end")
    base.add_text(drawing, 760, 119, "RESP./H", 6.8, base.MUTED, anchor="end")
    base.add_text(drawing, 806, 119, "SEC.", 6.8, base.MUTED, anchor="end")

    legend_x = 285
    for index, accuracy in enumerate((60, 70, 80, 90, 100)):
        x = legend_x + index * 52
        base.add_rect(drawing, x, 112, 18, 8, accuracy_color(float(accuracy)), base.WHITE, 0.4)
        base.add_text(drawing, x + 22, 119, f"{accuracy}%", 5.8, base.MUTED)

    row_top, row_h = 132, 25.0
    base.add_alternating_rows(drawing, row_top, row_h, len(rows), x=40, width=770)
    bar_x0, bar_x1 = 285, 655
    speed_max = 175.0
    for value in (0, 35, 70, 105, 140, 175):
        x = bar_x0 + (bar_x1 - bar_x0) * value / speed_max
        base.add_line(drawing, x, row_top, x, row_top + row_h * len(rows), base.GRID, 0.65)
        base.add_text(drawing, x, 497, str(value), 6.9, base.NAVY, anchor="middle")

    for rank, row in enumerate(rows, 1):
        top = row_top + (rank - 1) * row_h
        y = top + row_h * 0.55
        base.add_text(drawing, 44, y + 3, f"{rank:02d}", 8.3, base.MUTED)
        base.add_rect(drawing, 82, top + 4, 3, row_h - 8, base.PROVIDER_COLORS[row["provider"]])
        base.add_text(drawing, 96, top + row_h * 0.50, row["model"], 8.7, base.INK)
        base.add_text(drawing, 96, top + row_h * 0.79, row["provider"].upper(), 5.2, base.MUTED)
        width = (bar_x1 - bar_x0) * row["typical_responses_per_hour"] / speed_max
        base.add_rect(drawing, bar_x0, top + 6, width, row_h - 12, accuracy_color(row["accuracy_mean"]))
        base.add_text(drawing, 710, y + 3, f"{row['accuracy_mean']:.1f}", 7.6, base.INK, anchor="end")
        base.add_text(drawing, 760, y + 3, f"{row['typical_responses_per_hour']:.0f}", 7.6, base.INK, anchor="end")
        base.add_text(drawing, 806, y + 3, f"{row['median_seconds']:.1f}", 7.6, base.INK, anchor="end")
    base.add_line(drawing, bar_x0, 490, bar_x1, 490, base.NAVY, 1.1)
    add_standard_footer(drawing, "Accuracy is encoded redundantly by color and numeric label; speed remains the primary ordering.")
    return drawing


def provider_legend(drawing: Drawing) -> None:
    names = [("openai", "OpenAI"), ("anthropic", "Anthropic"), ("google", "Google"),
             ("deepseek", "DeepSeek"), ("xai", "xAI"), ("mistral", "Mistral")]
    x = 82
    for provider, label in names:
        base.add_circle(drawing, x, 112, 3.8, base.PROVIDER_COLORS[provider], base.WHITE, 0.5)
        base.add_text(drawing, x + 8, 115, label, 6.4, base.MUTED)
        x += 72


def draw_scatter_panel(
    drawing: Drawing,
    rows: list[dict[str, Any]],
    x0: float,
    x1: float,
    top: float,
    bottom: float,
    y_min: float,
    y_max: float,
    x_ticks: tuple[int, ...],
    y_ticks: tuple[int, ...],
    label_offsets: dict[str, tuple[float, float]],
) -> None:
    for value in x_ticks:
        x = log_scale(float(value), 20.0, 320.0, x0, x1)
        base.add_line(drawing, x, top, x, bottom, base.GRID, 0.65)
        base.add_text(drawing, x, bottom + 18, str(value), 6.8, base.NAVY, anchor="middle")
    for value in y_ticks:
        y = bottom - (bottom - top) * (value - y_min) / (y_max - y_min)
        base.add_line(drawing, x0, y, x1, y, base.GRID, 0.65)
        base.add_text(drawing, x0 - 8, y + 3, str(value), 6.8, base.NAVY, anchor="end")
    base.add_line(drawing, x0, bottom, x1, bottom, base.NAVY, 1.1)
    base.add_line(drawing, x0, top, x0, bottom, base.NAVY, 1.1)

    for row in rows:
        x = log_scale(row["median_seconds"], 20.0, 320.0, x0, x1)
        y = bottom - (bottom - top) * (row["accuracy_mean"] - y_min) / (y_max - y_min)
        base.add_circle(drawing, x, y, 5.2, base.PROVIDER_COLORS[row["provider"]], base.WHITE, 0.8)
        dx, dy = label_offsets.get(row["model"], (6.0, -5.0))
        anchor = "end" if dx < 0 else "start"
        base.add_text(drawing, x + dx, y + dy, SHORT_NAMES[row["model"]], 6.2, base.INK,
                      anchor=anchor, font="Helvetica-Bold")


def page_scatter_zoom(summary: list[dict[str, Any]]) -> Drawing:
    drawing = Drawing(base.PAGE_W, base.PAGE_H)
    base.add_page_header(
        drawing,
        "Option 3 - Accuracy versus median time, with a top-tier zoom",
        "The overview preserves the full benchmark; the zoom separates models compressed between 96% and 100% accuracy",
    )
    provider_legend(drawing)

    main_offsets = {
        "Claude Haiku 4.5": (6, -7), "OpenAI GPT-4.1": (-6, 12),
        "Claude Sonnet 4.5": (6, -6), "DeepSeek V4 Flash (no thinking)": (6, -6),
        "Gemini 3.5 Flash": (-6, 12), "OpenAI o3": (-6, -8), "Grok 4.3": (6, 12),
        "Claude Fable 5": (6, -6), "Gemma 4 31B IT": (6, -7),
        "Gemini 3.1 Pro Preview": (6, 12), "Grok 4.5": (6, 12),
        "DeepSeek V4 Flash": (-6, 12), "DeepSeek V4 Pro": (-6, -8), "GPT-5.6 Sol": (-6, 12),
    }
    draw_scatter_panel(
        drawing, summary, 72, 440, 148, 500, 60, 100,
        (20, 40, 80, 160, 320), (60, 70, 80, 90, 100), main_offsets,
    )
    base.add_text(drawing, 256, 536, "MEDIAN RESPONSE TIME (SECONDS, LOG SCALE)", 7.8, base.NAVY, anchor="middle")
    base.add_text(drawing, 40, 324, "MEAN ACCURACY (%)", 7.8, base.NAVY, anchor="middle", angle=90)
    base.add_text(drawing, 82, 164, "MORE CORRECT / FASTER", 6.5, base.GREEN, font="Helvetica-Bold")

    zoom_rows = [row for row in summary if row["accuracy_mean"] >= 96.0]
    zoom_offsets = {
        "Gemini 3.5 Flash": (6, 10), "OpenAI o3": (6, -7), "Claude Fable 5": (-6, 11),
        "Gemini 3.1 Pro Preview": (6, 11), "Grok 4.5": (6, 11),
        "DeepSeek V4 Flash": (6, -7), "DeepSeek V4 Pro": (-6, -7), "GPT-5.6 Sol": (-6, 11),
    }
    base.add_rect(drawing, 485, 132, 331, 391, HexColor("#FAFCFD"), base.GRID, 0.8)
    base.add_text(drawing, 500, 151, "TOP-ACCURACY ZOOM: 96% TO 100%", 7.2, base.NAVY, font="Helvetica-Bold")
    draw_scatter_panel(
        drawing, zoom_rows, 510, 798, 175, 480, 96, 100,
        (40, 80, 160, 320), (96, 97, 98, 99, 100), zoom_offsets,
    )
    base.add_text(drawing, 654, 515, "MEDIAN TIME (S, LOG SCALE)", 7.0, base.NAVY, anchor="middle")
    add_standard_footer(drawing, "Preferred direction is upper-left in both panels. Labels use shortened model names.")
    return drawing


def page_correlation_outliers(summary: list[dict[str, Any]], main_report: bool = False) -> Drawing:
    stats = correlation_diagnostics(summary)
    rows = stats["rows"]
    drawing = Drawing(base.PAGE_W, base.PAGE_H)
    base.add_text(drawing, 44, 43, "Response time vs accuracy", 24, base.NAVY)
    if not main_report:
        base.add_text(
            drawing, 798, 43, "OPTION 4", 7.0, base.MUTED,
            anchor="end", font="Helvetica-Bold",
        )
    base.add_text(drawing, 44, 69, "Correlation and model deviations | 17 models x 60 common exercises", 10.2, base.MUTED)

    takeaway_fill = base.blend(base.WHITE, base.GREEN, 0.10)
    takeaway_stroke = base.blend(base.WHITE, base.GREEN, 0.38)
    base.add_rect(drawing, 44, 86, 754, 38, takeaway_fill, takeaway_stroke, 0.8)
    base.add_text(drawing, 56, 102, "KEY RESULT", 6.8, base.GREEN, font="Helvetica-Bold")
    base.add_text(
        drawing, 118, 102,
        "Longer response time is associated with higher accuracy, but the gains flatten near the accuracy ceiling.",
        9.2, base.NAVY, font="Helvetica-Bold",
    )
    base.add_text(
        drawing, 118, 117,
        f"Pearson r (log time) = {stats['pearson_log_time']:.2f}   |   rank correlation rho = {stats['spearman']:.2f}   |   bounded-curve R-squared = {stats['trend_r_squared']:.2f}",
        6.9, base.MUTED,
    )

    # Correlation scatter.
    scatter_x0, scatter_x1 = 66.0, 452.0
    scatter_top, scatter_bottom = 176.0, 492.0
    y_min, y_max = 60.0, 102.0
    for value in (20, 40, 80, 160, 320):
        x = log_scale(float(value), 20.0, 320.0, scatter_x0, scatter_x1)
        base.add_line(drawing, x, scatter_top, x, scatter_bottom, base.GRID, 0.65)
        base.add_text(drawing, x, scatter_bottom + 18, str(value), 6.8, base.NAVY, anchor="middle")
    for value in (60, 70, 80, 90, 100):
        y = scatter_bottom - (scatter_bottom - scatter_top) * (value - y_min) / (y_max - y_min)
        base.add_line(drawing, scatter_x0, y, scatter_x1, y, base.GRID, 0.65)
        base.add_text(drawing, scatter_x0 - 8, y + 3, str(value), 6.8, base.NAVY, anchor="end")
    base.add_line(drawing, scatter_x0, scatter_bottom, scatter_x1, scatter_bottom, base.NAVY, 1.1)
    base.add_line(drawing, scatter_x0, scatter_top, scatter_x0, scatter_bottom, base.NAVY, 1.1)
    base.add_text(drawing, (scatter_x0 + scatter_x1) / 2, 530, "MEDIAN RESPONSE TIME (SECONDS, LOG SCALE)", 7.2, base.NAVY, anchor="middle")
    base.add_text(drawing, 26, (scatter_top + scatter_bottom) / 2, "MEAN ACCURACY (%)", 7.2, base.NAVY, anchor="middle", angle=-90)
    base.add_text(drawing, 66, 143, "1  OVERALL RELATIONSHIP", 8.2, base.NAVY, font="Helvetica-Bold")
    base.add_text(drawing, 66, 160, "BETTER = UP + LEFT", 6.6, base.GREEN, font="Helvetica-Bold")
    provider_legend_items = [
        (174, "openai", "OpenAI"),
        (228, "anthropic", "Anthropic"),
        (299, "google", "Google"),
        (354, "deepseek", "DeepSeek"),
        (423, "xai", "xAI"),
        (463, "mistral", "Mistral"),
    ]
    for x, provider, label in provider_legend_items:
        base.add_circle(drawing, x, 157, 3.5, base.PROVIDER_COLORS[provider], base.WHITE, 0.5)
        base.add_text(drawing, x + 7, 160, label, 5.7, base.MUTED)

    def scatter_x(seconds: float) -> float:
        return log_scale(seconds, 20.0, 320.0, scatter_x0, scatter_x1)

    def scatter_y(accuracy: float) -> float:
        return scatter_bottom - (scatter_bottom - scatter_top) * (accuracy - y_min) / (y_max - y_min)

    def trend_accuracy(seconds: float) -> float:
        return 100.0 - stats["curve_amplitude"] * (seconds / stats["minimum_time"]) ** (-stats["curve_exponent"])

    trend_times = [stats["minimum_time"] * (320.0 / stats["minimum_time"]) ** (index / 60) for index in range(61)]
    curve_color = HexColor("#D4A000")
    for index, (start, end) in enumerate(zip(trend_times, trend_times[1:])):
        if index % 3 != 2:
            base.add_line(
                drawing, scatter_x(start), scatter_y(trend_accuracy(start)),
                scatter_x(end), scatter_y(trend_accuracy(end)), curve_color, 2.8,
            )
    base.add_line(drawing, 330, 476, 341, 476, curve_color, 2.8)
    base.add_line(drawing, 346, 476, 357, 476, curve_color, 2.8)
    base.add_text(drawing, 363, 479, "EXPECTED CURVE", 6.2, curve_color, font="Helvetica-Bold")

    highlight = {row["model"] for row in sorted(rows, key=lambda row: -abs(row["residual_pp"]))[:3]}
    label_offsets = {
        "Claude Haiku 4.5": (8, -8),
        "OpenAI GPT-4.1": (8, 14),
        "DeepSeek V4 Flash (no thinking)": (8, -8),
        "Claude Sonnet 4.5": (8, 14),
        "Gemini 3.5 Flash": (-7, -10),
        "OpenAI o3": (-8, 14),
        "Grok 4.3": (-8, -8),
        "Claude Fable 5": (-8, -13),
        "Gemma 4 31B IT": (8, 14),
        "Gemini 3.1 Pro Preview": (8, 17),
        "Grok 4.5": (8, -12),
        "DeepSeek V4 Flash": (-5, 18),
        "DeepSeek V4 Pro": (8, 15),
        "GPT-5.6 Sol": (-8, -10),
    }
    for row in rows:
        x = scatter_x(row["median_seconds"])
        y = scatter_y(row["accuracy_mean"])
        if row["model"] in highlight:
            base.add_circle(drawing, x, y, 7.2, base.WHITE, base.NAVY, 1.2)
        base.add_circle(drawing, x, y, 4.8, base.PROVIDER_COLORS[row["provider"]], base.WHITE, 0.7)
        if row["model"] in label_offsets:
            dx, dy = label_offsets[row["model"]]
            label = SHORT_NAMES[row["model"]]
            if row["model"] in highlight:
                label += f" ({row['residual_pp']:+.1f})"
            base.add_text(
                drawing, x + dx, y + dy, label, 6.1, base.INK,
                anchor="end" if dx < 0 else "start", font="Helvetica-Bold",
            )

    # Residual plot: all models, sorted by deviation from the fitted trend.
    residual_rows = sorted(rows, key=lambda row: -row["residual_pp"])
    residual_x0, residual_x1 = 650.0, 800.0
    residual_min, residual_max = -16.0, 18.0
    residual_top, row_h = 176.0, 22.4

    def residual_x(value: float) -> float:
        return residual_x0 + (residual_x1 - residual_x0) * (value - residual_min) / (residual_max - residual_min)

    base.add_text(drawing, 478, 143, "2  WHO BEATS OR MISSES THE TREND?", 8.2, base.NAVY, font="Helvetica-Bold")
    base.add_text(drawing, 685, 160, "BELOW EXPECTED", 6.2, base.RED, anchor="middle", font="Helvetica-Bold")
    base.add_text(drawing, 758, 160, "ABOVE EXPECTED", 6.2, base.GREEN, anchor="middle", font="Helvetica-Bold")
    base.add_text(drawing, 800, 143, "ACCURACY GAP (POINTS)", 6.2, base.MUTED, anchor="end")
    for value in (-15, -10, -5, 0, 5, 10, 15):
        x = residual_x(float(value))
        base.add_line(drawing, x, residual_top, x, residual_top + row_h * len(residual_rows), base.GRID if value else base.NAVY, 1.0 if value == 0 else 0.55)
        base.add_text(drawing, x, 510, f"{value:+d}", 6.5, base.NAVY, anchor="middle")
    for index, row in enumerate(residual_rows):
        top = residual_top + index * row_h
        y = top + row_h * 0.57
        if index % 2:
            base.add_rect(drawing, 472, top, 334, row_h, base.ROW_ALT)
        base.add_text(drawing, 625, y + 3, SHORT_NAMES[row["model"]], 7.0, base.INK, anchor="end")
        zero = residual_x(0.0)
        value_x = residual_x(row["residual_pp"])
        residual_color = base.GREEN if row["residual_pp"] >= 0 else base.RED
        base.add_line(drawing, zero, y, value_x, y, residual_color, 2.0)
        base.add_circle(drawing, value_x, y, 4.0, base.PROVIDER_COLORS[row["provider"]], base.WHITE, 0.7)
        value_anchor = "start" if row["residual_pp"] >= 0 else "end"
        value_dx = 6 if row["residual_pp"] >= 0 else -6
        base.add_text(drawing, value_x + value_dx, y + 3, f"{row['residual_pp']:+.1f}", 6.5, residual_color, anchor=value_anchor, font="Helvetica-Bold")

    base.add_text(
        drawing, 44, 558,
        "HOW TO READ: right of zero = more accurate than expected; left of zero = less accurate than expected. Rings mark the 3 largest gaps.",
        7.1, base.MUTED,
    )
    footer = (
        "Common panel: 60 exercises (33 Analysis 3, 27 Physics 2), 17 models, 1,020 macro-averaged cells"
        if main_report
        else "Bounded saturating trend | descriptive association, not causation | 60 exercises, 17 models, 1,020 cells"
    )
    base.add_text(drawing, 44, 581, footer, 6.6, base.MUTED)
    if main_report:
        base.add_text(drawing, 800, 581, "4/4", 6.6, base.MUTED, anchor="end")
    return drawing


def export_one(name: str, title: str, drawing: Drawing) -> dict[str, Path]:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    RENDERED_DIR.mkdir(parents=True, exist_ok=True)
    svg_path = FIGURE_DIR / f"{name}.svg"
    pdf_path = PDF_DIR / f"{name}.pdf"
    renderSVG.drawToFile(drawing, str(svg_path))
    pdf = canvas.Canvas(str(pdf_path), pagesize=(base.PAGE_W, base.PAGE_H), pageCompression=1)
    pdf.setTitle(title)
    pdf.setSubject("Speed and correctness chart alternative for the balanced 17 x 60 benchmark")
    pdf.setAuthor("Francesco Bortot")
    pdf.setCreator("UniAIBench figure generator")
    renderPDF.draw(drawing, pdf, 0, 0)
    pdf.showPage()
    pdf.save()
    return {"svg": svg_path, "pdf": pdf_path}


def main() -> None:
    summary = load_summary()
    outputs = {
        "01_aligned_dual_ranking": export_one(
            "01_aligned_dual_ranking",
            "Option 1 - Aligned correctness and response-time rankings",
            page_dual_ranking(summary),
        ),
        "02_speed_bars_accuracy": export_one(
            "02_speed_bars_accuracy",
            "Option 2 - Speed bars colored by correctness",
            page_speed_bars(summary),
        ),
        "03_scatter_with_zoom": export_one(
            "03_scatter_with_zoom",
            "Option 3 - Accuracy versus median time, with a top-tier zoom",
            page_scatter_zoom(summary),
        ),
        "04_correlation_outliers": export_one(
            "04_correlation_outliers",
            "Option 4 - Correlation between response time and accuracy, with model deviations",
            page_correlation_outliers(summary),
        ),
    }
    readme = OUTPUT_DIR / "README.md"
    readme.write_text(
        """# Speed/correctness alternatives

These are separate English previews. They do not replace or modify the main response-time PDF.

1. Aligned dual ranking: accuracy and median time in synchronized panels.
2. Speed bars colored by correctness: speed is bar length; accuracy is color plus number.
3. Scatter with zoom: overview plus a dedicated 96-100% accuracy panel.
4. Correlation and outliers: model-level association plus residual deviations from the fitted trend.
""",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": {
            str(SUMMARY_PATH.relative_to(ANALYSIS_DIR)): sha256_file(SUMMARY_PATH),
            str(SOURCE_MANIFEST.relative_to(ANALYSIS_DIR)): sha256_file(SOURCE_MANIFEST),
        },
        "counts": {"models": 17, "common_items": 60, "alternatives": 4, "pages_per_pdf": 1},
        "main_report_modified": False,
        "outputs": {str(readme.relative_to(OUTPUT_DIR)): sha256_file(readme)},
    }
    for result in outputs.values():
        for path in result.values():
            manifest["outputs"][str(path.relative_to(OUTPUT_DIR))] = sha256_file(path)
    manifest_path = OUTPUT_DIR / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(OUTPUT_DIR), "manifest": str(manifest_path)}, indent=2))


if __name__ == "__main__":
    main()
