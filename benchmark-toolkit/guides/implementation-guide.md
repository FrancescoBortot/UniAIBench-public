# Implementation guide

This is the operational path from local responses to aggregate results. It is
generic: replace every placeholder with paths from your own benchmark, and keep
all row-level artifacts in a private directory ignored by version control.

The commands below are offline. Run each tool with `--help` for the definitive
CLI contract.

## 1. Create a private workspace

A practical layout is:

```text
benchmark-workspace/
|-- source-manifest.json
|-- contract/
|-- items/
|-- responses/
|-- rubrics/
|-- references/
|-- blind-batches/<BATCH_ID>/
|   |-- contract/
|   |-- inputs/
|   |-- judgments/
|   `-- blind-batch-manifest.json
|-- private/identity-maps/
|-- adjudication-drafts/<BATCH_ID>/
|-- adjudications/<BATCH_ID>/
|-- unblinded/
`-- reports/
```

The repository-level `.gitignore` excludes `/benchmark-workspace/`, but verify
that rule before adding any local files and keep a separate private backup. The
identity map must be private, permanent, and stored somewhere more durable than
a temporary directory.

## 2. Build the source manifest

Create the local source manifest described in
[`artifact-lifecycle.md`](artifact-lifecycle.md). It contains one record per
response with stable campaign, batch, source-run, system, repetition, and item
IDs plus relative paths to the response, source item, and frozen rubric. A
reference path is optional. `model_identity` may hold private provider-specific
metadata. At the manifest root, declare `judging_contract` with the frozen
judge-specification version, validator version, and relative paths to the judge
prompt, judgment schema, validator program, and schema-validation support
module. The exact shape is shown in
[`artifact-lifecycle.md`](artifact-lifecycle.md).

Before continuing, verify that:

- every source path exists below the intended workspace;
- response records are unique by source run and by
  `(system_id, item_id, repetition_id)`;
- every source item exists, is stable, and matches the declared item ID;
- every rubric is frozen and matches the item ID;
- every rubric declares the frozen judging contract's `judge_spec_version`;
- the judge prompt, output schema, and validator are frozen and versioned;
- prompt, dataset, response, rubric, and reference versions are already fixed.

## 3. Prepare the blind batch

```bash
.venv/bin/python benchmark-toolkit/tools/prepare_blind_batch.py \
  --source-manifest benchmark-workspace/source-manifest.json \
  --output-dir benchmark-workspace/blind-batches/replace-with-batch-id \
  --identity-map benchmark-workspace/private/identity-maps/replace-with-batch-id.json
```

The command creates anonymous inputs, a blind-batch manifest, and a private
identity map. It must not modify source responses. Move neither output after
creation without updating the declaring paths through a new preparation run.

Immediately validate the cross-file join:

```bash
.venv/bin/python benchmark-toolkit/tools/validate_blind_batch.py \
  --manifest benchmark-workspace/blind-batches/replace-with-batch-id/blind-batch-manifest.json \
  --identity-map benchmark-workspace/private/identity-maps/replace-with-batch-id.json
```

Validation without `--identity-map` checks only the judge-visible side. The
private-map validation is required before dispatch because it proves the full
bijection.

## 4. Judge anonymously

Dispatch only files listed by `blind_input_path`. Resolve the response's
`item_id` to exactly one `item_artifacts` entry and supply its hashed item,
rubric, and optional reference. Write each JSON judgment to its exact
`planned_judgment_path`. Give the judge neither the source manifest nor the
private identity map.

During work, incomplete coverage can be inspected explicitly:

```bash
.venv/bin/python benchmark-toolkit/tools/validate_judgment_batch.py \
  --manifest benchmark-workspace/blind-batches/replace-with-batch-id/blind-batch-manifest.json \
  --allow-incomplete
```

Before unblinding, omit `--allow-incomplete` and include the private map for the
full consistency check. If the batch has adjudications, also supply their
directory:

```bash
.venv/bin/python benchmark-toolkit/tools/validate_judgment_batch.py \
  --manifest benchmark-workspace/blind-batches/replace-with-batch-id/blind-batch-manifest.json \
  --identity-map benchmark-workspace/private/identity-maps/replace-with-batch-id.json \
  --adjudications-dir benchmark-workspace/adjudications/replace-with-batch-id
```

