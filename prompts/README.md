# Prompt templates

These templates separate the four roles in the evaluation pipeline. Replace
double-braced placeholders at runtime and version every material edit.

- `solver-prompt.md`: sent to the models being benchmarked; it contains only
  the task and permitted metadata.
- `rubric-builder-prompt.md`: used before any model response is inspected.
- `judge-prompt.md`: receives one anonymous response and one frozen rubric.
- `adjudicator-prompt.md`: supports a human reviewer after an explicit flag.

Never expose solutions, rubrics, other model answers, model identity, or scores
to the solver. Never expose the private identity map to a judge.
