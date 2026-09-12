# Analysis programs

These scripts are the executable source for all public paper and website chart
families. Run them from the repository root; do not run them from this folder.

Use `make tables` to rebuild the released CSVs, `make check-tables` to compare
them byte-for-byte without changing tracked files, and `make figures` for the
full supported dependency order. See
[`../FIGURE_PROVENANCE.md`](../FIGURE_PROVENANCE.md) for the complete mapping
between outputs, programs, and sanitized inputs.

`build_public_tables.py` is the canonical table generator. Its fixed inputs
are the two sanitized model--item panels, `model_catalog.json`, and
`benchmark_pricing_manifest.json`, together with
`config/public_analysis.json`; it does not access the private benchmark tree.
