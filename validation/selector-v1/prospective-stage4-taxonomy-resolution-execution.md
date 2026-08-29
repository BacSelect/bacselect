# BacSelect selector-v1 Stage 4 taxonomy-resolution execution

**PROSPECTIVE EXECUTION METHOD - NO STAGE 4 TAXONOMY RESULT GENERATED**

This method fixes the candidate input boundary, source-TaxID binding,
taxonomy-reference binding, resolution semantics, output contract, provenance,
blinding, testing, execution, audit and completion procedure for BacSelect
selector-v1 Stage 4 taxonomy resolution.

It is frozen after successful completion and Git freeze of Stage 3
chromosome-integrity evidence and before any real BacSelect candidate TaxID is
resolved against the frozen BacSelect taxonomy snapshot.

## Parent checkpoint

Parent BacSelect commit:

`a5d009d88d8e73378dcd99aabcb0554700525586`

Frozen Stage 3 completion-evidence SHA256:

`c5aff0e1e5cca6202688198a49069b1ae3e7b35d19f4939538d7c3f01ff562d2`

Stage 3 status is:

`STAGE3_CHROMOSOME_INTEGRITY_COMPLETE`

At this checkpoint:

- Stage 3 chromosome-integrity execution is complete;
- Stage 3 completion evidence is frozen in Git;
- the BacSelect taxonomy snapshot is already acquired and frozen;
- no real candidate TaxID has been resolved by Stage 4;
- no Stage 4 species TaxID has been generated;
- no complete eligible fresh universe has been generated;
- no external decision holdout has been generated;
- no structural feature has been calculated for that holdout;
- no OPS/SR external-holdout result has been calculated.

## Scientific precedence

The frozen post-sequence precedence remains:

1. source truth;
2. repeated-BioSample reconciliation;
3. chromosome-component integrity;
4. taxonomy;
5. complete eligible fresh universe.

Stage 4 must not reconsider or alter an earlier terminal outcome.

Taxonomy is evaluated only for a candidate whose frozen Stage 3 status is
exactly:

`PASS`

A Stage 3 candidate with status:

- `EXCLUDE_SOURCE_REPLICON_INTEGRITY`; or
- `REVIEW_UNRESOLVED`

is terminal before taxonomy and must not be taxonomically resolved by Stage 4.

No Stage 3 exclusion or unresolved candidate may be reinstated because its
taxonomy would otherwise resolve successfully.

## Stage 4 candidate input boundary

The authoritative Stage 3 candidate-decision artifact is:

`stage3-chromosome-integrity-decisions.tsv`

Its frozen SHA256 is:

`13d66c0febb809d30862730eff0b419c3568fc9cdd113970ac441b0fce748f04`

The Stage 3 decision artifact contains exactly:

`68278`

candidate rows.

The frozen Stage 3 aggregate status counts are:

- `PASS`: `68175`;
- `EXCLUDE_SOURCE_REPLICON_INTEGRITY`: `33`;
- `REVIEW_UNRESOLVED`: `70`.

Therefore the exact Stage 4 taxonomy input count is:

`68175`

The other `103` Stage 3 candidates are terminal before taxonomy.

The canonical join identity is the versioned GenBank assembly accession:

`canonical_genbank_assembly_accession`

It must match:

`^GCA_[0-9]+\.[0-9]+$`

Stage 4 production code must independently verify the frozen Stage 3 artifact
SHA256, exact schema, row count, unique canonical accessions, recognized
Stage 3 statuses and exact Stage 3 aggregate counts before deriving the Stage 4
PASS membership.

The Stage 4 PASS membership must be derived solely from the frozen Stage 3
decision artifact.

No baseline, holdout, feature or selector artifact may alter this membership.

## Frozen source TaxID evidence

The authoritative organism TaxID comes from the already frozen BacSelect raw
NCBI Datasets source snapshot.

Snapshot ID:

`snapshot-20260825T132821Z`

Frozen raw source JSONL:

`assembly_data_report.raw.jsonl`

Frozen raw JSONL SHA256:

`b1b016891ae4e976d03606dfb2f35f74b03d21cf3ec82832f77f4d113bd622d5`

Frozen raw record count:

`70850`

The raw source snapshot is physically retained outside Git.

The frozen NCBI Datasets serialization uses:

- canonical assembly accession: top-level `accession`;
- organism object: top-level `organism`;
- structured organism TaxID: `organism.tax_id`.

A schema-only audit performed before this method established:

- all `70850` records contain an `organism` object;
- all `70850` records contain `organism.tax_id`;
- all `organism.tax_id` values are JSON integers;
- all `70850` records contain a string `accession`.

