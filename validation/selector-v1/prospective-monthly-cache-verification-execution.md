# Prospective monthly cache-verification execution

## Status

This document defines the portable filesystem execution boundary for the
already-frozen BacSelect monthly cache-verification contract.

It does not alter:

- the frozen monthly cache-verification contract;
- the frozen monthly sequence-cache catalogue;
- the frozen Stage 2 sequence planner;
- source eligibility;
- source fingerprinting;
- source-truth semantics.

It does not perform:

- NCBI retrieval;
- sequence acquisition;
- cloud upload;
- Zenodo publication;
- website publication;
- workflow orchestration.

## Purpose

The executor reconstructs the complete deterministic cache-candidate population
for the current metadata-retained monthly universe, independently re-reads the
persisted evidence represented by the cumulative sequence-cache catalogue,
invokes the frozen cache verifier, and publishes the exact pure-contract
artifacts needed by Stage 2.

## Inputs

Execution requires:

- current Stage 1 production root;
- completed current metadata-eligibility evidence;
- the complete materialized prior sequence-cache catalogue history;
- a materialized BacSelect authoritative object namespace.

The authoritative object namespace root contains keys returned by the frozen:

`monthly_authoritative_storage.object_key_for_sha256()`

function.

Physical provider identity is not part of the scientific evidence.

## Explicit authorization

The command line requires:

`--authorize-real-execution`

Absence of this flag fails before production execution.

## Repository preflight

Before execution the wrapper proves:

- `HEAD` equals the explicitly supplied execution commit;
- local `origin/main` equals that commit;
- the repository is clean;
- the frozen metadata executor remains byte-identical;
- the frozen sequence-cache catalogue executor remains byte-identical;
- the frozen cache-verification contract, tests and method remain
  byte-identical;
- the frozen Stage 2 sequence-plan implementation remains byte-identical;
- source eligibility remains byte-identical;
- source fingerprinting remains byte-identical;
- source-truth execution remains byte-identical;
- this execution method, wrapper and wrapper tests have their expected
  identities.

No remote Git query is required.

## Current Stage 1 and metadata authority

The executor reuses the frozen monthly metadata executor's Stage 1 loader.

It therefore re-audits:

- release-start checkpoint;
- raw source response;
- source-snapshot record;
- exact release ID;
- exact source-snapshot ID;
- execution Git commit;
- frozen NCBI Datasets identity;
- production-root placement.

The completed metadata stage must contain exactly:

- `metadata-eligibility-assessments.jsonl`;
- `metadata-eligibility-summary.json`;
- `metadata-eligibility-record.json`.

The executor independently re-audits all three artifacts and then re-derives
the exact metadata execution completion receipt.

The metadata artifacts and completion receipt are read again before the current
metadata authority is accepted.

Only `RETAIN_METADATA` assessments form the current cache-verification metadata
universe.

## Prior catalogue discovery

Previous catalogue discovery reuses the frozen cumulative catalogue executor.

The supplied production root must contain the complete materialized canonical
catalogue history.

The complete chain is audited from `GENESIS` through the latest successful
catalogue.

The current release and later releases must not already contain a canonical
catalogue.

For a non-empty chain, the latest successfully chained catalogue is the sole
source catalogue for current cache-candidate reconstruction.

The executor records a deterministic identity over the complete discovered
chain, not only the latest catalogue.

## First-release proof

An empty pure cache candidate input is not accepted merely because no catalogue
file was found.

When prior catalogue history is empty, the executor additionally scans every
earlier canonical monthly production namespace in the supplied production root.

Genesis cache verification is rejected if an earlier canonical production
namespace contains:

- `sequence-acquisition/`;
- `sequence-acquisition-completion.json`;
- `sequence-cache-catalogue.json`.

This establishes the filesystem-level first-release proof over the supplied
complete materialization.

The orchestration layer remains responsible for ensuring that the materialized
production history supplied to this executor is complete with respect to
durable authoritative storage.

The executor does not make a network request to prove that external
materialization.

## Candidate completeness

For a non-empty prior catalogue, candidate input is reconstructed
deterministically from the complete latest catalogue.

A catalogue entry is considered for cache verification exactly when:

- its accession is retained by the current metadata stage;
- `origin_sequence_eligibility = eligible`;
- `origin_sequence_exclusion_reasons = none`.

No current BioSample-match filter is applied during candidate discovery.

