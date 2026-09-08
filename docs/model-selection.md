# Model selection and operation

The framework is model-agnostic. Select models by role and record exact versions
rather than treating a product name as a stable scientific identifier.

## Solver role

The solver is the system being measured. Include models according to the study
claim, not because they are convenient judges. Record:

- provider and exact API model identifier;
- endpoint and access date;
- reasoning or thinking mode;
- output-token limit;
- temperature, top-p, seed, and other supported controls;
- tool, retrieval, web, and calculator permissions;
- SDK name and version;
- retry and timeout policy.

All compared solvers should receive the same task information and resource
policy. Provider-specific syntax may differ, but semantic conditions should not.

## Rubric-builder role

Choose a model with strong domain competence, long-context reliability, and
consistent structured output. The model proposes a rubric; it does not approve
or freeze it. A human must independently verify the reference, point budgets,
alternatives, and neutrality.

The rubric builder must never see benchmark responses.

## Blind-judge role

Choose a model that can:

- follow a strict JSON output contract;
- apply criterion-level evidence rather than holistic preference;
- distinguish upstream errors from downstream consequences;
- respect alternative methods and non-applicable dimensions;
- flag uncertainty and reference conflicts.

Use the lowest practical sampling variance. Where available, prefer
deterministic or low-temperature evaluation. Preserve the exact judge model and
settings with every judgment.

Judge sensitivity should be measured with human audits or a second independent
judge on a predefined sample. Do not present an LLM judge as ground truth.

## Adjudication role

An adjudication model may organize evidence and test calculations, but the
final decision belongs to an accountable human reviewer. The adjudicator must
not rewrite historical artifacts or infer model identities.

## Avoiding role leakage

- never provide model identity or leaderboard position to a judge;
- never use observed response errors to retrofit a supposedly frozen rubric;
- do not allow the solver to access the reference or judging prompt;
- do not assume that using the same model family as solver and judge is neutral;
- disclose unavoidable overlap between model roles.

