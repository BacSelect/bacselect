# Prospective monthly sequence-plan execution

## Status

This document freezes the portable execution boundary for BacSelect monthly
Stage 2 sequence planning.

It does not change the frozen Stage 2 scientific planning contract.

The executor is a bridge between:

1. the completed monthly metadata-eligibility stage;
2. the completed monthly cache-verification stage; and
3. the already frozen monthly sequence-plan implementation.

It performs no sequence acquisition, no network access, no source-universe
query, no cache-verification science, and no publication.

## Purpose

The Stage 2 executor converts already authenticated monthly metadata and
verified-cache evidence into the exact two scientific artifacts consumed by the
portable Stage 3B sequence-transport executor:

- `sequence-plan/fresh-targets.tsv`;
- `sequence-plan/monthly-sequence-plan-record.json`.

A sibling execution seal is published only after the scientific directory has
been independently read back and re-audited:

- `sequence-plan-completion.json`.

## Frozen scientific authority

The executor must call the frozen Stage 2 functions directly:

- `build_monthly_sequence_plan()`;
- `fresh_target_manifest_bytes()`;
- `serialize_monthly_sequence_plan_record()`;
- `audit_monthly_sequence_plan_record()`.

The executor must not reproduce, modify or extend the scientific partitioning
rules.

In particular, the frozen planner remains solely responsible for:

- retained-genome reconstruction from metadata assessments;
- cache reuse;
- fresh acquisition;
- stale-cache handling;
- BioSample mismatch handling;
- deterministic accession ordering;
- batch sizing;
- acquisition-reason assignment.

## Repository identity

Execution requires:

- the expected Git commit;
- a clean repository;
- exact wrapper SHA256 supplied by the caller;
- exact wrapper-test SHA256 supplied by the caller;
- the frozen execution-method SHA256;
- exact frozen Stage 2 core and test identities;
- exact frozen cache-verification core and test identities;
- exact frozen cache-verification executor, executor-test and method
  identities;
- exact frozen metadata-eligibility core and test identities.

The cache-verification executor remains the frozen authority for current
Stage 1, metadata and catalogue-history reconstruction.

## Current metadata authority

The executor calls the frozen cache-verification executor's
`load_current_metadata_context()`.

That call re-audits:

- Stage 1 release-start evidence;
- source-snapshot evidence;
- current metadata scientific artifacts;
- metadata completion evidence;
- execution commit;
- production path identity.

The Stage 2 executor separately reads
`metadata-eligibility/metadata-eligibility-assessments.jsonl` and audits those
bytes with the frozen metadata-assessment auditor.

The retained accession/BioSample mapping derived by the frozen Stage 2 planner
must exactly equal the retained mapping already authenticated by the metadata
context.

## Cache-verification authority

The completed cache scientific stage is:

`cache-verification/`

and must contain exactly:

- `cache-verification-results.jsonl`;
- `verified-cache-evidence.jsonl`;
- `cache-verification-record.json`.

The sibling completion artifact is:

`cache-verification-completion.json`.

The executor reuses the frozen cache executor's exact scientific-stage
read-back helper and independently audits:

- cache-verification results;
- verified-cache evidence;
- cache-verification record.

The verified-cache JSONL is reconstructed only through
`audit_verified_cache_evidence()`.

No cache evidence is manufactured by this executor.

## Cache completion and catalogue history

The executor independently rediscoveries the complete prior cumulative
sequence-cache catalogue chain using the frozen cache executor.

For a first release, an empty catalogue chain is not sufficient by itself.
The frozen first-release proof is rerun to ensure that earlier canonical
production namespaces do not contain sequence-acquisition, completion or
catalogue evidence outside the chain.

The independently reconstructed catalogue history contributes:

- history mode;
- chain count;
- deterministic chain SHA256;
- latest source-catalogue release ID;
- latest source-catalogue SHA256;
- latest audited catalogue `entries_sha256`;
- latest audited catalogue entry count.

For chained history, those four source-catalogue fields are derived directly
from the latest audited `CatalogueChainItem`. They are never copied from the
cache-verification completion receipt that is being audited.

For first-release history they are deterministically `None`, `None`, `None`
and zero.

The completed cache-verification receipt is then rebuilt and re-audited using:

- current release identity;
- current source snapshot;
- current source-snapshot-record SHA256;
- current execution commit;
- current metadata record and completion identities;
- current retained count;
- independently reconstructed catalogue history mode/count/SHA256;
- source-catalogue descriptive fields from the sealed receipt;
- counts from the independently audited cache-verification record;
- exact scientific artifact SHA256 identities.

