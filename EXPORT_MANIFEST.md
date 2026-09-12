# Publication repository manifest

This repository is a clean, publication-oriented derivative of the complete
private UniAIBench research archive. It has an independent Git history.

## Included: the concrete study

- a machine-readable UniAIBench v1.0 study manifest;
- aggregate result panels, tables, eight selected English website figures,
  and all programs used to create the public paper and website chart families;
- a versioned public analysis configuration and byte-for-byte table
  regeneration check;
- the dated 14-configuration model catalog and pricing record;
- manuscript source and compiled paper;
- study provenance and an explicit mapping from the generic method to the
  concrete implementation;
- a link to the separately deployed website.

## Included: the reusable toolkit

- general benchmark-design, implementation, statistical-analysis, and
  extension guidance;
- the complete T1--T8 framework;
- blank rubric and judgment templates with JSON Schemas;
- reusable prompts for solver, rubric builder, judge, and adjudicator roles;
- generic tools for blind-batch preparation, validation, adjudication,
  unblinding, and aggregation;
- a generic multi-provider harness and configuration templates;
- study-independent tests and an enforced one-way dependency boundary.

## Included: repository governance

- deterministic publication-safety and structure checks;
- citation metadata and explicit licence boundaries;
- a human-reviewed publication checklist and review record.

## Excluded

- all source exercise statements and official solutions;
- all completed item-specific rubrics, including drafts and corrected versions;
- all model answer text and provider-native response payloads;
- all individual judgments, blind inputs, identity maps, and adjudications;
- retry archives, internal experiments, self-review campaigns, and Router work;
- work-in-progress exam-level analyses;
- the website source and generated Atlas;
- credentials, local paths, environments, dependencies, caches, and build
  products;
- the private repository's Git history.

The two public namespaces are intentionally different: `uniaibench/` contains
claims and evidence about one dated study, while `benchmark-toolkit/` contains
only reusable contracts and tools. The toolkit must not depend on the study.
