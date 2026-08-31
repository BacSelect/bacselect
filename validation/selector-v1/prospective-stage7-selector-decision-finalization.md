# Prospective Stage 7 selector-decision finalization

## Status

**PROSPECTIVE FINALIZATION METHOD — NO SELECTOR DECISION HAS BEEN READ OR GENERATED**

This document freezes the only authorized procedure for converting the already
completed and independently reproduced blinded Stage 7 analysis into the final
BacSelect selector-v1 OPS-versus-SR decision.

At the time this method is created:

- Stage 7 production is complete;
- the independent rebuild is complete;
- all six scientific artifacts are byte-identical between the two runs;
- aggregate-only Stage 7 completion evidence is committed and pushed;
- no selector outcome has been generated;
- no selector decision has been finalized;
- panel identities remain blinded;
- the real primary-metric values and exact selector products have not been read
  for decision finalization.

No real selector-decision read is permitted until this document, the finalizer
implementation and its synthetic tests are separately frozen, committed and
pushed.

## Governing frozen contracts

The scientific rule remains governed by:

`validation/selector-v1/prospective-selector-resolution-design.md`

SHA256:

`2584fddf1f06562c6cdb855a334da29840cb05df27724f08d6e010b56b7a332c`

The Stage 7 execution contract remains:

`validation/selector-v1/prospective-stage7-selector-resolution-execution.md`

SHA256:

`6f0e540cdc9def82a1645546196994817d3d75aabf8ed38a40dc062c1366ff45`

The Stage 7 completion barrier is:

`validation/selector-v1/stage7-selector-resolution-completion-evidence.json`

SHA256:

`bec926b41538ea231b2d9f3f0825a33ab358f764b8fdf3cf448ab35faf97b9d8`

This finalization method operationalizes those frozen contracts. It does not
alter the selector rule.

## Frozen Stage 7 implementation identities

The finalizer must bind and verify the following existing analysis
implementation/test identities before any decision input is interpreted:

- `src/bacselect/selector_resolution.py`
  `a972dd2d9e611a4c121c0cd6a9efebca9509adcf96ced3c0a02c570e4e570979`
- `tests/test_selector_resolution.py`
  `f2f9d52902c0a8e7819fe85ba9bbe2087f44e35c2d554727fadd10729635c90b`
- `src/bacselect/selector_resolution_artifacts.py`
  `6df58f9b4e49efa4b0b7f9139b9402a2af3d2b8b7a5f0095bc9291831bf2e00a`
- `tests/test_selector_resolution_artifacts.py`
  `74303f78169007b91b126a11c051777dd6f049d88c18e145548462849a691835`
- `src/bacselect/selector_resolution_analysis.py`
  `b228cc234e871593c1ce33e99d8bf7aa36c98fae8f7429cdf98117ded1cd81e6`
- `tests/test_selector_resolution_analysis.py`
  `8dc4c32ac3c087096f02a544a5d4921b2151c124709931b0a264251ba9223829`
- `src/bacselect/selector_resolution_execution.py`
  `24cb559f906529d5f1599159f560463b5226629000079e9691cd5d430a5a5ddf`
- `tests/test_selector_resolution_execution.py`
  `1bbeb9423080f95fe4fe47d2d9239035d6e034a44b1d37243ef6f01e3c5b3ea3`

The finalizer implementation and its own tests will receive separate SHA256
bindings after implementation and before real execution.

## Frozen byte-identity evidence

The aggregate-only selector-resolution byte-identity verification record has
SHA256:

`e8071eb213a716fd13d0eb747758cda3d9bc0791d07a909a4f3da0b938bde473`

The pushed Stage 7 completion evidence freezes:

`all_scientific_artifacts_byte_identical=true`

The finalizer must fail closed unless:

1. the completion-evidence SHA256 is exact;
2. the byte-identity-record SHA256 is exact;
3. all six per-artifact production/rebuild SHA256 pairs remain equal;
4. all six byte-identical booleans are true;
5. the aggregate byte-identical boolean is true;
6. both finalized run identities match the frozen completion evidence.

## Frozen decision-input artifact identities

The finalizer may use only the production copies of these three scientific
artifacts as interpreted decision inputs:

1. `selector-primary-metrics.tsv`
   SHA256
   `7d734bf39dc9dd974d7e9947ddca2697febd933d51d456959ee3571fa72b6855`
2. `selector-exact-products.json`
   SHA256
   `d84eb7eef0053aaea52a77ab81740a9cc708c0d790bf32fe3a6d3aae01ee46c3`
3. `selector-resolution-analysis-summary.json`
   SHA256
   `ac1f8551ac75457f7f6d6eab8bed75a0251929ee9ed723026993a13070d39ea1`

The corresponding independent-rebuild artifacts must have the same SHA256
values.

The finalizer does not need to interpret:

- projected holdout coordinates;
- genome-level nearest-panel distances;
- descriptive diagnostics.

