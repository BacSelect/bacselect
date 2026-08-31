# Prospective monthly sequence-cache catalogue

## Status

This document freezes the pure cumulative sequence-cache catalogue contract.

It does not implement filesystem discovery, durable object retrieval, cloud
storage, workflow orchestration, cache verification, Stage 2 production
writing, or publication.

## Purpose

The monthly sequence-cache catalogue is the authoritative discovery inventory
for sequence evidence that BacSelect has previously acquired and sealed through
the monthly Stage 3B sequence-acquisition completion contract.

It solves the cumulative-cache problem created once monthly reuse begins.

A later release may have few or zero fresh downloads. Therefore the latest
Stage 3B directory is not a complete cache inventory.

The catalogue evolves as:

previous authoritative catalogue
+
current completed Stage 3B acquisitions
=
current authoritative cumulative catalogue

## Separation from cache verification

The catalogue does not claim that an entry is valid for the current source
snapshot.

It records what immutable sequence evidence is available for possible reuse.

The later monthly cache-verification stage remains responsible for:

- current metadata membership;
- current BioSample agreement;
- package-object read-back;
- component reconstruction;
- component identity;
- topology-aware assembly fingerprint;
- frozen source-evidence identity;
- accession-scoped package-manifest identity;
- current-snapshot verification-record identity.

Accordingly the catalogue does not store:

- `verified_source_snapshot_id`;
- `component_identity_sha256`;
- `assembly_fingerprint`;
- `source_evidence_sha256`;
- `package_manifest_sha256`;
- `verification_record_sha256`.

## No embedded genome sequences

The catalogue does not embed FASTA sequence strings.

A future cache-verification executor reconstructs the `MonthlyCacheCandidate`
from immutable catalogue objects.

The candidate and component audit artifacts provide the expected metadata.
The accession-scoped package artifacts provide the bytes that are independently
read back and parsed.

## Package scope

The per-accession package population is exactly the set of package-manifest
rows beneath:

`ncbi_dataset/data/<canonical GCA accession>/...`

Batch-shared files such as:

`ncbi_dataset/data/assembly_data_report.jsonl`

are not duplicated into each accession entry.

This follows the frozen cache semantics:

- `package_manifest_sha256()` is accession-scoped;
- `source_evidence_sha256()` binds the candidate FASTA package row;
- batch-common provenance is a separate prerequisite.

## Content-addressed evidence

Catalogue records contain no physical filesystem, bucket, URL, or provider
location.

Every package artifact records:

- its NCBI package-relative path;
- its BacSelect authoritative-storage logical path;
- SHA256;
- byte size.

For an artifact whose NCBI package-relative path is `<package path>` and whose
origin batch is `<batch ID>`, the authoritative logical path is exactly:

`sequence-acquisition/<batch ID>/package/<package path>`

The mapping is part of the pure catalogue contract and must not be inferred by
a later executor from an undocumented storage convention.

Every batch-level evidence artifact records:

- deterministic BacSelect logical path;
- SHA256;
- byte size.

A later executor may resolve those identities through the frozen
authoritative-storage contract and its SHA-addressed object namespace.

## Batch provenance

Each distinct origin Stage 3B batch has one deterministic batch-provenance
record.

It binds:

- cache-origin release ID;
- cache-origin source-snapshot ID;
- cache-origin Git commit;
- origin batch ID;
- origin sequence-acquisition-completion SHA256;
- origin batch accession-list SHA256;
- origin package-file read-back SHA256;
- requested accession count;
- batch-summary artifact;
- candidate-audit artifact;
- component-audit artifact;
- package-files-manifest artifact.

The batch-provenance SHA256 is deterministic over those fields.

Each catalogue entry references one batch-provenance SHA256.

Batch-common provenance is therefore represented once rather than copied into
every accession entry.

## Catalogue entries

There is exactly one authoritative catalogue entry for each canonical `GCA_`
assembly accession.

An entry contains:

