# Configuration template

`benchmark_config.template.json` is intentionally non-runnable until its
placeholders and local dataset path are replaced. It also keeps
`provider_calls_authorized` false by default.

The template uses `local_data/items_2026/sessions/SESSION/`, with exactly three
UTF-8 files named `exercise_1.txt`, `exercise_2.txt`, and `exercise_3.txt`.
`session_directory_template`, `exercise_filename_glob`,
`exercise_filename_regex`, and `expected_exercises_per_session` make that
layout explicit and adaptable. Keep source material under `local_data/`, which
is ignored by Git, and generated artifacts under `local_outputs/`.

Always run an offline plan and dry run before authorizing provider calls:

```bash
python benchmark_harness.py plan --config PATH_TO_LOCAL_CONFIG
python benchmark_harness.py run --dry-run --config PATH_TO_LOCAL_CONFIG
```

The harness validates configurations against
[`benchmark-config.schema.json`](../schemas/benchmark-config.schema.json). A
real run writes a non-secret configuration and prompt snapshot under
`local_outputs/_campaign/`, and each run records the configuration hash,
endpoint, installed SDK version, prompt and response hashes, tools policy, and
access date. Never place credentials in configuration files or commit them.
