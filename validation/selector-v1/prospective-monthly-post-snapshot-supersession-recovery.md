# Prospective monthly post-snapshot supersession recovery

## Status

**Prospective recovery correction.**

This method is frozen before any real recovery execution under this
failure class and before any selector outcome is generated from recovered
evidence.

The failure class was observed during monthly acquisition before this
correction was designed. Accordingly, this document is prospective with
respect to the **recovery method and downstream use**, not prospective with
respect to discovery of the external-database condition.

## Purpose

BacSelect freezes a monthly source snapshot and derives an immutable set of
fresh acquisition targets from that snapshot.

An external assembly database remains mutable after the BacSelect snapshot
has been frozen. A target that was current at snapshot time may subsequently
be superseded while the same monthly release is still acquiring sequence
evidence.

The ordinary monthly Stage 3 metadata validator must continue to fail closed
when an acquisition-time assembly record is no longer current. This recovery
exists only to preserve the already-frozen monthly identity when the change
can be proven to be post-snapshot accession supersession.

This recovery does not redefine the monthly source universe.

## Failure class

The generic failure class is:

`post_snapshot_accession_supersession`

The class applies only when every affected target satisfies all of the
following:

1. The accession is an exact member of the frozen monthly fresh-target
   manifest.
2. The frozen source snapshot contains exactly one record for that accession.
3. In the frozen source snapshot:
   - the assembly status is `current`;
   - the current accession equals the target accession;
   - the assembly level is `Complete Genome`;
   - the BioSample equals the frozen target BioSample.
4. The acquisition-time Datasets metadata contains exactly one record for the
   same frozen accession.
5. In the acquisition-time record:
   - the assembly status is `previous`;
   - the current accession differs from the frozen target accession;
   - the assembly level remains `Complete Genome`;
   - the BioSample still equals the frozen target BioSample.
6. Every other target in the batch either remains valid under the ordinary
   frozen monthly metadata contract or independently satisfies this same
   generic supersession class.
7. The ordinary wrapper stopped before accepting the batch as finalized.
8. The failed source `.partial` is retained unchanged.

Any different metadata change is outside this recovery class.

Examples outside the class include:

- BioSample reassignment;
- assembly-level loss;
- missing or duplicate metadata records;
- target accession absent from the frozen snapshot;
- target accession already non-current in the frozen snapshot;
- metadata identity disagreement that is not explained solely by
  post-snapshot supersession.

Those states continue to fail closed.

## Frozen accession remains authoritative

The frozen accession is the BacSelect identity for the monthly release.

The acquisition-time successor accession is **evidence of the temporal
change only**.

The recovery must not:

- replace the frozen accession with its successor;
- substitute a paired RefSeq accession;
- regenerate the fresh-target manifest;
- modify the source snapshot;
- modify the metadata-eligibility result;
- rerun selection against a newer universe;
- silently reinterpret the target as the successor assembly.

The recovery requests and validates sequence evidence for the exact accession
that was frozen in the monthly source snapshot.

## Recovery workspace

The failed ordinary source `.partial` is immutable.

Recovery occurs in a separate commit-scoped workspace outside ordinary
`sequence-acquisition`.

The generic recovery-authority implementation in
`src/bacselect/monthly_sequence_recovery_authority.py` is reused.

Preparation must:

1. Fingerprint the entire preserved source `.partial`.
2. Fingerprint its package.
3. Write those source manifests into the recovery workspace.
4. Copy the package with metadata-preserving copy semantics.
5. Verify the copied package is initially byte-for-byte equivalent by strict
   content manifest.
6. Recheck the source `.partial` after copying.
7. Perform all subsequent retrieval and validation only on the recovery copy.

## Temporal-drift evidence

Recovery must create cause-specific evidence separate from the generic
authority summary.

At minimum, the cause-specific evidence records, for every affected target:

- frozen accession;
- frozen BioSample;
- frozen snapshot assembly status;
- frozen snapshot current accession;
- frozen snapshot assembly level;
- acquisition-time assembly status;
- acquisition-time current accession;
- acquisition-time assembly level;
- acquisition-time BioSample;
- source-snapshot evidence SHA256;
- acquisition-time metadata evidence SHA256;
- classification:
  `post_snapshot_accession_supersession`.

The evidence must preserve the original target order.

The generic `recovery-summary.json` remains the exact cause-agnostic schema
required by the frozen recovery-authority implementation. Cause-specific
fields must not be added to that summary.

