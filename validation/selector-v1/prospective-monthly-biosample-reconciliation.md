# Prospective monthly repeated-BioSample reconciliation

## Status

This document freezes the pure monthly BacSelect Stage 5 contract before any
monthly Stage 5 production execution is enabled.

Stage 5 adds no new repeated-BioSample scientific rule.

## Upstream boundary

Stage 5 begins only after monthly Stage 4 source truth is complete.

The Stage 4 decision table is authoritative for continuation.

Before Stage 5 derives any population membership, the exact SHA256 of the
Stage 4 decision table must equal the `decisions_sha256` authenticated by the
current Stage 4 completion receipt.

A syntactically valid subset, superset, alternate serialization, or different
Stage 4 decision table is therefore not accepted merely because its rows pass
the Stage 4 decision parser.

Only candidates whose Stage 4 `source_truth_status` is `SUITABLE` enter
Stage 5.

Stage 4 `EXCLUDE_SOURCE_TRUTH` and `REVIEW_UNRESOLVED` candidates are terminal
at the source-truth layer and do not participate in BioSample grouping,
fingerprint comparison, or representative selection.

A Stage 4 terminal candidate cannot influence which accession represents a
repeated BioSample.

## BioSample identity

For every Stage 4 `SUITABLE` accession, Stage 5 uses the BioSample already
bound in the current retained monthly metadata evidence.

Every Stage 5 accession must map to exactly one non-empty current BioSample.

Missing or contradictory BioSample evidence fails closed.

No BioSample identity is inferred from organism name, taxonomy, accession
history, prior panel membership, or selector outcome.

## Frozen scientific implementation

The repeated-BioSample scientific rule remains the already frozen
`reconcile_repeated_biosamples()` implementation in:

`src/bacselect/source_post_sequence_eligibility.py`

Monthly Stage 5 delegates through the already frozen
`reconcile_verified_candidates()` implementation in:

`src/bacselect/source_repeated_biosample_execution.py`

No alternative reconciliation implementation is permitted.

## Frozen source-evidence binding and fingerprint

Production execution will reconstruct the authenticated sequence evidence for
every Stage 4 `SUITABLE` accession and call the already frozen:

`fingerprint_stage2_candidate()`

That primitive:

1. reconstructs the candidate Primary Assembly components;
2. recomputes the frozen `source_evidence_sha256`;
3. requires exact equality to the source-evidence SHA recorded by Stage 4;
4. computes the frozen topology-aware assembly fingerprint.

The topology-aware fingerprint implementation remains:

`src/bacselect/source_fingerprint.py`

The Stage 4 `sequence_set_sha256` is not a substitute for the topology-aware
assembly fingerprint.

The pure monthly Stage 5 contract does not read FASTA, candidate audit,
component audit, package evidence, or authoritative storage.

It accepts only `VerifiedBioSampleFingerprint` records produced after that
evidence verification.

## Exact population invariant

The verified fingerprint population must equal the Stage 4 `SUITABLE`
population exactly.

For every candidate:

- accession must match;
- BioSample must match current metadata;
- `source_evidence_sha256` must match the Stage 4 decision;
- assembly fingerprint must be a valid lowercase SHA256.

Missing candidates, extra candidates, duplicate candidates, BioSample drift,
or source-evidence drift fail closed.

## Frozen repeated-BioSample rule

For a BioSample with one continuing member:

- status: `CONTINUE`;
- reason: `BIOSAMPLE_SINGLETON`.

For a repeated BioSample whose members have one identical assembly
fingerprint:

- the lexicographically smallest canonical versioned GCA accession is
  `CONTINUE`;
- its reason is `BIOSAMPLE_IDENTICAL_REPRESENTATIVE`;
- every other member is `NONREPRESENTATIVE`;
- their reason is `BIOSAMPLE_IDENTICAL_NONREPRESENTATIVE`.

For a repeated BioSample with two or more distinct assembly fingerprints:

- every member is `REVIEW_UNRESOLVED`;
- every reason is `BIOSAMPLE_FINGERPRINTS_DIFFER`.

No historical manual adjudication is consulted.

## Determinism

Stage 5 identity is canonical versioned GCA accession.

All output decisions are sorted by accession.

Input fingerprint ordering cannot alter the result.