This preserves the existing cache executor as the authority for the detailed
source-catalogue semantics while independently proving that the sealed receipt
belongs to the currently materialized catalogue chain.

## Planner input completeness

The planner receives:

1. the complete audited current metadata-assessment population; and
2. the complete audited `VerifiedMonthlyCacheEvidence` population.

The executor requires the resulting retained accession set to equal the
retained metadata context exactly.

The executor also requires the planner's cache-reuse accession set to equal the
audited verified-cache evidence population exactly.

Therefore:

- retained genomes without verified cache become fresh targets through the
  frozen planner;
- no verified-cache accession may disappear from the planner result;
- no non-retained verified-cache accession may be silently ignored;
- the executor does not create a second cache/fresh classification rule.

## Scientific output

The canonical scientific stage is:

`<stage1-root>/sequence-plan/`

The temporary stage is:

`<stage1-root>/sequence-plan.partial/`

The scientific directory contains exactly two regular files:

1. `fresh-targets.tsv`
2. `monthly-sequence-plan-record.json`

Directory mode is `0755`.

Artifact modes are `0644`.

The Stage 2 record is re-audited against:

- current source snapshot ID;
- current source-snapshot-record SHA256;
- exact fresh-target TSV bytes.

## Stage 3B hand-off

The existing portable Stage 3B executor consumes these exact paths through its
explicit CLI arguments:

- `--sequence-plan-record`;
- `--fresh-target-manifest`.

No Stage 3B code is modified by this work.

A Stage 2 release with zero fresh targets is valid. Stage 3B is simply not
invoked for such a release.

## Deterministic repeated audit

Before canonical scientific publication, the executor performs the complete
upstream reconstruction twice.

The two passes must agree on:

- metadata-context identity;
- metadata-assessment bytes;
- cache scientific artifact bytes;
- cache completion bytes;
- catalogue-history mode;
- catalogue-chain count;
- catalogue-chain SHA256.

The resulting Stage 2 scientific bytes must also be exactly identical across
both derivations.

Any change fails closed.

## No-clobber scientific publication

The executor does not publish the scientific directory with `os.rename()` or
`os.replace()`.

Publication is:

1. create `sequence-plan.partial` exclusively;
2. write and fsync both scientific artifacts;
3. read back and audit the partial stage;
4. repeat the complete upstream audit and scientific derivation;
5. create canonical `sequence-plan` with exclusive `mkdir`;
6. hard-link each already-audited artifact into the canonical directory;
7. fsync the canonical directory;
8. read back and re-audit the canonical scientific bytes;
9. require exact equality with the twice-derived candidate bytes;
10. remove the partial links only after successful canonical read-back;
11. fsync the Stage 1 root.

A competing final directory or artifact is never overwritten.

## Execution completion receipt

The sibling completion artifact is:

`<stage1-root>/sequence-plan-completion.json`

Schema:

`bacselect-monthly-sequence-plan-completion-v1`

Status:

`SEQUENCE_PLAN_EXECUTION_COMPLETE`

It binds:

- release ID;
- source snapshot ID;
- source-snapshot-record SHA256;
- execution Git commit;
- metadata record SHA256;
- metadata completion SHA256;
- cache-verification results SHA256;
- verified-cache-evidence SHA256;
- cache-verification-record SHA256;
- cache-verification-completion SHA256;
- retained count;
- cache-reuse count;
- fresh-acquisition count;
- fresh batch count;
- fresh-target-manifest SHA256;
- monthly-sequence-plan-record SHA256.

The receipt is deterministic canonical JSON.

It is written using a temporary inode plus a no-clobber hard link.

The final receipt is independently read back and rebuilt byte-for-byte.

## Existing-output policy

Execution fails if any of the following already exists before execution:

- `sequence-plan`;
- `sequence-plan.partial`;
- `sequence-plan-completion.json`;
- the completion temporary path.

The executor never overwrites a prior scientific stage or completion seal.

## Portability

The Stage 2 executor is local and offline.

It must not contain or invoke:

- Slurm;
- institution-specific paths;
- PHF infrastructure;
- Project Finch infrastructure;
- cloud-provider SDKs;
- HTTP clients;
- source acquisition;
- NCBI Datasets;
- publication services.

The only durable inputs are already materialized BacSelect production
artifacts.

## Authorization

The command-line entry point requires explicit
`--authorize-real-execution`.

Without that flag, execution fails before repository or production-state
mutation.

## Workflow state

This change does not wire Stage 2 into the monthly GitHub Actions workflow.

The production workflow remains preflight-only until orchestration is frozen
separately.
