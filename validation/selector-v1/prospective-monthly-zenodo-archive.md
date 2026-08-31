# Prospective monthly Zenodo scholarly archive

## Status

This document freezes the prospective scholarly-archive integrity model for
BacSelect monthly production.

It does not:

- create a Zenodo account;
- create an API token;
- create a Zenodo record;
- upload any data;
- publish any record;
- modify the monthly workflow;
- enable real source acquisition.

## Selected preservation model

Zenodo is the prospective primary scholarly archive for BacSelect monthly
scientific releases.

A paid S3-compatible object store is not required by the current BacSelect
design.

The previously frozen object-store specification remains valid as an optional
future backend design. Zenodo is not falsely claimed to implement S3/WORM
semantics.

## Separate software archive

The BacSelect software repository and the monthly BacSelect scientific dataset
are distinct scholarly objects.

The repository:

BacSelect/bacselect

will use Zenodo's GitHub integration for Software releases.

The monthly scientific release uses Dataset records and has its own dataset
DOI identities.

The software DOI and dataset DOI are not interchangeable.

## Record limits

The automated BacSelect design relies only on Zenodo's standard default
per-record limits:

- no more than 100 files;
- no more than 50,000,000,000 bytes.

Correctness does not depend on receiving additional storage quota.

If a BacSelect scientific stage is larger than the default record limit, it
must be divided into deterministic record parts.

Each part records:

- part index;
- total part count;
- monthly release;
- source snapshot;
- production Git commit;
- stage identity.

## Packaging

Zenodo should not receive thousands of individual hydrated NCBI files.

A later BacSelect packaging boundary will produce deterministic archive
packages suitable for scholarly preservation.

Archive packaging is not defined by this contract.

## Archive manifest

Each Zenodo record part has a canonical BacSelect SHA256 manifest.

The manifest binds:

- monthly release ID;
- exact Stage 1 source snapshot;
- production Git commit;
- stage identity;
- record-part index and count;
- exact filename;
- SHA256;
- exact byte count.

The manifest is deterministic and fail-closed.

## SHA256 remains authoritative

Zenodo transport checksums are not the BacSelect scientific identity.

BacSelect scientific content identity remains SHA256.

A successful Zenodo upload or publication response is insufficient to prove
archival integrity.

## Publication verification

After publication, every file is downloaded from the published Zenodo record.

BacSelect independently computes:

- SHA256;
- exact byte count.

Only an exact match with the frozen archive manifest permits the state:

PUBLISHED_VERIFIED

The publication receipt also binds:

- Zenodo environment;
- record ID;
- concept record ID;
- version-specific DOI;
- publication timestamp;
- verification timestamp;
- archive-manifest SHA256;
- complete readback inventory.

## Production versus sandbox

Production Zenodo records use normal Zenodo DOI identity.

Zenodo sandbox records use test DOI identity.

A sandbox record can never satisfy a BacSelect production publication gate.

## Conservative post-publication stability boundary

Current Zenodo documentation contains overlapping descriptions of its
post-publication file-correction period.

The detailed file-management documentation states that minor corrections may
be initiated within 30 days after publication and that the resulting correction
draft must be published within 45 days of the original publication.

BacSelect therefore uses 45 days as the conservative automated sealing
boundary.

This does not assert that arbitrary modification is permitted for the entire
45-day interval.

It simply ensures BacSelect never describes a record as sealed while any
ordinary documented correction workflow could still be completing.

## Sealed verification

At least 45 complete days after the original Zenodo publication timestamp,
BacSelect performs a second full download.

Every archived file is independently checked again for:

- exact SHA256;
- exact byte count.

Only exact reconciliation produces:

SEALED_VERIFIED

The sealed receipt binds the original publication receipt by SHA256.

Both publication and sealed receipts are canonical machine-readable artifacts.
Each is independently auditable against the archive manifest and the evidence
from which it was derived.

Exceptional repository-level correction, restriction or takedown mechanisms
may still exist and are not falsely represented as impossible.

## Monthly operation

The sealing check is asynchronous with the monthly release itself.

A newly published release may be PUBLISHED_VERIFIED while an older release is
eligible for SEALED_VERIFIED.

No production publication automation is enabled by this specification.

## API implementation is separate

Zenodo provides a REST API for deposit creation, file upload and publication.

The eventual executor will use:

- Zenodo sandbox first;
- a separate sandbox token;
- a production token only after sandbox proof;
- HTTPS Authorization headers;
- least-required deposit scopes;
- no token stored in source control.

The API executor is a later validation boundary.

## Fresh-runner recovery

Before production is enabled, BacSelect must prove that a fresh GitHub-hosted
runner can reconstruct archived scientific evidence from published Zenodo
records and reproduce the expected SHA256 identities.

## Outstanding production gates

Before real Zenodo publication is enabled, BacSelect must still freeze and
prove:

1. deterministic archive packaging;
2. deterministic record-part planning;
3. Zenodo metadata generation;
4. record and part relationships;
5. sandbox draft creation;
6. streamed file upload;
7. draft inventory verification;
8. sandbox publication;
9. complete post-publication SHA256 readback;
10. publication-receipt persistence;
11. production secret handling;
12. fresh-runner reconstruction;
13. 45-day sealed re-verification;
14. GitHub-to-Zenodo software release integration;
15. continued prohibition on real publication until all required gates pass.
