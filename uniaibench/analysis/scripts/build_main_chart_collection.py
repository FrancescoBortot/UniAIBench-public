#!/usr/bin/env python3
"""Build the canonical 14x60 chart collection used by the paper and public site.

The script does not modify ``uniaibench/paper/`` or any website source. It selects
the updated pages that correspond to the chart concepts exposed by the paper and
the separately maintained public site, places the public SVG exports under
``uniaibench/analysis/figures/site/``,
copies their standalone SVG sources into one folder, and merges the vector PDF
pages into a single canonical document.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab import rl_config
from reportlab.pdfgen import canvas

rl_config.invariant = 1


ANALYSIS_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ANALYSIS_DIR / "grafici_principali_14x60"
FIGURE_DIR = OUTPUT_DIR / "figures"
PDF_DIR = OUTPUT_DIR / "output" / "pdf"
OUTPUT_PDF = PDF_DIR / "grafici_principali_benchmark_14x60.pdf"
PUBLIC_SITE_FIGURE_DIR = ANALYSIS_DIR / "figures" / "site"


SELECTIONS = [
    {
        "number": 1,
        "title": "Overall ranking",
        "section": "Correctness",
        "pdf": "grafici_selezionati/output/pdf/selected_correctness_charts.pdf",
        "page": 1,
        "svg": "grafici_selezionati/figures_en/01_overall_ranking.svg",
        "used_by": ["benchmark_publication", "website"],
    },
    {
        "number": 2,
        "title": "Overall T1-T8 profile",
        "section": "Correctness",
        "pdf": "grafici_selezionati/output/pdf/selected_correctness_charts.pdf",
        "page": 2,
        "svg": "grafici_selezionati/figures_en/02_overall_t1_t8_profile.svg",
        "used_by": ["benchmark_publication", "website"],
    },
    {
        "number": 3,
        "title": "Ranking - Mathematical Analysis III",
        "section": "Correctness",
        "pdf": "grafici_selezionati/output/pdf/selected_correctness_charts.pdf",
        "page": 3,
        "svg": "grafici_selezionati/figures_en/03_analysis_3_ranking.svg",
        "used_by": ["benchmark_publication"],
    },
    {
        "number": 4,
        "title": "Ranking - General Physics II",
        "section": "Correctness",
        "pdf": "grafici_selezionati/output/pdf/selected_correctness_charts.pdf",
        "page": 5,
        "svg": "grafici_selezionati/figures_en/05_physics_2_ranking.svg",
        "used_by": ["benchmark_publication"],
    },
    {
        "number": 5,
        "title": "Mean cost ranking",
        "section": "Cost and tokens",
        "pdf": "grafici_token_costi_focus/output/pdf/focused_token_cost_charts.pdf",
        "page": 1,
        "svg": "grafici_token_costi_focus/figures_en/01_cost_ranking.svg",
        "used_by": ["benchmark_publication", "website"],
    },
    {
        "number": 6,
        "title": "Overall token composition",
        "section": "Cost and tokens",
        "pdf": "grafici_token_costi_focus/output/pdf/focused_token_cost_charts.pdf",
        "page": 2,
        "svg": "grafici_token_costi_focus/figures_en/02_token_composition.svg",
        "used_by": ["benchmark_publication", "website"],
    },
    {
        "number": 7,
        "title": "Typical response-time ranking",
        "section": "Response time",
        "pdf": "grafici_tempo_risposta_focus/output/pdf/focused_response_time_charts.pdf",
        "page": 1,
        "svg": "grafici_tempo_risposta_focus/figures_en/01_response_time_ranking.svg",
        "used_by": ["benchmark_publication", "website"],
    },
    {
        "number": 8,
        "title": "Where response times differ",
        "section": "Response time",
        "pdf": "grafici_tempo_risposta_focus/output/pdf/focused_response_time_charts.pdf",
        "page": 2,
        "svg": "grafici_tempo_risposta_focus/figures_en/02_model_exercise_heatmap.svg",
        "used_by": ["website"],
    },
    {
        "number": 9,
        "title": "How mean response time is formed",
        "section": "Response time",
        "pdf": "grafici_tempo_risposta_focus/output/pdf/focused_response_time_charts.pdf",
        "page": 3,
        "svg": "grafici_tempo_risposta_focus/figures_en/03_time_drivers.svg",
        "used_by": ["website"],
    },
    {
        "number": 10,
        "title": "Response time vs accuracy",
        "section": "Response time",
        "pdf": "grafici_tempo_risposta_focus/output/pdf/focused_response_time_charts.pdf",
        "page": 4,
        "svg": "grafici_tempo_risposta_focus/figures_en/04_response_time_accuracy_correlation.svg",
        "used_by": ["benchmark_publication", "website"],
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def replace_page_counter(page, number: int, total: int) -> None:
    """Cover the source-collection counter and add the canonical one."""
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    buffer = io.BytesIO()
    overlay = canvas.Canvas(buffer, pagesize=(width, height))
    overlay.setFillColorRGB(1, 1, 1)
    overlay.rect(width - 58, 0, 58, 24, fill=1, stroke=0)
    overlay.setFillColorRGB(0.36, 0.41, 0.45)
    overlay.setFont("Helvetica", 7)
    overlay.drawRightString(width - 16, 10, f"{number}/{total}")
    overlay.save()
    buffer.seek(0)
    page.merge_page(PdfReader(buffer).pages[0])


def main() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_SITE_FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    writer = PdfWriter()
    current_section = None
    section_parent = None
    manifest_pages = []

    for selection in SELECTIONS:
        source_pdf = ANALYSIS_DIR / selection["pdf"]
        source_svg = ANALYSIS_DIR / selection["svg"]
        if not source_pdf.is_file() or not source_svg.is_file():
            raise FileNotFoundError(f"Missing source for {selection['title']}")

        page_index = selection["page"] - 1
        reader = PdfReader(str(source_pdf))
        if page_index >= len(reader.pages):
            raise IndexError(f"Page {selection['page']} absent from {source_pdf}")
        page = reader.pages[page_index]
        replace_page_counter(page, selection["number"], len(SELECTIONS))
        writer.add_page(page)

        section = selection["section"]
        if section != current_section:
            section_parent = writer.add_outline_item(section, len(writer.pages) - 1)
            current_section = section
        writer.add_outline_item(selection["title"], len(writer.pages) - 1, parent=section_parent)

        slug = source_svg.stem
        target_svg = FIGURE_DIR / f"{selection['number']:02d}_{slug}.svg"
        shutil.copy2(source_svg, target_svg)
        public_svg = None
        if "website" in selection["used_by"]:
            public_svg = PUBLIC_SITE_FIGURE_DIR / target_svg.name
            shutil.copy2(source_svg, public_svg)
        manifest_pages.append(
            {
                **selection,
                "source_pdf": str(source_pdf.relative_to(ANALYSIS_DIR)),
                "source_svg": str(source_svg.relative_to(ANALYSIS_DIR)),
                "copied_svg": str(target_svg.relative_to(OUTPUT_DIR)),
                "public_site_svg": (
                    str(public_svg.relative_to(ANALYSIS_DIR)) if public_svg else None
                ),
                "source_pdf_sha256": sha256(source_pdf),
                "copied_svg_sha256": sha256(target_svg),
            }
        )

    writer.add_metadata(
        {
            "/Title": "UniAIBench - Main benchmark charts (14 x 60)",
            "/Subject": "Correctness, cost, tokens, and response time",
            "/Author": "UniAIBench",
        }
    )
    with OUTPUT_PDF.open("wb") as stream:
        writer.write(stream)

    manifest = {
        "collection": "main_benchmark_charts_14x60",
        "models": 14,
        "common_exercises": 60,
        "analysis_3_exercises": 33,
        "physics_2_exercises": 27,
        "pages": manifest_pages,
        "output_pdf": str(OUTPUT_PDF.relative_to(OUTPUT_DIR)),
        "output_pdf_sha256": sha256(OUTPUT_PDF),
        "notes": [
            "Union of the chart concepts currently used by benchmark_publication and website.",
            "The publication paper and deployed website consume these chart concepts.",
            "PDF pages remain vector-based; standalone SVGs are copied alongside the PDF.",
        ],
    }
    (OUTPUT_DIR / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"pdf": str(OUTPUT_PDF), "pages": len(writer.pages), "figures": len(SELECTIONS)}))


if __name__ == "__main__":
    main()
