# BacSelect monthly Stage 9 complete universe

## Status

This document prospectively freezes the monthly Stage 9 complete-universe
execution boundary before the first monthly complete-universe artifact is
generated.

Stage 9 adds no source, sequence, chromosome-integrity or taxonomy decision
rule.

## Scientific definition

The monthly complete universe contains exactly every candidate whose current
monthly Stage 8 taxonomy decision is:

`PASS`

Every member therefore has:

- passed the monthly source-truth gate;
- continued through repeated-BioSample reconciliation;
- passed chromosome-integrity evaluation;
- resolved successfully to a canonical species TaxID under the frozen monthly
  taxonomy snapshot.

A candidate withheld or excluded at any earlier layer is not reconsidered by
Stage 9.

## Stage 8 input authority

Stage 9 authenticates the canonical monthly Stage 8:

- taxonomy-resolution decisions;
- taxonomy-resolution record;
- taxonomy-resolution completion receipt;
- Stage 8 execution commit;
- authenticated Stage 7 completion identity.

The Stage 8 completion SHA256 is an explicit production input.

Stage 9 does not rerun taxonomy resolution.

## Frozen complete-universe primitive

The frozen validation and serialization primitive is:

`src/bacselect/source_complete_universe.py`

Stage 9 reuses:

- `CompleteUniverseRecord`;
- `require_complete_universe()`;
- `complete_universe_membership_sha256()`;
- `complete_universe_rows()`.

Monthly Stage 9 does not call the historical:

- `derive_complete_universe()`;
- terminal-composition reconstruction;
- Stage 5A production wrapper.

This is deliberate.

The historical Stage 5A workflow composed the complete Stage 1-4 decision
chain for selector-validation evidence. Monthly production already has a
completed, authenticated Stage 8 terminal taxonomy boundary. Reconstructing
historical terminal composition would add no new scientific decision and would
reintroduce obsolete stage semantics.

## No baseline or holdout

Monthly Stage 9 does not:

- reconstruct the historical selector-validation baseline;
- intersect current membership with a historical baseline;
- construct an external holdout;
- reconstruct historical absence;
- consult selector-resolution evidence.

The current complete monthly universe itself is the source population for
selector-v1 production.

## Canonical universe

Each Stage 8 PASS row becomes exactly one:

`CompleteUniverseRecord(accession, species_taxid)`

The universe is sorted lexicographically by canonical versioned GenBank
assembly accession.

Both accession and species TaxID are validated by the frozen primitive.

The expected monthly universe count and distinct species count are bound by the
authenticated Stage 8 completion receipt.

## Deterministic identities

Stage 9 freezes two content identities in addition to the artifact SHA256.

### Accession membership SHA256

The accession membership SHA256 uses the frozen BacSelect
`complete_universe_membership_sha256()` semantics:

- accession-sorted;
- one canonical accession per line;
- newline delimited;
- SHA256 over the exact membership payload.

### Accession to species mapping SHA256

The accession/species mapping SHA256 is computed over accession-sorted,
headerless ASCII rows:

`<canonical accession>\t<species TaxID>\n`

for every complete-universe member.

This fingerprint distinguishes universes with identical accession membership
but different species-group assignment.

## Canonical artifacts

The Stage 9 directory is:

`complete-universe`

The partial execution directory is:

`complete-universe.partial`

The canonical universe artifact is:

`complete-universe.tsv`

with exactly two columns:

1. `canonical_genbank_assembly_accession`;
2. `species_taxid`.

The canonical Stage 9 record is:

`monthly-complete-universe-record.json`

with schema:

`bacselect-monthly-complete-universe-record-v1`

The completion receipt is:

`complete-universe-completion-v1.json`

with schema:

`bacselect-monthly-complete-universe-completion-v1`

and terminal status:

`COMPLETE_UNIVERSE_EXECUTION_COMPLETE`

## Provenance

The Stage 9 record binds at minimum:

- monthly release ID;
- source snapshot ID;
- source production commit;
- taxonomy snapshot ID;
- taxonomy-snapshot execution commit;
- taxonomy-resolution execution commit;
- complete-universe execution commit;
- Stage 8 decisions SHA256;
- Stage 8 record SHA256;
- Stage 8 completion SHA256;
- frozen complete-universe primitive SHA256;
- complete-universe count;
- distinct species-TaxID count;
- accession-membership SHA256;
- accession/species-mapping SHA256;
- complete-universe artifact SHA256.

## Stage boundary

Stage 9 constructs the complete monthly eligible universe only.

It does not:

- calculate structural features;
- populate or update the structural-feature cache;
- calculate monthly percentile coordinates;
- choose species representatives;
- run OPS;
- construct public panel prefixes;
- publish GitHub or website release artifacts;
- publish to Zenodo.

Those remain later stages.

## Atomicity

Existing final, partial, temporary or completion paths are never overwritten.

Stage 1 through Stage 8 are reauthenticated before final directory publication
and again before completion publication.

A Stage 9 directory without its valid completion receipt is incomplete and
does not authorize Stage 10.
