# Reproducibility boundaries

Reproducibility is a chain of identities, not merely a code release.

## Record for every campaign

- dataset and item hashes;
- prompt content, version, and hash;
- complete configuration JSON;
- provider, model, endpoint, SDK, and date;
- response text hash and technical metadata;
- rubric, judge prompt, and judge-model versions;
- identity-map and judgment manifests;
- authority and exclusion decisions;
- analysis configuration and output hashes.

## Three reproducibility levels

1. **Method reproducibility:** another researcher can apply the same protocol to
   another dataset. The reusable toolkit supports that level directly.
2. **Analysis reproducibility:** aggregate tables and figures can be checked
   from released sanitized panels. A concrete study can support this by
   distributing a documented, sanitized analysis panel.
3. **Full experimental reproduction:** generation and judging can be repeated
   from identical source items and evidence. This requires private artifacts
   that a study may be unable or unauthorized to distribute, and may still
   differ because provider systems evolve.

## Dated model behavior

Hosted model identifiers can change behavior without repository changes. Treat
every result as bound to its recorded access date and provider metadata. Avoid
claiming that a score permanently characterizes a product family.

## Aggregate-data policy

Published panels should remove credentials, personal paths, private mappings,
response text, and unnecessary provider payloads. Retain only fields required
to verify reported metrics. Document every removed field and aggregation step.
