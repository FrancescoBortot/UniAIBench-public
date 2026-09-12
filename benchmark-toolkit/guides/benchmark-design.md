# Benchmark design

## 1. Define the claim

Start with a narrow statement of what the benchmark measures. Specify the
discipline, item type, expected answer format, allowed resources, scoring unit,
and intended population of models. Avoid claiming general intelligence from a
specialized sample.

## 2. Freeze the experimental contract

Before any scored run, record:

- dataset snapshot and item identifiers;
- generation-prompt version and hash;
- provider, exact model identifier, endpoint, and access date;
- reasoning mode, token limit, sampling controls, and tool policy;
- number of repetitions and randomization rule;
- retry, timeout, concurrency, and failure policy;
- output layout and benchmark identifier.

A configuration change creates a new campaign. Results from incompatible
configurations must not be written into the same output path.

## 3. Select and verify source items

Use items that match the benchmark claim and can be interpreted without hidden
context. Record provenance and redistribution constraints. Inspect every
figure, notation convention, and official reference. A reference answer is
evidence, not an infallible oracle: verify it independently before rubric
freezing.

## 4. Separate the stages

Maintain four distinct evidence layers:

1. source item and verified reference;
2. generated response and provider metadata;
3. anonymous judgment and frozen rubric;
4. unblinded aggregate report.

Do not expose solutions, rubrics, competing answers, or model identities during
generation. Do not expose the identity map during judging.

## 5. Define the evaluation unit

Version 1.0 of the reference harness uses one independently scored item as the
evaluation unit. Complete-exam or other bundled-task evaluation requires a
separate campaign design and is intentionally outside this release. The job
count must be derivable from the configuration:

```text
jobs = items × model configurations × repetitions
```

Declare how repetitions are combined. A conservative default is to aggregate
repetitions within each system--item cell and then compare matched cells,
preventing items with more retries or repetitions from receiving extra weight.

## 6. Plan failure handling

Distinguish technical failure from poor task performance. Record timeouts,
empty responses, safety refusals, truncation, provider errors, and invalid
payloads separately. Never silently replace a failed observation with a later
attempt without preserving the authority rule.

## 7. Predefine reporting

At minimum report:

- coverage and exclusions;
- central performance with uncertainty;
- dimension-level profiles;
- repetition stability;
- token, cost, and latency semantics;
- model and provider versions;
- known dataset, judge, and generalization limitations.

Report both the denominator and the aggregation level for every headline
number.
