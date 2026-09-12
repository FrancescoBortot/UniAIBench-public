# Human adjudication

Adjudication handles cases that cannot be resolved safely by ordinary judgment
validation.

## Typical triggers

- suspected error or omission in the reference solution;
- ambiguous statement, figure, convention, or unit;
- valid alternative method omitted from the frozen rubric;
- judge arithmetic or interpretation error;
- conflicting judgments on the same observable evidence;
- truncated, malformed, or operationally invalid response;
- any judgment with `requires_human_review: true`.

## Decision record

Create a new immutable adjudication artifact containing:

- case identifier and date;
- reviewer identity;
- triggering evidence;
- source artifact paths and hashes;
- decision and technical rationale;
- impact on reference, rubric, response validity, and scores;
- affected response set;
- re-evaluation requirement;
- supersession links.

Never edit the historical judgment to hide the original decision.

For a response-only review, use `uphold` when the reviewer explicitly confirms
that the original judgment and score stand unchanged. This clears a pending
review flag only if the underlying run is valid and no re-evaluation is
required. The original judgment must be cited by path and SHA-256 as a source
artifact. Use `no_action` only to record that no disposition was made; it does
not make a flagged judgment eligible for unblinding. `no_action`, `uphold`, and
`exclude_response` cannot leave re-evaluation pending. A response exclusion
must explicitly change response validity to `invalid` without changing the
reference, rubric, or score. A judgment replacement must cite every replacement
as a hash-verified source artifact and use `response_subset` as its re-evaluation
scope.

When correcting a final adjudication, retain the same campaign, batch,
classification, and exact affected-response set. Link the new record to the old
record by ID and SHA-256. A record may have only one successor; parallel
successors are rejected as an ambiguous fork.

## Impact analysis

Classify the decision:

- **response-only:** a single judgment was misapplied;
- **rubric-level:** one or more rubric criteria or alternatives change;
- **reference-level:** expected results or authoritative assumptions change;
- **campaign-level:** prompt, dataset, or configuration comparability changes.

Rubric- or reference-level changes normally require blind re-evaluation of every
affected response, not only the response that exposed the issue.

## Finalization

After revised judgments pass central validation:

1. mark the old artifacts as superseded without deleting them;
2. update the authority manifest;
3. unblind the complete affected set;
4. rebuild aggregate reports;
5. record changes in the release notes.
