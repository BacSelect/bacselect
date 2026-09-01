# Selector v1 reference public metadata

## Status

Prospective public-download contract for the frozen selector-v1 reference
panels.

This contract adds descriptive metadata to the already frozen reference-panel
membership. It does not change selector outcomes, ladder order, panel
membership, structural features, taxonomy decisions, or selector validation.

## Public identity

The selector-v1 reference identity is:

`selector-v1-reference`

It is not a dated BacSelect monthly release and must not be labelled with a
`YYYY.MM` release identifier.

## Frozen evidence

Reference metadata is derived only from evidence already bound to selector-v1:

1. the exact 500-accession winning OPS ladder;
2. the exact frozen NCBI source JSONL snapshot;
3. the exact selector-bound accession-to-species-TaxID mapping;
4. the exact frozen NCBI taxonomy archive containing `names.dmp`;
5. the official panel-generation summary and provenance.

No current or live NCBI lookup is permitted when reconstructing the
selector-v1 reference metadata.

## NCBI and BacSelect taxonomy

The public metadata preserves both:

- the source NCBI organism name and TaxID;
- the BacSelect-resolved species scientific name and species TaxID.

These are separate fields because the source organism identity can differ from
the species identity used by BacSelect.

The BacSelect species name is the `scientific name` associated with the frozen
BacSelect `species_taxid` in the exact frozen taxonomy `names.dmp`.

## Canonical metadata ladder

The canonical 500-row reference metadata ladder contains:

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

The canonical ladder is always exactly 500 rows in winning-selector rank order.

## Downloaded panel metadata

For a requested panel size `N`, where `10 <= N <= 500`, the public metadata
download is exactly the first `N` rows of the canonical metadata ladder.

The downloaded table contains:

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

`panel_size` is the actual requested N, including custom values such as 73.

`first_public_panel_n` is intentionally not included in the downloaded panel
table because it describes preset-ladder membership rather than the requested
panel itself.

## Formats

TSV is the canonical tabular representation.

Excel is a human-friendly rendering of the same downloaded-panel rows and
columns. It must not contain additional scientific values or dynamic website
state.

The accession-list download remains a one-column utility derivative of the
same ordered panel membership.

## Dynamic website state

Download counts and the countdown to the next BacSelect monthly update are
website state only.

They must not be written into TSV, Excel, accession-list, or scientific
release artefacts.
