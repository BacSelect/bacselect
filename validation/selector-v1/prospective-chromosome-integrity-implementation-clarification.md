# BacSelect selector-v1 chromosome-integrity implementation clarification

**PROSPECTIVE IMPLEMENTATION CLARIFICATION - NO CHROMOSOME-INTEGRITY OUTCOME GENERATED**

This clarification is frozen before BacSelect chromosome-integrity
implementation is executed on the real sequence-eligible candidate universe.

It does not change the scientific chromosome-integrity rule already frozen in
the selector-v1 source-acquisition/eligibility method or post-sequence
eligibility design. It resolves implementation details needed to apply that
rule deterministically and fail closed.

## Parent checkpoint

Parent BacSelect commit:

`a491ff48b74811badbd01d916d6782c7b7aaf5a0`

Frozen post-sequence eligibility design SHA256:

`2c3222421d6b7bb0adbf86a6eb44dae0d0ec7fa1fffcec8bdc1bbf6a0c5d9460`

Frozen post-sequence provenance-refinement SHA256:

`1113bc8b95f60288c8a4767481467f9b2585969f1b8ea3dbd4183caa91710df5`

No BacSelect chromosome-integrity outcome has been generated at this
checkpoint.

## Trigger

Chromosome-integrity review is triggered when both conditions hold:

1. the Primary Assembly contains at least two components whose molecule class
   is `Chromosome`;
2. at least one such chromosome component lacks closure evidence.

The trigger is a review condition. It is not itself evidence that the deposited
chromosome set is fragmented.

## Closure evidence

Closure evidence is present for a chromosome component when either:

1. the GenBank topology is `circular`; or
2. the GenBank definition contains the standalone word `complete`,
   case-insensitively.

The implementation for the definition rule is semantically equivalent to:

`re.search(r"\bcomplete\b", definition, flags=re.IGNORECASE)`

This operationalizes the already frozen requirement that the definition
explicitly identify a complete sequence.

A substring contained only within another word does not qualify. In
particular, `incomplete` and `incompletely` do not provide closure evidence.

This BacSelect rule takes precedence over the historical Project Finch review
extractor's broader implementation, which used substring membership for
`complete`.

Historical extractor SHA256:

`ab8c203424cfcf0f46b1b9c4f94686335f7e5d548b48195cb731d6f476ed5c17`

That historical implementation remains provenance for the original Project
Finch review but is not imported as the BacSelect closure predicate.

## Historical adjudication reuse boundary

The frozen historical Project Finch adjudication artifact is:

- commit:
  `24c75483c8fa6d1bcbaa9e32fe6c4c85efae0d97`
- SHA256:
  `def13131598e351d06c943f8a8e614e49b2c0b4bc55210ac7c9efd20f1f58828`

A historical chromosome-integrity adjudication may be reused only when all of
the following are true:

1. the current canonical GenBank assembly accession.version exactly matches
   the historical adjudication accession.version;
2. the candidate is sourced from the historical Project Finch cache rather
   than from fresh acquisition or fallback reacquisition;
3. BacSelect historical-cache verification for that accession reports
   `cache_content_verification == "pass"`;
4. the current candidate still triggers chromosome-integrity review under the
   BacSelect trigger and closure rule defined above;
5. the exact accession is present in the frozen historical adjudication
   artifact.

No attempt is made to infer equivalence between a newly acquired package and a
historical package.

A fresh package, a fallback-to-fresh package, an unverified cache package, a
different assembly version, or an accession absent from the frozen
adjudication artifact is not eligible for historical adjudication reuse.

The existing BacSelect historical-cache verifier is therefore part of the
reuse provenance boundary.

BacSelect cache-verifier SHA256:

`c0f2114907111ae9f7f89695fefcafa79fe4da3e3ed71acc597c5101db13963d`

The verifier re-hashes the frozen package manifest, component-sequence audit,
small provenance files, and accession-associated package files before an
accession receives `cache_content_verification == "pass"`.

## Historical outcome mapping

For an exactly reusable historical adjudication:

- `RETAIN_CONFIRMED_MULTIPARTITE` means chromosome integrity passes;
- `EXCLUDE_FRAGMENTED_CHROMOSOME_SET` means exclusion for source-replicon
  integrity;
- `UNRESOLVED` remains unresolved and is withheld.

BacSelect does not convert historical `UNRESOLVED` into evidence that a
chromosome set is fragmented.

For a currently triggered candidate without an exactly reusable historical
adjudication, the outcome is unresolved and the candidate is withheld.

No new identity-aware, organism-aware, literature-based or manual adjudication
is performed during the blinded selector-resolution phase.

## Non-triggered candidates

A source-truth-eligible candidate that does not trigger chromosome-integrity
review passes this chromosome-integrity layer without consulting historical
manual adjudications.

Historical adjudications are not used to alter non-triggered candidates.

## Fail-closed behavior

Malformed or internally inconsistent evidence must not be silently interpreted.

The implementation must fail closed on inputs that prevent deterministic
evaluation of:

- canonical accession.version;
- Primary Assembly membership;
- chromosome molecule classification;
- GenBank topology;
- GenBank definition evidence;
- historical cache-verification state;
- historical adjudication outcome.

An unknown historical adjudication outcome is an error, not a new category.

## Blinding and execution boundary

The chromosome-integrity implementation must not read or use:

- OPS or SR selector outcomes;
- selector distances;
- panel identities;
- panel membership;
- selector coverage results;
- structural-feature values.

Testing is synthetic-only until the implementation and its tests have been
frozen in Git.

No real BacSelect chromosome-integrity outcome is generated by this
clarification.
