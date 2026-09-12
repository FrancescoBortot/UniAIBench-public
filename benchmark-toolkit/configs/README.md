# Configuration template

`benchmark_config.template.json` is intentionally non-runnable until its
placeholders and local dataset path are replaced. It also keeps
`provider_calls_authorized` false by default.

All paths in a configuration are resolved relative to that configuration file,
not to the caller's shell directory. The bundled template therefore illustrates
`../local_data/items_2026/sessions/SESSION/`, with
UTF-8 inputs named `item_1.txt`, `item_2.txt`, and so on.
`session_directory_template`, `item_filename_glob`,
`item_filename_regex`, and `expected_items_per_session` make that
layout explicit and adaptable. When using the bundled configs, keep source
material under `benchmark-toolkit/local_data/`, which is ignored by Git, and
generated artifacts under `benchmark-toolkit/local_outputs/`. If you copy a
config to a separate private workspace, adjust its relative paths there and
place `.env` beside that config. With a bundled config, copy
`benchmark-toolkit/.env.example` to `benchmark-toolkit/.env` instead.

Session names and model output slugs must be safe single path components, and
each `(provider, output_slug)` pair must be unique. The item glob is a filename
pattern, while the session-directory template must remain inside
`dataset_root`. Every matched input must be a regular file whose resolved path
also remains inside that root; the harness rejects collisions, symlink escape,
or traversal before execution.

Always run an offline plan and dry run before authorizing provider calls:

```bash
.venv/bin/python benchmark-toolkit/harness/benchmark_harness.py plan --config PATH_TO_LOCAL_CONFIG
.venv/bin/python benchmark-toolkit/harness/benchmark_harness.py run --dry-run --config PATH_TO_LOCAL_CONFIG
```

The harness validates configurations against
[`benchmark-config.schema.json`](../schemas/benchmark-config.schema.json). A
template's `$schema` field uses the immutable `v1.0` URL and therefore remains
valid after copying; the harness itself uses the bundled schema offline. A
real run writes a non-secret configuration and prompt snapshot under
`local_outputs/_campaign/`, and each run records the configuration hash,
endpoint, installed SDK version, prompt and response hashes, tools policy, and
access date. Never place credentials in configuration files or commit them.
