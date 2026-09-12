# Extending the method to another benchmark

## Adaptation sequence

1. Write the benchmark claim and exclusion boundaries.
2. Define the task unit and a stable item identifier scheme.
3. Establish source provenance, permissions, and dataset versioning.
4. Map T1--T8 to observable domain-specific behavior.
5. Add domain fields to the rubric template without changing core invariants.
6. Write and freeze the solver prompt and resource policy.
7. Build rubrics from source material before model responses exist.
8. Validate and human-approve every rubric.
9. Run a small generation smoke test, then freeze the campaign configuration.
10. Create blind inputs and a permanent private identity map.
11. Judge one response at a time and validate all outputs.
12. Adjudicate flagged cases, unblind centrally, and aggregate matched units.
13. Publish methods, aggregate evidence, limitations, and licence boundaries.

## What should remain invariant

- rubrics are created without model answers;
- each criterion is atomic and belongs to one primary dimension;
- scores derive from criteria rather than holistic impressions;
- errors are not double-counted through propagation;
- model identity is hidden during judging;
- human review and corrections are versioned;
- unblinding occurs only after complete validation.

## What may change by domain

- T1--T8 interpretations and applicability;
- required units, conventions, citations, or evidence types;
- subproblem structure and point distribution;
- domain-specific ambiguity and validity checks;
- solver and judge model requirements;
- aggregation unit and uncertainty model.

## Minimum public release

A reusable methodology release should include:

- the domain mapping of T1--T8;
- blank rubric and judgment contracts;
- role-specific prompts;
- validators;
- a configuration template;
- reporting formulas and limitations;
- provenance and licence statements.

Source items and completed rubrics may remain private when redistribution or
benchmark-integrity constraints require it.

