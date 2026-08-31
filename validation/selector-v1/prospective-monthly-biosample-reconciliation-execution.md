# Prospective monthly repeated-BioSample execution

## Status

This document freezes the portable execution boundary for monthly BacSelect
Stage 5 repeated-BioSample reconciliation.

It does not authorize a real monthly production execution.

## Frozen scientific boundary

Stage 5 adds no scientific decision implementation.

The executor must use:

- frozen Stage 4 source-truth decisions to define the population;
- frozen Stage 4 evidence/provenance bridging for sequence reconstruction;
- frozen `fingerprint_stage2_candidate()` for topology-aware fingerprints;
- frozen monthly Stage 5 pure contract for reconciliation and serialization.

No alternative repeated-BioSample rule or fingerprint implementation is
permitted.

## Stage 4 authentication

Before Stage 5 derives any population, the executor independently re-audits:

- current retained metadata;
- current sequence-acquisition completion;
- the complete cumulative sequence-cache catalogue chain including the current
  release;
- the exact Stage 4 source-truth scientific directory;
- Stage 4 decisions;
- Stage 4 relations;
- Stage 4 source-truth record;
- Stage 4 completion receipt.

The exact SHA256 of `source-truth-decisions.tsv` must equal the authenticated
Stage 4 completion `decisions_sha256`.

The executor reconstructs Stage 4 population membership and completion
accounting rather than trusting a loose JSON field.

## Stage 5 population

Only Stage 4 `SUITABLE` candidates enter Stage 5.

The monthly Stage 5 pure contract must independently derive exactly the same
population from the authenticated Stage 4 decision artifact.

Stage 4 exclusions and unresolved candidates are terminal and cannot
participate in BioSample representative choice.

## Current sequence evidence

For an accession whose cumulative catalogue provenance originates in the
current release, the executor reuses the current audited sequence-acquisition
completion and frozen Stage 4 `_current_batch_evidence()` bridge.

The executor then uses frozen `validate_candidate_bridge()` to prove:

- exact accession identity;
- exact BioSample identity;
- sequence eligibility;
- `PASS` candidate status;
- Primary Assembly component count;
- exact accession-scoped package manifest;
- exact package artifact identities;
- exact FASTA basename, SHA256, size and package path.

The current local FASTA is resolved using the frozen package resolver.

Its SHA256 and size are rechecked before fingerprinting and again during
publication stability checks.

## Historical sequence evidence

For an accession whose origin release predates the current release, the
executor uses frozen `load_batch_evidence()` against the authoritative object
store.

That loader re-authenticates:

- origin batch summary;
- candidate audit;
- component audit;
- package-files manifest;
- origin sequence-acquisition completion;
- package read-back identity;
- batch-common package objects.

The accession FASTA is then loaded only through `read_required_object()` using
the exact SHA256 and size authenticated by the catalogue and origin package
manifest.

The FASTA is materialized temporarily under a candidate-specific
`package/<accession-scoped-path>` tree solely so the frozen source-evidence
loader can reconstruct the exact same evidence model used by Stage 4.

The temporary candidate tree is deleted immediately after fingerprinting.

No historical FASTA fallback, network fetch, EFetch, fuzzy path resolution or
accession-prefix search is permitted.

## Future-origin rejection

A catalogue provenance release later than the current monthly release fails
closed.

Current and prior release classification is based only on validated `YYYY.MM`
release identity.

## Fingerprint evidence

For every Stage 4 `SUITABLE` accession, the executor constructs the exact
frozen source-truth `CandidateAudit`, `ComponentAudit` and `PackageFile`
objects through the already frozen Stage 4 bridge.

It then calls only:

`fingerprint_stage2_candidate()`

That primitive must recompute `source_evidence_sha256` and require exact
equality to the Stage 4 decision before computing the topology-aware assembly
fingerprint.

The executor never substitutes Stage 4 `sequence_set_sha256`.

## Scientific outputs

Canonical Stage 5 scientific directory:

`<stage1-root>/biosample-reconciliation/`

Exact inventory:

- `biosample-reconciliation-decisions.tsv`;
- `monthly-biosample-reconciliation-record.json`.

