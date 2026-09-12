# Artifact lifecycle

This guide defines which artifact is authoritative at each stage and which
transitions are permitted. The objective is to make every score traceable
without revealing system identity to judges or rewriting historical evidence.

## Lifecycle at a glance

| Stage | Artifact | Visibility | Mutation rule |
|---|---|---|---|
| Source preparation | local source manifest and referenced files | private | freeze before batch preparation |
| Blinding | blind-batch manifest | judge-visible | immutable after sealing |
| Blinding | identity map | strictly private | immutable after sealing |
| Judging | anonymous judgment files | judge-visible | replace only invalid serialization before acceptance |
| Review | adjudication record | blind reviewers only | one final decision per new file; never overwrite |
| Unblinding | row-level unblinded results | private by default | regenerate from frozen inputs |
| Analysis | aggregate configuration and outputs | releasable after review | freeze config; regenerate outputs |

`draft` means incomplete and non-authoritative. `sealed`, `final`, and `frozen`
mean that the artifact must not be edited in place. A correction creates a new
version with an explicit supersession link.

## 1. Source preparation

Create a private source manifest with this minimum shape:

```json
{
  "schema_version": "1.0",
  "campaign_id": "replace-with-campaign-id",
  "batch_id": "replace-with-batch-id",
  "judging_contract": {
    "judge_spec_version": "replace-with-judge-spec-version",
    "judge_prompt_path": "contract/judge-prompt.md",
    "judgment_schema_path": "contract/judgment.schema.json",
    "validator_path": "contract/validate_judgment.py",
    "validator_support_path": "contract/schema_validation.py",
    "validator_version": "replace-with-validator-version"
  },
  "responses": [
    {
      "source_run_id": "replace-with-source-run-id",
      "system_id": "replace-with-stable-system-id",
      "repetition_id": "replace-with-repetition-id",
      "item_id": "replace-with-item-id",
      "item_path": "items/replace-with-item.txt",
      "response_path": "responses/replace-with-response-file.txt",
      "rubric_path": "rubrics/replace-with-rubric-file.json",
      "reference_path": "references/replace-with-reference-file.txt",
      "model_identity": {}
    }
  ]
}
```

`reference_path` is optional. Every path in the source manifest is interpreted
relative to the directory containing that manifest. Do not reuse a
`source_run_id`, and do not list the same source response more than once.

The `judging_contract` is mandatory. Preparation copies its prompt, schema,
validator, and dependency-free schema-validation support module into the blind
batch and records their SHA-256 hashes together
with the judge-specification and validator versions. This makes the exact
evaluation contract independently checkable before dispatch. Every referenced
rubric must declare the same `judge_spec_version`; preparation rejects a mixed
or mismatched batch.

The copied validator bundle is runnable from the batch as
`python contract/tools/validate_judgment.py JUDGMENT.json`. Central batch
validation also compares the active toolkit schema, validator, and support
module hashes with this frozen bundle. If they differ, use the toolkit revision
that prepared the batch rather than silently applying newer validation rules.

Freeze the source files before preparing the blind batch. Preparation computes
their hashes; a later byte-level change must invalidate validation rather than
silently update the recorded digest.

## 2. Blind-batch preparation

Preparation creates two coordinated artifacts:

- a blind-batch manifest containing the frozen judging contract, anonymous
  IDs, item IDs, response hashes, blind-input paths, frozen
  item/rubric/reference hashes, and planned judgment paths;
- a private identity map joining each anonymous ID to its source run, system,
  repetition, source response, and private model metadata.

The blind manifest must not contain provider, model, system, source-run, file
ordering, or naming information that lets a judge infer identity. Anonymous IDs
must be opaque and unrelated to system or execution order.

Before the first judgment, verify a bijection across the source manifest, blind
manifest, identity map, blind-input files, and planned judgment paths. For each
entry, all of the following must hold:

```text
blind.responses[].anonymous_response_id
    = identity.entries[].anonymous_response_id

blind.responses[].item_id
    = identity.entries[].item_id

blind.responses[].response_sha256
    = identity.entries[].source_response_sha256

blind.responses[].blind_input_path
    = identity.entries[].blind_input_path

blind.responses[].blind_input_sha256
    = identity.entries[].blind_input_sha256

blind.responses[].planned_judgment_path
    = identity.entries[].planned_judgment_path
```

Each join key and each planned judgment path must be unique. There must be
exactly one entry on both sides for every source response.

The identity map records the path and SHA-256 hash of the blind manifest. This
binds the private mapping permanently to the exact judge-visible batch.

## 3. Path-resolution rules

Resolve paths deterministically:

- source-manifest paths and `identity.entries[].source_response_path` are
  relative to the source-manifest directory;
