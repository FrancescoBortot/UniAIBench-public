# Blind-judging protocol

## 1. Freeze before dispatch

Before the first judgment, freeze:

- item and reference versions;
- rubric version and hash;
- judge specification and prompt hash;
- expected response inventory;
- output schema and validator version.

Record those judging-contract artifacts in the private source manifest.
Blind-batch preparation copies the prompt, schema, validator, and its
schema-validation support module into the judge-visible batch and binds every
file by SHA-256 in its manifest. Validation must verify those files before any
answer is dispatched.

## 2. Create anonymous inputs

Assign each response an opaque random identifier. Store a permanent one-to-one
identity map in the private archive containing:

- anonymous response ID;
- source run path or immutable run identifier;
- response hash;
- planned judgment path.

The map must never be included in judge inputs. Verify bijection among source
responses, anonymous IDs, map rows, and planned outputs before dispatch.

## 3. Isolate judgments

Give the judge one response at a time with only:

- anonymous response ID;
- item statement and authorized context;
- verified reference information;
- frozen rubric;
- judging prompt and JSON contract.

Do not provide other answers, previous scores, model names, provider metadata,
or aggregate results.

## 4. Score atomic criteria

For every criterion, record evidence, justification, credit fraction, awarded
points, and primary dimension. Derive T1--T8 by summing criteria. Apply
non-applicable normalization, extraordinary penalties, and predefined caps in
that order.

```text
raw = sum(applicable criterion points)
normalized = 100 × raw / applicable maximum
after penalties = max(0, normalized - extraordinary penalties)
final = min(after penalties, applicable structural cap)
```

## 5. Validate centrally

Reject or repair structurally invalid JSON before unblinding. Check:

- schema validity;
- exact response and item IDs;
- criterion coverage and uniqueness;
- point arithmetic and T1--T8 reconstruction;
- declared cap and penalty arithmetic;
- one judgment per expected response;
- explicit human-review flags.

Validation repairs may correct serialization or arithmetic derived from already
recorded criterion scores. They must not silently change substantive judgment.

## 6. Unblind only after completion

Unblind only when every expected judgment is valid or formally excluded. Apply
the private identity map centrally and create a separate named report. Keep the
anonymous evidence and map unchanged.
