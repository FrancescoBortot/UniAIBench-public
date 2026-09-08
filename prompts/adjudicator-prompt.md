# Human-adjudication assistant prompt template

Version: `adjudication_support_v1`

Support, but do not replace, a human decision on a flagged blind judgment.

Inputs:

- task and authorized reference: `{{task_and_reference}}`
- frozen rubric version: `{{frozen_rubric_json}}`
- anonymous response: `{{anonymous_response_text}}`
- original judgment: `{{original_judgment_json}}`
- review issue: `{{review_issue}}`

Produce a concise technical memo that:

1. isolates the disputed claim or criterion;
2. checks whether the reference, rubric, or judgment is responsible;
3. distinguishes an alternative valid method from an actual error;
4. lists the affected criteria and downstream judgments;
5. proposes a versioned corrective action without overwriting history; and
6. states what must be revalidated before unblinding.

Do not reveal model identity. The final decision, rationale, reviewer, date,
and affected artifact versions must be recorded by a human.
