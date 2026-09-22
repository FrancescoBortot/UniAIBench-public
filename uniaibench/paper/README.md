# UniAIBench paper

- `main_publication.tex`: current publication manuscript.
- `benchmark_publication.pdf`: compiled manuscript.
- `figures/`: publication figures and supporting assets.
- `scripts/`: paper-specific figure-generation utility.

From the repository root, build the current manuscript with Tectonic:

```bash
make paper
```

For a manuscript-only build from the repository root, use
`make -C uniaibench/paper publication`.

The paper reports the fixed, dated 14-configuration by 60-item matched panel.
Its archived score panel is available under `data/`; the current 17-configuration
aggregate release is available under `../analysis/`. Private run and judgment
artifacts are not distributed.

All supplementary chart programs are under `../analysis/scripts/`. Their
inputs and outputs are mapped in
[`../analysis/FIGURE_PROVENANCE.md`](../analysis/FIGURE_PROVENANCE.md). The
remaining `.tex` files under `figures/` are themselves declarative TikZ figure
sources.