This schema observation establishes the serialized field name only. It did not
emit accession or TaxID values and performed no taxonomy resolution.

The Project Finch documentation-style field name `organism.taxId` therefore
maps to the BacSelect frozen NCBI Datasets snake-case serialization:

`organism.tax_id`

No organism name, submitted species name, CheckM TaxID or other descriptive
taxonomy field is a fallback source for Stage 4 grouping.

## Source TaxID binding

Stage 4 must reconstruct an accession-to-organism-TaxID mapping directly from
the exact frozen raw source JSONL.

For every raw source record used by the loader:

1. the JSON value must be an object;
2. `accession` must be a canonical versioned GCA accession;
3. accessions must be unique across the raw source snapshot;
4. `organism` must be an object;
5. `organism.tax_id` must be an integer;
6. boolean values must not be accepted as integers;
7. `organism.tax_id` must be greater than zero.

The loader must fail closed on malformed, duplicate or conflicting source
evidence.

After the frozen raw source mapping is constructed, every one of the `68175`
Stage 4 candidate accessions must map to exactly one frozen organism TaxID.

A Stage 4 candidate absent from the frozen source mapping is a run-level input
integrity error, not a candidate-level taxonomy classification.

The source mapping is not reconstructed from:

- Stage 3 output columns;
- sequence package metadata;
- GenBank live services;
- current NCBI web records;
- organism names;
- species names;
- CheckM taxonomy;
- Project Finch historical species-resolution output.

The frozen raw BacSelect source snapshot is the sole source of the Stage 4
organism TaxID.

## Frozen BacSelect taxonomy snapshot

Stage 4 uses the already frozen BacSelect NCBI Taxonomy `new_taxdump`
snapshot.

Taxonomy snapshot ID:

`taxonomy-20260826T070308Z`

Git taxonomy-acquisition freeze evidence SHA256:

`ef7c7f73d5ad4dcc20f74f761e43a3e3c05e77d264b93d0a01d606a8e3866ac4`

Frozen taxonomy archive SHA256:

`005d1b674bb12719c003652c867486f83a5c860b4beb1016adf17f3c56c2d844`

Frozen resolver-input identities:

- `nodes.dmp`:
  `1d096a81dbd87eccc6d412b28c37ca1eee292fa80e22ae4347c91dcbc7f03153`;
- `merged.dmp`:
  `3dcd79305dbebc33f50292e7877b7094f99ba920041c7bce199c3b45b4c9e725`;
- `delnodes.dmp`:
  `9dab07574818ae7696d4a18d5512295e3054fb8260c167a3c894366866f10221`.

Frozen taxonomy snapshot record SHA256:

`4c89bc24bd06925b24f94b0313cf9ec987adc97b88dd72be19c037db6232b05b`

The accepted physical snapshot currently resides under:

`/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/taxonomy-snapshot-acquisition/078da985632603196b0912ebfb5a7a050be8eedd/20260826T070308Z/snapshot`

The physical path is operational location only.

The scientific identity is established by the frozen cryptographic identities,
not by path name alone.

Before production resolution, Stage 4 must verify the physical
`nodes.dmp`, `merged.dmp` and `delnodes.dmp` files against the exact frozen
SHA256 values above.

No live taxonomy lookup or replacement taxonomy snapshot is permitted.

## Frozen taxonomy algorithm

The frozen BacSelect taxonomy primitive is:

`src/bacselect/source_taxonomy.py`

SHA256:

`9c8c4149c5db2a757e8c201a6523bdb113511b5f72a4dd2893572dd8c7928e4d`

The frozen BacSelect post-sequence taxonomy composition implementation is:

`src/bacselect/source_post_sequence_eligibility.py`

SHA256:

`62fa1e2f7d806f94b5f5eca73fb768745d3913a4b218a4d354562033cd300fe8`

The source JSONL parser implementation supplying the frozen JSON-object
iteration semantics is:

`src/bacselect/source_eligibility.py`

SHA256:

`6e57dd950f972a9883e8fcbc78a18c694a5fabda58b03835f268eef681a03cc2`

Project Finch supplies algorithmic provenance only.

Frozen Project Finch taxonomy resolver provenance:

- Project Finch commit:
  `44f9e231a754962a6091105c031d330d686103aa`;
- path:
  `scripts/experiment-0/build_species_resolution.py`;
- SHA256:
  `fcc3321975eef2e250c166215680fdd60aa90d1eef20bd68543fac759fab8ee8`.