- canonical GenBank assembly accession;
- BioSample recorded by the completed Stage 3A candidate evidence;
- origin batch-provenance SHA256;
- origin Stage 3A sequence eligibility;
- origin Stage 3A sequence exclusion reasons;
- every accession-scoped package artifact;
- deterministic entry SHA256.

Entries are strictly sorted by canonical accession.

Package artifacts within an entry are strictly sorted by package path.

Each package artifact's authoritative logical path must agree exactly with the
entry's referenced origin batch provenance and its package-relative path.

Duplicate accessions or package paths fail closed.

## Current-acquisition derivation

The pure catalogue builder does not accept arbitrary preconstructed cache
entries.

For each current Stage 3B batch it accepts the exact bytes of:

- `batch-summary.json`;
- `candidate-sequence-audit.tsv`;
- `component-sequence-audit.tsv`;
- `package-files.tsv`.

Those bytes must match the SHA256 identities in the supplied release-level
sequence-acquisition completion record.

The candidate, component, and package TSVs must use the frozen Stage 3A field
schemas and canonical TSV representation.

The builder derives current catalogue entries from those authenticated bytes.

## Candidate checks

For every current candidate:

- the canonical assembly accession must be a valid versioned `GCA_`;
- expected and observed BioSample must agree;
- the Stage 3A result must be `PASS`;
- the candidate FASTA SHA256 must be valid;
- the primary-assembly count must be positive;
- the component audit must contain exactly that many primary components;
- components may belong only to accessions in the candidate audit;
- each component length must be positive;
- each component sequence SHA256 must be valid;
- topology must be `circular`, `linear`, or `unspecified`;
- component ambiguous-base counts must be non-negative;
- candidate sequence eligibility and exclusion reasons must be reproduced
  exactly from the Primary Assembly component evidence;
- `ambiguous_nucleotide` is present exactly when the Primary Assembly
  component evidence contains ambiguous bases;
- `unresolved_topology` is present exactly when at least one Primary Assembly
  component has `unspecified` topology;
- at least one accession-scoped package artifact must exist;
- the candidate FASTA must bind uniquely by path or basename plus SHA256 to
  one accession-scoped package artifact.

No genome sequence is parsed by this contract.

## Cache-candidate materialization

The catalogue is an acquisition-evidence inventory, so it retains both
origin sequence-eligible and origin sequence-ineligible completed
acquisitions.

This does not mean every catalogue entry may be passed to the frozen monthly
cache verifier.

The future cache-verification executor may construct a
`MonthlyCacheCandidate` only from a catalogue entry whose:

`origin_sequence_eligibility = eligible`

and whose origin exclusion reasons are `none`.

This is required because the frozen cache-verification contract accepts only
`linear` and `circular` Primary Assembly component topology. Stage 3A uses
`unspecified` topology to mark unresolved topology and records that candidate
as sequence-ineligible.

An origin sequence-ineligible catalogue entry therefore remains authoritative
evidence that BacSelect acquired that assembly, but it is not materialized as
a `MonthlyCacheCandidate`.

It contributes no verified-cache evidence for Stage 2 unless a later,
separately frozen design changes that rule.

Origin Stage 3A eligibility is historical acquisition evidence. It is not a
claim that the assembly is eligible for the current monthly source snapshot.

## Completion authority

Current acquisitions may enter the catalogue only through a release-level
record with:

- schema `bacselect-monthly-sequence-acquisition-completion-v1`;
- status `SEQUENCE_ACQUISITION_COMPLETE`;
- matching source snapshot;
- matching origin Git commit;
- internally consistent completed accession and batch counts.

The pure catalogue contract validates the canonical completion record structure
and binds every supplied batch evidence payload to the completion-row SHA256
identities.

The production catalogue executor must additionally obtain that completion
record from the frozen completion executor boundary and perform the full frozen
completion audit before catalogue construction.

The catalogue contract does not replace that filesystem-level audit.

## Genesis

The first authoritative catalogue has:

