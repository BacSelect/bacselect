# Prospective monthly Zenodo packaging

## Status

This document freezes the local deterministic packaging and Zenodo record-part
planning boundary.

It does not contact Zenodo, use credentials, publish records, alter the monthly
workflow or enable real source acquisition.

## Packaging format

BacSelect packages scientific stage evidence as deterministic uncompressed
POSIX pax tar archives.

Compression is deliberately not part of this first format.

The goal is byte-for-byte deterministic package identity without introducing a
compressor implementation or compressor-version dependency.

A compressed format may be introduced later only as a separately frozen format.

## Explicit source membership

Package membership is explicit.

The packager receives:

- one package root;
- a finite list of relative POSIX logical paths.

It does not recursively discover files.

This prevents incidental temporary files, logs or future filesystem changes
from silently entering a scientific archive.

Only regular files are accepted.

Symlinks and path traversal are rejected.

## Internal package manifest

Every tar begins with:

BACSELECT_PACKAGE_MANIFEST.json

The embedded canonical manifest binds:

- monthly release;
- exact Stage 1 source snapshot;
- production Git commit;
- stage identity;
- source file count;
- source byte count;
- sorted logical paths;
- exact SHA256;
- exact byte count.

The reserved manifest name cannot also be supplied as a source artifact.

## Tar normalization

Every tar member uses fixed metadata:

- mode 0644;
- uid 0;
- gid 0;
- empty owner name;
- empty group name;
- mtime 0;
- regular-file type.

Members are sorted by logical path after the embedded package manifest.

Source filesystem ownership, mode and modification time therefore do not alter
the package bytes.

## Source mutation safeguard

Source files are hashed while the internal manifest is created.

Immediately before each source is written into the tar, its byte count and
SHA256 are checked again.

After the tar is complete, BacSelect reopens it and independently verifies:

- member inventory;
- member order;
- normalized metadata;
- exact embedded manifest bytes;
- SHA256 and byte count of every archived source member.

Only then is the temporary package atomically promoted to its final filename.

Existing final outputs are never overwritten.

## Package scientific identity

The completed tar is hashed with SHA256.

Its final filename, SHA256 and byte count become a ZenodoArchiveFile and are
therefore bound by the already-frozen Zenodo archive manifest.

## Zenodo record limits

The upstream Zenodo archive contract freezes the default service limits as:

- 100 files per record;
- 50,000,000,000 bytes per record.

The packaging planner uses a stricter payload allowance:

- 99 package files;
- 49,999,000,000 package bytes.

One file slot and 1,000,000 bytes are deliberately reserved for the record's
outer BacSelect archive-manifest/control artifact.

This is BacSelect headroom, not a claim that Zenodo itself requires a one
megabyte control file.

## Record-part planning

Completed package files are sorted by filename.

They are assigned sequentially to record parts.

A new part begins before adding a package would exceed either frozen payload
limit.

A single package larger than the payload byte limit fails closed and must be
repackaged at a finer scientific boundary.

The planner never depends on additional Zenodo quota.

## Record-part manifests

After partitioning, each part receives the existing canonical Zenodo archive
manifest.

Every part therefore binds:

- part index;
- total part count;
- release;
- source snapshot;
- Git commit;
- stage;
- package filenames;
- package SHA256 values;
- package byte counts.

## Portability

The implementation uses only the Python standard library and existing BacSelect
Zenodo-contract primitives.

It contains no network operations, institutional paths, scheduler assumptions,
credentials or Zenodo API execution.

## Remaining boundaries

Before Zenodo publication can be enabled, BacSelect still requires:

1. stage-specific definitions of which production files enter each package;
2. archive filename derivation;
3. outer archive-manifest persistence inside each Zenodo record;
4. Zenodo metadata generation and relationships;
5. sandbox API execution;
6. sandbox publication and complete SHA256 readback;
7. fresh-runner reconstruction;
8. production credential handling;
9. production publication gating.

## Canonical logical paths

Package logical paths must already be in canonical relative POSIX form.

Equivalent but textually different spellings such as double separators,
explicit `.` components, leading `./`, or trailing separators are rejected
rather than normalized silently.

This ensures that one archived source member has one canonical logical-path
identity.

## Record-headroom proof

The one-file and 1,000,000-byte control reserve is regression-tested at the
worst frozen payload geometry:

- 99 package files;
- maximum permitted payload byte count;
- maximum accepted package filenames.

The generated outer Zenodo archive manifest must fit entirely within the
reserved control byte allowance, and the resulting file and byte totals must
remain within the upstream 100-file and 50,000,000,000-byte record limits.
