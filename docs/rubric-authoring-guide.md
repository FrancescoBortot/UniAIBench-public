# Rubric-authoring guide

## Required inputs

The rubric builder may receive only:

- the item statement;
- an official or expert reference solution;
- authorized figures and conventions;
- the domain-specific T1--T8 interpretation;
- the blank rubric template and schema.

It must not receive model answers, model identities, rankings, or known failure
patterns. Record `created_without_model_answers: true` only when this separation
has been maintained.

## Authoring sequence

1. **Verify the reference.** Recompute essential symbolic, numeric, logical,
   dimensional, and domain-dependent steps. Record ambiguities or suspected
   errors instead of silently correcting them.
2. **Decompose the task.** Create one rubric subproblem for each deliverable.
   Subproblem weights must sum to 1.
3. **Record acceptable solution space.** List expected results, required
   conditions, equivalent forms, and alternative valid methods.
4. **Create atomic criteria.** Each criterion should test one observable claim
   or step and belong to one primary T dimension.
5. **Allocate point budgets.** Criterion maxima must reconstruct the declared
   T1--T8 budgets and the intended subproblem weights exactly.
6. **Anchor partial credit.** Define evidence-based fractions such as 0.75,
   0.50, and 0.25 where meaningful. Avoid vague labels such as "mostly good".
7. **Define propagation and caps.** State how upstream mistakes affect later
   work and which structural failures impose score ceilings.
8. **Mark applicability.** Decide whether every dimension is applicable before
   answers are observed.
9. **Validate mechanically.** Run the schema and invariant validator.
10. **Review and freeze.** A human reviewer checks the reference, coverage,
    budgets, alternatives, and neutrality before setting `frozen: true`.

## Quality rules

A valid rubric must:

- be answer-independent and model-independent;
- cover every explicit task request;
- avoid style, verbosity, or formatting preferences unless required by the
  task;
- accept mathematically or scientifically equivalent formulations;
- not privilege the reference method when alternatives are valid;
- not introduce requirements absent from the item or evaluation protocol;
- distinguish incorrect reasoning from a correct result reached accidentally;
- make human-review triggers explicit.

## Versioning

Never overwrite a rubric after it has been used. A correction creates a new
version with:

- a new version identifier and date;
- the reason for change;
- the previous rubric hash;
- affected criteria and judgments;
- a decision on whether all affected responses require blind re-evaluation.

The private archive should retain every frozen and superseded version. Public
methodology repositories may distribute only blank templates.

## Validation

Validate a filled rubric with:

```bash
python tools/validate_rubric.py path/to/rubric.json
```

The blank template is checked with `--template`, which permits placeholders and
an unapproved state.

