# Methodology guides

Read the documents in this order:

1. [`benchmark-design.md`](benchmark-design.md): define the study and freeze
   the experimental contract.
2. [`t1-t8-framework.md`](t1-t8-framework.md): understand the default scoring
   dimensions.
3. [`rubric-authoring-guide.md`](rubric-authoring-guide.md): build and freeze
   item-specific atomic rubrics.
4. [`model-selection.md`](model-selection.md): assign models to solver, rubric,
   judge, and adjudication roles.
5. [`blind-judging-protocol.md`](blind-judging-protocol.md): evaluate answers
   without model identity leakage.
6. [`human-adjudication.md`](human-adjudication.md): resolve contested or
   invalid cases without rewriting history.
7. [`reproducibility.md`](reproducibility.md): preserve configurations,
   evidence, hashes, and reporting boundaries.
8. [`extending-the-method.md`](extending-the-method.md): adapt the framework to
   another discipline.
9. [`artifact-lifecycle.md`](artifact-lifecycle.md): keep blind, private,
    adjudicated, unblinded, and aggregate artifacts separate and traceable.
10. [`implementation-guide.md`](implementation-guide.md): run the complete
    offline workflow using the reusable contracts and tools.
11. [`statistical-analysis.md`](statistical-analysis.md): aggregate matched
    repetitions, handle missing observations, and quantify uncertainty.

The exact models, prices, source material, and outcomes of the concrete
UniAIBench v1.0 study are intentionally documented under
[`../../uniaibench/`](../../uniaibench/), not in these generic guides.
