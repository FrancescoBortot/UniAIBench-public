# Artifact templates

This directory contains blank, domain-extensible artifact templates. Completed
rubrics, source items, responses, real judgments, identity maps, and
adjudications are deliberately excluded.

| Template | Role |
|---|---|
| `rubric.template.json` | Atomic scoring contract created and frozen before target answers are inspected |
| `judgment.template.json` | One structured blind evaluation of one anonymous response |
| `blind-batch-manifest.template.json` | Judge-visible inventory and planned judgment paths |
| `identity-map.template.json` | Private bijection between anonymous IDs and source runs |
| `adjudication.template.json` | Append-only human decision linked to hashed evidence |
| `aggregation-config.template.json` | Frozen eligibility, repetition, missing-data, and uncertainty rules |

To create a rubric:

1. copy `rubric.template.json` outside the tracked tree or under a
   locally ignored working directory;
2. read [`../guides/rubric-authoring-guide.md`](../guides/rubric-authoring-guide.md)
   and [`../guides/t1-t8-framework.md`](../guides/t1-t8-framework.md);
3. fill it using only the task, an independently checked reference, and the
   domain specification—never model answers;
4. validate it from the repository root with
   `.venv/bin/python benchmark-toolkit/tools/validate_rubric.py PATH`;
5. obtain human approval and set `frozen` only before judging starts.

The JSON Schemas are [`../schemas/rubric.schema.json`](../schemas/rubric.schema.json)
and the corresponding files under [`../schemas/`](../schemas/). The end-to-end
use of all workflow templates is documented in the
[`implementation guide`](../guides/implementation-guide.md).

Each template uses the immutable `v1.0` schema URL, so its `$schema` reference
continues to work after the file is copied into a private workspace. Local
validation remains fully offline because the toolkit validators load their
bundled schemas directly.
