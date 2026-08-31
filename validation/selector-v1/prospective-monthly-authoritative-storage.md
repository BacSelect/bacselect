# Prospective monthly authoritative storage

## Status

This document freezes the provider-neutral authoritative-storage contract for
BacSelect monthly production.

It does not enable source acquisition, upload production data, select a cloud
provider or modify the scheduled monthly workflow.

## Purpose

GitHub-hosted runner storage is transient.

GitHub Actions caches and ordinary workflow artifacts are therefore not
authoritative scientific storage for BacSelect.

A monthly production stage is not durably preserved merely because a command
completed successfully on a runner.

## Storage model

Authoritative BacSelect production uses three linked identities:

1. immutable content-addressed objects;
2. a canonical stage manifest;
3. a verified authoritative-storage receipt.

All scientific files are addressed by their SHA256 content identity.

The canonical object key is:

`objects/sha256/AA/BB/<sha256>`

where `AA` and `BB` are the first two and second two hexadecimal byte pairs of
the SHA256.

The key contains no mutable filename, release alias or "latest" pointer.

Identical bytes therefore map to the same durable object.

Different logical files may legitimately refer to the same content-addressed
object.

## Logical artifact identity

A stage manifest preserves the logical path of every production artifact while
binding that logical path to:

- SHA256;
- exact byte count;
- canonical content-addressed object key.

Logical paths must be relative POSIX paths.

Absolute paths, traversal components, empty path components and platform
backslash separators are forbidden.

Logical paths are unique within a stage manifest.

## Stage manifest

The frozen schema is:

`bacselect-authoritative-storage-manifest-v1`

The manifest binds:

- monthly release ID;
- source snapshot ID;
- production Git commit;
- stage ID;
- logical artifact count;
- total logical bytes;
- unique object count;
- total unique bytes;
- sorted logical artifact identities.

The manifest itself is canonical deterministic JSON.

It is also content-addressed.

Its immutable storage key is:

`manifests/monthly/<release>/production/<commit>/<stage>/sha256/<manifest-sha256>.json`

There is no mutable manifest key.

## Durable read-back requirement

Successful upload is not sufficient evidence that an object is authoritative.

After storage, the production backend must independently obtain for every
required object:

- object key;
- SHA256 identity;
- exact byte count.

The observations must exactly match the expected content-addressed objects.

This requirement includes the stage manifest itself.

Provider ETags are not automatically acceptable as SHA256 identities because
multipart and provider-specific ETag semantics may differ.

The future storage backend must expose or preserve an independently verifiable
SHA256 value.

## Authoritative receipt

Only after every required durable object has been read back and reconciled may
BacSelect create:

`bacselect-authoritative-storage-receipt-v1`

The receipt binds:

- release;
- source snapshot;
- production Git commit;
- stage;
- manifest SHA256;
- immutable manifest object key;
- complete verified object inventory.

The receipt is canonical deterministic JSON and itself receives an immutable
content-addressed key:

`receipts/monthly/<release>/production/<commit>/<stage>/sha256/<receipt-sha256>.json`

A workflow success flag is not a substitute for this receipt.

## Immutability requirements for the production backend

The eventual durable provider must support the following semantics.

### Create-only writes

Production automation must not overwrite an existing BacSelect object key.

If a key already exists, execution may continue only after independent
read-back confirms that its SHA256 and size exactly match the requested object.

A mismatching existing key is a hard failure.

### Delete separation

The routine monthly workflow must not possess permission to delete
authoritative production objects.

Deletion, retention-policy changes and destructive administration must be
separate privileged operations.

### Versioning or retention protection

The production store must provide durable protection against accidental
replacement or deletion, such as object versioning, immutable retention,
object-lock semantics, or an equivalent provider mechanism.

Provider selection must document the exact mechanism before production is
enabled.

### No transient authority

The following may be used for transport or acceleration but are never the
authoritative copy:

- GitHub runner filesystems;
- GitHub Actions cache;
- expiring workflow artifacts;
- local workstation files;
- institutional scratch storage.

## Stage granularity

Each durable production boundary receives its own stage manifest and receipt.

Examples include:

- Stage 1 source-query evidence;
- Stage 2 sequence-plan evidence;
- each Stage 3B acquisition batch;
- later taxonomy, feature, selection, packaging and publication boundaries.

This permits deterministic resume and verification without requiring one
mutable monolithic release archive.

## Stage 1 evidence

At minimum the Stage 1 durable manifest must preserve the exact production
evidence required to reconstruct and audit the source snapshot, including:

- release-start checkpoint;
- raw NCBI response;
- source-query stderr;
- source-query execution record;
- source-snapshot record.

The exact production implementation may include additional Stage 1 files.

## Stage 2 evidence

The Stage 2 durable manifest must preserve at least:

- monthly sequence-plan record;
- exact fresh-target manifest;
- any cache-reuse or retained-universe evidence required by the frozen Stage 2
  implementation.

## Stage 3B / Stage 3A evidence

A completed acquisition batch must preserve the complete evidence needed for
independent reconstruction and audit.

This includes the immutable batch directory contents produced by the frozen
Stage 3B executor, including:

- batch target manifest;
- accession input;
- pre-network attempt provenance;
- Datasets command/stdout/stderr/exit evidence;
- dehydrated ZIP;
- extracted hydrated package;
- hydration provenance;
- targeted retry evidence where applicable;
- Stage 3A candidate audit;
- Stage 3A component audit;
- Stage 3A package-file manifest;
- final batch summary.

Failed partial batches may also be durably retained for debugging and recovery,
but a failed-partial receipt must never be interpreted as a completed
scientific stage.

## Provider independence

The scientific storage identity does not include:

- cloud vendor;
- bucket name;
- account ID;
- GitHub runner identity;
- local filesystem path;
- institutional infrastructure.

A provider migration therefore does not alter scientific object identities,
manifest identities or receipt identities.

## Production enablement gate

Before real monthly acquisition is enabled, BacSelect must additionally freeze:

1. the concrete durable-object provider;
2. authentication from GitHub-hosted Actions;
3. create-only upload behavior;
4. SHA256 read-back verification;
5. deletion separation;
6. versioning/retention protection;
7. upload-resume behavior for large sequence objects;
8. storage of the authoritative receipt itself;
9. recovery tests showing a fresh runner can reconstruct a stage solely from
   authoritative storage.

Until those gates pass, monthly source acquisition remains disabled.

## Receipt versus backend execution evidence

The authoritative receipt is deliberately provider-neutral.

It proves that the complete expected content-addressed object inventory was
reconciled against an exact set of read-back observations. It does not, by
itself, identify or authenticate the external service that produced those
observations.

The concrete production storage backend must therefore preserve separate
execution evidence identifying at least:

- the configured durable-storage namespace;
- the backend/provider implementation;
- the read-back operation used to obtain SHA256 and byte-count observations;
- the production Git commit and storage implementation identity;
- the resulting authoritative manifest and receipt identities.

Those operational storage identifiers must not alter the SHA256 identities of
scientific objects or stage manifests.

A provider migration may therefore produce new backend execution evidence while
preserving the same scientific content-addressed objects and manifest identity.

## Exact source-snapshot identity

An authoritative monthly manifest accepts only the frozen Stage 1 source
snapshot form:

`bacselect-source-YYYY.MM-YYYYMM01THHMMSSZ`

The timestamp year and month must match the release ID and the snapshot date
must be day 01.