## Metadata recovery semantics

The ordinary monthly metadata validator remains unchanged.

A separate recovery metadata validator may accept an acquisition-time
`previous` status only after proving the complete failure-class contract
against the frozen source snapshot.

For recovered targets:

- snapshot-time currentness supplies the monthly currentness authority;
- the exact frozen accession remains the target identity;
- the acquisition-time record proves the later supersession;
- BioSample and Complete Genome constraints must still agree;
- the successor accession is recorded but is never substituted.

For unaffected targets in the same recovered batch, ordinary monthly metadata
semantics are reproduced exactly.

## Transport

The recovery may hydrate or retrieve evidence only for the exact frozen
accessions already present in the frozen batch.

The preferred first transport path is the original Datasets package/fetch
contract copied from the failed source partial.

The recovery must not infer a successor accession from a filename, redirect,
paired accession, or naming convention.

If exact frozen-accession transport cannot be completed, recovery fails.
That state is not converted into sequence ineligibility.

Any additional transport fallback requires its own prospective contract
unless already covered by a previously frozen generic recovery mechanism.

## Scientific validation

After exact frozen-accession sequence evidence is present, the scientific
sequence checks must remain equivalent to the ordinary monthly Stage 3
science.

Recovery must preserve:

- exact target accession;
- exact BioSample;
- Complete Genome requirement;
- Primary Assembly component semantics;
- exact FASTA/component identity;
- exact GBFF/component identity;
- component-length agreement;
- FASTA versus GBFF sequence equality;
- topology interpretation;
- ambiguous-base accounting;
- sequence eligibility and exclusion semantics.

Post-snapshot supersession is not itself sequence ineligibility.

## Batch semantics

Recovery is batch-preserving.

It must retain:

- every frozen target in the batch;
- the exact target order;
- the ordinary candidate/component schemas;
- ordinary scientific results for unaffected targets;
- recovered scientific results for affected targets.

The recovery does not create a reduced batch containing only superseded
targets.

## Finalization

Before finalization:

1. The source `.partial` fingerprint must still equal its frozen recovery
   source fingerprint.
2. The recovery package must be fully fingerprinted.
3. Cause-specific supersession evidence must validate.
4. Candidate and component audits must validate.
5. The generic recovery-authority pre-final audit must pass.

The recovery directory is then atomically renamed from `.partial` to final.

The finalized recovery is re-audited using the same authority implementation.

## Authority resolution

The existing generic authority resolver is reused.

For each expected batch:

- ordinary final only -> `fresh`;
- preserved source `.partial` plus exactly one valid finalized recovery ->
  `fresh-recovery`;
- ordinary final plus recovery -> fail;
- partial without accepted recovery -> fail;
- recovery without preserved source partial -> fail;
- multiple recoveries -> fail;
- source fingerprint mismatch -> fail;
- unfinished recovery partial -> fail;
- no provider -> fail.

The recovery cause does not alter these authority semantics.

## Completion and cache catalogue

Sequence-acquisition completion and sequence-cache catalogue must eventually
use the same recovery-aware authority resolution.

They must independently validate the authoritative provider and evidence
hashes.

No recovery may be accepted by completion while being interpreted as an
ordinary finalized source batch by the cache catalogue.

## Downstream source class

Recovered batches remain explicitly classified as:

`fresh-recovery`

They are not silently canonicalized as ordinary `fresh`.

Downstream source-truth logic already distinguishes `fresh-recovery`; this
provenance must be retained.

## Prohibited shortcuts

The following are prohibited:

- accepting acquisition-time `previous` globally in ordinary Stage 3;
- replacing a frozen accession with its successor;
- replacing GenBank evidence with paired RefSeq evidence;
- changing the monthly target set;
- changing the frozen source snapshot;
- editing the failed source `.partial`;
- manually injecting files into ordinary `sequence-acquisition`;
- classifying temporal supersession as sequence ineligibility;
- choosing a recovery by newest timestamp or directory ordering;
- accession-specific exceptions.

## Prospectivity boundary

Before implementation of this correction is frozen:

- no real supersession recovery is executed;
- no preserved incident partial is modified;
- no successor accession is substituted;
- no selector outcome is generated from recovered evidence;
- no monthly source identity is changed.

Only synthetic recovery fixtures may be used during implementation and
testing.