- `identity.blind_batch_manifest_path` is relative to the identity-map file;
- `blind_input_path`, `planned_judgment_path`, item paths, rubric paths, and
  reference paths in the blind manifest are relative to the blind-manifest
  directory;
- the copies of `blind_input_path` and `planned_judgment_path` in the identity
  map retain those blind-manifest-relative semantics even when the map lives in
  another directory;
- adjudication paths in a draft are relative to `--artifact-root`, or to the
  draft directory when no root is supplied; the recorder normalizes them to
  paths relative to the immutable output record for downstream validation;
- aggregation input and output paths are relative to the aggregation config.

Operational tools should resolve and normalize paths before access and reject
unexpected traversal outside the selected working root. Do not rely on the
current shell directory.

## 4. Judgment and central validation

Judges receive only a single anonymous response and its authorized item,
reference, frozen rubric, prompt, and schema. They do not receive the source
manifest, identity map, other responses, existing scores, or aggregates.

Central validation must establish:

- schema validity and exact campaign/batch context;
- exact response and item IDs;
- one valid judgment per expected anonymous response;
- unique planned and actual judgment paths;
- criterion, dimension, penalty, cap, and total-score arithmetic;
- explicit disposition of every `requires_human_review` case.

An incomplete batch may be inspected, but it is not eligible for unblinding.
Serialization repairs may create a corrected artifact while preserving the
original. They must not silently change a substantive score.

## 5. Append-only adjudication

Create one adjudication JSON file per human decision. A finalized record is
immutable. If it is later corrected, write a new record whose
`supersedes_adjudication_id` and `supersedes_adjudication_sha256` identify the
previous record. A correction must retain the same campaign, batch,
classification, and exact set of affected anonymous responses. Each record may
have at most one direct successor, so the lineage can never fork. Never edit or
delete the earlier record.

Adjudication remains blind: use anonymous response IDs and do not add model
identity. Reference- or rubric-level decisions normally require re-evaluation
of every affected anonymous response. Revised judgments are new artifacts; the
adjudication record describes which earlier artifacts they supersede.

The v1 authority resolver applies only response-level leaf decisions:

- `uphold` resolves a review flag while retaining the original judgment only
  when the run is valid, no re-evaluation is pending, and the adjudication
  changes neither reference, rubric, response validity, nor score. The original
  judgment must be cited by path and hash as a source artifact;
- `no_action` records the human decision but deliberately leaves any existing
  review flag unresolved. It changes no artifact and cannot leave a pending
  re-evaluation request;
- `replace_judgment` selects a new, hash-verified judgment listed in
  `reevaluation.replacement_artifact_paths` while retaining the original. Its
  re-evaluation scope is the affected response subset;
- `exclude_response` marks response validity as `invalid`, requires no pending
  re-evaluation, changes neither reference nor rubric, and never converts the
  exclusion to a zero score.

Rubric-, reference-, and campaign-level decisions require a newly frozen batch;
the tools do not reinterpret the old batch implicitly. When several decision
versions exist, only a final record that is not superseded may be authoritative.

Draft records are not authority. Finalization requires a named or pseudonymous
human reviewer, a technical rationale, hashes for source evidence, an impact
classification, and an explicit re-evaluation decision.

## 6. Unblinding gate

Unblind only when:

1. blind-manifest and identity-map hashes and bijection are valid;
2. every expected response has exactly one authoritative valid judgment or a
   formally recorded exclusion;
3. every required adjudication is final and every required re-evaluation is
   present and validated;
4. no unresolved human-review flag remains.

Pass the adjudication directory to validation and unblinding whenever such
records exist. Unblinding is a deterministic join. It creates a new result
artifact and does not modify the blind manifest, identity map, judgments, or
adjudications. Preserve the anonymous ID, source-artifact hashes, judgment hash,
and applied adjudication reference in each unblinded row so the join can be
audited later. Keep exclusions in a separate list.

## 7. Aggregation and release

Freeze the aggregation configuration before producing reportable results. The
config identifies the exact unblinded input by path and hash, the system/item/
repetition/score fields, all eligibility and missing-data rules, the
within-item and across-item reductions, and the bootstrap seed.

Aggregate from the immutable row-level result; do not hand-edit report tables.
Generated outputs should record the configuration hash, input hash, counts,
coverage, exclusions, and software version. Row-level unblinded data remains
private unless it passes a separate rights, privacy, and benchmark-integrity
review.

## Failure and recovery rule

A failed transition leaves its inputs authoritative and its partial output
non-authoritative. Correct the cause, write a new output path, and rerun the
offline validation. Never repair a mismatch by guessing identity from response
content, file order, score similarity, or model style.
