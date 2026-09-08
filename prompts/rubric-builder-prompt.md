# Rubric-builder prompt template

Version: `rubric_builder_v1`

Create an atomic T1--T8 rubric for the task below using the supplied reference
material and domain specification. You must not inspect or infer any model
answer.

Inputs:

- item: `{{item_text}}`
- independently checked reference: `{{reference_solution}}`
- domain specification: `{{domain_specification}}`
- rubric JSON Schema: `{{rubric_schema}}`

Requirements:

1. Split the task into explicit subproblems with weights summing to one.
2. Create observable, non-overlapping atomic criteria.
3. Assign each criterion to one primary T1--T8 dimension.
4. Define full, partial, and zero-credit evidence.
5. Record equivalent expressions and legitimate alternative methods.
6. State how propagated errors are treated so one mistake is not penalized
   repeatedly.
7. Mark inapplicable dimensions explicitly and define any justified caps or
   human-review triggers.
8. Return only schema-valid JSON with `frozen` and `approved` set to false.

Do not optimize the rubric for any observed answer. Human review and freezing
are separate mandatory steps.
