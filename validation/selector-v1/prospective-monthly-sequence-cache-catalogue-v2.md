# Prospective monthly sequence-cache catalogue v2

## Status

Prospective frozen design.

This document defines the recovery-aware sequence-cache catalogue contract before
implementation. Cache v1 remains immutable.

## Purpose

Cache v2 must consume the recovery-aware monthly sequence-acquisition completion
contract without erasing the distinction between ordinary `fresh` acquisition
and accepted `fresh-recovery` acquisition.

The cumulative catalogue remains a scientific cache of exact accession-scoped
sequence package evidence. Recovery changes provenance, not the scientific
meaning of an accepted candidate.

## Non-negotiable boundary

The existing files:

- `src/bacselect/monthly_sequence_cache_catalogue.py`
- `validation/selector-v1/run_monthly_sequence_cache_catalogue.py`
- their existing tests

remain unchanged.

Cache v2 is a separate core and execution path.

## Authority is resolved again

The cache executor must not treat the completion artifact as a substitute for
filesystem/provider authority.

For every current Stage 3B batch it independently calls the frozen generic
authority resolver.

An ordinary authoritative batch is revalidated through the frozen ordinary
provider adapter.

A recovery authoritative batch is revalidated through the frozen recovery
provider adapter.

The resulting provider evidence is then compared exactly with completion-v2.
A disagreement fails closed.

No newest-path selection, accession-specific exception, implicit recovery-root
discovery, or provider fallback is permitted.

## Commit identities

Cache v2 keeps these identities separate:

1. `source_production_commit`
2. `completion_execution_commit`
3. `cache_execution_commit`

The source snapshot remains bound to the source production commit.

The completion artifact remains bound to the completion execution commit.

The cache implementation remains bound to the cache execution commit.

## Normalized current-batch evidence

The pure cache-v2 core receives provider-neutral current-batch evidence with:

- batch ID
- source class
- recovery class
- provider-summary name and bytes
- candidate-audit bytes
- component-audit bytes
- package-manifest name and bytes
- source-partial name
- recovery commit
- source batch/package hashes
- recovery package/summary hashes
- cause-evidence hash
- optional transport-record hash

No absolute filesystem path is persisted in this evidence.

## Provider-specific names

For `fresh`:

- provider summary: `batch-summary.json`
- package manifest: `package-files.tsv`
- provider prefix: `sequence-acquisition/<batch>/`

For `fresh-recovery`:

- provider summary: `recovery-summary.json`
- package manifest: `recovery-package-files.tsv`
- provider prefix:
  `sequence-acquisition-recovery/<recovery-commit>/source-<source-production-commit>/<batch>/`

Recovery is never projected into `sequence-acquisition/<batch>`.

## Shared scientific evidence

Ordinary and recovery packages expose the same generic package-manifest row
shape:

`path`, `size_bytes`, `sha256`.

Candidate and component audit schemas are also common after the provider has
passed its frozen validation contract.

Cache v2 therefore reuses the scientific candidate/component/package
derivation rules rather than weakening or duplicating them.

The provider-specific difference is retained in provenance and logical paths.

## Batch provenance v2

New current batches use
`bacselect-monthly-sequence-cache-batch-provenance-v2`.

The provenance records:

- batch ID and accession-set identity
- `source_class`
- `recovery_class`
- source production commit
- completion execution commit
- cache execution commit
- provider summary reference
- candidate audit reference
- component audit reference
- package-manifest reference
- completion hash
- package readback hash
- requested-accession count
- all generic recovery identity hashes where applicable

For `fresh`, all recovery-only fields are null.

For `fresh-recovery`, the recovery identity is mandatory.

The recovery class must therefore survive into the cumulative cache.

## Package artifact paths

Package artifact logical paths are validated against the batch provenance that
owns the entry.

Ordinary:

`sequence-acquisition/<batch>/package/<package-path>`

Recovery:

`sequence-acquisition-recovery/<recovery-commit>/source-<source-production-commit>/<batch>/package/<package-path>`

A recovery artifact can never masquerade as an ordinary artifact.

## Entries

The scientific entry fields remain:

- BioSample
- canonical GenBank assembly accession
- origin batch-provenance hash
- sequence eligibility
- exclusion reasons
- package artifacts

The source class does not need to be duplicated into every entry because each
entry is cryptographically bound to one batch-provenance record.

New v2 entries use a v2 entry hash domain.

## Historical chain compatibility

A cache-v2 release may chain from either:

- an existing cache-catalogue v1 artifact, or
- a cache-catalogue v2 artifact.

A previous v1 catalogue is audited with the frozen v1 auditor.

Its carried entries and batch-provenance rows are preserved without rehashing,
rewriting, or migration.

New current entries use v2 provenance.

If a current accession replaces a legacy accession entry, the current v2 entry
wins under the existing replacement semantics.

A v2 catalogue can therefore contain legacy v1 provenance for carried entries
and v2 provenance for current entries.

Historical hashes remain meaningful.

## Population accounting

The derived current population must equal completion-v2
`fresh_acquisition_count`.

The cumulative accounting invariants remain:

- current = new + replaced
- previous = carried + replaced
- catalogue = carried + new + replaced

No recovery batch is excluded merely because its source class is
`fresh-recovery`.

## Failure policy

Fail closed on:

- no authoritative provider
- ordinary and recovery authority simultaneously
- unexpected partial state
- completion/provider mismatch
- source-class mismatch
- recovery-class mismatch
- provider-summary mismatch
- candidate/component audit mismatch
- package-manifest or readback mismatch
- ambiguous or invalid historical catalogue chain

## Execution boundaries

Design freeze performs no real recovery, no network access, no cache
publication and no mutation of production evidence.

The three preserved production incident partials remain untouched.

There is no batch-specific or accession-specific cache logic.
