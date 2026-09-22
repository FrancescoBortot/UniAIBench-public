# Data provenance

The UniAIBench study uses examination material from the **University of Padua**
for Mathematical Analysis III and General Physics II.

This public repository does not distribute:

- examination statements;
- official solutions;
- scans, source PDFs, or source figures;
- completed item-specific rubrics;
- model response texts;
- individual judgments or private identity mappings.

The `uniaibench/` study release publishes only sanitized numerical evidence,
derived tables and figures, model metadata, methodology mappings, and the
paper. Generic prompts, schemas, blank templates, and workflow tools are
published separately under `benchmark-toolkit/`.

The complete source archive remains private and is not covered by the licences
of this repository. Citations to the institution identify provenance; they do
not assert that third-party examination material is relicensed here.

## Frozen pricing provenance

The exact input and output rates used for the current cost estimates are published
in [`analysis/data/benchmark_pricing_manifest.json`](analysis/data/benchmark_pricing_manifest.json).
Each of its 17 records gives the applied rate, an official provider reference,
and the origin class of the frozen value.

When an applied rate came from a private operational campaign configuration,
the manifest publishes only the configuration's SHA-256 fingerprint. The
filename, local path, and configuration contents remain private. A fingerprint
binds the public rate record to one exact private snapshot; it is an integrity
identifier, not a substitute for access to that snapshot or independent proof
that the configured rate was correct.
