#!/usr/bin/env python3
"""Build a focused four-page token/cost report without replacing prior artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.graphics import renderPDF, renderSVG
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

import build_selected_token_cost_charts as base


OUTPUT_DIR = base.ANALYSIS_DIR / "grafici_token_costi_focus"
FIGURES_IT = OUTPUT_DIR / "figures"
FIGURES_EN = OUTPUT_DIR / "figures_en"
PDF_DIR = OUTPUT_DIR / "output" / "pdf"
RENDERED_IT = OUTPUT_DIR / "output" / "rendered"
RENDERED_EN = OUTPUT_DIR / "output" / "rendered_en"

TEXT = {
    "it": {
        "pdf_title": "Grafici focus - token e costi",
        "pdf_subject": "Benchmark 14 x 60: classifica, composizione, driver e tariffe",
        "p3_title": "Come si forma il costo medio",
        "p3_sub": "Volume consumato e costo effettivo unitario spiegano insieme il costo per risposta",
        "formula": "COSTO MEDIO = TOKEN MEDI x COSTO EFFETTIVO PER 1M / 1.000.000",
        "x": "TOKEN ANALITICI MEDI PER RISPOSTA",
        "y": "COSTO EFFETTIVO PER 1M TOKEN ANALITICI (USD)",
        "few_low": "POCHI TOKEN\nCOSTO UNITARIO BASSO",
        "few_high": "POCHI TOKEN\nCOSTO UNITARIO ALTO",
        "many_low": "MOLTI TOKEN\nCOSTO UNITARIO BASSO",
        "many_high": "MOLTI TOKEN\nCOSTO UNITARIO ALTO",
        "p3_note": "La tariffa effettiva incorpora il mix reale di input e output: non coincide necessariamente con un prezzo di listino.",
        "p4_title": "Tariffe per milione di token",
        "p4_sub": "Prezzi unitari usati nel benchmark | confronto diretto, indipendente dai token consumati",
        "input": "INPUT",
        "output": "OUTPUT",
        "axis": "USD PER 1 MILIONE DI TOKEN",
        "p4_note": "Il reasoning e fatturato come output dove previsto. Gemma usa la tariffa zero configurata per questa campagna.",
        "footer": "Panel comune: 60 esercizi, 14 modelli, 840 celle macro-mediate",
        "rank": "POS.",
        "model": "MODELLO",
        "bubble_mean": "DIMENSIONE BOLLA = COSTO MEDIO PER RISPOSTA",
    },
    "en": {
        "pdf_title": "Focused token and cost charts",
        "pdf_subject": "14 x 60 benchmark: ranking, composition, drivers, and token rates",
        "p3_title": "How mean cost is formed",
        "p3_sub": "Consumed volume and effective unit cost jointly explain cost per response | each bubble is one model",
        "formula": "MEAN COST = MEAN TOKENS x EFFECTIVE COST PER 1M / 1,000,000",
        "x": "MEAN ANALYTICAL TOKENS PER RESPONSE",
        "y": "EFFECTIVE COST PER 1M ANALYTICAL TOKENS (USD)",
        "few_low": "FEWER TOKENS\nLOW UNIT COST",
        "few_high": "FEWER TOKENS\nHIGH UNIT COST",
        "many_low": "MORE TOKENS\nLOW UNIT COST",
        "many_high": "MORE TOKENS\nHIGH UNIT COST",
        "p3_note": "The effective rate includes the observed input/output mix, so it need not equal either published list price.",
        "p4_title": "Rates per million tokens",
        "p4_sub": "Unit prices used in the benchmark | direct comparison, independent of consumed volume",
        "input": "INPUT",
        "output": "OUTPUT",
        "axis": "USD PER 1 MILLION TOKENS",
        "p4_note": "Reasoning is billed as output where applicable. Gemma uses the campaign-configured zero rate.",
        "footer": "Common panel: 60 exercises, 14 models, 840 macro-averaged cells",
        "rank": "RANK",
        "model": "MODEL",
        "bubble_mean": "BUBBLE SIZE = MEAN COST PER RESPONSE",
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def effective_rate(row: dict[str, str]) -> float:
    tokens = float(row["analytical_total_tokens_total"])
    return float(row["cost_total_usd"]) / tokens * 1_000_000 if tokens else 0.0


def add_multiline(drawing: Drawing, x: float, top: float, value: str, color: Any, anchor: str) -> None:
    for index, line in enumerate(value.split("\n")):
        base.add_text(drawing, x, top + index * 9, line, 6.1, color, anchor=anchor, font="Helvetica-Bold")


def page_cost_explained(summary: list[dict[str, str]], lang: str) -> Drawing:
    t = TEXT[lang]
    rows = sorted(summary, key=lambda row: float(row["cost_mean_usd"]))
    drawing = Drawing(base.PAGE_W, base.PAGE_H)
    base.add_page_header(drawing, t["p3_title"], t["p3_sub"])

    base.add_rect(drawing, 44, 90, 760, 31, HexColor("#F3F7F9"), base.GRID, 0.7)
    base.add_text(drawing, 292, 110, t["formula"], 9.0, base.NAVY, anchor="middle", font="Helvetica-Bold")
    base.add_line(drawing, 548, 94, 548, 117, base.GRID, 0.9)
    base.add_circle(drawing, 575, 106, 4.2, base.GREEN, base.WHITE, 0.8)
    base.add_circle(drawing, 594, 106, 8.0, base.GREEN, base.WHITE, 0.8)
    base.add_text(drawing, 612, 109, t["bubble_mean"], 6.8, base.NAVY, font="Helvetica-Bold")

    x0, x1, top, bottom = 92, 600, 153, 502
    x_values = [float(row["analytical_total_tokens_mean"]) for row in rows]
    y_values = [effective_rate(row) for row in rows]
    x_max = math.ceil(max(x_values) / 5000) * 5000
    y_max = math.ceil(max(y_values) / 10) * 10
    x_mid = statistics.median(x_values)
    y_mid = statistics.median(y_values)
    sx = lambda value: x0 + (x1 - x0) * value / x_max
    sy = lambda value: bottom - (bottom - top) * value / y_max
    mid_x, mid_y = sx(x_mid), sy(y_mid)

    base.add_rect(drawing, x0, top, mid_x - x0, mid_y - top, HexColor("#FCF4EF"))
    base.add_rect(drawing, mid_x, top, x1 - mid_x, mid_y - top, HexColor("#F8ECE9"))
    base.add_rect(drawing, x0, mid_y, mid_x - x0, bottom - mid_y, HexColor("#EDF7F5"))
    base.add_rect(drawing, mid_x, mid_y, x1 - mid_x, bottom - mid_y, HexColor("#F2F7F6"))

    for tick in range(6):
        x = x0 + (x1 - x0) * tick / 5
        value = x_max * tick / 5
        base.add_line(drawing, x, top, x, bottom, base.GRID, 0.65)
        base.add_text(drawing, x, 520, f"{value/1000:.0f}k", 7.2, base.NAVY, anchor="middle")
        y = bottom - (bottom - top) * tick / 5
        value_y = y_max * tick / 5
        base.add_line(drawing, x0, y, x1, y, base.GRID, 0.65)
        base.add_text(drawing, x0 - 10, y + 3, f"${value_y:.0f}", 7.2, base.NAVY, anchor="end")
    base.add_line(drawing, mid_x, top, mid_x, bottom, base.MUTED, 1.0)
    base.add_line(drawing, x0, mid_y, x1, mid_y, base.MUTED, 1.0)
    base.add_line(drawing, x0, bottom, x1, bottom, base.NAVY, 1.2)
    base.add_line(drawing, x0, top, x0, bottom, base.NAVY, 1.2)

    add_multiline(drawing, x0 + 8, top + 14, t["few_high"], base.RED, "start")
    add_multiline(drawing, x1 - 8, top + 14, t["many_high"], base.RED, "end")
    add_multiline(drawing, x0 + 8, bottom - 28, t["few_low"], base.GREEN, "start")
    add_multiline(drawing, x1 - 8, bottom - 28, t["many_low"], base.GREEN, "end")

    max_cost = max(float(row["cost_mean_usd"]) for row in rows)
    for index, row in enumerate(rows, start=1):
        x, y = sx(float(row["analytical_total_tokens_mean"])), sy(effective_rate(row))
        radius = 4.2 + 6.5 * math.sqrt(float(row["cost_mean_usd"]) / max_cost if max_cost else 0)
        color = base.PROVIDER_COLORS[row["provider"]]
        base.add_circle(drawing, x, y, radius, color, base.WHITE, 1)
        base.add_text(drawing, x, y + 2.2, str(index), 5.2, base.WHITE, anchor="middle", font="Helvetica-Bold")

    base.add_text(drawing, (x0 + x1) / 2, 546, t["x"], 8.1, base.NAVY, anchor="middle")
    base.add_text(drawing, 44, (top + bottom) / 2, t["y"], 8.0, base.NAVY, anchor="middle", angle=90)

    list_x, list_top, list_height = 628, 155, 24.7
    base.add_text(drawing, list_x, 140, t["rank"], 7.0, base.MUTED)
    base.add_text(drawing, list_x + 30, 140, t["model"], 7.0, base.MUTED)
    for index, row in enumerate(rows, start=1):
        row_top = list_top + (index - 1) * list_height
        if index % 2 == 0:
            base.add_rect(drawing, list_x - 6, row_top - 12, 178, list_height, base.ROW_ALT)
        base.add_text(drawing, list_x, row_top, f"{index:02d}", 7.2, base.MUTED)
        base.add_rect(drawing, list_x + 28, row_top - 10, 3, 15, base.PROVIDER_COLORS[row["provider"]])
        base.add_text(drawing, list_x + 37, row_top, row["model"], 7.4, base.INK)
    base.add_footer(drawing, t["p3_note"], 3, 4, t["footer"])
    return drawing


def page_unit_rates(summary: list[dict[str, str]], lang: str) -> Drawing:
    t = TEXT[lang]
    rows = sorted(summary, key=lambda row: (float(row["output_rate_usd_per_million"]), float(row["input_rate_usd_per_million"])))
    drawing = Drawing(base.PAGE_W, base.PAGE_H)
    base.add_page_header(drawing, t["p4_title"], t["p4_sub"])

    base.add_rect(drawing, 44, 92, 11, 11, base.TOKEN_COLORS["input"])
    base.add_text(drawing, 61, 101, t["input"], 7.6, base.MUTED)
    base.add_rect(drawing, 116, 92, 11, 11, base.TOKEN_COLORS["reasoning"])
    base.add_text(drawing, 133, 101, t["output"], 7.6, base.MUTED)
    base.add_text(drawing, 718, 101, t["input"], 7.3, base.MUTED, anchor="end")
    base.add_text(drawing, 800, 101, t["output"], 7.3, base.MUTED, anchor="end")

    row_top, row_height = 116, 25.2
    base.add_alternating_rows(drawing, row_top, row_height, len(rows))
    plot_x0, plot_x1 = 275, 660
    axis_max = max(50.0, max(float(row["output_rate_usd_per_million"]) for row in rows))
    for tick in range(6):
        value = axis_max * tick / 5
        x = plot_x0 + (plot_x1 - plot_x0) * tick / 5
        base.add_line(drawing, x, row_top, x, row_top + row_height * len(rows), base.GRID, 0.7)
        base.add_text(drawing, x, 490, f"${value:.0f}", 7.3, base.NAVY, anchor="middle")
    for index, row in enumerate(rows, start=1):
        top = row_top + (index - 1) * row_height
        base.add_provider_label(drawing, index, row["model"], row["provider"], top, row_height)
        input_rate = float(row["input_rate_usd_per_million"])
        output_rate = float(row["output_rate_usd_per_million"])
        x_input = plot_x0 + (plot_x1 - plot_x0) * input_rate / axis_max
        x_output = plot_x0 + (plot_x1 - plot_x0) * output_rate / axis_max
        y = top + row_height * 0.55
        base.add_line(drawing, x_input, y, x_output, y, HexColor("#AEBBC7"), 1.4)
        base.add_circle(drawing, x_input, y - 3.2, 4.3, base.TOKEN_COLORS["input"], base.WHITE, 0.8)
        base.add_circle(drawing, x_output, y + 3.2, 4.3, base.TOKEN_COLORS["reasoning"], base.WHITE, 0.8)
        base.add_text(drawing, 718, y + 3, f"${input_rate:.3f}".rstrip("0").rstrip("."), 8.3, base.TOKEN_COLORS["input"], anchor="end")
        base.add_text(drawing, 800, y + 3, f"${output_rate:.3f}".rstrip("0").rstrip("."), 8.3, base.TOKEN_COLORS["reasoning"], anchor="end")
    base.add_line(drawing, plot_x0, 483, plot_x1, 483, base.NAVY, 1.3)
    base.add_text(drawing, (plot_x0 + plot_x1) / 2, 518, t["axis"], 8.2, base.NAVY, anchor="middle")
    base.add_footer(drawing, t["p4_note"], 4, 4, t["footer"])
    return drawing


def export_set(lang: str, drawings: list[Drawing]) -> dict[str, Any]:
    english = lang == "en"
    figure_dir = FIGURES_EN if english else FIGURES_IT
    rendered_dir = RENDERED_EN if english else RENDERED_IT
    pdf_name = "focused_token_cost_charts.pdf" if english else "grafici_token_costi_focus.pdf"
    names = (
        ["01_cost_ranking", "02_token_composition", "03_cost_explained", "04_rates_per_million"]
        if english
        else ["01_classifica_costi", "02_composizione_token", "03_costo_spiegato", "04_tariffe_per_milione"]
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
    pdf.setAuthor("anonymous")
    pdf.setCreator("anonymous")
    for drawing in drawings:
        renderPDF.draw(drawing, pdf, 0, 0)
        pdf.showPage()
    pdf.save()
    return {"pdf": pdf_path, "figures": [figure_dir / f"{name}.svg" for name in names], "rendered": rendered_dir}


def write_analysis(summary: list[dict[str, str]]) -> Path:
    path = OUTPUT_DIR / "LETTURA_PAGINA_3.md"
    rows = sorted(summary, key=lambda row: float(row["cost_mean_usd"]))
    path.write_text(
        """# Come leggere la pagina 3

