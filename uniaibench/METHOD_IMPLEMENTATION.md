# How UniAIBench instantiates the reusable method

This document identifies which choices belong specifically to UniAIBench v1.1
and how they relate to the generic workflow under
[`benchmark-toolkit/`](../benchmark-toolkit/). It is a traceability map, not a
replacement for the paper or the toolkit guides.

| Generic stage | UniAIBench v1.1 decision | Public evidence |
|---|---|---|
| Define scope | Advanced open-ended Mathematical Analysis III and General Physics II tasks; one item per request | [`STUDY_MANIFEST.json`](STUDY_MANIFEST.json), paper |
| Record provenance | University of Padua examination material; source text and solutions kept outside this repository | [`DATA_PROVENANCE.md`](DATA_PROVENANCE.md) |
| Select solvers | 17 explicitly versioned model--mode configurations | [`profile/evaluated-models.md`](profile/evaluated-models.md), `analysis/data/model_catalog.json` |
| Freeze evaluation | Item-specific atomic 100-point rubrics organized by T1--T8, created before target responses were inspected | Paper methodology; generic rubric contract in the toolkit |
| Generate answers | Direct provider APIs, closed-resource condition, no web, tools, retrieval, calculators, or code execution | Paper methodology; generic solver prompt and harness in the toolkit |
| Blind judgments | One anonymous answer at a time, separated from the private model-identity map | Paper methodology; generic blind-judging protocol in the toolkit |
| Validate and adjudicate | Deterministic artifact validation followed by versioned human decisions for genuine ambiguities | Paper methodology; generic validators and adjudication protocol in the toolkit |
| Unblind and aggregate | Unblinding only after batch validation; matched comparison across the common 60-item panel | `analysis/data/`, `analysis/config/public_analysis.json`, the public table generator, and `analysis/tables/` |
| Report | Correctness, T1--T8 profiles, token use, estimated cost, latency, coverage, and limitations | `analysis/figures/site/`, paper, and [uniaibench.org](https://uniaibench.org) |

## What is deliberately not generalized

The following are study choices, not toolkit defaults:

- the University of Padua source material;
- the two subjects and 60-item sample;
- the 17 evaluated model--mode configurations;
- the benchmark date and recorded provider prices;
- the observed scores, tokens, costs, response times, and failures;
- the exact completed rubrics and all protected response-level artifacts.

A new benchmark should define these independently and document its own source
rights, sampling logic, validity threats, execution contract, and reporting
scope.

## Dependency rule

The relationship is one-way: this study may use contracts or programs from
`benchmark-toolkit/`, but reusable toolkit code and configuration must never
import or reference `uniaibench/`. The repository checks this automatically so
that third-party reuse does not silently depend on this study's data.
