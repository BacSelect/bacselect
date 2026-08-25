# BacSelect source-parser pre-outcome schema refinement

## Status

**PRE-OUTCOME IMPLEMENTATION REFINEMENT**

This note is frozen after acquisition of the raw external source metadata
snapshot but before any BacSelect metadata-eligibility classification, holdout
membership calculation, structural-feature calculation, or OPS-versus-SR
coverage outcome.

The frozen raw source snapshot is:

- snapshot ID: `snapshot-20260825T132821Z`;
- raw JSONL SHA256:
  `b1b016891ae4e976d03606dfb2f35f74b03d21cf3ec82832f77f4d113bd622d5`;
- raw record count: 70,850.

The raw source checkpoint was committed at:

`98cc62c90ec8226fbd16bca128aa8efb42aec8a8`

## Refinement 1: emitted JSON key form

The prospective source method refers semantically to NCBI assembly-report
fields using documentation-style names such as
`assemblyInfo.assemblyStatus`.

The frozen NCBI Datasets 18.35.0 CLI response produced by
`--as-json-lines` serializes the corresponding keys in snake_case, including:

- `assembly_info`;
- `assembly_info.assembly_status`;
- `assembly_info.assembly_level`;
- `assembly_info.atypical.is_atypical`;
- `assembly_info.atypical.warnings`;
- `assembly_info.biosample.accession`;
- `current_accession`;
- `source_database`.

The implementation therefore binds to the actual frozen CLI serialization
while preserving the already frozen semantic rules.

This does not alter the scientific eligibility rule.

## Refinement 2: query-return validation

A schema-only aggregate audit of the frozen raw response established that all
70,850 returned records expose:

- a valid versioned GCA accession;
- `current_accession == accession`;
- `source_database == SOURCE_DATABASE_GENBANK`;
- `assembly_info.assembly_status == current`;
- `assembly_info.assembly_level == Complete Genome`.

These observations validate the return shape of the already frozen server-side
discovery query. They are not holdout membership or selector outcomes.

The same schema-only audit observed that 12 records lack a BioSample object and
recorded the aggregate atypical-warning vocabulary. These are input-schema
observations only. No record-level eligibility classification was emitted or
frozen before this parser implementation.

## Refinement 3: test invocation

The BacSelect repository uses a `src/` layout and the `bacselect-dev`
environment does not currently install the package into that environment.

A plain:

`python -m pytest`

therefore fails during collection with `ModuleNotFoundError: bacselect`.

For validation in the current development environment, tests are invoked with:

`PYTHONPATH=src python -m pytest`

This is a test-harness/import-path correction only. It does not change package
code or scientific behavior.

## Sequencing of raw acquisition and parser validation

The prospective source method stated that implementation validation should
precede first network execution.

In practice, the raw metadata response was acquired and frozen before this
parser implementation was installed and tested.

That sequencing deviation is recorded explicitly.

The raw network acquisition performed no candidate eligibility
classification, no baseline-membership comparison, no structural-feature
calculation, and no selector comparison. The parser and its synthetic tests are
therefore frozen before the first outcome-producing eligibility analysis of the
snapshot.

No raw snapshot data are consumed by the package installation or test suite.

## Identity blinding

Synthetic tests use dummy accessions only.

The parser's blinded aggregate-summary helper emits counts by decision, reason,
and normalized warning. It does not emit accessions, BioSample identifiers,
organism names, or TaxIDs.

Record identities remain available internally for later fail-closed
reconciliation but are not part of blinded scientific interpretation output.

## Scope

This parser implements only the metadata layer.

It does not decide:

- repeated-BioSample sequence reconciliation;
- Primary Assembly component sequence eligibility;
- source structural-integrity eligibility;
- chromosome-component integrity adjudication;
- species resolution;
- membership relative to the frozen 55,306-genome baseline;
- structural features;
- OPS/SR coverage.

Those stages remain separately gated by the prospective source and
selector-resolution methods.
