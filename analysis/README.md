# Aggregate analysis release

This directory contains sanitized, aggregate outputs from the dated UniAIBench
study. It contains no task statement, official solution, completed rubric,
model-answer text, individual judgment, or private identity map.

- `data/model_item_scores.csv`: one aggregate model--item score row per common
  evaluation cell, including T1--T8 summaries.
- `data/model_item_resources.csv`: aggregate token, time, and reconstructed-cost
  metadata for those cells.
- `tables/`: principal rankings, coverage, T1--T8 profiles, and resource tables.
- `figures/`: publication-ready visual summaries.
- `scripts/`: executable generators for the paper and website chart families.
- `site_exports/`: ignored working output containing text-free TypeScript data
  modules for the separate website codebase; regenerate it with `make figures`.

See [`FIGURE_PROVENANCE.md`](FIGURE_PROVENANCE.md) for the exact mapping from
each output family to its program and public input files. Run `make figures`
from the repository root to rebuild the chart collections.

The principal matched panel comprises 14 model configurations and 60 common
items. Some cells summarize repeated runs; consult `n_responses` rather than
assuming one response per row. Provider pricing and model availability are
time-dependent, so the dates and source fields in the resource data are part
of the interpretation.

These files support aggregate-result inspection, not reconstruction of the
private source-to-judgment pipeline. See `../docs/reproducibility.md`.
