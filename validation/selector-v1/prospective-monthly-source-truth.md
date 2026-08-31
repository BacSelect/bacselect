# Prospective monthly source-truth contract

## Status

This document freezes the pure monthly Stage 4 source-truth composition
contract for BacSelect production.

It is frozen before the portable monthly source-truth executor is written.

This contract adds no new source-truth scientific decision rule.

## Scientific authority

The frozen BacSelect source-truth stack remains authoritative:

- `src/bacselect/source_truth.py`;
- `src/bacselect/source_truth_execution.py`;
- `src/bacselect/source_post_sequence_eligibility.py`.

The monthly contract must not reproduce or alter the duplicate,
containment or source-truth adjudication semantics.

## Current monthly population authority

The current cumulative sequence-cache catalogue is the sequence-evidence
convergence layer for monthly production.

By Stage 4, downstream science must not distinguish a genome merely because
its current evidence was:

- reused from a prior verified monthly cache entry; or
- acquired freshly in the current release.

Both are represented by the current audited cumulative catalogue.

The catalogue must be audited using the frozen
`audit_sequence_cache_catalogue()` implementation.

## Metadata coverage

The complete current retained metadata accession/BioSample population is an
independent Stage 4 input.

The cumulative catalogue must contain exactly one entry for every current
retained accession.

No current retained accession may be absent.

The cumulative catalogue may also contain historical cache entries for
accessions that are no longer in the current retained metadata population.
Those entries remain valid cache history but do not enter the current Stage 4
population or source-truth evaluation.

For every current retained accession, catalogue BioSample must exactly equal
the current metadata BioSample.

## Sequence eligibility precedes source truth

The cumulative catalogue preserves the Stage 3A sequence-eligibility result:

- `eligible`;
- `ineligible`.

Stage 4 must preserve this classification exactly.

The complete retained population is partitioned into:

`retained = sequence eligible + sequence ineligible`

with no overlap and no missing accession.

Sequence-ineligible candidates are terminal at the sequence-eligibility
layer.

They must not receive:

- a source-truth decision;
- a source-truth exclusion;
- a source-truth unresolved status;
- source-truth relation evidence.

In particular, Stage 4 must not reinterpret sequence ineligibility as
`EXCLUDE_SOURCE_TRUTH`.

Only sequence-eligible candidates enter the frozen source-truth evaluation.

## Source-truth evaluation population

The source-truth evaluation population is exactly the sorted set of current
catalogue entries whose frozen sequence eligibility is `eligible`.

Every sequence-eligible accession must receive exactly one
`SourceTruthDecision`.

No other accession may receive one.

Every source-truth decision must contain:

- canonical GenBank assembly accession;
- frozen source-evidence SHA256;
- frozen sequence-set SHA256;
- terminal source-truth status;
- non-empty source-truth reason.

Allowed terminal source-truth statuses remain exactly:

- `SUITABLE`;
- `EXCLUDE_SOURCE_TRUTH`;
- `REVIEW_UNRESOLVED`.

## Evidence materialization boundary

The pure monthly contract does not perform authoritative-object I/O.

The later portable executor is responsible for materializing the authenticated
evidence referenced by the current catalogue.

For each sequence-eligible catalogue entry the executor must follow:

`origin_batch_provenance_sha256`

to the audited batch provenance and independently re-audit the authenticated:

- candidate-sequence audit;
- component-sequence audit;
- package-files manifest.

The accession-scoped package artifacts recorded by the catalogue must exactly
match the authenticated package manifest.

The candidate FASTA object must be read from the authoritative content-addressed
object store and must match its frozen:

- size;
- SHA256;
- package identity;
- candidate-audit identity.

The frozen source-truth FASTA/parser/component reconstruction semantics remain
authoritative.

## No new evidence representation

The monthly executor should materialize evidence into the existing frozen
`source_truth_execution` model rather than creating a second biological
representation.

The relevant frozen objects remain:

