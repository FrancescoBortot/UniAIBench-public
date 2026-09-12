# Contributing

Contributions are welcome in two distinct tracks:

- `benchmark-toolkit/`: study-independent methods, contracts, prompts,
  validators, harness adapters, and tests;
- `uniaibench/`: corrections to the dated study metadata, public evidence,
  analysis programs, figures, or paper.

Toolkit code must not import or reference `uniaibench/`. A study-specific
choice belongs under `uniaibench/`; a reusable capability belongs under
`benchmark-toolkit/` and requires a study-independent test.

Before opening a pull request:

1. create a branch and keep changes narrowly scoped;
2. run `python3.11 -m venv .venv` and install `requirements.txt`;
3. run `make check-toolkit` for toolkit changes;
4. run `make check-uniaibench` for study-evidence changes;
5. run `make check` and `make check-strict` before submitting;
6. run `make check-tables`, then `make figures`, when analysis code changes;
7. run `make paper` when manuscript or paper figures change;
8. confirm that no source exercise, official solution, completed rubric,
   response, judgment, identity map, credential, or personal path is included.

Do not submit provider credentials or third-party examination content. Changes
to rubric semantics, score arithmetic, or publication aggregates must explain
their effect on reproducibility and comparability.

Do not add UniAIBench results as defaults or fixtures in the reusable toolkit.
Tests for the toolkit must create synthetic temporary artifacts at runtime and
must not commit synthetic or real exercise content as a persistent dataset.
