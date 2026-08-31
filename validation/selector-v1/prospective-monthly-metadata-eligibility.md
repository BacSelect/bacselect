# Prospective monthly metadata-eligibility evidence

## Status

This document freezes the pure monthly metadata-eligibility evidence contract.

It does not execute NCBI Datasets, contact a network service, inspect a cache,
alter the monthly workflow, or enable source-sequence acquisition.

## Scientific implementation

The monthly layer does not redefine metadata eligibility.

It applies the already-frozen implementation in:

`src/bacselect/source_eligibility.py`

to the exact raw Stage 1 NCBI Datasets JSONL response.

The frozen metadata semantics therefore remain:

- canonical versioned `GCA_` identity;
- current accession consistency;
- GenBank source;
- current assembly status;
- Complete Genome assembly level;
- supported BioSample identity;
- automatic exclusion only for the frozen atypical-warning set;
- withholding for unresolved malformed atypical-warning structure.

Sequence eligibility, repeated-BioSample reconciliation, structural integrity,
taxonomy and selector outcomes remain later stages.

## Exact raw-source reconstruction

The evidence contract receives the exact Stage 1 raw-response bytes.

It parses each nonblank JSONL line and calls the frozen
`source_eligibility.assess_records()` implementation.

The resulting assessments are sorted by accession before persistence.

The production evidence record later reconstructs those assessments directly
from the raw response. Caller-supplied assessments therefore cannot establish
scientific identity independently of the Stage 1 bytes.

## Row-level assessment artifact

The canonical row-level artifact is:

`metadata-eligibility-assessments.jsonl`

Each line contains exactly:

- schema version;
- accession;
- BioSample or null;
- metadata decision;
- canonical sorted reasons;
- normalized atypical warnings.

Each JSON object uses deterministic single-line canonical serialization.

Rows are accession-sorted and accession identity must be unique.

The artifact preserves the row-level information required by the monthly
sequence planner.

## Blinded aggregate summary

The canonical blinded artifact is:

`metadata-eligibility-summary.json`

It contains only:

- record count;
- decision counts;
- reason counts;
- warning counts.

It contains no accession or BioSample identifiers.

The summary is deterministically reconstructed from the row-level assessment
artifact.

## Provenance record

The canonical provenance artifact is:

`metadata-eligibility-record.json`

It binds:

- exact source snapshot ID;
- SHA256 of the Stage 1 source-snapshot record;
- exact Stage 1 raw-response SHA256 and byte count;
- exact row-level assessment SHA256;
- exact blinded-summary SHA256;
- SHA256 of the frozen source-eligibility implementation;
- total assessment count;
- retained count;
- excluded count;
- withheld count;
- completion status and schema version.

Before that record can be built, the assessment artifact is independently
reconstructed from the exact raw Stage 1 bytes and must match byte-for-byte.

## Execution boundary still pending

This contract is pure.

A separate production executor must still:

1. audit `release-start-checkpoint.json`;
2. audit `source-snapshot-record.json` against the exact raw response;
3. prove the expected production Git commit;
4. prove the exact `source_eligibility.py` implementation SHA256;
5. write the three canonical metadata artifacts below the audited production
   root;
6. read them back and audit them before atomic completion.

That executor will be frozen separately.

## Cache boundary

Metadata eligibility does not inspect or classify cache reuse.

The verified monthly cache-evidence boundary remains a separate prerequisite
for the Stage 2 sequence-plan writer.

For the first monthly release, an empty cache may be scientifically valid only
when that empty state is explicitly established by the future monthly
cache-verification evidence layer.
