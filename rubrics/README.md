# Rubric template

This directory contains only the blank, domain-extensible rubric template.
Completed UniAIBench rubrics and source exercises are deliberately excluded.

To create a rubric:

1. copy `templates/rubric.template.json` outside this repository or under a
   locally ignored working directory;
2. read `docs/rubric-authoring-guide.md` and `docs/t1-t8-framework.md`;
3. fill it using only the task, an independently checked reference, and the
   domain specification—never model answers;
4. validate it with `python tools/validate_rubric.py PATH`;
5. obtain human approval and set `frozen` only before judging starts.

The JSON Schema is `schemas/rubric.schema.json`.
