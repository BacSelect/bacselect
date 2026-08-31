# Prospective monthly sequence-acquisition completion

## Status

This document defines the pure release-level completion contract for BacSelect
monthly Stage 3B sequence acquisition.

It does not execute Stage 3B.

It does not discover filesystem paths.

It does not modify the frozen Stage 3B batch executor.

## Purpose

The frozen Stage 2 sequence-plan record already defines the complete monthly
fresh-acquisition population and the exact expected number of Stage 3B batches.

The frozen Stage 3B executor produces one final directory per completed batch.

Before those batches can be treated as an authoritative completed acquisition
stage, BacSelect requires a release-level completion seal.

## Expected population

The completion contract first audits:

- current source-snapshot ID;
- current source-snapshot-record SHA256;
- Stage 2 sequence-plan record;
- Stage 2 fresh-target manifest.

The Stage 2 record determines:

- fresh-acquisition count;
- frozen batch size;
- expected batch count.

The fresh-target manifest determines the exact accession, BioSample and
acquisition-reason membership of every expected batch.

## Deterministic batch identities

Expected final batch IDs are exactly:

`batch-00001` through `batch-NNNNN`.

For every expected index, the target population is re-derived from the exact
Stage 2 fresh-target manifest using the frozen Stage 3B batch size.

The completion contract reuses the frozen Stage 3B target-manifest and
accession-list identity functions.

## Discovery completeness

The filesystem executor must report:

- every discovered final batch ID;
- every discovered partial batch ID;
- any malformed or unexpected batch-like entry.

The pure contract requires:

- final batch IDs exactly equal the expected set;
- no duplicate final batch;
- no missing expected batch;
- no extra final batch;
- no partial batch;
- no unexpected batch-like entry.

A completion seal cannot be generated otherwise.

## Batch-summary validation

Each final batch summary must:

- use the frozen Stage 3B summary schema;
- be in the frozen canonical Stage 3B JSON representation;
- have result `PASS`;
- bind the same source snapshot;
- bind the same source-snapshot record;
- bind the exact Stage 2 sequence-plan record;
- bind the exact Stage 2 fresh-target manifest;
- bind the expected origin Git commit;
- bind the frozen NCBI Datasets version;
- bind the expected frozen NCBI environment;
- have the exact expected batch index and batch count;
- use the frozen batch size;
- report the exact full fresh-target count;
- report the exact expected number of accessions for that batch;
- report the correct first and last accession.

## Exact batch membership

For each batch, the completion contract independently derives:

- batch-target-manifest SHA256;
- accession-list SHA256.

The values must agree with:

1. the exact Stage 2-derived batch population;
2. the Stage 3B batch summary;
3. independently re-hashed persisted batch artifacts supplied by the executor.

## Persisted artifact read-back

The executor must independently re-hash the persisted:

- batch-targets manifest;
- accession list;
- dehydrated ZIP;
- Datasets `fetch.txt`;
- attempt-origin record;
- candidate-sequence audit;
- component-sequence audit;
- package-files manifest.

The observed identities must equal the identities bound by the final Stage 3B
summary.

## Package-file verification

The Stage 3B `package-files.tsv` manifest is not sufficient by itself to prove
that the persisted package contents remain intact.

Before a release-level completion seal is constructed, the filesystem executor
must independently re-hash every file represented by that manifest.

The pure contract receives:

- the exact persisted `package-files.tsv` bytes;
- one read-back observation for every package file;
- each observed relative path;
- each observed file size;
- each observed SHA256.

The pure contract requires:

- the `package-files.tsv` SHA256 to equal the identity bound by the Stage 3B
  summary;
- the manifest to use the frozen Stage 3A package-file schema;
- canonical, unique and sorted package paths;
- the read-back path set to equal the manifest path set exactly;
- no missing, extra or duplicate read-back observation;
- every observed size to equal the manifest size;
- every observed SHA256 to equal the manifest SHA256;
- the verified package-file count to equal the Stage 3B summary count.

A deterministic SHA256 over the complete verified read-back population is
stored in the release-level completion record.

The pure contract therefore does not accept a caller-provided boolean as proof
of package revalidation.

## Scientific audit population

The number of candidate-sequence audit rows must equal the exact expected
target count for the batch.

The component-audit population cannot contain fewer rows than the candidate
population.

The completion contract does not reinterpret sequence eligibility or structural
biology.

## Zero-fresh release

A valid Stage 2 plan may contain:

- fresh-acquisition count: zero;
- expected batch count: zero.

This is a valid completed Stage 3B acquisition stage.

Its completion record contains:

- completed batch count: zero;
- completed accession count: zero;
- an empty batch list.

No fake Stage 3B batch is created.

The future completion executor must not invoke the Stage 3B batch executor for
this state.

## Non-zero release

For a non-zero Stage 2 fresh population, a completion seal is generated only
when:

- exactly all expected final batches exist;
- no partial or unexpected batch-like entries exist;
- every final summary passes the completion audit;
- every exact batch target identity agrees with Stage 2;
- every required persisted artifact re-hashes correctly;
- every package file has been independently reverified;
- the sum of completed batch target counts equals the complete Stage 2 fresh
  population.

## Completion record

The canonical completion record binds:

- source-snapshot ID;
- source-snapshot-record SHA256;
- origin Git commit;
- NCBI environment SHA256;
- Stage 2 sequence-plan-record SHA256;
- Stage 2 fresh-target-manifest SHA256;
- fresh-acquisition count;
- batch size;
- expected batch count;
- completed batch count;
- completed accession count;
- one deterministic row per completed batch.

Each batch row binds:

- batch ID;
- batch index;
- batch-summary SHA256;
- batch-target-manifest SHA256;
- accession-list SHA256;
- requested accession count;
- first and last accession;
- candidate-audit SHA256;
- component-audit SHA256;
- package-files SHA256;
- package-file count;
- package-file read-back count;
- package-file read-back evidence SHA256;
- fetch-entry count.

## Cumulative cache boundary

This completion record proves only the completeness of the current release's
fresh Stage 3B acquisition stage.

It is not itself the cumulative BacSelect cache catalogue.

After this contract and its filesystem executor are frozen, BacSelect must
define a cumulative sequence-cache catalogue that combines:

- previously authoritative reusable cache entries; and
- newly completed Stage 3B acquisitions.

That cumulative catalogue becomes the authoritative discovery source for the
next month's cache-verification executor.

## Production wiring

This pure contract does not enable:

- Stage 3B execution;
- monthly workflow execution;
- NCBI retrieval;
- cache reuse;
- Zenodo publication;
- website publication.
