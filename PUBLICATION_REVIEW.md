# Publication readiness review

> **Current status (21 September 2026):** the publication review was completed
> successfully before release, and UniAIBench v1.0 is publicly available.

- **Review date:** 12 September 2026
- **Repository version:** v1.0
- **Current repository visibility:** public
- **Official website:** https://uniaibench.org

## Review outcome

- `AI_REVIEW_STATUS: PASSED`
- `HUMAN_RIGHTS_STATUS: CONFIRMED`
- **Repository publication:** completed after review

## Deterministic review

The repository validator checks required files, local Markdown links, JSON
syntax, source-exercise filenames, sensitive CSV headers, official URL
consistency, release metadata, and the required publication-review records. It
rejects forbidden private-artifact paths in both the working tree and Git
history. It also scans the current text files and every reasonably sized UTF-8
text blob reachable from Git history for credential patterns, absolute local
paths, and the shapes of private workflow artifacts: identity maps, source and
blind-batch manifests, item-specific rubrics, individual judgments,
adjudications, and unblinded results. Only the canonical, semantically blank
templates are exempt. Files named `.env` are rejected by path and never opened.
The validator additionally verifies that reusable toolkit code and
configuration do not depend on the UniAIBench study tree.

The complete local gate is:

```bash
make check-strict
```

GitHub Actions additionally rebuilds public figures, compiles the paper, and
validates `CITATION.cff`. A separate scheduled workflow checks external links.
The repository includes a 1280 x 640 first-party social-preview image under
`uniaibench/assets/`, together with its editable SVG source and the official project
symbol. Its typography, colours, copy, and composition follow the visual system
used by `https://uniaibench.org` rather than an independent repository theme.
The standalone analysis-figure directory contains exactly eight current
English SVGs corresponding to the website evidence views. The overall ranking
is also used by the README. These are generated data visualizations rather than
screenshots, making them sharp at every display size and auditable across
platforms. Superseded, Italian, article-specific, and unreferenced exports are
excluded, while every program needed for the paper and website chart families
remains available.

## AI-assisted semantic review

The public repository was reviewed for internal consistency across its two
explicit namespaces: `uniaibench/` for the concrete v1.0 study and
`benchmark-toolkit/` for the reusable method. Documentation, prompts, schemas,
aggregate tables, model catalog, chart programs, paper, licences, and
provenance were included in that review. No examination text,
official solution, completed item-specific rubric, model-answer text,
individual judgment, or private identity map was identified.

AI review is a risk-reduction measure, not a legal opinion.

## Human confirmation

The author confirmed that the original material included in this repository may
be published. Third-party examination material remains outside the repository
and outside the licences granted here. The repository was published after the
review and rights checks were completed.