Their frozen SHA256 identities remain part of the completion and byte-identity
evidence and must remain unchanged.

## Frozen final ladder fingerprints

The only valid final deterministic baseline ladder fingerprints are:

- OPS:
  `c81d9fd30cda2d49f0f6c81d4bf99dace9fff811c7612036d9265ef90707fa13`
- SR:
  `3c703f5f898e0a13c6eb8568c0b83f5b0d19d4e374155d2d3a8a4e20378bd51f`

The authoritative fingerprint namespace is:

`BacSelect-selector-v1|final300-2400|{selector}|ladder|N=500`

Historical pre-final fingerprints are invalid for finalization.

## Finalizer predecision gate

Before opening any interpreted decision-input artifact, the finalizer must
verify:

1. repository HEAD equals the prospectively frozen finalizer execution commit;
2. local `origin/main` equals that same commit;
3. the Git working tree is clean;
4. this prospective finalization method SHA256 is exact;
5. the selector-resolution prospective design SHA256 is exact;
6. the Stage 7 execution-method SHA256 is exact;
7. the Stage 7 completion-evidence SHA256 is exact;
8. all frozen existing Stage 7 implementation/test SHA256 values are exact;
9. the finalizer implementation/test SHA256 values are exact;
10. the byte-identity verification-record SHA256 is exact;
11. both finalized analysis-run envelopes exist;
12. all frozen scientific-artifact SHA256 values match completion evidence;
13. all six production/rebuild scientific artifact pairs remain byte-identical;
14. the final OPS and SR ladder fingerprints are exact;
15. completion evidence states
    `identity_bearing_outputs_committed_to_git=false`;
16. completion evidence states `selector_outcome_generated=false`;
17. completion evidence states `selector_decision_finalized=false`.

Any failure stops finalization before product interpretation.

## Primary-metric table contract

After all predecision checks pass, the finalizer may parse the frozen production
`selector-primary-metrics.tsv`.

It must require exactly:

- UTF-8 text;
- header:
  `selector<TAB>N<TAB>weighted_p95`;
- exactly 12 data rows;
- OPS rows first at N=10,20,50,100,200,500;
- SR rows second at N=10,20,50,100,200,500;
- no duplicate selector/panel-size pair;
- no additional columns;
- each stored `weighted_p95` text parses to a finite non-negative binary64
  value;
- canonical deterministic `.17g` serialization reproduces the complete input
  bytes exactly.

The finalizer must not use the primary-metric values as a secondary criterion.

## Exact-product artifact contract

The finalizer may then parse the frozen production
`selector-exact-products.json`.

It must require exactly:

- canonical UTF-8 JSON;
- `schema_version` equal to 1;
- `status` equal to `STAGE7_EXACT_PRODUCTS_COMPLETE`;
- `selectors` containing exactly `OPS` and `SR`;
- each selector containing exactly `numerator` and `denominator`;
- each numerator is an integer greater than or equal to zero;
- each denominator is an integer greater than zero;
- no outcome, winner or fallback field;
- canonical frozen serialization reproduces the complete input bytes exactly.

For each selector the parsed exact rational value is:

`Fraction(numerator, denominator)`

The parsed fraction must already be reduced, meaning its numerator and
denominator must equal the parsed stored integers after `Fraction`
construction.

## Independent recomputation check

Before resolving OPS versus SR, the finalizer must independently reconstruct
both exact products from the 12 stored primary-metric binary64 values using the
already frozen primitive:

`exact_six_size_product`

For each selector and each N in:

`10,20,50,100,200,500`

the parsed binary64 value is passed through the frozen rule:

`Fraction.from_float(float(d(S,N)))`

The recomputed OPS and SR exact products must equal the corresponding exact
fractions parsed from `selector-exact-products.json`.

Any mismatch fails closed.

## Analysis-summary contract

The finalizer must verify the production
`selector-resolution-analysis-summary.json` SHA256 and canonical schema.

The summary must remain blinded and non-decisional.

At minimum it must bind the exact SHA256 values of:

- `selector-primary-metrics.tsv`;
- `selector-exact-products.json`.

It must not contain:

- primary metric values;
- exact product numerators or denominators;
- a winner;
- a selector outcome;
- genome identities;
- species identities;
- panel identities.

## Single authorized selector comparison

Only after every preceding verification succeeds may the finalizer perform the
decision comparison.

It must call the already frozen exact resolver:

`resolve_exact_products(ops_product, sr_product)`

exactly once for the real decision.

The rule is immutable:

- OPS product strictly lower than SR product -> `OPS`;
- SR product strictly lower than OPS product -> `SR`;
- exact equality -> `UNRESOLVED`.

There is:

- no tolerance;
- no significance test;
- no equivalence margin;
- no secondary metric;
- no diagnostic override;
- no manual override;
- no fallback criterion.

## Selector-decision record

