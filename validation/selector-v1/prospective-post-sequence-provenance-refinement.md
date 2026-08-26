# BacSelect selector-v1 prospective post-sequence provenance refinement

## Status

**PROSPECTIVE PROVENANCE REFINEMENT — NO POST-SEQUENCE OUTCOME GENERATED**

This checkpoint is an additive provenance refinement to the post-sequence
eligibility design frozen at BacSelect commit
`236170fc797088bd0657882a44aaf4ec08e02e14`.

It does not alter any scientific eligibility rule, precedence rule,
chromosome-integrity rule, taxonomy rule, holdout rule, or blinding rule.

No real post-sequence eligibility outcome has been generated.

## Reason for refinement

The frozen Project Finch source-truth batch worker delegates sequence
equivalence and full-containment operations to a separate containment driver.

The original post-sequence implementation-reference table bound the batch
worker and the source-truth adjudicator but did not independently bind that
transitive driver.

The chromosome-integrity design also permits exact reuse of historical Project
Finch adjudications only when accession.version and relevant source evidence
are unchanged. The historical evidence extractor, correction semantics and
adjudication artifact therefore require explicit provenance identities.

## Transitive source-truth implementation

The exact Project Finch containment implementation is now bound by
`post-sequence-transitive-implementation-references.tsv`.

The production source-truth wrapper is also bound as provenance that the
genome-wide source-truth worker consumed the exact containment-driver SHA256
recorded here.

The inherited containment semantics include origin-independent treatment of
circular molecules.

No structural-feature extreme-selection logic from the historical driver is
inherited by BacSelect. Only the sequence-equivalence, containment and
associated source-evidence primitives required by the already frozen
BacSelect source-truth procedure are algorithmic provenance.

## Chromosome-integrity provenance

The exact Project Finch source-replicon evidence extractor, its tests, the
historical correction implementation and tests, and the frozen historical
source-replicon adjudication artifact are now cryptographically bound.

Historical adjudications remain reusable only under the rule already frozen
at commit `236170fc797088bd0657882a44aaf4ec08e02e14`:

- identical canonical accession.version;
- unchanged, content-verified historical source package;
- unchanged relevant Primary Assembly component identities, sequences,
  topology and closure evidence.

No historical adjudication is generalized to another accession, another
assembly version or changed evidence.

A novel or unmatched chromosome-integrity trigger remains withheld unresolved.

## Prospective boundary

This refinement was frozen before:

- current repeated-BioSample outcomes;
- current source structural-integrity outcomes;
- BacSelect chromosome-integrity outcomes;
- BacSelect taxonomy acquisition or resolution;
- complete eligible fresh-universe membership;
- external decision-holdout membership;
- external structural-feature outcomes;
- OPS/SR selector outcomes.

The original prospective post-sequence eligibility design remains unmodified.
