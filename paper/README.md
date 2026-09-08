# UniAIBench paper

- `main_publication.tex`: current publication manuscript.
- `benchmark_publication.pdf`: compiled manuscript.
- `figures/`: publication figures and supporting assets.
- `scripts/`: paper-specific figure-generation utility.

Build the current manuscript with Tectonic:

```bash
make publication
```

The paper reports the dated 14-model by 60-item matched panel. Aggregate source
data are available under `../analysis/`; private run and judgment artifacts are
not distributed.

All supplementary chart programs are under `../analysis/scripts/`. Their
inputs and outputs are mapped in
[`../analysis/FIGURE_PROVENANCE.md`](../analysis/FIGURE_PROVENANCE.md). The
remaining `.tex` files under `figures/` are themselves declarative TikZ figure
sources.
