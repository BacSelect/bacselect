# BacSelect monthly release package v1

## Status

This document prospectively freezes the Stage 15 serialization contract before
the first BacSelect monthly production package is generated.

It does not generate, publish, upload, archive or modify a monthly release.

## Release identity

A monthly public panel is identified by:

- release `YYYY.MM`;
- selector `OPS`;
- selector version `1.0.0`;
- architecture schema `1`;
- panel size `N`.

The monthly panel identity string is:

`bacselect-YYYY.MM`

Supported public panel sizes are:

`10, 20, 50, 100, 200, 500`

Custom integer N from 10 through 500 remains the exact prefix of the same
monthly ladder and does not rerun OPS.

## Canonical public metadata ladder

The package contains one canonical 500-row metadata ladder:

`bacselect-YYYY.MM-metadata-ladder-n500.tsv`

Its exact ordered fields are:

1. `selection_rank`
2. `first_public_panel_n`
3. `genbank_assembly_accession`
4. `biosample_accession`
5. `ncbi_organism_name`
6. `ncbi_organism_taxid`
7. `bacselect_species_name`
8. `bacselect_species_taxid`
9. `assembly_name`
10. `submitter`
11. `assembly_release_date`
12. `panel_identity`
13. `selector`
14. `selector_version`
15. `architecture_schema_version`
16. `source_snapshot_sha256`
17. `taxonomy_snapshot_sha256`
18. `execution_git_commit`
19. `ncbi_assembly_url`

All fields are non-empty text. Tabs, carriage returns and newlines are
forbidden inside fields.

`selection_rank` is exactly 1 through 500.

`first_public_panel_n` is the smallest preset panel containing that rank.

The 500 rows contain 500 unique canonical GCA accession.version identifiers and
500 distinct resolved BacSelect species TaxIDs.

## Metadata sources

Public metadata is derived only from frozen monthly evidence.

- GenBank assembly accession, BioSample accession, NCBI organism name, NCBI
  organism TaxID, assembly name, submitter and assembly release date come from
  the immutable day-01 NCBI assembly metadata response.
- BacSelect species TaxID comes from the frozen monthly taxonomy-resolution
  decision.
- BacSelect species name is the scientific name for that resolved species
  TaxID in the frozen monthly taxonomy `names.dmp`.
- `source_snapshot_sha256` is the SHA256 of the immutable day-01 raw NCBI
  assembly metadata response.
- `taxonomy_snapshot_sha256` is the SHA256 of the frozen monthly NCBI taxonomy
  archive.
- `execution_git_commit` is the exact Stage 13 selector execution commit.

No current web lookup is allowed during release packaging.

## Per-panel human-facing downloads

For each preset N, Stage 15 produces:

- `bacselect-YYYY.MM-nN.txt`
- `bacselect-YYYY.MM-nN.tsv`
- `bacselect-YYYY.MM-nN.xlsx`

The TXT file is the exact newline-delimited accession prefix already frozen by
Stage 14.

The TSV/XLSX schema is:

1. `panel_identity`
2. `panel_size`
3. `selection_rank`
4. `genbank_assembly_accession`
5. `biosample_accession`
6. `ncbi_organism_name`
7. `ncbi_organism_taxid`
8. `bacselect_species_name`
9. `bacselect_species_taxid`
10. `assembly_name`
11. `submitter`
12. `assembly_release_date`
13. `selector`
14. `selector_version`
15. `architecture_schema_version`
16. `source_snapshot_sha256`
17. `taxonomy_snapshot_sha256`
18. `execution_git_commit`
19. `ncbi_assembly_url`

Rows are the exact first N rows of the canonical metadata ladder.

## XLSX byte contract

XLSX output mirrors the existing BacSelect website workbook contract.

It uses:

- one worksheet named `Panel metadata`;
- inline strings only;
- frozen first row;
- autofilter over all 19 columns;
- the frozen BacSelect header style;
- eight fixed XLSX members;
- ZIP storage method 0, without compression;
- UTF-8 ZIP filename flag;
- DOS timestamp 1980-01-01 00:00:00;
- deterministic member order;
- no dynamic timestamps or application-generated IDs.

No `openpyxl`, `xlsxwriter` or other external workbook library is required.

## Public release package

The final Stage 15 executor will include at least:

- the canonical N=500 metadata ladder TSV;
- TXT, TSV and XLSX downloads for all six preset N;
- the complete Stage 13 OPS ladder;
- Stage 13 selector trace;
- Stage 14 structural-coverage summary;
- release summary;
- release evidence manifest;
- release provenance;
- SHA256 checksums.

The detailed distance table remains preserved scientific evidence and does not
need to be duplicated into routine human-facing downloads.

## Scientific evidence binding

Large upstream scientific evidence is not copied merely to create duplicate
bytes in the routine public package.

Instead, Stage 15 contains a deterministic evidence manifest binding immutable
production evidence by:

- semantic role;
- release-root-relative path;
- SHA256;
- byte count.

The frozen role vocabulary is:

- `source_snapshot_metadata`
- `metadata_eligibility`
- `source_truth_eligibility`
- `biosample_reconciliation`
- `chromosome_integrity_review`
- `taxonomy_snapshot_identity`
- `species_resolution`
- `raw_structural_features`
- `percentile_geometry`
- `species_representatives`
- `complete_diversity_ladder`
- `selector_trace`
- `public_panel_coverage`

Those evidence objects remain eligible for later deterministic scholarly
archive packaging.

## Checksums

`SHA256SUMS` is ASCII text.

Each line is:

`<lowercase SHA256><two spaces><filename>`

Rows are sorted lexicographically by filename.

`SHA256SUMS` does not include itself.

Its own identity is bound by the Stage 15 execution record and completion
receipt.

## Production and rebuild

The production Stage 15 package and independent rebuild package must be
byte-identical for every deterministic artifact.

Production and rebuild use separate fresh roots.

Any mismatch blocks publication.

## Repository boundary

This serialization contract is pure.

Freezing this document and its implementation does not create September
release bytes.

No Stage 15 production directory may exist before the execution wrapper and
tests are frozen.