- `CandidateAudit`;
- `ComponentAudit`;
- `PackageFile`;
- `SourceTruthDecision`.

Scientific evaluation remains delegated to the frozen source-truth
implementation.

## Deterministic memberships

The pure monthly contract records three deterministic accession memberships:

1. current retained population;
2. sequence-eligible population;
3. sequence-ineligible population.

Each membership has:

- count;
- deterministic accession-membership SHA256.

The eligible and ineligible memberships must be disjoint and exhaustive over
the retained membership.

## Decision artifact

The source-truth decision artifact uses the already frozen decision-row
vocabulary:

- `canonical_genbank_assembly_accession`;
- `source_evidence_sha256`;
- `sequence_set_sha256`;
- `duplicate_relation_count`;
- `containment_relation_count`;
- `source_truth_status`;
- `source_truth_reason`.

Rows are sorted by canonical GenBank accession.

There is exactly one decision row per sequence-eligible accession.

## Relation artifact

The relation artifact uses the already frozen source-truth relation-row
vocabulary:

- `canonical_genbank_assembly_accession`;
- `relation_type`;
- `left_component`;
- `right_component`;
- `inner_component`;
- `outer_component`;
- `inner_topology`;
- `outer_topology`;
- `relation`;
- `outer_origin_crossing`.

Only accessions with a source-truth decision may occur.

Per-accession duplicate and containment row counts must equal the counts
recorded in the corresponding decision row.

## Monthly source-truth record

Schema:

`bacselect-monthly-source-truth-record-v1`

Status:

`MONTHLY_SOURCE_TRUTH_COMPLETE`

The deterministic record binds:

- release ID;
- current source-snapshot ID;
- production Git commit;
- current sequence-cache catalogue SHA256;
- current catalogue entry-set SHA256;
- current metadata record SHA256;
- current metadata completion SHA256;
- retained count and membership SHA256;
- sequence-eligible count and membership SHA256;
- sequence-ineligible count and membership SHA256;
- source-truth decision count;
- decision artifact SHA256;
- relation count;
- relation artifact SHA256;
- terminal source-truth status counts;
- source-truth reason counts.

The decision count must exactly equal the sequence-eligible count.

## Record audit

The monthly record auditor does not trust membership counts from the record
itself.

It re-audits the supplied current cumulative catalogue, reconstructs the
current retained/eligible/ineligible population against current metadata, and
then audits the exact decision and relation bytes.

The record is accepted only if rebuilding the deterministic record produces
identical canonical JSON bytes.

## Repeated-BioSample hand-off

Stage 5 repeated-BioSample reconciliation begins only from source-truth
`SUITABLE` candidates.

The Stage 4 decision artifact therefore preserves the exact source-truth status
and source-evidence identity needed by the frozen repeated-BioSample
fingerprinting implementation.

The later Stage 5 executor may independently rematerialize the same
catalogue-backed sequence evidence to calculate the frozen topology-aware
assembly fingerprint.

Stage 4 does not perform repeated-BioSample reconciliation.

## Identity blindness

Stage 4 must not use:

- species;
- taxonomy;
- organism name;
- clinical importance;
- publication status;
- previous panel membership;
- selector distances;
- final panel membership.

Source truth remains identity-independent and is evaluated before selector
construction.

## Portability

The pure contract performs:

- no network access;
- no cloud access;
- no authoritative-object access;
- no NCBI query;
- no Slurm execution;
- no institution-specific infrastructure.

Those concerns belong to the later portable executor.

## Historical wrapper

`validation/selector-v1/run_source_truth_execution.py` remains historical
selector-v1 evidence.

It must not be generalized into monthly production.

Its Project Finch, historical-cache, recovery and fixed-population bindings are
not monthly production dependencies.

Monthly production reuses the frozen science, not the historical execution
environment.

## Workflow state

Freezing this pure contract does not modify the monthly GitHub Actions
workflow.

The workflow remains preflight-only pending separate orchestration freeze.
