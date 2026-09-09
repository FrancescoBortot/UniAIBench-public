# Publication checklist

The repository remains private until the owner explicitly changes its GitHub
visibility. Publication readiness is assessed in three independent layers.

## 1. Deterministic validation

Run the fast, repeatable checks after every material change:

```bash
make check
make check-strict
```

`make check-strict` validates the required records below. It deliberately does
not require a checkbox saying that `make check-strict` was run, which would
make the gate circular.

## 2. AI-assisted semantic review

- [x] <!-- required:ai-review --> Review the repository for semantic
      inconsistencies, ambiguous publication boundaries, accidental source
      reconstruction, misleading claims, and presentation problems. The dated
      result is recorded in [`PUBLICATION_REVIEW.md`](PUBLICATION_REVIEW.md).

AI review is advisory. It cannot grant rights or authorize publication.

## 3. Human final review

- [x] <!-- required:rights --> The author confirms that the original material
      included in this repository may be published under the declared licences.
- [x] <!-- required:scope --> The author has reviewed the public/private boundary:
      no examination statement, official solution, completed rubric, response
      text, individual judgment, or identity map is distributed here.
- [x] <!-- required:licence --> The licence scope and third-party exclusions in
      [`LICENSE.md`](LICENSE.md) have been reviewed.
- [x] <!-- required:metadata --> README counts, paper date, release version, and
      the official `https://uniaibench.org` URL have been checked.
- [x] <!-- required:aggregate-data --> Aggregate CSV files have been reviewed for
      personal or confidential fields.

The owner must still give a separate explicit instruction before changing the
repository visibility from private to public.

## Release administration

- [x] Create the `v1.0` tag and corresponding private GitHub Release.
- [ ] Change visibility to public only after an explicit owner instruction.
- [ ] Optional: archive the release and add its DOI to `CITATION.cff`.

Unchecked operational and optional items do not make deterministic validation
fail. They are intentionally outside the technical readiness gate.