## 5. Record adjudication without rewriting history

Copy `benchmark-toolkit/templates/adjudication.template.json` to a private
draft, cite every source artifact and hash, and record the decision while
identities remain hidden. Before recording, set `decision_status` to `final` and
`reviewer.human_confirmed` to `true`. Finalize it to a new path:

```bash
.venv/bin/python benchmark-toolkit/tools/record_adjudication.py \
  --draft benchmark-workspace/adjudication-drafts/replace-with-batch-id/replace-with-adjudication-id.json \
  --output benchmark-workspace/adjudications/replace-with-batch-id/replace-with-adjudication-id.json \
  --artifact-root benchmark-workspace
```

Paths declared in the draft are resolved from `--artifact-root`; the recorder
stores portable paths relative to the final record. Without that option, draft
paths are resolved from the draft's directory.

Never overwrite an existing final record. A correction is a new decision with
the previous decision's ID and SHA-256 in the two supersession fields. It must
retain the same campaign, batch, classification, and exact affected-response
set, and the previous record cannot already have another successor. Final
records are created with owner-only read/write permissions. A
response-only `replace_judgment` decision points to a new judgment through
`reevaluation.replacement_artifact_paths`; retain the original planned
judgment. Cite replacement evidence by path and hash in the adjudication
record. A final, human-confirmed `uphold` resolves the original review flag
only when the run is valid, no re-evaluation is pending, and the original
score and governing artifacts remain unchanged. The original judgment must be
included among the adjudication's hash-verified source artifacts. `no_action` is non-resolving:
it records the decision but leaves any review flag in place and changes no
artifact. `exclude_response` creates a formal exclusion by setting response
validity to `invalid`; neither outcome can leave re-evaluation pending.

The v1 tools do not apply rubric-, reference-, or campaign-level changes inside
an existing batch. Freeze the corrected authority, create a new blind batch,
and re-evaluate its complete affected set instead.

After recording all decisions and replacements, rerun judgment-batch
validation with `--adjudications-dir`. Only final adjudication records that are
not themselves superseded can supply authority. Keep drafts outside the
directory passed to this option; every JSON file found there is treated as a
candidate immutable record and must validate as final.

## 6. Unblind only after the gate passes

```bash
.venv/bin/python benchmark-toolkit/tools/unblind_results.py \
  --manifest benchmark-workspace/blind-batches/replace-with-batch-id/blind-batch-manifest.json \
  --identity-map benchmark-workspace/private/identity-maps/replace-with-batch-id.json \
  --adjudications-dir benchmark-workspace/adjudications/replace-with-batch-id \
  --output benchmark-workspace/unblinded/replace-with-batch-id.json
```

Omit `--adjudications-dir` when no adjudication exists. The tool must fail on
incomplete coverage, a broken hash, a non-bijective map, conflicting authority,
or unresolved review. Its output is row-level and private by default. Formally
excluded responses are reported separately and do not become zero scores.
Retain the anonymous ID and all provenance hashes so any row can be traced back
without modifying original evidence.

## 7. Freeze and run aggregation

Copy `benchmark-toolkit/templates/aggregation-config.template.json`, replace its sentinel values,
select policies before inspecting headline comparisons, and change `status` to
`frozen`. Record the exact SHA-256 of the unblinded input and replace
`expected_repetitions_per_cell: null` with the campaign's planned count whenever
that count is fixed.

```bash
.venv/bin/python benchmark-toolkit/tools/aggregate_results.py \
  --config benchmark-workspace/aggregation-config.json
```

Review coverage and exclusions before interpreting rankings. Report the
aggregation hierarchy and uncertainty method with every result. The formulas
and recommended defaults are defined in
[`statistical-analysis.md`](statistical-analysis.md).

## 8. Completion checklist

A reusable benchmark run is complete only when:

- the source manifest and all source hashes are frozen;
- the blind manifest and private identity map form a verified bijection;
- every expected judgment is schema-valid and arithmetically valid;
- all human-review cases have immutable decisions and required replacements;
- unblinding was produced as a new deterministic artifact;
- the aggregation config is frozen and identifies its input by hash;
- outputs report denominators, coverage, exclusions, software version, and
  config/input hashes;
- no private artifact or credential entered the public release accidentally.
