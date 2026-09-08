# T1--T8 evaluation framework

The default framework assigns 100 points across eight dimensions. Item-specific
rubrics distribute these budgets among observable atomic criteria.

| Dimension | Budget | General interpretation |
|---|---:|---|
| T1 | 20 | Understanding, abstraction, and formalization of the task |
| T2 | 15 | Selection and setup of a valid solution method |
| T3 | 20 | Correct mathematical, logical, or computational development |
| T4 | 15 | Correct final results and coverage of all requests |
| T5 | 10 | Domains, units, assumptions, constraints, and validity conditions |
| T6 | 8 | Internal consistency, scale, and discipline-specific plausibility |
| T7 | 7 | Rigorous use of definitions, laws, principles, and theorems |
| T8 | 5 | Independent checks, limiting cases, or required verification |

## Domain interpretation

The dimensions remain stable while their observable meaning is adapted.

- In mathematics, T1 emphasizes formalization; T5 emphasizes domains and
  hypotheses; T6 emphasizes structural plausibility; T7 emphasizes theorem
  conditions.
- In physics, T1 emphasizes physical modelling; T5 includes dimensions and
  units; T6 includes order of magnitude and physical plausibility; T7 includes
  assumptions and validity regimes.
- In another discipline, document an equally explicit mapping before creating
  item rubrics.

## Atomic scoring rule

Each criterion:

- checks one observable element;
- belongs to one subproblem;
- has exactly one primary T dimension;
- defines a maximum score;
- states full-, partial-, and zero-credit evidence;
- records accepted equivalent forms and alternative methods;
- specifies how a single upstream error propagates.

Dimension scores are sums, not independent impressions:

```text
T_k = sum(points awarded to criteria whose primary dimension is T_k)
raw score = T1 + T2 + ... + T8
```

Extra penalties are allowed only for effects not already represented by atomic
criteria. A structural cap is applied only when predefined conditions are met.

## Non-applicable criteria

A criterion or dimension can be non-applicable only when that status was fixed
before responses were observed. If the applicable maximum is below 100, use:

```text
normalized score = 100 × raw applicable points / applicable maximum
```

T8 must not reward redundant repetition. Mark it non-applicable when no
independent check is requested or methodologically meaningful.

## Error propagation

Penalize an originating error once. Later steps that are internally correct
relative to that error can retain development credit, while T4 separately
reflects an incorrect final result. Do not count every downstream consequence
as a new causal error.

