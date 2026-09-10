# Aggregate analysis release

This directory contains sanitized, aggregate outputs from the dated UniAIBench
study. It contains no task statement, official solution, completed rubric,
model-answer text, individual judgment, or private identity map.

- `data/model_item_scores.csv`: one aggregate model--item score row per common
  evaluation cell, including T1--T8 summaries.
- `data/model_item_resources.csv`: aggregate token, time, and reconstructed-cost
  metadata for those cells.
- `data/model_catalog.json`: canonical model identity, specification, reasoning,
  and dated pricing metadata used by documentation, paper, and website exports.
- `tables/`: principal rankings, coverage, T1--T8 profiles, and resource tables.
- `figures/site/`: eight current English SVG figures corresponding to the
  evidence views published on the website. The overall ranking is also used by
  the repository README. Other final paper figures remain under
  `../paper/figures/`; intermediate and alternative chart outputs are rebuilt
  on demand and are not versioned.
- `scripts/`: executable generators for the paper and website chart families.
- `site_exports/`: ignored working output containing text-free TypeScript data
  modules for the separate website codebase; regenerate it with `make figures`.

See [`FIGURE_PROVENANCE.md`](FIGURE_PROVENANCE.md) for the exact mapping from
each output family to its program and public input files. Run `make figures`
from the repository root to rebuild the chart collections.

The principal matched panel comprises 14 model configurations and 60 common
items. Some cells summarize repeated runs; consult `n_responses` rather than
assuming one response per row. Provider pricing and model availability are
time-dependent, so the dates and source fields in the resource data and
canonical model catalog are part of the interpretation.

These files support aggregate-result inspection, not reconstruction of the
private source-to-judgment pipeline. See `../docs/reproducibility.md`.

## Website figure set

| Figure | Evidence view |
|---|---|
| [`01_01_overall_ranking.svg`](figures/site/01_01_overall_ranking.svg) | Mean accuracy with 95% confidence intervals |
| [`02_02_overall_t1_t8_profile.svg`](figures/site/02_02_overall_t1_t8_profile.svg) | T1--T8 correctness profile |
| [`05_01_cost_ranking.svg`](figures/site/05_01_cost_ranking.svg) | Mean estimated cost ranking |
| [`06_02_token_composition.svg`](figures/site/06_02_token_composition.svg) | Token composition by model |
| [`07_01_response_time_ranking.svg`](figures/site/07_01_response_time_ranking.svg) | Typical response-time ranking |
| [`08_02_model_exercise_heatmap.svg`](figures/site/08_02_model_exercise_heatmap.svg) | Exercise-normalized response-time heatmap |
| [`09_03_time_drivers.svg`](figures/site/09_03_time_drivers.svg) | Token volume and effective time intensity |
| [`10_04_response_time_accuracy_correlation.svg`](figures/site/10_04_response_time_accuracy_correlation.svg) | Response time versus accuracy |

These are static, auditable counterparts of interactive browser views. They
are not screenshots: `make figures` regenerates them from the public aggregate
tables through the same versioned chart programs.