La pagina 3 separa le due cause del costo medio per risposta:

- asse orizzontale: quanti token analitici usa mediamente il modello;
- asse verticale: costo effettivo per un milione di token analitici, calcolato come costo totale diviso token totali;
- dimensione della bolla: costo medio finale per risposta.

La relazione e esatta sul panel comune:

`costo medio = token medi x costo effettivo per 1M / 1.000.000`

Il costo effettivo non e una tariffa di listino: riassume il mix realmente osservato di input, output e reasoning. La pagina 4 mostra invece soltanto le tariffe input/output usate nel benchmark.

## Perche mantenere entrambe le pagine

- Pagina 3 risponde a: il modello costa di piu perche usa piu token o perche i suoi token sono piu cari?
- Pagina 4 risponde a: quali prezzi per milione di token sono stati applicati a ciascun modello?
""",
        encoding="utf-8",
    )
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", choices=("it", "en", "both"), default="both")
    args = parser.parse_args()
    summary = base.read_csv(base.SUMMARY_PATH)
    if len(summary) != 14:
        raise RuntimeError("Expected 14 models")
    outputs: dict[str, dict[str, Any]] = {}
    languages = ("it", "en") if args.lang == "both" else (args.lang,)
    for lang in languages:
        drawings = [
            base.page_cost_ranking(summary, lang, total_pages=4),
            base.page_token_composition(summary, lang, total_pages=4),
            page_cost_explained(summary, lang),
            page_unit_rates(summary, lang),
        ]
        outputs[lang] = export_set(lang, drawings)
    analysis_path = write_analysis(summary)
    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sources": {
            str(base.SUMMARY_PATH.relative_to(base.ANALYSIS_DIR)): sha256_file(base.SUMMARY_PATH),
            str(base.RAW_PATH.relative_to(base.ANALYSIS_DIR)): sha256_file(base.RAW_PATH),
            str((base.ANALYSIS_DIR / "tables" / "tariffe_token_costi.csv").relative_to(base.ANALYSIS_DIR)): sha256_file(base.ANALYSIS_DIR / "tables" / "tariffe_token_costi.csv"),
        },
        "counts": {"pages_per_pdf": 4, "models": 14, "common_items": 60, "model_item_cells": 840},
        "outputs": {},
    }
    for output in outputs.values():
        for item in [output["pdf"], *output["figures"]]:
            manifest["outputs"][str(item.relative_to(OUTPUT_DIR))] = sha256_file(item)
    manifest["outputs"][str(analysis_path.relative_to(OUTPUT_DIR))] = sha256_file(analysis_path)
    manifest_path = OUTPUT_DIR / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pdfs": [str(outputs[x]["pdf"]) for x in languages], "manifest": str(manifest_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
