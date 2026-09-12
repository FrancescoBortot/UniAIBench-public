# Blind-judge prompt template

Version: `1.0`

Evaluate exactly one anonymous response. Model identity, provider, price,
latency, and other responses are deliberately unavailable.

Inputs:

- task: `{{item_text}}`
- authorized reference, when the frozen protocol permits one:
  `{{authorized_reference}}`
- frozen rubric: `{{frozen_rubric_json}}`
- anonymous response ID: `{{anonymous_response_id}}`
- response: `{{anonymous_response_text}}`
- judgment JSON Schema: `{{judgment_schema}}`

Procedure:

1. Verify that the response is judgeable and addresses the supplied task.
2. Assess every atomic rubric criterion independently using quoted or precisely
   located evidence from the response.
3. Credit valid alternative methods and equivalent forms permitted by the
   rubric.
4. Track causal error propagation and avoid duplicate penalties for one root
   error.
5. Sum criterion awards into T1--T8; do not create a second holistic score.
6. Normalize only over applicable dimensions, then apply explicit penalties or
   caps once.
7. Flag ambiguity, a suspected reference conflict, an uncovered valid method,
   or insufficient evidence for human review.
8. Return only schema-valid JSON.

Do not guess the model identity and do not modify the frozen rubric.
