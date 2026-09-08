#!/usr/bin/env python3
"""Build the six selected correctness charts as vector figures and a six-page PDF."""

from __future__ import annotations

import csv
import math
import os
import subprocess
from pathlib import Path

from reportlab import rl_config
from reportlab.graphics import renderPDF, renderSVG
from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
from reportlab.lib.colors import HexColor, Color, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

rl_config.invariant = 1


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "tables"
OUT_ROOT = ROOT / "grafici_selezionati"
FIGURES_IT = OUT_ROOT / "figures"
FIGURES_EN = OUT_ROOT / "figures_en"
PDF_DIR = OUT_ROOT / "output" / "pdf"
RASTER_IT = OUT_ROOT / "output" / "rendered"
RASTER_EN = OUT_ROOT / "output" / "rendered_en"

WIDTH = 1100
HEIGHT = 760

INK = HexColor("#172431")
NAVY = HexColor("#17324D")
MUTED = HexColor("#607080")
GRID = HexColor("#D7E0E7")
PALE = HexColor("#F5F7F9")
ROW_ALT = HexColor("#FAFBFC")

PROVIDER_COLORS = {
    "openai": HexColor("#087F72"),
    "anthropic": HexColor("#A65300"),
    "google": HexColor("#2363C7"),
    "deepseek": HexColor("#5B4BCE"),
    "xai": HexColor("#202124"),
}

SCOPES = [
    {
        "slug": "overall",
        "ranking": "classifica_principale_complessiva.csv",
        "profile": "profilo_t1_t8_complessiva.csv",
        "ranking_title": {"it": "Classifica complessiva", "en": "Overall ranking"},
        "profile_title": {"it": "Profilo complessivo T1-T8", "en": "Overall T1-T8 profile"},
    },
    {
        "slug": "analysis_3",
        "ranking": "classifica_principale_analisi_3.csv",
        "profile": "profilo_t1_t8_analisi_3.csv",
        "ranking_title": {"it": "Classifica - Analisi Matematica III", "en": "Ranking - Mathematical Analysis III"},
        "profile_title": {"it": "Profilo T1-T8 - Analisi Matematica III", "en": "T1-T8 profile - Mathematical Analysis III"},
    },
    {
        "slug": "physics_2",
        "ranking": "classifica_principale_fisica_2.csv",
        "profile": "profilo_t1_t8_fisica_2.csv",
        "ranking_title": {"it": "Classifica - Fisica Generale II", "en": "Ranking - General Physics II"},
        "profile_title": {"it": "Profilo T1-T8 - Fisica Generale II", "en": "T1-T8 profile - General Physics II"},
    },
]

