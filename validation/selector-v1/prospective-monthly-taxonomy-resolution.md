# BacSelect monthly Stage 8 taxonomy resolution

## Status

This document prospectively freezes the monthly Stage 8 taxonomy-resolution
execution boundary before the first monthly taxonomy-resolution result is
generated.

It changes no taxonomy scientific rule.

## Scientific rule

For every candidate that reached Stage 6 status `PASS`, Stage 8 begins with the
structured `organism.tax_id` from the frozen monthly Stage 1 NCBI Datasets raw
source response.

The TaxID is normalized through the frozen monthly Stage 7 `merged.dmp`,
`delnodes.dmp` and `nodes.dmp`.

The first lineage ancestor whose rank is exactly `species` is the canonical
species grouping TaxID.

The frozen implementation remains:

- `src/bacselect/source_taxonomy.py`;
- `src/bacselect/source_post_sequence_eligibility.py`;
- `src/bacselect/source_taxonomy_execution.py`;
- `src/bacselect/source_eligibility.py`.

No live taxonomy service is queried during Stage 8.

## Monthly input boundary

The canonical monthly Stage 6 decision artifact is authenticated through the
frozen Stage 6-v2 and Stage 7-v3 chain.

Only rows with:

`chromosome_integrity_status = PASS`

enter taxonomy resolution.

Candidates that reached Stage 6:

- `REVIEW_UNRESOLVED`; or
- `EXCLUDE_SOURCE_REPLICON_INTEGRITY`

are terminal before taxonomy and are not passed to the taxonomy resolver.

The monthly Stage 6 table is not rewritten into the historical selector
validation Stage 3 schema.

Instead, after the monthly table has been authenticated and audited, Stage 8
constructs the small in-memory compatibility population required by the
already-frozen taxonomy evaluator.

This adapter changes no membership and no scientific status.

## Source TaxID binding

The sole source of candidate organism TaxIDs is:

`assembly_data_report.raw.jsonl`

from the authenticated current monthly Stage 1 snapshot.

The exact raw-response SHA256 must match the identity bound by Stage 7-v3.

Every Stage 8 candidate must occur exactly once in the frozen raw source
mapping and must carry a positive integer `organism.tax_id`.

Names are not fallback taxonomy evidence.

## Taxonomy snapshot binding

Stage 8 consumes only the canonical Stage 7-v3 snapshot from the same monthly
release.

At minimum it authenticates:

- Stage 7-v3 completion;
- monthly taxonomy-snapshot record;
- `nodes.dmp`;
- `merged.dmp`;
- `delnodes.dmp`;
- taxonomy snapshot identity;
- Stage 7 execution commit.

No taxonomy download occurs in Stage 8.

## Resolution semantics

The frozen taxonomy composition semantics are unchanged.

Successful resolution produces:

- status `PASS`;
- reason `TAXONOMY_SPECIES_RESOLVED`;
- positive normalized organism TaxID;
- positive species TaxID.

Unresolved normalization or lineage traversal produces:

`REVIEW_UNRESOLVED`

with the existing frozen reason codes.

No unresolved taxonomy result is converted into a successful species grouping.

## Monthly output

The canonical Stage 8 directory is:

`taxonomy-resolution`

The acquisition/execution workspace is:

`taxonomy-resolution.partial`

The canonical decisions file is:

`taxonomy-resolution-decisions.tsv`

Its columns are:

1. `canonical_genbank_assembly_accession`;
2. `organism_taxid`;
3. `normalized_organism_taxid`;
4. `species_taxid`;
5. `taxonomy_status`;
6. `taxonomy_reason`.

The monthly field names deliberately remove the historical selector-validation
`stage4_*` naming while preserving the exact frozen decision values.

The canonical record is:

`monthly-taxonomy-resolution-record.json`

Its schema is:

`bacselect-monthly-taxonomy-resolution-record-v1`

The completion receipt is:

`taxonomy-resolution-completion-v1.json`

Its schema is:

`bacselect-monthly-taxonomy-resolution-completion-v1`

The terminal completion status is:

`TAXONOMY_RESOLUTION_EXECUTION_COMPLETE`

## Provenance

The Stage 8 record binds at minimum:

- monthly release ID;
- source snapshot ID;
- source production commit;
- taxonomy snapshot ID;
- Stage 7 execution commit;
- Stage 8 execution commit;
- Stage 6 decision, record and completion identities;
- Stage 7 record and completion identities;
- raw source-response SHA256;
- `nodes.dmp`, `merged.dmp` and `delnodes.dmp` SHA256;
- frozen taxonomy implementation SHA256 identities;
- exact Stage 8 input count and membership SHA256;
- source record count;
- exact decision count;
- PASS and unresolved counts;
- exact decision SHA256;
- distinct resolved species-TaxID count.

## Stage boundary

Stage 8 performs taxonomy resolution only.

It does not:

- construct the complete monthly eligible universe;
- calculate structural features;
- calculate species-balanced percentiles;
- choose species representatives;
- run OPS;
- generate public panels;
- publish a release;
- publish to Zenodo.

Those remain later monthly stages.

A successful Stage 8 completion with unresolved taxonomy rows records the
scientific state faithfully. Later publication remains fail-closed according to
the monthly publication contract.

## Stability and failure

Stage 1 through Stage 7 evidence is reauthenticated before final Stage 8
publication and again before completion publication.

Any upstream identity change fails closed.

Existing canonical, partial or completion paths are never overwritten.

A canonical Stage 8 directory without its valid completion receipt is
incomplete evidence and does not authorize Stage 9.