Project Finch historical taxonomy files, historical species mappings,
historical expected counts and historical species identities are not Stage 4
scientific inputs.

## Candidate taxonomy-resolution semantics

For each Stage 4 candidate, the frozen BacSelect
`resolve_taxonomy()` semantics are authoritative.

The query is the positive integer from:

`organism.tax_id`

The TaxID is first normalized using the frozen `merged.dmp`,
`delnodes.dmp` and `nodes.dmp` evidence.

Allowed normalization statuses are exactly:

- `PASS`;
- `MERGED_CYCLE`;
- `DELETED`;
- `MISSING`.

A normalization result with status:

- `MERGED_CYCLE`;
- `DELETED`; or
- `MISSING`

produces Stage 4 status:

`REVIEW_UNRESOLVED`

with the corresponding reason:

- `TAXONOMY_NORMALIZE_MERGED_CYCLE`;
- `TAXONOMY_NORMALIZE_DELETED`;
- `TAXONOMY_NORMALIZE_MISSING`.

A successful normalization must return a positive normalized TaxID.

The frozen taxonomy lineage is then traversed from that normalized TaxID.

The first ancestral node whose rank is exactly:

`species`

is the species grouping identity.

Allowed species-ancestor statuses are exactly:

- `PASS`;
- `LINEAGE_CYCLE`;
- `MISSING_NODE`;
- `NO_SPECIES_ANCESTOR`.

A species-ancestor result with status:

- `LINEAGE_CYCLE`;
- `MISSING_NODE`; or
- `NO_SPECIES_ANCESTOR`

produces Stage 4 status:

`REVIEW_UNRESOLVED`

with the corresponding reason:

- `TAXONOMY_SPECIES_LINEAGE_CYCLE`;
- `TAXONOMY_SPECIES_MISSING_NODE`;
- `TAXONOMY_SPECIES_NO_SPECIES_ANCESTOR`.

Successful species resolution produces Stage 4 status:

`PASS`

and reason:

`TAXONOMY_SPECIES_RESOLVED`

with a positive integer species TaxID.

Unknown normalization or species-ancestor statuses are run-level fail-closed
errors.

An internally inconsistent result, including an unresolved status carrying a
species TaxID, is a run-level fail-closed error.

Species names are not used for grouping.

## Repeated organism TaxIDs

Multiple Stage 4 candidates may share the same frozen organism TaxID.

An implementation may memoize resolution by organism TaxID for computational
efficiency provided that:

- the cache exists only within the current execution;
- the first resolution uses the frozen BacSelect taxonomy implementation;
- all candidates with that organism TaxID receive exactly the same taxonomy
  decision;
- caching cannot alter output ordering or classification;
- no result is loaded from a historical taxonomy-resolution output.

This is an execution optimization only and does not change the scientific
rule.

## Stage 4 identity-bearing output

The primary Stage 4 candidate result is written outside Git as:

`stage4-taxonomy-decisions.tsv`

Its exact columns are:

1. `canonical_genbank_assembly_accession`;
2. `organism_taxid`;
3. `normalized_organism_taxid`;
4. `species_taxid`;
5. `stage4_status`;
6. `stage4_reason`.

Rows are sorted lexicographically by
`canonical_genbank_assembly_accession`.

For `PASS` rows:

- `organism_taxid` is a positive integer;
- `normalized_organism_taxid` is a positive integer;
- `species_taxid` is a positive integer;
- reason is `TAXONOMY_SPECIES_RESOLVED`.

For a normalization-unresolved row:

- `organism_taxid` is present;
- `normalized_organism_taxid` is empty;
- `species_taxid` is empty.

For a species-ancestor-unresolved row:

- `organism_taxid` is present;
- `normalized_organism_taxid` is present;
- `species_taxid` is empty.

The identity-bearing Stage 4 TSV remains scratch-only.

It is not committed to Git before the selector-resolution decision.

## Predecision provenance

Before the first real candidate TaxID is resolved, production execution must
write a Stage 4 predecision provenance artifact outside Git.

It must bind at least:

