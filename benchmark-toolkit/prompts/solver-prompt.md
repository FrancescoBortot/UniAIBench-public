# Solver prompt template

Version: `solver_prompt_v1`

## Prompt to send to the model

You are solving one item under controlled benchmark conditions.

Benchmark: {{benchmark_id}}
Assessment: {{assessment_name}}
Context: {{assessment_context}}
Domain: {{domain}}
Subject: {{subject}}
Topic: {{topic}}
Session: {{session}}
Item: {{item_id}}
Allowed tools: {{allowed_tools}}
Web access: {{web_allowed}}
Allowed materials: {{allowed_materials}}

Problem:

{{problem_text}}

Provide a complete, self-contained solution. State assumptions, justify the
method, show the essential derivation, answer every request, and perform a
brief independent check when possible. Do not claim to have used tools or
sources that were unavailable.