A BioSample change must reach the frozen cache verifier, which records
`current_biosample_mismatch` and requires fresh acquisition.

A retained accession absent from the catalogue is not fabricated as a cache
candidate.

It will receive no verified-cache row and Stage 2 will therefore apply its
already-frozen `no_verified_cache` rule.

An origin sequence-ineligible catalogue entry remains acquisition evidence but
is not materialized as `MonthlyCacheCandidate`.

## Batch provenance reconstruction

Every materialized candidate references one audited catalogue
batch-provenance record.

Before candidates from that batch are admitted, the executor independently
resolves and re-hashes the SHA-addressed objects for:

- batch summary;
- candidate audit;
- component audit;
- package-files manifest;
- origin sequence-acquisition completion.

The batch summary is first audited using the frozen sequence-acquisition
completion transport-summary auditor. This requires the exact Stage 3B summary
schema, canonical JSON, frozen schema version and `PASS` result.

The audited batch summary must then agree with the catalogue provenance for:

- source snapshot;
- origin Git commit;
- requested accession count;
- accession-list SHA256;
- candidate-audit SHA256;
- component-audit SHA256;
- package-files SHA256.

The origin completion is first audited with the frozen cumulative catalogue
completion auditor. This requires exact canonical completion schema, release,
source-snapshot and Git identities, deterministic batch ordering, accession
accounting and package read-back accounting.

The audited origin completion must then contain the matching batch and agree on:

- batch ID;
- requested accession count;
- accession-list SHA256;
- batch-summary SHA256;
- candidate-audit SHA256;
- component-audit SHA256;
- package-files SHA256;
- package-file read-back SHA256.

The candidate, component and package TSVs are parsed using the already-frozen
Stage 3A field schemas and the frozen catalogue canonical TSV parser.

Malformed or missing batch-common provenance fails the complete verification
run.

It is not silently converted to a per-accession cache miss.

## Batch-common package evidence

Package-manifest rows that are not accession-scoped are batch-common evidence.

Those SHA-addressed objects must be present and match exact expected size and
SHA256 before the batch provenance prerequisite is considered verified.

This includes shared package evidence such as the batch assembly-data report.

Accession-scoped package objects are handled separately below.

## Accession package reconstruction

For every candidate, the catalogue entry's accession-scoped package artifacts
must agree exactly with the accession-scoped rows in the authenticated origin
package-files manifest.

Each artifact binds:

- NCBI package-relative path;
- BacSelect logical path;
- expected byte size;
- expected SHA256.

The executor resolves each artifact through the SHA-addressed object namespace.

For accession-scoped objects:

- missing object produces an unpopulated observed read-back;
- present object has its actual size and SHA256 recorded;
- symbolic links or non-regular object entries fail closed.

Missing, size-mismatched or SHA-mismatched accession package objects are
therefore passed to the frozen verifier as ordinary read-back observations.

The frozen verifier alone assigns:

- `package_file_missing`;
- `package_file_size_mismatch`;
- `package_file_sha256_mismatch`.

## Primary Assembly sequence reconstruction

The authenticated candidate audit supplies:

- candidate FASTA basename;
- candidate FASTA SHA256;
- Primary Assembly component count.

The authenticated component audit supplies:

- component accession;
- length;
- topology;
- raw sequence SHA256.

When the candidate FASTA object has exact expected size and SHA256, the
executor parses that exact SHA-addressed object using the frozen
source-truth FASTA parser.

Every required Primary Assembly component must be present.

The reconstructed component sequence is then passed to
`MonthlyCacheCandidate`.

If the FASTA object itself is missing or fails package read-back identity, the
executor supplies placeholder component sequence text only so that the frozen
verifier can apply the earlier package-failure rule.

It does not fabricate verified sequence evidence.

## Frozen verifier invocation

Candidate objects are passed unchanged in meaning to:

`verify_cache_candidates()`

with:

- current source-snapshot ID;
- complete current retained accession-to-BioSample mapping.

The executor does not duplicate:

- component identity;
- topology-aware assembly fingerprint;
- source-evidence identity;
- per-accession package-manifest identity;
- candidate verification-record identity.

Those remain owned by the frozen pure contract.

## Repeated read-back before publication

Before publication, the executor repeats:

- current metadata audit;
- prior catalogue-chain discovery;
- candidate reconstruction from the authoritative object namespace;
- frozen cache verification;
- all three pure-contract serializations.

The second result must be byte-identical to the first.