- schema version;
- BacSelect production execution Git commit;
- this Stage 4 method SHA256;
- Stage 3 completion-evidence SHA256;
- Stage 3 candidate-decision SHA256;
- Stage 4 expected input count `68175`;
- frozen raw source snapshot ID;
- frozen raw source SHA256;
- frozen raw source record count `70850`;
- source TaxID field `organism.tax_id`;
- taxonomy snapshot ID;
- taxonomy acquisition-freeze SHA256;
- archive SHA256;
- `nodes.dmp` SHA256;
- `merged.dmp` SHA256;
- `delnodes.dmp` SHA256;
- frozen taxonomy snapshot-record SHA256;
- BacSelect taxonomy primitive SHA256;
- BacSelect post-sequence composition SHA256;
- BacSelect source parser SHA256;
- Project Finch taxonomy provenance commit, path and SHA256;
- taxonomy resolution generated: `false`;
- complete eligible universe generated: `false`;
- holdout membership generated: `false`;
- structural features calculated: `false`;
- selector outcomes calculated: `false`.

The predecision provenance must be finalized before candidate TaxID resolution
begins.

## Stage 4 aggregate output

After all `68175` Stage 4 candidates have been classified successfully, the
execution must write an aggregate summary outside Git containing at least:

- Stage 4 status;
- Stage 4 input candidate count;
- Stage 4 decision-row count;
- status counts;
- reason counts;
- unique frozen organism-TaxID count;
- resolved distinct species-TaxID count;
- Stage 4 candidate-decision SHA256;
- Stage 4 predecision-provenance SHA256;
- Stage 4 execution-provenance SHA256;
- input-evidence-manifest SHA256;
- taxonomy resolution generated: `true`;
- complete eligible universe generated: `false`;
- holdout membership generated: `false`;
- structural features calculated: `false`;
- selector outcomes calculated: `false`.

The aggregate counts must close exactly to `68175`.

The aggregate summary must not contain:

- accession identities;
- organism TaxID identities;
- normalized TaxID identities;
- species TaxID identities;
- species names;
- baseline membership;
- holdout membership;
- structural-feature values;
- OPS/SR outcomes;
- panel identities;
- selector distances;
- selector coverage.

Counts alone are permitted.

## Execution provenance

The completed execution provenance must bind at least:

- BacSelect production execution Git commit;
- predecision-provenance SHA256;
- input-evidence-manifest SHA256;
- Stage 4 decision-artifact SHA256;
- Stage 4 input candidate count;
- Stage 4 decision-row count;
- Stage 4 status and reason counts;
- taxonomy snapshot identities;
- frozen implementation identities;
- taxonomy resolution generated: `true`;
- complete eligible universe generated: `false`;
- holdout membership generated: `false`;
- structural features calculated: `false`;
- selector outcomes calculated: `false`.

## Content manifest

A deterministic content manifest must bind the finalized Stage 4 artifacts by:

- relative path;
- byte size;
- SHA256.

The finalized Stage 4 artifact set must include at least:

- `stage4-taxonomy-decisions.tsv`;
- `stage4-input-evidence-manifest.tsv`;
- `stage4-predecision-provenance.json`;
- `stage4-execution-provenance.json`;
- `stage4-aggregate-summary.json`.

The content manifest itself is also SHA256 hashed.

## Atomic output boundary

Production execution must write into a new `.partial` directory.

The final output directory must not exist before execution.

The implementation must refuse to reuse an existing final directory or
existing partial directory.

The predecision artifacts are written inside the partial directory before
candidate taxonomy resolution.

Candidate decisions and completed aggregate/provenance artifacts are written
only after all Stage 4 candidates have been classified successfully.

The partial directory is promoted atomically to the final directory only after
all final artifacts and their content manifest have been written successfully.

A failed run must not expose a partial execution as a completed Stage 4 result.

Failed partial evidence is retained for audit and is not deleted or
reinterpreted as successful output.

## Production stdout and stderr

Production stdout may report only non-identity-bearing information such as:

- preflight status;
- frozen input hashes;
- total candidate counts;
- aggregate Stage 4 status counts;
- aggregate reason counts;
- output artifact SHA256 values;
- completion status.

Production stdout and stderr must not emit:

- candidate accession values;
- organism TaxID values;
- normalized TaxID values;
- species TaxID values;
- species names.

An identity-bearing candidate error encountered after production resolution has
begun must fail closed without printing the candidate identity.

Identity-bearing diagnostic evidence, if required for recovery, remains in a
separately controlled scratch artifact rather than standard output.

## Run-level failures versus candidate unresolved states

The following are candidate-level taxonomy outcomes when produced through the
frozen resolver:

- merged cycle;
- deleted TaxID;
- missing TaxID;
- lineage cycle;
- missing lineage node;
- no species ancestor.

The following are run-level errors:

