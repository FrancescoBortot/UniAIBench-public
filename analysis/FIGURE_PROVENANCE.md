# Figure and website-chart provenance

Every chart program needed by the public paper and website presentation is
kept in this repository. The programs consume only the sanitized aggregate
panels under `analysis/data/` and the derived tables under `analysis/tables/`.
They do not require source exercises, official solutions, model answers,
individual judgments, completed rubrics, or identity maps.

## Rebuild commands

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
make figures
make paper
```

Generated working directories named `analysis/grafici_*` are ignored by Git.
The canonical supplementary PDFs are copied to `paper/figures/` by
`make figures`.

## Tracked-output policy

Only `analysis/figures/overall_ranking.png` is retained as a standalone chart,
because it is the English figure displayed in the repository README. Final
figures actually used by the manuscript are retained under `paper/figures/`.
Italian, superseded, intermediate, and unreferenced chart exports are generated
on demand but are not versioned in the publication repository.

The tracked `paper/figures/` directory is intentionally limited to two groups:

- the seven `.tex` figures directly included by `main_publication.tex`;
- four current English supplementary PDFs covering correctness, token/cost,
  response time, and model specifications.

Unused legacy diagram sources are excluded. The publication validator enforces
both tracked-output lists so that unrelated chart exports cannot be added
silently.

## Output-to-source map

| Published output or chart family | Source program | Public numerical inputs |
|---|---|---|
| Correctness rankings and T1--T8 profiles, including the English README figure at `analysis/figures/overall_ranking.png` | `analysis/scripts/build_selected_charts.py` | ranking and profile CSVs in `analysis/tables/` |
| Cost ranking, token composition, distributions, heatmap, and thinking contrast | `analysis/scripts/build_selected_token_cost_charts.py` | `model_item_resources.csv` and resource tables |
| Focused cost charts | `analysis/scripts/build_token_cost_focus_charts.py` | outputs of the selected token/cost generator |
| Response-time ranking, heatmap, drivers, and accuracy correlation | `analysis/scripts/build_response_time_focus_charts.py` and `build_speed_correctness_alternatives.py` | public resource panel and overall ranking table |
| Canonical ten-chart collection used by the paper and website | `analysis/scripts/build_main_chart_collection.py` | the chart families above |
| Model catalog documentation | `analysis/scripts/build_model_catalog_docs.py` | `analysis/data/model_catalog.json` |
| Model technical-specification appendix | `analysis/scripts/build_model_specifications_pdf.py` | `analysis/data/model_catalog.json` |
| Website chart-data modules | `analysis/scripts/build_website_benchmark_data.py` | both public model--item panels, derived tables, and `model_catalog.json` |
| Paper item-difficulty strip | `paper/scripts/build_item_difficulty_figure.py` | `analysis/data/model_item_scores.csv` |

The remaining paper diagrams are declarative TikZ programs stored directly as
`paper/figures/*.tex`; LaTeX compiles them without a separate Python generator.
They cover the benchmark map, rubric anatomy, performance overview, subject
contrast, token ablation, and resource frontiers.

## Boundary

Upstream extraction from private responses and judgments is deliberately not
published. This repository starts from sanitized model--item panels. It
therefore supports exact public analysis and figure reconstruction within that
boundary, not regeneration of model answers or blind judgments.
