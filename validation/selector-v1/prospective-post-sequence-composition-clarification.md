# BacSelect selector-v1 post-sequence composition clarification

**PROSPECTIVE COMPOSITION CLARIFICATION - NO REAL CANDIDATE OUTCOME GENERATED**

This document fixes the execution order and terminal-state semantics used to
compose already frozen selector-v1 post-sequence eligibility rules.

It is frozen before the post-sequence composition implementation is executed
on the real provisional sequence-eligible candidate pool.

It does not alter the scientific eligibility rules. It resolves ordering that
must be deterministic before those rules are composed.

## Parent checkpoint

Parent BacSelect commit:

`806d35a8deafd9bbbd6eca272719c227b51478b0`

Frozen post-sequence eligibility design SHA256:

`2c3222421d6b7bb0adbf86a6eb44dae0d0ec7fa1fffcec8bdc1bbf6a0c5d9460`

Frozen chromosome-integrity implementation clarification SHA256:

`c13114780c6788f4b9541d6428edf1d2e0827ff3797541b848ec1570a57ac30b`

Frozen primitive SHA256 identities:

- `source_fingerprint.py`
  `6c994d243709abdbe9d7c8949e156009b9f31f3fcef3247cc3c5679e2fff41c9`
- `source_truth.py`
  `6aac349e591daebfc2569c14633cc807b5d7186ed4ed3e79f37f6627f5184486`
- `source_taxonomy.py`
  `9c8c4149c5db2a757e8c201a6523bdb113511b5f72a4dd2893572dd8c7928e4d`
- `source_chromosome_integrity.py`
  `04f1b580ec9480a20f3679b7eb996da08a074c48ff246549df2e0ed20b97b9c0`

No real post-sequence composition outcome has been generated at this
checkpoint.

## Composition principle

Candidate-local, identity-independent source-truth eligibility is evaluated
before repeated-BioSample representative selection.

Repeated-BioSample reconciliation is then applied only among members that
remain source-truth suitable.

Chromosome-component integrity is evaluated only for candidates that survive
repeated-BioSample reconciliation.

Taxonomy is resolved only for candidates that remain otherwise eligible after
those layers.

Baseline membership is not an input to any of these steps.

## Stage 1: source structural integrity

Every current sequence-eligible candidate is independently classified using
the frozen BacSelect source-truth implementation.

A source-truth result of `SUITABLE` continues to repeated-BioSample
reconciliation.

A result of `EXCLUDE_SOURCE_TRUTH` is a terminal scientific exclusion for the
complete eligible fresh universe.

A result of `REVIEW_UNRESOLVED` is terminal withholding for the blinded
selector-resolution experiment.

An excluded or unresolved source-truth candidate does not participate in
repeated-BioSample representative selection.

This prevents evidence already judged unsuitable or unresolved by the
identity-independent source-truth rule from determining which otherwise
suitable representation survives a BioSample group.

## Stage 2: repeated-BioSample reconciliation

Repeated-BioSample grouping is evaluated among source-truth-`SUITABLE`
candidates using the frozen BioSample identity and topology-aware assembly
fingerprint semantics.

For a BioSample with zero continuing members, no member continues.

For a BioSample with exactly one continuing member, that member continues
without a repeated-BioSample exclusion or unresolved state.

For a BioSample with two or more continuing members:

1. compute the frozen topology-aware assembly fingerprint for every continuing
   member;
2. if all fingerprints are identical, retain exactly the lexicographically
   smallest canonical versioned GCA accession as the representative;
3. mark all other continuing members as non-representative duplicate
   representations;
4. if two or more distinct fingerprints occur, withhold every continuing
   member of that BioSample as unresolved.

A source-truth-excluded or source-truth-unresolved member is never reinstated,
relabelled as a duplicate representation, or used to choose the
representative.

No historical manual repeated-BioSample adjudication is consulted.

## Stage 3: chromosome-component integrity

Only a candidate that survives repeated-BioSample reconciliation is evaluated
at the chromosome-integrity layer.

The frozen BacSelect chromosome-integrity implementation determines whether
the candidate passes, is excluded for source-replicon integrity, or is
withheld unresolved.

Historical Project Finch chromosome adjudication reuse remains governed
strictly by the separately frozen chromosome-integrity clarification.

Chromosome-integrity outcomes do not cause a previously non-representative
BioSample member to be promoted as a replacement representative.

This ordering prevents accession-specific historical adjudication availability
from influencing deterministic repeated-BioSample representative selection.

## Stage 4: taxonomy

Taxonomy is resolved only for a candidate that has:

- source-truth status `SUITABLE`;
- survived repeated-BioSample reconciliation; and
- passed chromosome-component integrity.

The structured organism TaxID from the frozen BacSelect source snapshot is
first normalized through the frozen BacSelect taxonomy snapshot.

Normalization must return a resolved TaxID with status `PASS`.

The first lineage ancestor whose rank is exactly `species` is then resolved.

Species resolution must return a species TaxID with status `PASS`.

Deleted, missing, cyclic, lineage-unresolved or no-species-ancestor outcomes
are candidate-level unresolved taxonomy states and are withheld from the
complete eligible fresh universe.

A malformed or internally inconsistent frozen taxonomy snapshot is a
run-level fail-closed error rather than a candidate classification.

The resolved species TaxID is the grouping identity. A species name is
descriptive only.

## Terminal composition dispositions

The composition layer uses four high-level dispositions:

- `ELIGIBLE`
- `EXCLUDED`
- `WITHHELD_UNRESOLVED`
- `NONREPRESENTATIVE`

The high-level disposition does not replace primitive reason codes.

The composition record must also preserve the terminal layer and the
underlying deterministic reason.

The terminal layer is one of:

- `source_truth`
- `repeated_biosample`
- `chromosome_integrity`
- `taxonomy`
- `eligible`

Examples:

- source-truth biological exclusion:
  `EXCLUDED`, terminal layer `source_truth`;
- differing repeated-BioSample fingerprints:
  `WITHHELD_UNRESOLVED`, terminal layer `repeated_biosample`;
- identical repeated-BioSample non-representative:
  `NONREPRESENTATIVE`, terminal layer `repeated_biosample`;
- fragmented chromosome-set exclusion:
  `EXCLUDED`, terminal layer `chromosome_integrity`;
- unresolved chromosome integrity:
  `WITHHELD_UNRESOLVED`, terminal layer `chromosome_integrity`;
- unresolved taxonomy:
  `WITHHELD_UNRESOLVED`, terminal layer `taxonomy`;
- candidate passing all stages:
  `ELIGIBLE`, terminal layer `eligible`.

Unknown primitive status values, impossible state combinations or missing
required evidence are errors and must fail closed.

## Complete eligible fresh universe

Only records with final composition disposition `ELIGIBLE` enter the complete
eligible fresh universe.

Identity-bearing complete-universe output remains outside Git and is frozen by
count plus cryptographic fingerprint before structural-feature calculation.

## External decision holdout

Only after the complete eligible fresh universe is frozen is frozen baseline
membership consulted.

The external decision holdout is:

complete eligible fresh universe
intersect
`retained_absent_from_baseline`

Baseline membership must not alter source truth, repeated-BioSample
reconciliation, chromosome integrity, taxonomy or complete-universe
membership.

## Blinding boundary

The composition implementation must not read or use:

- OPS outcomes;
- SR outcomes;
- selector distances;
- panel identities;
- panel membership;
- selector coverage;
- structural-feature values.

Testing and differential validation remain synthetic-only until the composition
implementation and tests are frozen in Git.

No real BacSelect post-sequence composition outcome is generated by this
clarification.
