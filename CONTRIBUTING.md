# Contributing

Contributions are welcome for methodology, validators, schemas, documentation,
the reference harness, and aggregate-analysis programs.

Before opening a pull request:

1. create a branch and keep changes narrowly scoped;
2. run `python3.11 -m venv .venv` and install `requirements.txt`;
3. run `make check`;
4. run `make figures` when analysis code changes;
5. run `make paper` when manuscript or paper figures change;
6. confirm that no source exercise, official solution, completed rubric,
   response, judgment, identity map, credential, or personal path is included.

Do not submit provider credentials or third-party examination content. Changes
to rubric semantics, score arithmetic, or publication aggregates must explain
their effect on reproducibility and comparability.
