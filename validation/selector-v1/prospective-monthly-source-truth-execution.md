# Prospective monthly source-truth execution

## Status

This document freezes the portable execution boundary for BacSelect monthly
Stage 4 source truth.

It is written after the pure monthly source-truth contract was frozen and
before any real monthly Stage 4 source-truth result is generated.

The executor adds no new source-truth scientific rule.

## Frozen scientific authority

Monthly Stage 4 delegates scientific classification to the already frozen:

- `src/bacselect/source_truth.py`;
- `src/bacselect/source_truth_execution.py`;
- `src/bacselect/monthly_source_truth.py`.

The historical selector-v1 source-truth production wrapper remains unchanged
and is not a monthly production dependency.

## Frozen execution preflights

Stage 4 independently runs the frozen repository preflights of both:

- the monthly cache-verification executor;
- the monthly sequence-cache catalogue executor.

Pinning only those wrapper files is insufficient because their reusable
evidence loaders depend on additional frozen modules and methods.

Stage 4 therefore requires the complete transitive dependency sets accepted by
those frozen preflights to remain unchanged.

## Upstream population authority

The current retained metadata population is re-audited from the current
monthly metadata stage.

The current cumulative sequence-cache catalogue is discovered through the
complete canonical catalogue chain and must be the final chain member for the
current release.

The current catalogue must match:

- the current release ID;
- the current source-snapshot ID;
- the current production Git commit.

The pure monthly source-truth contract then requires exact accession/BioSample
coverage of the current retained metadata population.

The cumulative catalogue may contain additional historical cache entries.
Those entries remain part of cache history but are excluded from the current
Stage 4 population unless their accession is present in current retained
metadata.

## Evidence-location rule

The current cumulative catalogue is the scientific evidence-provenance
authority, but physical evidence may reside in two locations.

### Current-release origin

If a catalogue entry references batch provenance whose
`cache_origin_release_id` is the current release, Stage 4 uses the current
local Stage 3B batch only after independently re-auditing the current
sequence-acquisition completion.

The local batch evidence must match the catalogue batch provenance exactly.

### Earlier-release origin

If a catalogue entry references an earlier release, the origin batch evidence
is loaded from the authoritative content-addressed object root using the
frozen monthly cache-execution evidence loader.

Required evidence is fail-closed.

Missing or corrupt evidence is not converted to fresh acquisition at Stage 4.

## Origin provenance coherence

Every catalogue batch provenance row used by Stage 4 must represent an origin
release that is not later than the current release.

A later origin release is invalid and fails closed.

For current-release origin evidence, Stage 4 independently requires exact
agreement with the re-audited current sequence-acquisition completion for:

- origin release ID;
- source-snapshot ID;
- production Git commit;
- origin completion SHA256;
- batch ID;
- requested accession count;
- accession-list SHA256;
- batch-summary SHA256;
- candidate-audit SHA256;
- component-audit SHA256;
- package-files-manifest SHA256;
- package-file-readback SHA256.

These checks are performed independently of the catalogue entry's own
self-consistency audit.

## Required source-truth evidence

For every sequence-eligible candidate, Stage 4 requires:

- exactly one candidate audit row;
- exact current BioSample agreement;
- `sequence_eligibility = eligible`;
- `exclusion_reasons = none`;
- `result = PASS`;
- a positive Primary Assembly record count;
- exact Primary Assembly component evidence;
- the exact accession-scoped package manifest;
- exact agreement between catalogue package artifacts and the authenticated
  package manifest;
- exactly one candidate FASTA package row matching candidate basename and
  SHA256.

## Current local FASTA

For current-release origin evidence, the frozen source-truth evaluator reads
the existing re-audited Stage 3B package FASTA.

No copy is required.

## Earlier authoritative FASTA

For earlier-release origin evidence, the candidate FASTA object is a required
authoritative object.

The object must exactly match its catalogue/package:

- SHA256;
- size.

The object is copied into a temporary private materialization tree solely so
the frozen source-truth path-resolution code can consume the same evidence
shape used by selector-v1.

