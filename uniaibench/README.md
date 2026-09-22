# UniAIBench current study release

This directory contains the public aggregate evidence for **UniAIBench v1.1**,
the current study release described by the repository. It is intentionally separate from
the reusable [`benchmark-toolkit/`](../benchmark-toolkit/) so that readers can
distinguish dated research choices from general-purpose machinery.

## Study scope

UniAIBench evaluates complete, open-ended solutions to 60 advanced
university-level items: 33 from Mathematical Analysis III and 27 from General
Physics II. Seventeen model--mode configurations were compared on the same item
panel under closed-resource, no-tool conditions. The published aggregate
evidence represents 1,020 matched model--item cells and 1,104 retained responses.

The current aggregate snapshot is dated **16 September 2026**. The paper remains
the fixed 14-configuration snapshot dated **14 August 2026**. Model identifiers,
reasoning modes, prices, results, and operational measurements must be
interpreted as properties of that dated campaign rather than permanent product
properties.

## What this directory contains

| Path | Purpose |
|---|---|
| [`STUDY_MANIFEST.json`](STUDY_MANIFEST.json) | Machine-readable identity, counts, dates, and public/private boundary |
| [`METHOD_IMPLEMENTATION.md`](METHOD_IMPLEMENTATION.md) | Mapping from the generic toolkit workflow to this study |
| [`DATA_PROVENANCE.md`](DATA_PROVENANCE.md) | Origin and redistribution policy for source material |
| [`profile/evaluated-models.md`](profile/evaluated-models.md) | The 17 configurations, technical metadata, and dated prices |
| [`analysis/data/benchmark_pricing_manifest.json`](analysis/data/benchmark_pricing_manifest.json) | Frozen benchmark rates and public/private provenance records |
| [`analysis/data/`](analysis/data/) | Sanitized model--item score and resource panels |
| [`analysis/tables/`](analysis/tables/) | Derived rankings, coverage, T1--T8 profiles, token and cost summaries |
| [`analysis/figures/site/`](analysis/figures/site/) | Eight selected English figures used as public evidence views |
| [`analysis/scripts/`](analysis/scripts/) | Programs used to regenerate paper and website chart families |
| [`paper/`](paper/) | Fixed v1.0 manuscript snapshot, canonical figures, and compiled paper |

## What is authoritative

The two CSV panels under `analysis/data/` are the canonical public numerical
inputs for correctness and resource analysis. `model_catalog.json` is the
canonical public record of the evaluated configurations, and
`benchmark_pricing_manifest.json` is the canonical frozen-rate provenance
record. Tables, figures, model documentation, and website exports are derived
from those inputs.

The exact relationship between every published visual and its generator is
recorded in [`analysis/FIGURE_PROVENANCE.md`](analysis/FIGURE_PROVENANCE.md).
The paper build policy is documented in [`paper/README.md`](paper/README.md).

## Reproducing the public evidence

From the repository root, after creating the environment described in the
[main README](../README.md):

```bash
make check-uniaibench
make check-tables
make figures
make paper
```

`make check-uniaibench` validates the public data, model catalog, and every
released table without calling any provider. `make check-tables` is the
focused byte-for-byte table check. `make figures` regenerates the tables and
public derived outputs. `make paper` regenerates those outputs and compiles
the manuscript.

These commands reproduce the released aggregate views; they do not recreate
model answers or individual judgments because the protected source workflow is
not distributed.

## Public/private boundary

This study directory does **not** contain examination statements, official
solutions, completed item-specific rubrics, model-answer text, raw provider
payloads, individual judgments, blind inputs, identity maps, adjudications,
Router experiments, full-exam experiments, or website source code.

That boundary prevents this publication repository from becoming a source
dataset or response archive while retaining enough evidence to inspect the
study's aggregate claims and regenerate its public presentation.

## Relationship to the reusable toolkit

UniAIBench is one implementation of the contracts and workflow in
[`benchmark-toolkit/`](../benchmark-toolkit/). Third-party users should copy or
adapt the toolkit, not the study's model list, source selection, prices, or
results. The toolkit is tested to remain independent of this directory.
