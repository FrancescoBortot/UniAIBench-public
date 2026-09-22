# Figure and website-chart provenance

Every chart program needed by the public paper and website presentation is
kept in this repository. The programs consume only the sanitized aggregate
panels under `uniaibench/analysis/data/` and the derived tables under
`uniaibench/analysis/tables/`.
They do not require source exercises, official solutions, model answers,
individual judgments, completed rubrics, or identity maps.

## Rebuild commands

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
make check-tables
make figures
make paper
```

Generated working directories named `uniaibench/analysis/grafici_*` and the
current model-specification PDF under `uniaibench/analysis/output/` are ignored
by Git. `make figures` does not modify the fixed paper snapshot.

## Tracked-output policy

Only the eight current English website views are retained as standalone SVGs
under `uniaibench/analysis/figures/site/`; the overall ranking is also displayed in the
repository README. Final figures actually used by the manuscript are retained
under `uniaibench/paper/figures/`. Italian, superseded, intermediate, article-specific,
and unreferenced chart exports are generated on demand but are not versioned in
the publication repository.

The tracked `uniaibench/paper/figures/` directory is intentionally limited to two groups:

- the seven `.tex` figures directly included by `main_publication.tex`;
- four fixed v1.0 English supplementary PDFs covering correctness, token/cost,
  response time, and model specifications.

Unused legacy diagram sources are excluded. The publication validator enforces
both tracked-output lists so that unrelated chart exports cannot be added
silently.

## Output-to-source map

| Published output or chart family | Source program | Public numerical inputs |
|---|---|---|
| All 11 released CSV tables | `uniaibench/analysis/scripts/build_public_tables.py` | the two sanitized model--item panels, `model_catalog.json`, `benchmark_pricing_manifest.json`, and `config/public_analysis.json` |
| Correctness rankings and T1--T8 profiles, including the English README figure at `uniaibench/analysis/figures/site/01_01_overall_ranking.svg` | `uniaibench/analysis/scripts/build_selected_charts.py` | ranking and profile CSVs in `uniaibench/analysis/tables/` |
| Cost ranking, token composition, distributions, heatmap, and thinking contrast | `uniaibench/analysis/scripts/build_selected_token_cost_charts.py` | `model_item_resources.csv` and resource tables |
| Focused cost charts | `uniaibench/analysis/scripts/build_token_cost_focus_charts.py` | outputs of the selected token/cost generator |
| Response-time ranking, heatmap, drivers, and accuracy correlation | `uniaibench/analysis/scripts/build_response_time_focus_charts.py` and `build_speed_correctness_alternatives.py` | public resource panel and overall ranking table |
| Canonical ten-chart collection, including the eight tracked website SVGs | `uniaibench/analysis/scripts/build_main_chart_collection.py` | the chart families above |
| Model catalog documentation | `uniaibench/analysis/scripts/build_model_catalog_docs.py` | `uniaibench/analysis/data/model_catalog.json` |
| Current model technical-specification supplement | `uniaibench/analysis/scripts/build_model_specifications_pdf.py` | `uniaibench/analysis/data/model_catalog.json` |
| Website chart-data modules | `uniaibench/analysis/scripts/build_website_benchmark_data.py` | both public model--item panels, derived tables, and `model_catalog.json` |
| Paper item-difficulty strip | `uniaibench/paper/scripts/build_item_difficulty_figure.py` | fixed `uniaibench/paper/data/model_item_scores_14x60.csv` snapshot |

The remaining paper diagrams are declarative TikZ programs stored directly as
`uniaibench/paper/figures/*.tex`; LaTeX compiles them without a separate Python generator.
They cover the benchmark map, rubric anatomy, performance overview, subject
contrast, token ablation, and resource frontiers.

## Boundary

Upstream extraction from private responses and judgments is deliberately not
published. This repository starts from sanitized model--item panels. It
therefore supports exact public analysis and figure reconstruction within that
boundary, not regeneration of model answers or blind judgments.

The sanitized score panel stores values at eight-decimal precision. Released
rankings are consequently defined as the deterministic aggregation of that
public precision, rather than an inaccessible higher-precision private
intermediate. The prompt-hash consistency flag is retained as an explicitly
labelled upstream attestation because prompt hashes themselves are excluded.
