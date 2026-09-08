# Solver prompt template

Version: `solver_prompt_v1`

## Prompt to send to the model

You are solving one advanced university-level problem under controlled
benchmark conditions.

Institution: {{institution}}
Programme: {{degree_program}}
Course or subject: {{subject}}
Assessment: {{exam_name}}
Academic year: {{academic_year}}
Allowed tools: {{allowed_tools}}
Web access: {{web_allowed}}
Allowed materials: {{allowed_materials}}

Problem:

{{problem_text}}

Provide a complete, self-contained solution. State assumptions, justify the
method, show the essential derivation, answer every request, and perform a
brief independent check when possible. Do not claim to have used tools or
sources that were unavailable.