- Stage 3 artifact SHA256 mismatch;
- Stage 3 schema/count/status inconsistency;
- incorrect Stage 4 input count;
- duplicate Stage 3 accession;
- raw source SHA256 mismatch;
- raw source record-count mismatch;
- malformed raw JSON;
- duplicate raw source accession;
- malformed canonical accession;
- missing or malformed `organism` object;
- absent `organism.tax_id`;
- non-integer, boolean or non-positive organism TaxID;
- Stage 4 PASS accession absent from the frozen raw source mapping;
- taxonomy freeze mismatch;
- `nodes.dmp`, `merged.dmp` or `delnodes.dmp` SHA256 mismatch;
- malformed or internally inconsistent taxonomy structure;
- unknown frozen resolver status;
- internally inconsistent taxonomy decision;
- output-path collision;
- incomplete artifact finalization.

No run-level evidence-integrity failure may be converted into a candidate-level
`REVIEW_UNRESOLVED` classification.

## Testing boundary

Stage 4 implementation testing is synthetic-only until:

1. this method is frozen in Git;
2. the dedicated Stage 4 execution implementation is written;
3. its synthetic tests pass;
4. the production wrapper is written and tested;
5. the implementation, tests and wrapper are frozen in Git.

Synthetic tests must not read:

- the real Stage 3 decision artifact;
- the real raw source JSONL;
- the real BacSelect taxonomy snapshot;
- any real BacSelect candidate accession;
- any real BacSelect candidate TaxID.

Synthetic tests must cover at least:

- exact Stage 3 PASS filtering;
- Stage 3 terminal short-circuiting;
- duplicate Stage 3 accession rejection;
- unknown Stage 3 status rejection;
- exact Stage 3 aggregate accounting;
- exact raw source SHA binding through fixture equivalents;
- canonical GCA validation;
- raw source duplicate accession rejection;
- missing `organism` rejection;
- missing `organism.tax_id` rejection;
- boolean TaxID rejection;
- non-integer TaxID rejection;
- non-positive TaxID rejection;
- missing Stage 4 accession-to-source mapping;
- current TaxID normalization PASS;
- single-step merged TaxID;
- multi-step merged TaxID;
- merged cycle;
- deleted TaxID;
- missing TaxID;
- species resolves to itself;
- descendant resolves to first exact `species` ancestor;
- exact `species` rank semantics;
- lineage cycle;
- missing lineage node;
- no species ancestor;
- unknown taxonomy status failure;
- internally inconsistent taxonomy result failure;
- deterministic output ordering;
- exact aggregate accounting;
- in-run repeated-TaxID memoization equivalence;
- no name-based fallback;
- no CheckM grouping input;
- no live taxonomy access;
- no baseline access;
- no holdout construction;
- no structural-feature access;
- no OPS/SR access;
- atomic finalization safeguards.

## Blinding boundary

Stage 4 necessarily reads candidate accession and organism TaxID identities
inside the production process and writes identity-bearing taxonomy decisions to
scratch.

Those identities remain blinded from scientific interpretation before the
selector decision.

Before selector-resolution outcome calculation, Git may contain only
non-identity-bearing Stage 4 evidence such as:

- aggregate counts;
- cryptographic fingerprints;
- implementation identities;
- taxonomy snapshot identities;
- execution provenance.

Git must not contain the Stage 4 candidate-decision table or a list of species
TaxIDs.

Stage 4 must not read or use:

- frozen baseline membership;
- prospective holdout membership;
- OPS outcomes;
- SR outcomes;
- selector distances;
- panel identities;
- panel membership;
- selector coverage;
- structural-feature values.

## Completion boundary

Successful Stage 4 execution does not itself authorize complete-universe or
holdout construction.

After production Stage 4 execution:

1. identity-bearing Stage 4 output remains scratch-only;
2. aggregate outputs and cryptographic identities are independently audited;
3. blinded Stage 4 completion evidence is generated;
4. that completion evidence is reviewed and frozen in Git;
5. only then may the complete eligible fresh universe be composed
   prospectively from the already frozen upstream terminal outcomes and Stage 4
   taxonomy results.

No holdout construction, structural-feature calculation or selector-resolution
analysis is permitted during Stage 4.

## Prospective freeze statement

This method is frozen before:

- any real Stage 4 PASS candidate organism TaxID is read for taxonomy
  resolution;
- any real candidate taxonomy decision is generated;
- any Stage 4 species TaxID is generated;
- any complete eligible fresh-universe membership is generated;
- any final holdout membership is generated;
- any external-holdout structural feature is calculated;
- any OPS/SR external-holdout outcome is calculated.

No production Stage 4 taxonomy execution is authorized until the method,
implementation, synthetic tests and production wrapper have each passed their
respective prospective freeze gates.