Repeated-BioSample grouping is based only on current BioSample and verified
topology-aware assembly fingerprint.

Acquisition route, batch identity, filesystem ordering, taxonomy, organism
identity, prior panel membership, and selector output cannot affect Stage 5
scientific decisions.

## Pure Stage 5 decision artifact

The deterministic decision fields are:

- `canonical_genbank_assembly_accession`;
- `biosample`;
- `source_evidence_sha256`;
- `assembly_fingerprint`;
- `biosample_status`;
- `biosample_reason`.

The decision artifact therefore binds the exact verified fingerprint evidence
used by the repeated-BioSample decision.

## Pure Stage 5 record

Schema:

`bacselect-monthly-biosample-reconciliation-record-v1`

Status:

`MONTHLY_BIOSAMPLE_RECONCILIATION_COMPLETE`

The record binds:

- release ID;
- source-snapshot ID;
- origin Git commit;
- Stage 4 source-truth decision SHA256;
- Stage 4 source-truth record SHA256;
- Stage 4 source-truth completion SHA256;
- Stage 4 `SUITABLE` count;
- Stage 4 `SUITABLE` membership SHA256;
- Stage 5 decision count;
- Stage 5 decision artifact SHA256;
- total BioSample-group count;
- singleton-group count;
- repeated-group count;
- identical repeated-group count;
- differing repeated-group count;
- deterministic Stage 5 status counts;
- deterministic Stage 5 reason counts.

The auditor reconstructs the Stage 4 `SUITABLE` population, revalidates every
decision row, reruns the frozen reconciliation from the recorded verified
fingerprints, and reconstructs the exact canonical record bytes.

## Accounting invariants

The following identities must hold:

`CONTINUE + NONREPRESENTATIVE + REVIEW_UNRESOLVED = Stage 4 SUITABLE count`

`singleton groups + repeated groups = all Stage 5 BioSample groups`

`identical repeated groups + differing repeated groups = repeated groups`

No expected production outcome count is frozen prospectively.

## Fail-closed behaviour

The pure contract fails on:

- malformed Stage 4 decisions;
- Stage 4 decision-table SHA256 disagreement with the authenticated Stage 4
  completion;
- empty Stage 4 `SUITABLE` population;
- missing current BioSample;
- malformed accession;
- malformed source-evidence SHA;
- missing verified candidate;
- extra verified candidate;
- duplicate verified candidate;
- BioSample disagreement;
- Stage 4 source-evidence disagreement;
- malformed assembly fingerprint;
- unexpected frozen reconciler status/reason;
- incomplete decision coverage;
- reordered or duplicated serialized decisions;
- decision output that differs from a fresh invocation of the frozen
  reconciler;
- record identity mismatch;
- impossible group accounting.

## Downstream boundary

Only Stage 5 `CONTINUE` candidates may proceed to monthly Stage 6 structural
or chromosome-component integrity.

`NONREPRESENTATIVE` and `REVIEW_UNRESOLVED` are terminal at the repeated
BioSample layer.

A later Stage 6 failure does not promote a Stage 5 nonrepresentative as a
replacement representative.

Stage 5 does not inspect or generate:

- chromosome-integrity outcomes;
- taxonomy outcomes;
- monthly eligible-universe membership;
- structural features;
- OPS/SR distances;
- panel identities;
- selector outcomes.

## Identity blindness

Stage 5 does not inspect organism popularity, clinical importance, taxonomy,
previous BacSelect panel membership, or any desired final panel size.

The only representative rule is the frozen repeated-BioSample rule above.

## Execution boundary

A separate portable monthly Stage 5 executor will later:

1. authenticate the current Stage 4 completion and recover its exact
   `decisions_sha256`;
2. authenticate the exact Stage 4 decision artifact against that completion;
3. authenticate the current cumulative sequence-evidence catalogue;
4. reconstruct each Stage 4 `SUITABLE` candidate from current local or
   authoritative historical evidence;
5. call frozen `fingerprint_stage2_candidate()`;
6. pass only verified fingerprint records to this pure contract;
7. write and re-audit canonical Stage 5 artifacts;
8. publish a fail-closed Stage 5 completion receipt.

That executor is intentionally not part of this pure contract freeze.
