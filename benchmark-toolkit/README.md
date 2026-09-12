# Benchmark Toolkit

This directory is the reusable part of the repository. It provides a generic,
offline-first workflow for designing, generating, blind-judging, adjudicating,
unblinding, and aggregating an open-ended benchmark.

It does **not** contain UniAIBench source items, completed rubrics, model
responses, individual judgments, private identity maps, or study results.
Those boundaries are intentional: the toolkit describes how to run a study,
while `../uniaibench/` documents what was done and released for UniAIBench.

The dependency is one-way:

```text
UniAIBench study artifacts -> use the Benchmark Toolkit method
Benchmark Toolkit          -> does not depend on UniAIBench artifacts
```

## Quick check

From the repository root, create the supported Python environment, install the
pinned dependencies, and run the complete offline toolkit check:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
make check-toolkit
```

Start a generation campaign by copying a template from [`configs/`](configs/)
and passing it to the reference harness in [`harness/`](harness/). Planning and
dry-run checks are offline; provider calls require separate credentials, network
access, budget, and explicit authorization. No demo dataset is stored here.

## Start here

1. Read [`guides/benchmark-design.md`](guides/benchmark-design.md) and define
   the experimental contract.
2. Adapt the blank rubric and prompts without using target-model answers.
3. Follow the end-to-end [`implementation guide`](guides/implementation-guide.md).
4. Use the JSON templates in [`templates/`](templates/) for local artifacts.
5. Validate the blind batch before the first judgment, and unblind only after
   every expected judgment is valid or formally excluded.
6. Freeze an aggregation configuration and apply the formulas in
   [`guides/statistical-analysis.md`](guides/statistical-analysis.md).

All example paths are relative and all template values are placeholders. Copy
templates into a private, ignored working directory before filling them. The
templates do not authorize provider calls and must not be treated as completed
research artifacts.

## Contents

| Directory | Purpose |
|---|---|
| `configs/` | Generic generation-campaign configuration templates |
| `guides/` | Design, scoring, judging, lifecycle, and analysis guidance |
| `harness/` | Reference multi-provider generation harness |
| `prompts/` | Role-separated solver, rubric, judge, and adjudicator prompts |
| `schemas/` | Machine-readable JSON contracts |
| `templates/` | Blank rubric and workflow artifact templates |
| `tools/` | Offline preparation, validation, unblinding, and aggregation tools |
| `tests/` | Offline contract and workflow tests |

## Artifact flow

```text
local source manifest
        |
        v
blind batch manifest + private identity map
        |
        v
anonymous judgments ----> append-only adjudication records when needed
        |
        v
validated complete batch
        |
        v
unblinded local results
        |
        v
aggregate tables and uncertainty estimates
```

The blind manifest contains no model identity. The private identity map is the
only artifact that joins anonymous response IDs to source runs and systems.
Keep it outside judge-visible directories. See
[`guides/artifact-lifecycle.md`](guides/artifact-lifecycle.md) for the authority,
hashing, path-resolution, and immutability rules.

## Workflow contracts

The additional templates and matching schemas are:

- `blind-batch-manifest`: public-to-judges inventory of anonymous inputs,
  planned judgment paths, and hashes of the frozen judging contract;
- `identity-map`: permanent private one-to-one mapping back to source runs;
- `adjudication`: one immutable human decision per file, linked by
  supersession rather than rewritten;
- `aggregation-config`: frozen rules for eligibility, repetitions, items,
  missing observations, uncertainty, and outputs.

The local source manifest is a preparation input, not one of these four
versioned JSON-Schema contracts. Its minimum shape is documented in
[`guides/artifact-lifecycle.md`](guides/artifact-lifecycle.md) and is validated
operationally by `prepare_blind_batch.py`, including paths, uniqueness, frozen
rubrics, and item consistency.

For the four templates above, JSON Schema verifies structure. The offline tools
additionally verify file
existence, SHA-256 hashes, cross-file joins, uniqueness, expected judgment
coverage, and safe path resolution. Schema validity alone is therefore not a
completed batch.

## Safety boundary

Keep at least these artifacts private unless a separate release review permits
publication:

- source items and references whose licences do not permit redistribution;
- responses and provider-native payloads;
- completed item rubrics and individual judgments;
- the identity map and unblinded row-level results;
- credentials, local paths, reviewer personal data, and operational logs.

The toolkit performs no provider call during preparation, validation,
adjudication recording, unblinding, or aggregation. Generation remains a
separate, explicitly authorized operation.
