# BacSelect historical cache content-verification implementation

## Status

**PROSPECTIVE IMPLEMENTATION — CACHE CONTENT NOT YET RE-HASHED**

This implementation is frozen after the cache-reuse acquisition design and
before expensive full-content verification of the historical Project Finch
sequence snapshot.

It performs no network access and downloads no sequence data.

## Purpose

BacSelect may reuse historical Project Finch source-sequence evidence only when
the evidence remains byte-identical to its frozen package manifests and its
batch-level provenance remains intact.

The verifier converts that policy into a deterministic, fail-closed procedure.

## Historical evidence contract

The historical snapshot contains:

- 111 batches;
- 55,426 unique historical candidate accessions;
- 166,844 package-manifest rows.

All 111 batches were produced with NCBI Datasets 18.35.0 and environment lock
SHA256:

`6d965c7c4f7db0464e4fba2434f85f1b7da3f7136790babca444888b6e6096cd`

Four recorded historical snapshot-script identities are accepted:

- `1e2298d0ed0749d2ba58edd53d6bfc08626f1a494d8197469adbe787287070ff`
- `6981522b47c5a5c75d8a000b2fffca2176a9395e79996d8a9203aca0a4a58bb0`
- `780f8aabe2e6d9b4425498ee1f0170e3b0d55328100a4aea02efc875d4d29665`
- `8b5ff91a8dc0796d573520dedc82736ff162bd99bba19ae30ef91d6be45c9936`

No other snapshot-script identity is accepted without a prospectively frozen
implementation refinement.

## Verification unit

Verification is executed independently per historical batch.

Each batch re-verifies the small frozen provenance hashes for:

- `accessions.txt`;
- `candidate-sequence-audit.tsv`;
- `component-sequence-audit.tsv`;
- `package-files.tsv`;
- `dehydrated.zip`;
- `attempt-origin.json`.

It also checks the recorded Datasets version, environment-lock identity, and
snapshot-script identity.

## Full package content hashing

Every row in historical `package-files.tsv` is re-evaluated.

The verifier requires:

1. a safe relative path;
2. exactly one existing file under one of the two historically observed package
   layouts;
3. exact recorded byte size;
4. exact streaming SHA256 match.

A size mismatch fails without spending time hashing the mismatched file.

No package byte is copied into BacSelect.

## Accession-scoped versus batch-common evidence

A package-manifest path containing exactly one distinct canonical GCA
accession.version is accession-scoped.

Repeated occurrences of the same GCA in directory and file names are treated
as one identity.

Paths containing no GCA are batch-common provenance.

Paths containing more than one distinct GCA fail closed.

An accession passes cache content verification only when:

- all accession-scoped package files for that accession pass; and
- all batch-common package evidence and small batch provenance pass.

A failure in one accession-scoped file sends only that accession to fresh
acquisition.

A batch-common provenance failure sends every accession in that historical
batch to fresh acquisition.

This is conservative and prevents partial trust in a batch whose shared
provenance cannot be established.

## Failure semantics

`fallback_to_fresh` is an acquisition decision, not a scientific source
exclusion.

A failed cache verification never causes BacSelect to silently drop an
assembly. The assembly is added to the fresh-download set and evaluated under
the same frozen fresh sequence-validation rules.

Historical sequence-ineligible evidence can still pass cache content
verification. For example, an assembly previously shown to contain ambiguous
nucleotide content remains a valid, reusable ineligibility result if its
evidence is byte-identical.

## Outputs

Each batch produces internal scratch artifacts:

- `package-file-verification.tsv`;
- `accession-cache-verification.tsv`;
- `batch-cache-verification-summary.json`.

The first two may contain accessions and are not public blinded outcome
artifacts.

After all 111 batches finish, deterministic aggregation produces:

- `historical-cache-content-verification.tsv`;
- `historical-cache-content-verification-summary.json`.

The aggregate TSV is identity-bearing and remains internal.

The aggregate summary contains only counts and whole-artifact SHA256 values and
is suitable for a blinded Git checkpoint.

## Execution topology

This implementation intentionally does not freeze scheduler concurrency,
walltime, or Slurm resource requests.

Those are operational execution parameters and will be inspected and frozen in
a separate runner before the expensive re-hash is launched.

The scientific verifier itself is independent of task ordering.

## Integrity and reproducibility

The verifier:

- streams large files rather than loading them into memory;
- writes deterministic TSV ordering;
- writes sorted-key JSON;
- validates aggregate batch count;
- validates aggregate accession count;
- validates aggregate package-manifest row count;
- detects duplicate accessions across batches;
- verifies each batch accession-output SHA256 before aggregation.

The expected complete historical contract is:

- 111 batches;
- 55,426 accessions;
- 166,844 package-manifest rows.

## Blinding

The verifier consumes no:

- OPS/SR panel identity;
- selector distance;
- structural feature;
- taxonomy/species assignment;
- organism name.

No selector outcome can affect cache verification.

## Storage policy

The verification creates hashes, manifests, and small audit outputs only.

It does not duplicate historical FASTA, GBFF, sequence-report, or archive
content.

The historical Project Finch snapshot remains immutable while BacSelect relies
on it.

## Required gate before execution

Before the historical 371-GiB cache is re-hashed:

1. this implementation and synthetic tests must be committed;
2. the repository must be clean;
3. the Slurm runner must be frozen against this exact implementation identity;
4. the output root must be new and empty;
5. no network command may be present in the runner.

## Prospectivity statement

At this implementation freeze:

- historical package content has not yet been fully re-hashed by BacSelect;
- no final cache-pass/fallback count exists;
- no real fresh-download manifest exists;
- no BacSelect genome sequence has been downloaded;
- no fresh source eligibility has been generated;
- no structural feature has been calculated;
- no OPS/SR holdout distance has been calculated;
- the selector-resolution decision remains unresolved.
