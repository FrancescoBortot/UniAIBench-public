# Statistical analysis

This guide defines a conservative default for repeated, matched benchmark
observations. Deviations are allowed, but they must be selected before viewing
headline results and encoded in the frozen aggregation configuration.

## Units and notation

Let

```text
y[s,i,r] = valid final score for system s, item i, repetition r
```

The response is the raw observation, the system--item cell is the comparison
unit, and the item is the default resampling unit. Retries that merely replace
a failed transport attempt are not new repetitions and must follow the
campaign's predeclared authority rule.

## Primary score

First combine valid repetitions within each system--item cell:

```text
cell_score[s,i] = mean over r of y[s,i,r]
```

Then give every eligible item equal weight:

```text
system_score[s] = mean over i of cell_score[s,i]
```

This two-level reduction prevents an item with more repetitions from receiving
extra weight. Use `median` or `first_authoritative` within a cell only when that
choice was specified in advance. Do not pool all responses directly unless
every cell has the same planned and retained repetition count and response
weighting is the stated estimand.

For a weighted item estimand:

```text
weighted_score[s] = sum_i(w[i] * cell_score[s,i]) / sum_i(w[i])
```

Weights must come from the frozen benchmark design, not observed difficulty or
system performance.

## Matched comparisons

Compare two systems on their common eligible items:

```text
difference[a,b] = mean over common i of
                  (cell_score[a,i] - cell_score[b,i])
```

Report the common-item count and coverage for both systems. A difference of two
independently calculated means is not a paired comparison when their item sets
differ.

## T1--T8 dimensions

Aggregate dimensions using the same repetition-then-item hierarchy. When point
budgets differ by item, calculate a within-response percentage first:

```text
dimension_percent = 100 * awarded_dimension_points / applicable_dimension_max
```

Exclude a dimension only when its rubric status was fixed as
`not_applicable` before responses were viewed. Never convert non-applicability
to zero. Always report the applicable denominator for each dimension.

## Missing observations and failures

Keep technical validity separate from answer quality:

- provider errors, timeouts, malformed payloads, and empty outputs are
  operational failures;
- a valid response that earns no credit is a score of zero;
- a response excluded by a final adjudication is an exclusion, not a zero;
- unresolved review is neither valid nor eligible for aggregation.

Choose one policy in advance:

- `fail`: require every planned observation and the complete matched panel;
  stop on any formal exclusion, ineligible record, or incomplete cell. This is
  the recommended headline-policy default.
- `exclude_cell`: omit incomplete cells, report each exclusion, and use only a
  declared matched subset for comparisons.
- `available_case`: summarize every available cell. Use this for descriptive
  operational reporting, not an unlabeled matched ranking.

Never impute performance from another repetition or silently rerun until a
preferred answer appears. Report planned responses, retained responses,
complete cells, excluded cells, and item coverage per system.

The aggregation command resolves its input and output paths relative to the
directory containing the frozen configuration and rejects paths that escape
that operational root. It writes the three outputs through a temporary staging
directory so a failed write cannot leave a partial report in place.

## Bootstrap uncertainty

For system scores, resample items with replacement. Each sampled item carries
all systems and all retained repetitions in its cells, preserving the matched
design. Recompute the complete two-level statistic for every replicate.

For a system difference, use the same sampled item indices for both systems.
The default interval is the percentile interval at the configured confidence
level:

```text
lower = quantile(alpha / 2)
upper = quantile(1 - alpha / 2)
alpha = 1 - confidence_level
```

Use a fixed recorded seed and a sufficiently large predeclared sample count.
The reusable config template uses 10,000 replicates and 95% confidence as
defaults, not as universal requirements. Stratify item resampling only when the
strata were part of the sampling design; sample within each stratum and retain
its intended weight.

Bootstrap intervals describe uncertainty over the sampled item set under the
chosen design. They do not capture model-version drift, judge bias, source
selection bias, or provider nondeterminism outside retained repetitions.

## Repetition stability

When there are at least two planned repetitions, report within-cell variation
separately from the primary score. Useful quantities include:

- the standard deviation or range within each system--item cell;
- the proportion of cells whose repetitions cross a declared score threshold;
- system-level distributions of absolute repetition differences.

Do not treat repetitions from the same item as independent item samples.

## Tokens, cost, and latency

Apply the same cell-then-item hierarchy to resource metrics when comparing
systems. Define fields and units explicitly:

- input, cached-input, reasoning, and visible-output tokens must remain
  distinguishable when the provider exposes them;
- estimated cost must record the dated price source and formula;
- latency must state start/end events and whether retries, queueing, streaming,
  or client overhead are included.

Sum components within one response where that is the metric definition, then
reduce repetitions and items. Do not average provider-reported token categories
with incompatible semantics. Missing resource values follow a separately
declared resource policy and never default to zero.

The v1 `aggregate_results.py` command calculates score aggregates only. The
aggregation schema reserves an optional `resources` declaration for extensions,
but the v1 tool does not calculate those fields; omit it from executable v1
configs and analyze resources with a separately validated program.

## Rounding and rankings

Compute from full-precision values and round only presentation outputs. Publish
the unrounded ordering key or a tie rule when rounded scores appear equal.
Rankings should include confidence intervals, coverage, and the number of
eligible items; small numeric differences are not automatically meaningful.

## Required provenance for every aggregate

Record at least:

- input path and SHA-256;
- aggregation-config path and SHA-256;
- software or repository revision;
- system, item, repetition, and score field names;
- eligibility, missing-data, repetition, and item policies;
- planned and retained counts plus explicit exclusions;
- bootstrap method, sample count, confidence level, seed, and resampling unit;
- generation timestamp and output hashes.

An aggregate table without these fields may be useful for exploration, but it
is not a reproducible benchmark result.
