# Publication readiness review

- **Review date:** 10 September 2026
- **Repository version:** v1.0
- **Repository visibility:** private
- **Official website:** https://uniaibench.org

## Review status

- `AI_REVIEW_STATUS: PASSED`
- `HUMAN_RIGHTS_STATUS: CONFIRMED`
- `PUBLIC_VISIBILITY_STATUS: NOT_AUTHORIZED`

## Deterministic review

The repository validator checks required files, local Markdown links, JSON
syntax, credential patterns, absolute local paths, forbidden private-artifact
paths in the current tree and Git history, source exercise filenames, completed
rubrics, sensitive CSV headers, official URL consistency, release metadata, and
the required publication-review records.

The complete local gate is:

```bash
make check-strict
```

GitHub Actions additionally rebuilds public figures, compiles the paper, and
validates `CITATION.cff`. A separate scheduled workflow checks external links.
The repository includes a 1280 x 640 first-party social-preview image under
`docs/assets/`, together with its editable SVG source and the official project
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

The public repository was reviewed for internal consistency across the README,
documentation, prompts, schemas, aggregate tables, model catalog, chart
programs, paper, licences, and provenance statement. No examination text,
official solution, completed item-specific rubric, model-answer text,
individual judgment, or private identity map was identified.

AI review is a risk-reduction measure, not a legal opinion and not publication
authorization.

## Human confirmation

The author confirmed that the original material included in this repository may
be published. Third-party examination material remains outside the repository
and outside the licences granted here. The final decision to change GitHub
visibility remains a separate manual action by the repository owner.