- `catalogue_mode = GENESIS`;
- no previous catalogue release ID;
- no previous catalogue SHA256;
- previous catalogue entry count zero.

The production executor must prove that no eligible prior authoritative monthly
catalogue exists before invoking genesis mode.

A fabricated choice to ignore an existing prior catalogue is not permitted by
the production design.

## Chaining

A later catalogue has:

- `catalogue_mode = CHAINED`;
- exact previous catalogue release ID;
- SHA256 of the exact previous canonical catalogue bytes;
- previous catalogue entry count.

The previous catalogue must pass its standalone pure audit.

Its release ID must be strictly earlier than the current release ID.

An immediately preceding calendar month is not required; a failed or absent
monthly production release does not invalidate the next successful chain.

## Merge semantics

For an accession present only in the previous catalogue:

the prior entry is carried forward unchanged.

For an accession present only in current completed acquisition evidence:

a new current-origin entry is added.

For an accession present in both:

the current completed acquisition deterministically replaces the prior entry.

Replacement occurs even if the biological sequence is identical.

The latest completed acquisition becomes the authoritative cache origin for that
accession.

## No deletion from current-universe absence

An accession is not deleted merely because it is absent from a later monthly
source snapshot or metadata-retained population.

The catalogue is a cumulative sequence-evidence inventory, not the current
eligible source universe.

The later cache-verification executor intersects catalogue discovery with the
current monthly metadata population.

## Zero-fresh releases

A sequence-acquisition completion with zero fresh acquisitions is valid.

For a chained zero-fresh release:

- current acquisition count is zero;
- new entry count is zero;
- replacement count is zero;
- every previous entry is carried forward unchanged;
- referenced prior batch provenance remains unchanged.

The new top-level catalogue record still binds the current release,
source-snapshot identity, Git commit, current completion SHA256, and previous
catalogue SHA256.

For genesis with zero fresh acquisitions, the catalogue is valid and empty.

## Provenance pruning

The current catalogue contains exactly the batch-provenance rows referenced by
its current entries.

If every entry from an old batch is replaced by later acquisitions, that old
batch-provenance row is no longer required in the current catalogue.

Historical catalogue bytes remain immutable through the previous-catalogue
chain.

## Determinism

Catalogue entries are sorted by canonical accession.

Batch provenance is sorted by batch-provenance SHA256.

Each entry and batch-provenance record has its own deterministic SHA256.

The catalogue additionally records SHA256 identities for:

- the complete entry set;
- the complete referenced batch-provenance set.

Canonical JSON uses:

- ASCII;
- sorted object keys;
- two-space indentation;
- one trailing newline.

## Accounting

The record explicitly stores:

- previous catalogue entry count;
- carried-forward entry count;
- new entry count;
- replaced entry count;
- current acquisition count;
- final catalogue entry count;
- referenced batch-provenance count.

Required identities are:

current acquisition count
=
new entry count
+
replaced entry count

previous catalogue entry count
=
carried-forward entry count
+
replaced entry count

final catalogue entry count
=
carried-forward entry count
+
new entry count
+
replaced entry count

Current acquisition count must equal the fresh-acquisition count of the
sequence-acquisition completion record.

## Purity boundary

The pure contract performs no:

- filesystem discovery;
- filesystem reads or writes;
- network access;
- NCBI requests;
- Git commands;
- cloud API calls;
- object retrieval;
- workflow mutation;
- Zenodo publication;
- Slurm execution;
- historical Project Finch lookup.

It operates only on supplied immutable bytes and values.

## Production executor boundary

The later portable catalogue executor must:

- prove exact repository/version identity;
- locate and fully re-audit the authoritative sequence-acquisition completion;
- prove genesis absence or locate exactly one previous authoritative catalogue;
- retrieve the current completed batch evidence bytes;
- bind them to the completion seal;
- invoke this pure contract;
- write the catalogue atomically with no-clobber semantics;
- read back and re-audit the exact final bytes;
- persist the catalogue as authoritative storage evidence.

That executor is intentionally not part of this contract.