A successful finalizer writes exactly one aggregate selector-decision record
outside Git first.

The record may contain:

- schema version;
- finalization status;
- selector decision: `OPS`, `SR` or `UNRESOLVED`;
- exact OPS product numerator and denominator;
- exact SR product numerator and denominator;
- SHA256 of the primary-metric artifact;
- SHA256 of the exact-product artifact;
- SHA256 of the analysis-summary artifact;
- SHA256 of the byte-identity verification record;
- SHA256 of the Stage 7 completion evidence;
- frozen OPS and SR final ladder fingerprints;
- frozen design, method, implementation, finalizer and environment identities;
- finalizer execution commit.

The selector-decision record must not contain:

- any genome accession;
- any species identity;
- any holdout row key;
- any panel member identity;
- any raw feature value;
- any projected coordinate;
- any genome-level distance.

The record must be serialized deterministically and written atomically.

## Decision-record Git freeze

The selector-decision record does not authorize panel unblinding merely by
existing in scratch.

After generation:

1. audit the record against this frozen method;
2. verify its deterministic byte identity;
3. commit only the aggregate selector-decision record to Git;
4. push that commit;
5. verify local `HEAD == origin/main` and a clean working tree.

Only after the selector-decision record itself is committed and pushed may the
post-decision boundary open.

## Post-decision boundary

Only after the pushed selector-decision record exists may BacSelect:

- unblind the winning frozen baseline ladder for audit;
- generate official selector-v1 nested panels;
- package a public selector-v1 release;
- enable publication automation.

If the decision is `UNRESOLVED`, no winning ladder exists and no fallback
selector may be substituted.

Until the decision-record push succeeds:

- panel identities remain blinded;
- no official selector-v1 panel is generated;
- no selector-v1 public release is packaged;
- no monthly selector publication is enabled.

## Synthetic implementation tests required before real finalization

Finalizer implementation tests must use synthetic fixtures only.

They must cover at minimum:

1. exact completion-evidence identity is required;
2. byte-identity verification record identity is required;
3. any false per-artifact byte-identity flag blocks finalization;
4. aggregate byte identity must be true;
5. finalized production and rebuild identities must match;
6. all six scientific artifact hashes must match the frozen evidence;
7. primary-metric header must be exact;
8. primary-metric table must contain exactly 12 rows;
9. primary-metric row ordering must be exact;
10. primary-metric panel-size set must be exactly 10,20,50,100,200,500;
11. duplicate primary-metric rows are rejected;
12. additional primary-metric columns are rejected;
13. non-finite primary values are rejected;
14. negative primary values are rejected;
15. non-canonical primary-metric serialization is rejected;
16. exact-product schema must be exact;
17. exact-product selector set must be exactly OPS and SR;
18. non-integer numerator or denominator is rejected;
19. negative numerator is rejected;
20. zero or negative denominator is rejected;
21. non-reduced stored rational products are rejected;
22. non-canonical exact-product serialization is rejected;
23. exact products must independently recompute from primary metrics;
24. a product mismatch blocks the decision;
25. analysis summary must bind the primary-metric artifact SHA256;
26. analysis summary must bind the exact-product artifact SHA256;
27. identity-bearing fields in decision inputs are rejected;
28. outcome-bearing fields in predecision analysis inputs are rejected;
29. strictly lower OPS product resolves to OPS;
30. strictly lower SR product resolves to SR;
31. exact product equality resolves to UNRESOLVED;
32. no secondary tie-breaker exists;
33. final decision record contains no genome/species/panel identity;
34. final decision serialization is deterministic;
35. finalizer refuses real execution unless its own implementation and tests are
    frozen at exact SHA256 values;
36. finalizer refuses real execution unless repository HEAD and `origin/main`
    equal the frozen execution commit;
37. finalizer refuses real execution with a dirty working tree.

No test may open or parse the real production or rebuild primary-metric,
exact-product or analysis-summary artifacts.

## Failure semantics

Finalization fails closed if any frozen identity, artifact hash, byte-identity
condition, schema, serialization, recomputation or exact-decision condition is
violated.

A failure does not authorize:

- modifying the Stage 7 analysis artifacts;
- recomputing Stage 7 with altered inputs;
- changing OPS or SR;
- changing panel sizes;
- altering the percentile rule;
- altering weighted-p95;
- introducing a tolerance;
- introducing a secondary criterion;
- manually choosing a selector;
- unblinding either baseline ladder.

All failed evidence is preserved.

## Current authorization boundary

At this prospective method creation:

`FINALIZER_PROSPECTIVE_METHOD_FROZEN=no`

`FINALIZER_IMPLEMENTATION_FROZEN=no`

`SELECTOR_DECISION_EXECUTION_AUTHORIZED=no`

`SELECTOR_DECISION_FINALIZED=no`

`PANEL_UNBLINDING_AUTHORIZED=no`

The real selector products remain unopened for decision finalization.
