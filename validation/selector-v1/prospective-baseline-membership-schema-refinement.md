# BacSelect baseline-membership pre-outcome schema refinement

## Status

**PRE-OUTCOME MEMBERSHIP IMPLEMENTATION REFINEMENT**

This note is frozen after the metadata-eligibility result was committed, but
before any fresh metadata-retained accession was compared with the frozen
55,306-genome baseline.

No structural features or OPS-versus-SR outcomes have been calculated.

## Frozen inputs

Fresh raw source snapshot:

- snapshot ID: `snapshot-20260825T132821Z`;
- raw JSONL SHA256:
  `b1b016891ae4e976d03606dfb2f35f74b03d21cf3ec82832f77f4d113bd622d5`.

Frozen baseline raw 300/2400 feature matrix:

- file:
  `structural-feature-matrix-300-2400.tsv`;
- SHA256:
  `86c0c3d49317dfc3cc452114e3863666fe2112b6a3ae8dae2090b60a2a598948`;
- data rows: 55,306.

## Baseline accession column

A schema-only audit of the frozen baseline matrix established that it contains
15 columns and exactly one column in which every one of the 55,306 rows is a
unique versioned canonical GCA accession.

That column is named:

`canonical_genbank_assembly_accession`

and is column index 2 in the current TSV serialization.

The membership implementation binds to the **column name**, not the positional
index.

## Failed positional audit

An earlier schema audit incorrectly assumed that column 0 contained accessions.
Column 0 is actually `batch`, so the fail-closed validation stopped with:

- 55,306 data rows;
- 111 unique values in column 0;
- zero canonical GCA matches.

No fresh retained accession was compared with the baseline during that failed
audit.

This failed assumption therefore produced no membership result and no
scientific outcome.

## Membership definition

For this stage only:

1. load the frozen 55,306 canonical baseline GCA accessions;
2. take only records already classified `RETAIN_METADATA` by the frozen source
   metadata parser;
3. partition those retained accessions into:
   - present in the frozen baseline;
   - absent from the frozen baseline.

The absent group is described only as **metadata-retained and absent from the
frozen baseline** or **newly observed relative to the frozen baseline**.

It is not yet the final external holdout because sequence eligibility,
repeated-BioSample reconciliation, source structural integrity, species
resolution, and the frozen adequacy gate remain outstanding.

It must not be described as newly deposited unless deposition dates are
separately established.

## Blinding

The scientific output of this stage is aggregate counts only.

It does not contain:

- GCA or GCF accessions;
- BioSample identifiers;
- organism names;
- TaxIDs;
- species names.

The implementation may hold accessions in memory to perform exact set
membership, but identities are not emitted by the blinded summary.

## Scope

This comparator does not calculate:

- sequence eligibility;
- repeated-BioSample reconciliation;
- source structural-integrity eligibility;
- taxonomy/species resolution;
- structural features;
- panel distances;
- OPS/SR selector outcomes.

The prospective selector-resolution decision remains unresolved.