TEXT = {
    "it": {
        "mean_sub": "Accuratezza media su {n} esercizi comuni | ordine: dal migliore al peggiore",
        "how": "COME LEGGERE",
        "how_desc": "Punto = accuratezza media; linea con estremi = intervallo di confidenza 95%",
        "rank": "POS.", "model": "MODELLO", "mean": "MEDIA", "ci": "IC 95%",
        "axis": "ACCURATEZZA MEDIA (%) - PIU A DESTRA = PIU RISPOSTE CORRETTE",
        "axis_note": "Asse focalizzato: {lo}-100% (non parte da zero). Un intervallo piu corto indica una stima piu precisa.",
        "profile_sub": "Percentuale media dei punti assegnati per criterio su {n} esercizi comuni",
        "criteria": "CRITERI DI VALUTAZIONE",
        "points": "PUNTI OTTENUTI (%)",
        "heat": "Rosso = meno punti | Verde = piu punti",
        "heat_na": "Rosso = meno punti | Verde = piu punti | T8: N/D",
        "pdf_title": "Grafici selezionati - correttezza",
        "pdf_subject": "Classifiche del benchmark e profili T1-T8",
    },
    "en": {
        "mean_sub": "Mean accuracy across {n} common exercises | ranked top to bottom: best -> worst",
        "how": "HOW TO READ",
        "how_desc": "Dot = mean accuracy; horizontal line with end caps = 95% confidence interval",
        "rank": "RANK", "model": "MODEL", "mean": "MEAN", "ci": "95% CI",
        "axis": "MEAN ACCURACY (%) - FARTHER RIGHT = MORE CORRECT ANSWERS",
        "axis_note": "Focused axis: {lo}-100% (does not start at zero). A shorter interval indicates a more precise estimate.",
        "profile_sub": "Mean percentage of points awarded by criterion across {n} common exercises",
        "criteria": "EVALUATION CRITERIA",
        "points": "POINTS AWARDED (%)",
        "heat": "Red = fewer points | Green = more points",
        "heat_na": "Red = fewer points | Green = more points | T8: N/A",
        "pdf_title": "Selected correctness charts",
        "pdf_subject": "Benchmark rankings and T1-T8 profiles",
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def fnum(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    return float(value)


def fmt(value: float, decimals: int = 2) -> str:
    return f"{value:.{decimals}f}"


def add_text(
    drawing: Drawing,
    x: float,
    y: float,
    value: str,
    size: float,
    color=INK,
    font: str = "Helvetica",
    anchor: str = "start",
) -> None:
    drawing.add(
        String(
            x,
            y,
            value,
            fontName=font,
            fontSize=size,
            fillColor=color,
            textAnchor=anchor,
        )
    )


def provider_color(provider: str):
    return PROVIDER_COLORS.get(provider.lower(), MUTED)


def forest_chart(rows: list[dict[str, str]], title: str, lang: str) -> Drawing:
    t = TEXT[lang]
    drawing = Drawing(WIDTH, HEIGHT)
    drawing.add(Rect(0, 0, WIDTH, HEIGHT, fillColor=white, strokeColor=None))

    n_items = int(rows[0]["n_items"])
    min_low = min(float(row["accuracy_ci95_low"]) for row in rows)
    axis_min = max(0, math.floor((min_low - 2.0) / 5.0) * 5.0)
    axis_max = 100.0

    plot_left = 365
    plot_right = 855
    mean_x = 945
    ci_x = 1070
    first_y = 578
    row_gap = 33.2
    axis_y = 105

    add_text(drawing, 42, 710, title, 29, NAVY, "Helvetica-Bold")
    add_text(
        drawing,
        42,
        672,
        t["mean_sub"].format(n=n_items),
        15,
        MUTED,
    )

    add_text(drawing, 42, 642, t["how"], 11.5, NAVY, "Helvetica-Bold")
    drawing.add(Line(170, 646, 288, 646, strokeColor=HexColor("#40596B"), strokeWidth=4.2))
    drawing.add(Line(170, 638, 170, 654, strokeColor=HexColor("#40596B"), strokeWidth=2.8))
    drawing.add(Line(288, 638, 288, 654, strokeColor=HexColor("#40596B"), strokeWidth=2.8))
    drawing.add(Circle(231, 646, 8, fillColor=HexColor("#087F72"), strokeColor=INK, strokeWidth=0.8))
    add_text(
        drawing,
        307,
        641,
        t["how_desc"],
        13,
        INK,
        "Helvetica-Bold",
    )

    add_text(drawing, 42, 610, t["rank"], 12, MUTED, "Helvetica-Bold")
    add_text(drawing, 88, 610, t["model"], 12, MUTED, "Helvetica-Bold")
    add_text(drawing, mean_x, 610, t["mean"], 12, MUTED, "Helvetica-Bold", "end")
    add_text(drawing, ci_x, 610, t["ci"], 12, MUTED, "Helvetica-Bold", "end")
    drawing.add(Line(42, 600, 1070, 600, strokeColor=GRID, strokeWidth=1.2))

    def scale_x(value: float) -> float:
        return plot_left + (value - axis_min) / (axis_max - axis_min) * (plot_right - plot_left)

    tick_step = 10
    first_tick = int(math.ceil(axis_min / tick_step) * tick_step)
    ticks = sorted({float(axis_min), *[float(t) for t in range(first_tick, 101, tick_step)], 100.0})
    for tick in ticks:
        x = scale_x(tick)
        is_endpoint = tick in (float(axis_min), 100.0)
        drawing.add(
            Line(
                x,
                axis_y,
                x,
                594,
                strokeColor=HexColor("#B7C4CE") if is_endpoint else GRID,
                strokeWidth=1.35 if is_endpoint else 0.9,
            )
        )
        drawing.add(Line(x, axis_y - 8, x, axis_y + 2, strokeColor=NAVY, strokeWidth=2))
        tick_label = f"{int(tick)}%"
        anchor = "start" if tick == float(axis_min) else "end" if tick == 100.0 else "middle"
        add_text(drawing, x, 78, tick_label, 14, NAVY, "Helvetica-Bold", anchor)

    drawing.add(Line(plot_left, axis_y, plot_right, axis_y, strokeColor=NAVY, strokeWidth=2.2))

    for index, row in enumerate(rows):
        y = first_y - index * row_gap
        if index % 2:
            drawing.add(Rect(36, y - 15, 1040, 31, fillColor=ROW_ALT, strokeColor=None))

        rank = int(row["rank"])
        rank_text = f"{rank:02d}"
        add_text(drawing, 42, y - 5, rank_text, 13, MUTED, "Helvetica-Bold")
        accent = provider_color(row["provider"])
        drawing.add(Rect(73, y - 10, 4, 21, fillColor=accent, strokeColor=None))
        add_text(drawing, 88, y - 2, row["model"], 14, INK, "Helvetica-Bold")
        add_text(drawing, 88, y - 14, row["provider"].upper(), 8.5, MUTED)

        low = float(row["accuracy_ci95_low"])
        mean = float(row["accuracy_mean"])
        high = float(row["accuracy_ci95_high"])
        x_low = scale_x(low)
        x_mean = scale_x(mean)
        x_high = scale_x(high)

        drawing.add(Line(plot_left, y, plot_right, y, strokeColor=PALE, strokeWidth=5))
        drawing.add(Line(x_low, y, x_high, y, strokeColor=HexColor("#40596B"), strokeWidth=4.2))
        drawing.add(Line(x_low, y - 8, x_low, y + 8, strokeColor=HexColor("#40596B"), strokeWidth=2.8))
        drawing.add(Line(x_high, y - 8, x_high, y + 8, strokeColor=HexColor("#40596B"), strokeWidth=2.8))
        drawing.add(Circle(x_mean, y, 9, fillColor=white, strokeColor=white, strokeWidth=4))
        drawing.add(Circle(x_mean, y, 7, fillColor=accent, strokeColor=INK, strokeWidth=0.9))

        add_text(drawing, mean_x, y - 5, fmt(mean), 14, INK, "Helvetica-Bold", "end")
        add_text(
            drawing,
            ci_x,
            y - 5,
            f"[{fmt(low)}, {fmt(high)}]",
            11.5,
            MUTED,
            "Helvetica",
            "end",
        )

    add_text(
        drawing,
        (plot_left + plot_right) / 2,
        47,
        t["axis"],
        12.5,
        NAVY,
        "Helvetica-Bold",
        "middle",
    )
    add_text(
        drawing,
        42,
        17,
        t["axis_note"].format(lo=int(axis_min)),
        10.5,
        MUTED,
    )
    return drawing


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))


HEAT_STOPS = [
    (0.0, "#9F2F35"),
    (50.0, "#D87355"),
    (70.0, "#F2C29F"),
    (85.0, "#E8EFE9"),
    (95.0, "#78B8AA"),
    (100.0, "#087F72"),
]


def heat_color(value: float) -> Color:
    clamped = min(100.0, max(0.0, value))
    for (lo_v, lo_hex), (hi_v, hi_hex) in zip(HEAT_STOPS, HEAT_STOPS[1:]):
        if lo_v <= clamped <= hi_v:
            ratio = (clamped - lo_v) / (hi_v - lo_v)
            lo = _hex_to_rgb(lo_hex)
            hi = _hex_to_rgb(hi_hex)
            rgb = tuple(lo[i] + (hi[i] - lo[i]) * ratio for i in range(3))
            return Color(*rgb)
    return HexColor(HEAT_STOPS[-1][1])


def text_color_for(fill: Color) -> Color:
    luminance = 0.2126 * fill.red + 0.7152 * fill.green + 0.0722 * fill.blue
    return white if luminance < 0.52 else INK


def profile_chart(
    profile_rows: list[dict[str, str]],
    ranking_rows: list[dict[str, str]],
    title: str,
    lang: str,
) -> Drawing:
    t = TEXT[lang]
    drawing = Drawing(WIDTH, HEIGHT)
    drawing.add(Rect(0, 0, WIDTH, HEIGHT, fillColor=white, strokeColor=None))

    providers = {row["model"]: row["provider"] for row in ranking_rows}
    n_items = int(ranking_rows[0]["n_items"])
    table_left = 350
    cell_w = 87
    cell_h = 33
    first_y = 585

    add_text(drawing, 42, 710, title, 29, NAVY, "Helvetica-Bold")
    add_text(
        drawing,
        42,
        672,
        t["profile_sub"].format(n=n_items),
        15,
        MUTED,
    )
    add_text(drawing, table_left + 4 * cell_w, 650, t["criteria"], 11.5, MUTED, "Helvetica-Bold", "middle")
    add_text(drawing, 42, 625, t["rank"], 12, MUTED, "Helvetica-Bold")
    add_text(drawing, 88, 625, t["model"], 12, MUTED, "Helvetica-Bold")
    for col in range(8):
        x = table_left + col * cell_w
        add_text(drawing, x + cell_w / 2, 625, f"T{col + 1}", 17, NAVY, "Helvetica-Bold", "middle")

    for index, row in enumerate(profile_rows):
        y = first_y - index * cell_h
        if index % 2:
            drawing.add(Rect(36, y - 13, 306, 31, fillColor=ROW_ALT, strokeColor=None))

        rank = int(row["rank"])
        add_text(drawing, 42, y - 4, f"{rank:02d}", 12.5, MUTED, "Helvetica-Bold")
        accent = provider_color(providers[row["model"]])
        drawing.add(Rect(73, y - 11, 4, 23, fillColor=accent, strokeColor=None))
        add_text(drawing, 88, y - 4, row["model"], 14.5, INK, "Helvetica-Bold")

        for col in range(8):
            key = f"dimension_T{col + 1}"
            value = fnum(row[key])
            x = table_left + col * cell_w
            if value is None:
                fill = HexColor("#E9EDF0")
                label = "N/A"
                label_color = MUTED
            else:
                fill = heat_color(value)
                label = fmt(value, 1)
                label_color = text_color_for(fill)
            drawing.add(
                Rect(
                    x + 1,
                    y - 14,
                    cell_w - 2,
                    cell_h - 2,
                    fillColor=fill,
                    strokeColor=white,
                    strokeWidth=1,
                )
            )
            add_text(
                drawing,
                x + cell_w / 2,
                y - 5,
                label,
                13.5,
                label_color,
                "Helvetica-Bold" if value is not None and value >= 95 else "Helvetica",
                "middle",
            )

    legend_x = 350
    legend_y = 63
    legend_w = 400
    segments = 100
    for index in range(segments):
        value = index + 0.5
        drawing.add(
            Rect(
                legend_x + index * legend_w / segments,
                legend_y,
                legend_w / segments + 0.25,
                18,
                fillColor=heat_color(value),
                strokeColor=None,
            )
        )
    add_text(drawing, legend_x, 91, t["points"], 12.5, NAVY, "Helvetica-Bold")
    for tick in (0, 50, 70, 85, 100):
        x = legend_x + tick / 100 * legend_w
        drawing.add(Line(x, legend_y - 4, x, legend_y + 18, strokeColor=white, strokeWidth=1.1))
        anchor = "start" if tick == 0 else "end" if tick == 100 else "middle"
        add_text(drawing, x, 42, f"{tick}%", 11.5, NAVY, "Helvetica-Bold", anchor)

    if all(fnum(row["dimension_T8"]) is None for row in profile_rows):
        add_text(drawing, 790, 69, t["heat_na"], 12, NAVY, "Helvetica-Bold")
    else:
        add_text(drawing, 790, 69, t["heat"], 12, NAVY, "Helvetica-Bold")

    return drawing


def write_drawing(drawing: Drawing, stem: Path) -> None:
    renderSVG.drawToFile(drawing, str(stem.with_suffix(".svg")))
    temp_pdf = stem.with_suffix(".pdf")
    renderPDF.drawToFile(drawing, str(temp_pdf))
    cache_dir = OUT_ROOT / ".render_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    render_env = os.environ.copy()
    render_env["XDG_CACHE_HOME"] = str(cache_dir)
    subprocess.run(
        [
            "pdftoppm",
            "-png",
            "-r",
            "160",
            "-singlefile",
            str(temp_pdf),
            str(stem),
        ],
        check=True,
        env=render_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    temp_pdf.unlink()


def write_pdf(charts: list[tuple[str, Drawing]], output: Path, lang: str) -> None:
    page_w, page_h = landscape(A4)
    pdf = canvas.Canvas(str(output), pagesize=(page_w, page_h))
    pdf.setTitle(TEXT[lang]["pdf_title"])
    pdf.setSubject(TEXT[lang]["pdf_subject"])
    margin_x = 16
    margin_y = 14
    for _name, drawing in charts:
        scale = min((page_w - 2 * margin_x) / WIDTH, (page_h - 2 * margin_y) / HEIGHT)
        x = (page_w - WIDTH * scale) / 2
        y = (page_h - HEIGHT * scale) / 2
        pdf.saveState()
        pdf.translate(x, y)
        pdf.scale(scale, scale)
        renderPDF.draw(drawing, pdf, 0, 0)
        pdf.restoreState()
        pdf.showPage()
    pdf.save()


def main() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    for lang in ("it", "en"):
        figures = FIGURES_EN if lang == "en" else FIGURES_IT
        raster_dir = RASTER_EN if lang == "en" else RASTER_IT
        figures.mkdir(parents=True, exist_ok=True)
        raster_dir.mkdir(parents=True, exist_ok=True)
        charts: list[tuple[str, Drawing]] = []
        for scope_index, scope in enumerate(SCOPES):
            ranking_rows = read_csv(TABLES / scope["ranking"])
            profile_rows = read_csv(TABLES / scope["profile"])
            ranking = forest_chart(ranking_rows, scope["ranking_title"][lang], lang)
            ranking_name = (
                f"{2 * scope_index + 1:02d}_{scope['slug']}_ranking"
                if lang == "en"
                else ["01_classifica_complessiva", "03_classifica_analisi_3", "05_classifica_fisica_2"][scope_index]
            )
            write_drawing(ranking, figures / ranking_name)
            charts.append((ranking_name, ranking))
            profile = profile_chart(profile_rows, ranking_rows, scope["profile_title"][lang], lang)
            profile_name = (
                f"{2 * scope_index + 2:02d}_{scope['slug']}_t1_t8_profile"
                if lang == "en"
                else ["02_profilo_t1_t8_complessiva", "04_profilo_t1_t8_analisi_3", "06_profilo_t1_t8_fisica_2"][scope_index]
            )
            write_drawing(profile, figures / profile_name)
            charts.append((profile_name, profile))

        pdf_name = "selected_correctness_charts.pdf" if lang == "en" else "grafici_correttezza_selezionati.pdf"
        output_pdf = PDF_DIR / pdf_name
        write_pdf(charts, output_pdf, lang)
        cache_dir = OUT_ROOT / ".render_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        render_env = os.environ.copy()
        render_env["XDG_CACHE_HOME"] = str(cache_dir)
        subprocess.run(
            ["pdftoppm", "-png", "-r", "140", str(output_pdf), str(raster_dir / ("page" if lang == "en" else "pagina"))],
            check=True,
            env=render_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"Created {len(charts)} {lang} charts in {figures}")
        print(f"PDF: {output_pdf}")


if __name__ == "__main__":
    main()
