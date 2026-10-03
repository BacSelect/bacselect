# Monthly Stage 7 local-CAS operational correction

## Status

This document prospectively freezes the Stage 7-v3 operational correction for
the first BacSelect monthly production release.

It changes no taxonomy scientific rule.

It supersedes only the claim that a filesystem content-addressed view on
institutional scratch is itself durable authoritative storage.

## Reason for the correction

The frozen monthly taxonomy executor implements strong local content-addressed
publication semantics:

- SHA256-addressed objects;
- no-clobber writes;
- exact byte-count verification;
- fresh filesystem read-back;
- deterministic manifest construction;
- deterministic receipt construction.

The original Stage 7 execution contract described that filesystem boundary as
durable authoritative storage.

The separately frozen BacSelect preservation contracts make a stronger and
different statement:

- institutional scratch storage is not the durable authoritative copy;
- Zenodo is the selected prospective primary scholarly archive;
- a paid S3-compatible object store is not required;
- durable scholarly publication and verification occur at the later release
  archive/publication boundary.

Stage 7-v3 resolves that terminology and lifecycle mismatch.

## Scientific invariants

Stage 7-v3 must not modify:

- `src/bacselect/monthly_taxonomy_snapshot.py`;
- the frozen taxonomy source URL;
- archive validation;
- controlled extraction;
- `nodes.dmp`, `merged.dmp` or `delnodes.dmp` semantics;
- structural validation;
- taxonomy snapshot identity construction;
- the Stage 7 monthly taxonomy record;
- Stage 1 through Stage 6 authentication;
- candidate filtering;
- taxonomy resolution.

Taxonomy resolution remains a later stage.

## Local content-addressed view

Stage 7-v3 uses a caller-supplied:

`--local-cas-root`

The root is a verified local content-addressed view used for operational
integrity and deterministic resume/reconciliation.

It retains the existing frozen object-key structure:

`objects/sha256/<AA>/<BB>/<sha256>`

and the existing deterministic manifest and receipt bytes.

Under Stage 7-v3 these objects prove local content identity and read-back only.

They do not prove:

- external durability;
- object-lock retention;
- cloud-provider identity;
- Zenodo publication;
- scholarly archival preservation.

## Legacy internal terminology

The frozen Stage 7 support implementation and provider-neutral storage helper
contain historical names including:

- `authoritative_root`;
- `authoritative_manifest`;
- `authoritative_receipt`;
- `bacselect-authoritative-storage-manifest-v1`;
- `bacselect-authoritative-storage-receipt-v1`.

Stage 7-v3 reuses those frozen helpers only as a compatibility implementation
for deterministic local CAS publication and read-back.

Their legacy names must not be interpreted as evidence that institutional
scratch has become BacSelect's durable scholarly archive.

The Stage 7-v3 public completion schema therefore does not expose
`authoritative_storage_*` fields.

## Stage 7-v3 completion

The completion schema is:

`bacselect-monthly-taxonomy-snapshot-completion-v3`

The terminal Stage 7 status remains:

`TAXONOMY_SNAPSHOT_EXECUTION_COMPLETE`

The completion binds the existing taxonomy identities and all upstream
production execution identities.

Storage evidence is represented as:

- `local_cas_status`;
- `local_cas_manifest_sha256`;
- `local_cas_manifest_key`;
- `local_cas_receipt_sha256`;
- `local_cas_receipt_key`;
- `local_cas_verified_object_count`.

The required local CAS status is:

`LOCAL_CONTENT_ADDRESSABLE_VIEW_VERIFIED`

The durable archive boundary is explicitly:

`DEFERRED_TO_PUBLICATION_GATE`

## Downstream boundary

A valid Stage 7-v3 completion may authorize later monthly scientific stages to
consume the frozen taxonomy snapshot because those stages require stable,
cryptographically verified taxonomy inputs, not proof of scholarly publication.

No Stage 7-v3 completion is sufficient to publish a BacSelect monthly release.

Durable archival publication remains a later release/publication requirement.

## Scholarly archive

Zenodo remains the selected prospective primary scholarly archive for the
monthly BacSelect scientific dataset.

The final publication boundary must independently bind and verify the packaged
release against its frozen SHA256 identities.

Stage 7-v3 does not claim:

- that Zenodo publication has occurred;
- that a Zenodo DOI exists;
- that `PUBLISHED_VERIFIED` has been reached;
- that the release is publicly publishable.

## Immutability

Historical Stage 7-v1 and Stage 7-v2 code and evidence are not rewritten.

Stage 7-v3 is additive.

The first successful Stage 7-v3 production completion becomes the applicable
Stage 7 authority for the September 2026 monthly execution chain.
