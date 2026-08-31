# Prospective monthly metadata-eligibility execution

## Status

This document defines the portable production execution boundary for the
already-frozen monthly metadata-eligibility evidence contract.

It does not alter the frozen metadata science.

It does not perform a network request, inspect sequence cache state, acquire
genome sequence, execute Stage 3 transport, or publish a Zenodo record.

## Upstream requirement

Execution consumes one already-complete Stage 1 production root.

The executor requires:

- `release-start-checkpoint.json`;
- `assembly_data_report.raw.jsonl`;
- `source-snapshot-record.json`.

The source-snapshot record is audited against the exact checkpoint and raw
response before any metadata stage directory is created.

The audited Stage 1 record must bind:

- the requested execution Git commit;
- NCBI Datasets version `18.35.0`;
- the frozen scientific environment identity;
- the canonical release ID and source-snapshot identity.

The supplied Stage 1 directory must equal:

`<production-root>/<release>/production/<commit>`

No alternate directory is accepted.

## Repository identity

The command-line production boundary requires:

- `HEAD == expected commit`;
- local `origin/main == expected commit`;
- a clean working tree;
- the exact frozen `source_eligibility.py` SHA256;
- the exact frozen monthly metadata-contract SHA256;
- the exact frozen monthly metadata-contract test SHA256;
- the exact frozen monthly metadata-contract method SHA256;
- the exact metadata-execution method SHA256;
- caller-supplied exact SHA256 identities for the executor and its test.

These checks are local Git and local-file reads only.

They do not contact GitHub.

## Scientific implementation identity

The executor binds to:

`src/bacselect/source_eligibility.py`

SHA256:

`6e57dd950f972a9883e8fcbc78a18c694a5fabda58b03835f268eef681a03cc2`

and:

`src/bacselect/monthly_metadata_eligibility.py`

SHA256:

`90c86d304d42c3e7dc4978a28d1d01a92660d9a359e07516f536ff3a0a2df87f`

The frozen metadata-contract method is also bound by SHA256.

The metadata executor does not duplicate metadata-eligibility rules.

## Stage transaction

The scientific stage directory is:

`metadata-eligibility/`

Before publication, all work occurs under:

`metadata-eligibility.partial/`

Both paths are below the audited Stage 1 production root.

Execution fails if the final stage, partial stage, or completion receipt already
exists.

A previous partial or incompletely published execution is never silently
resumed, overwritten or deleted.

## Persisted scientific artifacts

The stage directory contains exactly:

- `metadata-eligibility-assessments.jsonl`;
- `metadata-eligibility-summary.json`;
- `metadata-eligibility-record.json`.

Files are written as fresh mode-0644 files through a temporary file, fsynced,
atomically renamed and read back.

No extra files or directories are accepted inside the scientific stage.

The stage directory is mode 0755.

## Independent reconstruction

The executor reconstructs metadata assessments directly from the exact Stage 1
raw bytes using the frozen parser.

It then creates:

1. canonical row-level assessments;
2. the blinded summary derived from those assessments;
3. the provenance record binding Stage 1, raw source, parser implementation,
   assessments and summary.

All three artifacts are read back and independently audited while still inside
the partial stage directory.

Only after those audits succeed is the partial directory fsynced and atomically
renamed to `metadata-eligibility/`.

The parent production directory is fsynced after that rename.

## Post-promotion verification

After the directory rename, the executor verifies:

- exact three-file inventory;
- directory mode 0755;
- artifact modes 0644;
- byte-for-byte identity with the pre-promotion payloads;
- assessment audit;
- summary audit;
- provenance-record audit.

The directory name alone is not sufficient evidence that execution completed.

## Completion receipt

Only after post-promotion verification succeeds does the executor create:

`metadata-eligibility-completion.json`

as a sibling of `metadata-eligibility/`.

The completion receipt is execution evidence, not a fourth scientific
metadata artifact.

It binds:

- schema and completion status;
- release ID;
- source-snapshot ID;
- Stage 1 source-snapshot-record SHA256;
- execution Git commit;
- canonical metadata stage name;
- exact SHA256 identities of all three scientific metadata artifacts.

The receipt is canonical JSON, written as a fresh mode-0644 atomic artifact,
fsynced, read back and audited.

A downstream stage must require and audit both:

- `metadata-eligibility/`;
- `metadata-eligibility-completion.json`.

The existence of `metadata-eligibility/` without a valid completion receipt
means the stage is incomplete and must not be consumed.

## Failure semantics

Any scientific, provenance or artifact-validation failure before final
directory promotion leaves no canonical metadata stage.

A failure after directory promotion but before completion-receipt publication
may leave `metadata-eligibility/` present, but no valid completion receipt.

Such a directory is explicitly incomplete and must not be consumed.

No previous evidence is automatically deleted or overwritten.

This distinction also covers exceptional filesystem failures around final
directory synchronization.

## Explicit production authorization

The command-line entry point requires:

`--authorize-real-execution`

This authorization permits only this local metadata-production write.

It does not authorize:

- a new NCBI query;
- sequence acquisition;
- cache reuse;
- Zenodo publication;
- website publication.

## Remaining production boundaries

Completion of this stage does not establish cache reuse.

The next required boundary remains monthly cache verification.

Only after metadata eligibility and cache verification are both frozen can the
monthly Stage 2 sequence-plan writer safely materialize its production
partition.