A source catalogue, metadata artifact or required object that changes during
execution therefore prevents publication.

A package object that changes from a cache miss to valid evidence, or vice
versa, also prevents publication rather than allowing execution timing to
determine reuse.

## Scientific output stage

The canonical stage is:

`<stage1 root>/cache-verification/`

The incomplete stage is:

`<stage1 root>/cache-verification.partial/`

The completed stage contains exactly:

1. `cache-verification-results.jsonl`;
2. `verified-cache-evidence.jsonl`;
3. `cache-verification-record.json`.

All files are mode `0644`.

The directory is mode `0755`.

The three files are exactly the canonical payloads defined by the frozen pure
cache-verification contract.

No execution-only fields are inserted into those scientific artifacts.

## Cache-verification record

The frozen cache-verification record is built from:

- current source-snapshot ID;
- current source-snapshot-record SHA256;
- metadata record SHA256;
- metadata completion SHA256;
- metadata-retained count;
- exact results JSONL;
- exact verified-cache evidence JSONL.

Its candidate-input count therefore records the exact candidate population
actually supplied to the frozen verifier.

## Execution completion receipt

After the scientific stage has been promoted and independently re-audited, the
executor publishes:

`<stage1 root>/cache-verification-completion.json`

This receipt is execution provenance, not a fourth pure-contract scientific
artifact.

It binds:

- release ID;
- current source-snapshot ID;
- current source-snapshot-record SHA256;
- execution Git commit;
- metadata-record SHA256;
- metadata-completion SHA256;
- retained metadata count;
- catalogue-history mode;
- complete catalogue-chain count and SHA256;
- latest source-catalogue release, SHA256, entry-set SHA256 and entry count when
  present;
- number of retained origin-eligible catalogue entries reconstructed as
  candidates;
- results SHA256;
- verified-cache-evidence SHA256;
- cache-verification-record SHA256;
- candidate-input count;
- verified-cache count;
- fallback-to-fresh count.

For first-release execution, source-catalogue identity fields are null and
counts are zero.

## Publication

Scientific stage construction is fail-closed:

1. refuse an existing canonical stage;
2. refuse an existing partial stage;
3. refuse an existing completion receipt;
4. create a fresh mode-0755 partial directory;
5. create each scientific file using exclusive creation;
6. fsync and read back each file;
7. audit all three frozen contracts;
8. fsync the partial directory;
9. repeat current metadata, catalogue and object reconstruction;
10. require byte-identical repeated pure outputs;
11. create the canonical stage directory using exclusive `mkdir`;
12. hard-link each already-audited scientific artifact from the partial stage
    into the canonical stage with no overwrite;
13. fsync and independently read back the canonical stage;
14. require exact byte equality with the already-audited candidate payloads;
15. remove the partial-stage links only after successful canonical read-back;
16. fsync the Stage 1 root;
17. independently re-audit the completed stage;
18. publish the completion receipt using a temporary inode plus no-clobber hard
    link;
19. fsync and read back the completion receipt;
20. audit its exact deterministic bytes.

Neither `os.rename()` nor `os.replace()` is used to publish the scientific
stage. A competing canonical directory or artifact therefore cannot be
overwritten by this executor.

The completion receipt also uses no-clobber hard-link publication.

## Failure semantics

Malformed execution provenance fails the run.

Examples include:

- broken catalogue chain;
- missing origin batch artifact;
- corrupt batch artifact;
- missing origin completion object;
- malformed canonical TSV;
- candidate audit disagreement with catalogue entry;
- component audit disagreement;
- catalogue package artifact absent from its authenticated package manifest;
- missing batch-common package object;
- symbolic-link substitution;
- duplicate accession evidence;
- candidate completeness mismatch.

Ordinary accession-scoped package read-back failure is not malformed
provenance.

It is represented to the frozen verifier and results in fresh acquisition.

## Portability

The executor contains no:

- PHF filesystem path;
- Slurm dependency;
- Project Finch dependency;
- historical validation-root dependency;
- NCBI request;
- cloud-provider SDK;
- Zenodo call.

The only subprocess use is inherited local Git repository identity checking.

## Stage 2 boundary

Only `verified-cache-evidence.jsonl` is suitable for reconstruction as
`VerifiedMonthlyCacheEvidence`.

The Stage 2 production writer must require the matching
`cache-verification-completion.json` before consuming that payload.

The Stage 2 production writer remains a separate next implementation.