That materialization tree is not a scientific artifact and is deleted before
publication.

## Scientific evaluation

Every sequence-eligible accession is evaluated exactly once using:

`source_truth_execution.evaluate_candidate()`

with the frozen:

- `CandidateAudit`;
- `ComponentAudit`;
- `PackageFile`.

Sequence-ineligible candidates do not receive source-truth decisions.

## Stage outputs

Canonical Stage 4 directory:

`<stage1-root>/source-truth/`

Scientific files:

- `source-truth-decisions.tsv`;
- `source-truth-relations.tsv`;
- `monthly-source-truth-record.json`.

Sibling completion receipt:

`<stage1-root>/source-truth-completion.json`

The scientific directory contains exactly the three scientific files.

## Partial and temporary paths

Scientific staging directory:

`<stage1-root>/source-truth.partial/`

Temporary authoritative materialization directory:

`<stage1-root>/source-truth-materialization.partial/`

Temporary completion path:

`<stage1-root>/.source-truth-completion.json.tmp`

All three paths must be absent before execution.

No partial or temporary path is accepted as completed evidence.

## Publication

Scientific files are written with exclusive creation and fsync.

They are fully re-audited before publication.

Canonical publication uses hard links and does not use rename or replace.

The final scientific directory is created only after all partial scientific
files have passed audit.

The final files are re-read and re-audited after publication.

The sibling completion receipt is published only after the canonical
scientific directory passes final audit.

If completion publication fails, the newly published scientific directory is
removed so an incomplete Stage 4 execution cannot masquerade as complete.

## Input stability

Before canonical publication the executor re-audits:

- current metadata;
- current sequence-acquisition completion;
- complete catalogue chain;
- current catalogue identity.

Every FASTA used for source-truth evaluation is re-hashed before publication
and must remain identical in size and SHA256.

The same stability checks are repeated after scientific publication and before
completion publication.

## Completion receipt

Schema:

`bacselect-monthly-source-truth-completion-v1`

Status:

`SOURCE_TRUTH_EXECUTION_COMPLETE`

The completion receipt binds:

- release ID;
- source-snapshot ID;
- source-snapshot-record SHA256;
- execution Git commit;
- metadata record SHA256;
- metadata completion SHA256;
- complete catalogue-chain count and SHA256;
- current catalogue SHA256;
- current catalogue entry-set SHA256;
- retained, sequence-eligible and sequence-ineligible counts;
- all three population membership SHA256 values;
- source-truth decision count;
- relation count;
- decision artifact SHA256;
- relation artifact SHA256;
- monthly source-truth record SHA256;
- frozen monthly source-truth implementation SHA256;
- frozen source-truth execution implementation SHA256.

The completion auditor reconstructs the exact canonical receipt bytes.

## Fail-closed behaviour

Execution fails if any of the following occurs:

- metadata or catalogue population mismatch;
- broken catalogue history;
- current acquisition completion mismatch;
- catalogue origin batch provenance mismatch;
- missing origin batch evidence;
- missing authoritative FASTA;
- authoritative object size or SHA256 mismatch;
- candidate BioSample mismatch;
- package artifact mismatch;
- malformed component evidence;
- source-truth evaluation failure;
- non-terminal source-truth output;
- input mutation during execution;
- pre-existing canonical, partial or temporary Stage 4 output;
- publication read-back mismatch.

There is no Stage 4 fallback-to-fresh path.

## Portability

The executor performs no:

- NCBI query;
- general network access;
- cloud-provider SDK call;
- Slurm execution;
- institution-specific path access;
- Project Finch invocation.

The authoritative object root is a caller-supplied portable filesystem view of
the frozen content-addressed object namespace.

## Authorization

Real Stage 4 execution requires explicit:

`--authorize-real-execution`

The command also requires the expected Git commit, wrapper SHA256 and wrapper
test SHA256.

## Workflow state

Freezing this executor does not wire it into the monthly GitHub Actions
workflow.

The production workflow remains preflight-only until orchestration is frozen
separately.
