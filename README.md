# UniAIBench

**A reusable methodology and an empirical benchmark for evaluating complete AI
solutions to advanced university-level problems.**

UniAIBench combines controlled multi-provider generation, item-specific atomic
rubrics, blind judging, versioned human adjudication, and multi-objective
reporting. The current study covers Mathematical Analysis III and General
Physics II, but the public framework is designed to be adapted to other
disciplines.

[Explore the UniAIBench website](https://modelfit-research-preview.francescobortot007.chatgpt.site)
or read the [current paper](paper/benchmark_publication.pdf).

## Why this repository exists

Many benchmarks check only whether a final answer matches a key. UniAIBench
instead evaluates observable reasoning quality: problem interpretation, method
selection, derivation, final result, assumptions, consistency, and verification.

This repository provides:

- a domain-extensible T1--T8 rubric framework;
- blank rubric templates and machine-readable JSON Schemas;
- reusable prompts for solving, rubric construction, blind judging, and
  adjudication;
- guidance for model selection, execution, validation, and reporting;
- a multi-provider reference harness;
- aggregate results, figures, and the scientific paper from the UniAIBench
  study.

It intentionally does **not** distribute examination statements, official
solutions, completed item-specific rubrics, model response texts, individual
judgments, or private identity maps.

| Included here | Kept in the private research archive |
|---|---|
| Methodology, prompts, schemas, blank rubric template, reference harness | Examination statements and official solutions |
| Sanitized model--item score and resource panels | Completed rubrics and criterion-level judgments |
| Aggregate tables, figure programs, paper source, and compiled paper | Model response text, provider payloads, and blind identity maps |
| Website chart-data exporter and a link to the deployed site | Website source, Atlas records, retries, and internal experiments |

## Method in one view

```text
Define scope and freeze the generation configuration
                         |
                         v
Select source material and independently verify references
                         |
                         v
Build an atomic rubric before seeing model answers
                         |
                         v
Generate answers under the same controlled conditions
                         |
                         v
Create anonymous IDs and a permanent private identity map
                         |
                         v
Judge one anonymous answer at a time against the frozen rubric
                         |
                         v
Validate judgments and adjudicate flagged cases without overwriting history
                         |
                         v
Unblind only after validation, then aggregate and report
```

## T1--T8 framework

The default 100-point budget is:

| Dimension | General purpose | Points |
|---|---|---:|
| T1 | Problem understanding and formalization | 20 |
| T2 | Method selection and setup | 15 |
| T3 | Mathematical or logical development | 20 |
| T4 | Final result and request coverage | 15 |
| T5 | Domains, units, assumptions, and structural conditions | 10 |
| T6 | Internal consistency and domain plausibility | 8 |
| T7 | Rigorous use of definitions, principles, and theorems | 7 |
| T8 | Independent verification and limiting cases | 5 |

Each score is derived from atomic criteria assigned to exactly one primary
dimension. The dimensions are not scored a second time from a holistic
impression. See [the full dimension guide](docs/t1-t8-framework.md).

## Repository structure

```text
UniAIBench-public/
|-- docs/                    reusable methodology and extension guides
|-- schemas/                 rubric and judgment JSON Schemas
|-- rubrics/templates/       blank, unfilled rubric templates
|-- prompts/                 role-specific prompt templates
|-- configs/                 generic benchmark configuration template
|-- tools/                   offline rubric, judgment, and release validators
|-- analysis/                aggregate data, figures, and all chart programs
|-- results/                 additional aggregate result views
|-- paper/                   manuscript source and compiled PDF
|-- benchmark_harness.py     multi-provider reference implementation
`-- DATA_PROVENANCE.md       provenance boundary for the private source set
```

## Start here

1. Read [Benchmark design](docs/benchmark-design.md).
2. Adapt the [rubric template](rubrics/templates/rubric.template.json) and
   [rubric schema](schemas/rubric.schema.json) to your domain.
3. Follow the [rubric-authoring guide](docs/rubric-authoring-guide.md).
4. Customize the prompts in [`prompts/`](prompts/README.md).
5. Follow the [blind-judging](docs/blind-judging-protocol.md) and
   [human-adjudication](docs/human-adjudication.md) protocols.
6. Validate every artifact before unblinding.

For a complete adaptation sequence, see
[Extending the method](docs/extending-the-method.md).

Run all offline structural, schema, safety, and aggregate-data checks with:

```bash
make check
```

## Headline results

The analysis snapshot is dated **14 August 2026**. The top six configurations
in the matched 60-item panel were:

| Rank | Configuration | Mean score | 95% item-bootstrap interval |
|---:|---|---:|---:|
| 1 | GPT-5.6 Sol | 98.72% | 97.04--99.86% |
| 2 | Claude Fable 5 | 97.99% | 96.15--99.38% |
| 3 | DeepSeek V4 Flash | 97.24% | 94.66--99.16% |
| 4 | Gemini 3.1 Pro Preview | 97.05% | 95.11--98.60% |
| 5 | Gemini 3.5 Flash | 96.95% | 95.10--98.51% |
| 6 | DeepSeek V4 Pro | 96.71% | 94.76--98.31% |

The overlapping intervals do not support treating this ordering as a sharply
separated leaderboard. Subject stability, token use, cost, and response time
remain necessary parts of the comparison.

## Choosing and using models

The method does not require a specific vendor or model. It separates four
roles:

- **solver:** the system being benchmarked;
- **rubric builder:** a capable structured-output assistant used before model
  answers are available;
- **blind judge:** a technically competent model that evaluates one anonymous
  answer at a time;
- **adjudication assistant:** optional decision support for cases escalated to
  human review.

Exact provider, model identifier, date, endpoint, reasoning mode, token limit,
and sampling settings must be recorded. Human approval remains mandatory for
rubric freezing and adjudication decisions. See
[Model selection and operation](docs/model-selection.md). The complete
[evaluated-model catalog](docs/evaluated-models.md) records all 14 benchmark
configurations, their technical specifications, reasoning modes, official
links, and both current and frozen benchmark prices.

## Reference harness

The Python harness supports OpenAI, Anthropic, Google, Kimi/Moonshot,
DeepSeek, and xAI adapters. It is included as a reference implementation; the
private examination dataset is not included.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python benchmark_harness.py --help
```

Copy and adapt [`configs/benchmark_config.template.json`](configs/benchmark_config.template.json).
The template sets `provider_calls_authorized` to `false`; do not enable it until
an offline plan and one-job smoke test have been reviewed. Real runs require
credentials, network access, and provider credit.

## Results and reproducibility

The principal published comparison uses 14 model configurations across 60
common exercises, forming 840 model--item cells from 924 retained responses.

- [`analysis/data/`](analysis/data/): sanitized model--item score and resource
  panels;
- [`analysis/tables/`](analysis/tables/): aggregate rankings and T1--T8 profiles;
- [`analysis/figures/`](analysis/figures/): publication figures;
- [`analysis/scripts/`](analysis/scripts/): executable chart and website-data
  generators, with an [output-to-source map](analysis/FIGURE_PROVENANCE.md);
- [`results/`](results/): additional aggregate exam-level views;
- [`paper/`](paper/): manuscript and current compiled PDF.

The repository supports method reproduction and exact regeneration of public
chart data and figure families from the sanitized panels. It does not claim
full regeneration of answers or judgments without the private source
artifacts. See
[Reproducibility boundaries](docs/reproducibility.md).

## Data and completed-rubric policy

The source material comes from examination material of the University of
Padua. Source statements, official solutions, and all 60 completed rubrics are
kept outside this repository. Only the general framework and blank templates
are published. See [`DATA_PROVENANCE.md`](DATA_PROVENANCE.md).

## Website

The public repository links to the website but does not distribute its source
code. The site is a presentation layer and is not required to understand or
reuse the benchmark methodology.

## Citation and licences

Citation metadata are available in [`CITATION.cff`](CITATION.cff).

Contributions should follow [`CONTRIBUTING.md`](CONTRIBUTING.md).

- software is licensed under the MIT License;
- original documentation, prompts, schemas, blank templates, aggregate data,
  figures, and paper are licensed under CC BY 4.0;
- third-party names, trademarks, and non-distributed source material are not
  covered by those grants.

See [`LICENSE.md`](LICENSE.md) for the exact scope.

## Author

Francesco Bortot