The identity-bearing decision artifact contains accession, BioSample,
source-evidence SHA256, assembly fingerprint, Stage 5 status and Stage 5
reason.

## Publication safety

Before scientific evaluation, the executor requires all of these paths to be
absent:

- canonical Stage 5 directory;
- partial Stage 5 directory;
- materialization directory;
- Stage 5 completion receipt;
- Stage 5 completion temporary path.

Scientific artifacts are first written with `O_EXCL`, mode `0644`, fsync and
exact read-back validation into:

`biosample-reconciliation.partial`

The partial stage must have exactly the two scientific artifacts.

The canonical directory is created without overwrite and populated by
hard-linking the already audited partial files.

No `rename()` or `replace()` publication is used.

If publication validation fails, the incomplete canonical Stage 5 directory
is removed and no completion receipt is published.

## Stability gates

Before and after canonical scientific publication, and before and after
completion publication, the executor rechecks:

- current metadata identity;
- complete catalogue-chain identity;
- current catalogue identity;
- Stage 4 decisions;
- Stage 4 relations;
- Stage 4 record;
- Stage 4 completion receipt;
- every current local FASTA observed during fingerprinting;
- every current-release batch provenance bundle used during fingerprinting by
  rerunning frozen `_current_batch_evidence()` against the freshly re-audited
  current sequence-acquisition completion;
- every authoritative historical FASTA object observed during fingerprinting;
- every historical batch provenance bundle used during fingerprinting by
  rerunning frozen `load_batch_evidence()`, thereby re-authenticating its
  batch summary, candidate audit, component audit, package-files manifest,
  origin acquisition completion and batch-common package objects.

A changed upstream artifact fails the execution closed.

## Completion receipt

Schema:

`bacselect-monthly-biosample-reconciliation-completion-v1`

Status:

`BIOSAMPLE_RECONCILIATION_EXECUTION_COMPLETE`

The receipt binds:

- release ID;
- source-snapshot ID;
- source-snapshot-record SHA256;
- execution Git commit;
- metadata record and completion SHA256;
- cumulative catalogue-chain count and SHA256;
- current sequence-cache catalogue and entries SHA256;
- Stage 4 completion SHA256;
- Stage 4 decision SHA256;
- Stage 4 record SHA256;
- Stage 5 `SUITABLE` count and membership SHA256;
- Stage 5 decision count;
- `CONTINUE` count;
- `NONREPRESENTATIVE` count;
- `REVIEW_UNRESOLVED` count;
- all Stage 5 BioSample group counts;
- Stage 5 decisions SHA256;
- Stage 5 record SHA256;
- frozen Stage 5 scientific implementation identities.

Accounting must prove:

`CONTINUE + NONREPRESENTATIVE + REVIEW_UNRESOLVED = decision count`

`decision count = Stage 4 SUITABLE count`

`singleton groups + repeated groups = all BioSample groups`

`identical repeated groups + differing repeated groups = repeated groups`

## Completion publication

The completion receipt is written to a unique temporary file using `O_EXCL`,
mode `0644`, fsync and exact read-back.

After a full stability check it is hard-linked to:

`<stage1-root>/biosample-reconciliation-completion.json`

The final receipt is re-audited and upstream stability is rechecked before the
temporary link is removed.

Presence of the completion receipt therefore marks successful Stage 5
execution.

## Portability

The executor contains no:

- NCBI network acquisition;
- Slurm;
- `/NGS/...` path;
- PHF-specific path;
- institution-specific environment;
- cloud-provider-specific API;
- employer runner dependency.

Current local sequence evidence and provider-neutral authoritative objects are
the only sequence inputs.

## Downstream boundary

Only Stage 5 `CONTINUE` candidates may enter monthly Stage 6 structural or
chromosome-component integrity.

A later Stage 6 exclusion does not promote a Stage 5
`NONREPRESENTATIVE` accession.

Stage 5 does not inspect or generate taxonomy, structural features, OPS/SR
distances, panel membership or selector outcomes.

## Real-execution authorization

The CLI requires an explicit:

`--authorize-real-execution`

flag.

The monthly workflow remains unchanged and preflight-only while this executor
is being frozen and validated.
