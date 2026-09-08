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

