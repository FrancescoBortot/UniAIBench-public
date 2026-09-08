# Configuration template

`benchmark_config.template.json` is intentionally non-runnable until its
placeholders and local dataset path are replaced. It also keeps
`provider_calls_authorized` false by default.

The reference harness expects each configured session to resolve to a folder
named `02_esercizi_YEAR_SESSION`, containing exactly three UTF-8 files named
`esercizio_1.txt`, `esercizio_2.txt`, and `esercizio_3.txt`. The Italian names
are retained for compatibility with the reference implementation. Keep source
material under `local_data/`, which is ignored by Git, and generated artifacts
under `local_outputs/`.

Always run an offline plan and dry run before authorizing provider calls:

```bash
python benchmark_harness.py plan --config PATH_TO_LOCAL_CONFIG
python benchmark_harness.py run --dry-run --config PATH_TO_LOCAL_CONFIG
```

Record exact model identifiers, provider modes, limits, repetitions,
concurrency, prompt version, and dates. Never commit credentials.
