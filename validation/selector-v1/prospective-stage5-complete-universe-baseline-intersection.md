# BacSelect Stage 5 complete-universe and baseline-intersection method

## Status

**PROSPECTIVE METHOD — NO COMPLETE-UNIVERSE OR HOLDOUT MEMBERSHIP GENERATED**

This method is frozen after Stage 4 taxonomy resolution was formally completed
and before any identity-bearing complete eligible fresh-universe manifest,
reconstructed absent-from-baseline membership, final external decision holdout,
structural feature, OPS/SR distance, or selector-resolution outcome is
generated.

The BacSelect repository immediately before this method was created is:

`08d93b0e8ff663be467eb7f7ea8b14161a328b75`

Stage 4 is formally closed by:

`validation/selector-v1/stage4-taxonomy-resolution-completion-evidence.json`

with SHA256:

`b878dd9f20c01867b87265b9d35c23db5ad556621c5750a0193d9e1f2b5960ad`

Stage 4 contains:

- 68,175 taxonomy-resolution input candidates;
- 67,957 `PASS` candidates;
- 218 `REVIEW_UNRESOLVED` candidates;
- all 218 unresolved candidates have reason
  `TAXONOMY_NORMALIZE_DELETED`;
- 16,144 resolved species TaxIDs among the Stage 4 PASS population.

The identity-bearing Stage 4 decision artifact remains outside Git and has
SHA256:

`74ddebdb1ff0d2f9aedaf564c2622ce748795fdb43aa19e2bcef0c4b35788ade`

No complete eligible fresh universe has yet been generated.

No final external decision holdout has yet been generated.

## Purpose

Stage 5 has two sequential scientific phases:

1. **Stage 5A — complete eligible fresh-universe composition and freeze**
2. **Stage 5B — frozen baseline-membership reconstruction, holdout
   intersection, and adequacy evaluation**

Stage 5B is forbidden from starting until Stage 5A has been successfully
finalized and cryptographically frozen.

This sequencing implements the already-frozen BacSelect rule:

> only after the complete eligible fresh universe is frozen is frozen baseline
> membership consulted.

Stage 5 does not calculate structural features or selector outcomes.

## Frozen upstream scientific rules

Stage 5 does not create or reinterpret any source-eligibility rule.

It implements the already-frozen post-sequence composition rules in:

`validation/selector-v1/prospective-post-sequence-composition-clarification.md`

The current SHA256 of that clarification at method freeze is:

`e1399bd9d8a9f62c6cdb855a334da29840cb05df27724f08d6e010b56b7a332c`

It also remains subordinate to:

- `validation/selector-v1/prospective-post-sequence-eligibility-design.md`;
- `validation/selector-v1/prospective-selector-resolution-design.md`;
- `docs/scientific-specification.md`.

No rule in Stage 5 may override those frozen designs.

## Canonical genome identity

The only genome identifier used for membership operations is the versioned
canonical GenBank assembly accession matching the frozen BacSelect canonical
GCA rule.

GCF accessions are not substituted.

Unversioned accessions are not accepted.

No accession normalization, version collapsing, or live lookup is permitted.

## Membership fingerprint definition

All accession-set membership fingerprints use the already-frozen BacSelect
`accession_membership_sha256` definition from:

`src/bacselect/source_truth_execution.py`

whose current SHA256 at method freeze is:

`83b8ec7fce774c0b68cb2af982aef13904c6b64b3ee695512c578f98e5de9b92`

The exact fingerprint serialization is:

1. validate every accession as canonical;
2. require accession uniqueness;
3. sort accessions lexicographically;
4. serialize each accession as ASCII followed by exactly one newline;
5. SHA256 the complete byte sequence.

No header participates in the accession membership fingerprint.

Whole-artifact SHA256 values are additionally calculated for every frozen
identity-bearing TSV.

# Stage 5A — complete eligible fresh universe

## Stage 5A input boundary

Stage 5A operates only on the already completed post-sequence scientific
decision chain.

The execution must bind the exact frozen Stage 1, Stage 2, Stage 3, and Stage 4
completion-evidence records and their exact decision artifacts before
composition begins.

The chained scientific progression is:

1. source truth;
2. repeated-BioSample reconciliation;
3. chromosome integrity;
4. taxonomy resolution.

The chained membership invariants must be validated exactly:

- Stage 2 input membership equals the continuing Stage 1 membership;
- Stage 3 input membership equals the continuing Stage 2 membership;
- Stage 4 input membership equals the PASS Stage 3 membership;
- the complete eligible universe equals the PASS Stage 4 membership.

Any mismatch is a run-level fail-closed error.

## Stage 5A predecision provenance

Before any real Stage 1, Stage 2, Stage 3, or Stage 4 identity-bearing decision
artifact is parsed, Stage 5A writes:

`stage5a-predecision-provenance.json`

The predecision record binds, without parsing candidate rows:

- the Stage 5 method identity;
- the execution Git commit;
- the frozen Stage 1 completion-evidence identity;
- the frozen Stage 2 completion-evidence identity;
- the frozen Stage 3 completion-evidence identity;
- the frozen Stage 4 completion-evidence identity;
- the expected upstream decision-artifact SHA256 identities;
- the expected chained membership SHA256 identities;
- the expected 68,480 composition input count;
- the expected 67,957 Stage 4 PASS count;
- the expected 16,144 resolved Stage 4 species groups.

At the instant this predecision record is finalized it must state that:

- no Stage 1–4 candidate decision row has been parsed by Stage 5;
- terminal composition has not been generated;
- the complete eligible universe has not been generated;
- baseline membership has not been consulted;
- the raw metadata source has not been parsed by Stage 5;
- the baseline matrix has not been parsed by Stage 5;
- historical absence membership has not been reconstructed;
- holdout membership has not been generated;
- structural features have not been calculated;
- selector outcomes have not been calculated.

The predecision artifact itself contains no candidate or species identity.

Physical input identities may be SHA256-verified before candidate rows are
parsed, but no scientific membership may be derived before this predecision
record exists.

## Stage 5A terminal composition

The complete composition layer uses exactly four high-level dispositions:

- `ELIGIBLE`
- `EXCLUDED`
- `WITHHELD_UNRESOLVED`
- `NONREPRESENTATIVE`

The terminal layer is exactly one of:

- `source_truth`
- `repeated_biosample`
- `chromosome_integrity`
- `taxonomy`
- `eligible`

The earliest terminal scientific layer determines the final composition
disposition.

A candidate that continues through every preceding stage and has Stage 4
taxonomy status `PASS` is:

- disposition `ELIGIBLE`;
- terminal layer `eligible`.

A source-truth exclusion is `EXCLUDED`.

A source-truth unresolved outcome is `WITHHELD_UNRESOLVED`.

A repeated-BioSample non-representative outcome is `NONREPRESENTATIVE`.

A repeated-BioSample unresolved outcome is `WITHHELD_UNRESOLVED`.

A chromosome-integrity exclusion is `EXCLUDED`.

A chromosome-integrity unresolved outcome is `WITHHELD_UNRESOLVED`.

A taxonomy unresolved outcome is `WITHHELD_UNRESOLVED`.

The primitive terminal status and primitive terminal reason are preserved
unchanged in the composition record.

Unknown primitive statuses, missing decision evidence, duplicate accession
membership, impossible stage transitions, or contradictory terminal states are
run-level fail-closed errors.

## Stage 5A expected accounting

The already-frozen stage aggregates imply the following expected final
composition accounting:

- complete sequence-eligible composition population: 68,480;
- source-truth exclusions: 121;
- repeated-BioSample non-representatives: 6;
- repeated-BioSample unresolved: 75;
- chromosome-integrity exclusions: 33;
- chromosome-integrity unresolved: 70;
- taxonomy unresolved: 218;
- complete eligible fresh universe: 67,957.

Therefore the expected high-level final disposition counts are:

- `ELIGIBLE`: 67,957;
- `EXCLUDED`: 154;
- `WITHHELD_UNRESOLVED`: 363;
- `NONREPRESENTATIVE`: 6.

These counts must close exactly to 68,480.

They are validation invariants, not newly chosen thresholds.

## Stage 5A terminal composition artifact

Stage 5A writes an identity-bearing scratch-only artifact:

`stage5-terminal-composition.tsv`

with exactly these columns:

1. `canonical_genbank_assembly_accession`
2. `final_disposition`
3. `terminal_layer`
4. `terminal_status`
5. `terminal_reason`
6. `species_taxid`

Rows are sorted lexicographically by canonical accession.

`species_taxid` is populated only for `ELIGIBLE` records.

For non-eligible records, `species_taxid` is empty.

No organism name, species name, BioSample identifier, OPS/SR identity, panel
identity, distance, or structural-feature value is included.

This artifact remains outside Git.

## Complete eligible fresh-universe artifact

Stage 5A derives the complete eligible fresh universe only from records with
final disposition `ELIGIBLE`.

The complete-universe artifact is:

`complete-eligible-fresh-universe.tsv`

with exactly these columns:

1. `canonical_genbank_assembly_accession`
2. `species_taxid`

Rows are sorted lexicographically by canonical accession.

The expected row count is exactly:

`67,957`

Every accession is unique.

Every species TaxID is a positive integer.

The complete-universe accession membership must equal the Stage 4 PASS
membership exactly.

The complete-universe distinct species-TaxID count must equal the frozen
Stage 4 resolved species-TaxID count:

`16,144`

This artifact remains outside Git.

## Stage 5A freeze point

Before any baseline-membership input is opened or parsed, Stage 5A must:

1. finish the terminal composition artifact;
2. finish the complete eligible fresh-universe artifact;
3. calculate their byte sizes;
4. calculate their whole-artifact SHA256 values;
5. calculate the complete-universe accession membership SHA256;
6. calculate the complete-universe row count;
7. calculate the distinct species-TaxID count;
8. write `stage5a-execution-provenance.json`;
9. write `stage5a-aggregate-summary.json`;
10. write `stage5a-content-manifest.tsv`;
11. atomically finalize the Stage 5A output directory.

The finalized Stage 5A artifact set is exactly:

- `stage5a-predecision-provenance.json`;
- `stage5-terminal-composition.tsv`;
- `complete-eligible-fresh-universe.tsv`;
- `stage5a-execution-provenance.json`;
- `stage5a-aggregate-summary.json`;
- `stage5a-content-manifest.tsv`.

No additional scientific Stage 5A artifact is permitted without a prospective
method amendment made before production Stage 5A execution.

Only after that final directory exists may Stage 5B begin.

The Stage 5A final directory must never be modified after finalization.

A failed Stage 5A attempt preserves partial evidence and cannot be interpreted
as a complete universe.

## Stage 5A baseline prohibition

The Stage 5A implementation must not read, parse, or load:

- the 55,306-genome baseline matrix;
- baseline accession membership;
- the historical 70,477-member metadata-retained membership;
- the historical 15,445-member absent-from-baseline membership;
- the historical baseline-membership summary;
- OPS or SR ladder membership;
- structural features;
- selector distances;
- panel identities.

This prohibition is tested explicitly.

# Stage 5B — baseline reconstruction and external holdout

## Stage 5B authorization boundary

Stage 5B may start only after Stage 5A has:

- finalized successfully;
- produced exactly 67,957 eligible genomes;
- produced exactly 16,144 resolved species groups;
- frozen the complete-universe accession membership fingerprint;
- frozen the complete-universe whole-artifact fingerprint.

Stage 5B must consume the finalized Stage 5A complete-universe artifact as an
immutable input.

It must not regenerate or alter complete-universe membership.

## Stage 5B predecision provenance

Before the frozen raw source snapshot or the 55,306-row baseline matrix is
parsed, Stage 5B writes:

`stage5b-predecision-provenance.json`

The Stage 5B predecision record binds:

- the Stage 5 method identity;
- the execution Git commit;
- the finalized Stage 5A content-manifest SHA256;
- the finalized Stage 5A execution-provenance SHA256;
- the complete-universe whole-artifact SHA256;
- the complete-universe accession membership SHA256;
- the complete-universe count of 67,957;
- the complete-universe distinct species count of 16,144;
- the frozen raw-source SHA256;
- the frozen metadata-parser SHA256;
- all four frozen metadata-eligibility evidence SHA256 identities;
- the authoritative 55,306-row baseline-matrix SHA256;
- the frozen membership-comparator SHA256;
- all four frozen aggregate baseline-membership evidence SHA256 identities.

At the instant this predecision record is finalized it must state that:

- Stage 5A is finalized and immutable;
- raw source records have not been parsed by Stage 5B;
- baseline matrix rows have not been parsed by Stage 5B;
- historical absence membership has not been reconstructed;
- final holdout membership has not been generated;
- the adequacy gate has not been evaluated;
- structural features have not been calculated;
- selector outcomes have not been calculated.

The Stage 5B predecision artifact contains no candidate or species identity.

Physical SHA256 verification of the frozen inputs is permitted before parsing,
but no absence or holdout membership may be derived before this predecision
record exists.

## Why historical absence membership must be reconstructed

The original prospective baseline-membership comparison intentionally emitted
aggregate blinded results only.

No identity-bearing 15,445-member absent-from-baseline artifact was frozen.

The frozen historical run recorded:

- output identity level: `aggregate_blinded_only`;
- metadata-retained genomes: 70,477;
- present in baseline: 55,032;
- absent from baseline: 15,445;
- baseline genomes absent from metadata-retained source: 274.

Therefore Stage 5B reconstructs that identity membership deterministically from
the exact original frozen inputs.

This is reconstruction of an already-frozen membership rule, not a new
baseline comparison rule.

## Frozen historical aggregate evidence

The reconstruction is additionally bound to the already-frozen metadata
eligibility evidence:

- `external-holdout-metadata-eligibility-run.tsv`
  SHA256:
  `e8bd35f491299ab716c9c616547055818d718bcf9bdcaa1ac34d4207b3b4b1c6`;
- `external-holdout-metadata-eligibility-freeze.tsv`
  SHA256:
  `0113b2ba31a1c1af82d302c7ffec81e40100a6b2bc7be751ebef2cef951b9bbe`;
- `external-holdout-metadata-eligibility-summary.json`
  SHA256:
  `108b631e1ce0c6344b4c39b6249f59ba05c8e922078548b7a9624703bd082adf`;
- `external-holdout-metadata-eligibility-files.sha256`
  SHA256:
  `2992971075d508df9964f0def91c2bc2d6ac756e10c53db60f0c7d3f8a52eb4c`.

Those records freeze:

- raw source records: 70,850;
- `RETAIN_METADATA`: 70,477;
- `EXCLUDE_METADATA`: 373;
- metadata unresolved: 0.

The reconstruction is also bound to the already-frozen aggregate
baseline-membership evidence:

- `external-holdout-baseline-membership-run.tsv`
  SHA256:
  `6b96daf2b3d22f130492e5054d57695693d946ee847f6a51fadb6e1c3d7a99ba`;
- `external-holdout-baseline-membership-freeze.tsv`
  SHA256:
  `9e719301f3adcec92d6d019ce6cdc1d830507f651ff4b99ba965c4655e43a767`;
- `external-holdout-baseline-membership-summary.json`
  SHA256:
  `4f0440fc4231e511033e06c82b2b5e444aae5bfb189b487632ef58dab23aaedb`;
- `external-holdout-baseline-membership-files.sha256`
  SHA256:
  `d5fd5aa445d2f26f49c747ed4e6e3ac741f477922b2779539a595f6853bfac9d`.

Those records freeze:

- baseline accessions: 55,306;
- metadata retained: 70,477;
- retained present in baseline: 55,032;
- retained absent from baseline: 15,445;
- baseline not in metadata retained: 274.

The historical metadata and membership evidence is aggregate-only and does not
supply the reconstructed identity set directly.

## Frozen baseline reconstruction inputs

The frozen raw source snapshot has SHA256:

`b1b016891ae4e976d03606dfb2f35f74b03d21cf3ec82832f77f4d113bd622d5`

The historical metadata parser is:

`src/bacselect/source_eligibility.py`

with frozen and current SHA256:

`6e57dd950f972a9883e8fcbc78a18c694a5fabda58b03835f268eef681a03cc2`

The historical membership comparator is:

`src/bacselect/source_membership.py`

with frozen and current SHA256:

`ffd4bb04f913df3d658b591739f3ad876c24d9a8d795242c926c97987dffce4e`

The historical membership execution commit is:

`ebcb32481d99d062dcd1e5ed4b918e8638884085`

The frozen aggregate membership result was committed as:

`78a5bca45d1687c23e619946f7084baec7960ac9`

The authoritative baseline membership artifact is the final BacSelect 300/2400
raw structural-feature matrix:

`/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/final-feature-space/0f75c51edc37259f168ad10faf44d536dd9b75a5/structural-feature-matrix-300-2400.tsv`

with:

- data rows: 55,306;
- accession column:
  `canonical_genbank_assembly_accession`;
- SHA256:
  `86c0c3d49317dfc3cc452114e3863666fe2112b6a3ae8dae2090b60a2a598948`.

The older Project Finch corrected 150/400 matrix with SHA256 beginning
`fd264bed...` is not the baseline-membership comparator input and must not be
substituted.

## Exact historical reconstruction

Stage 5B must reproduce the original historical comparison exactly:

1. SHA256-verify the frozen raw source snapshot;
2. parse it with the frozen metadata parser;
3. require the historical aggregate metadata result;
4. retain only records with decision `RETAIN_METADATA`;
5. require exactly 70,477 unique retained canonical GCA accessions;
6. SHA256-verify and load the frozen 55,306-row final 300/2400 baseline matrix;
7. extract the baseline accession column by exact column name;
8. require exactly 55,306 unique canonical GCA baseline accessions;
9. partition the 70,477 retained accessions against the baseline;
10. require exactly:
    - 55,032 retained present in baseline;
    - 15,445 retained absent from baseline;
    - 274 baseline accessions absent from metadata-retained membership.

If any historical aggregate differs, Stage 5B fails closed and no holdout is
generated.

No alternative parser, baseline matrix, accession field, or reconstructed
membership may be substituted.

## Reconstructed absence artifact

After exact historical aggregate reproduction succeeds, Stage 5B writes the
scratch-only identity-bearing artifact:

`reconstructed-retained-absent-from-baseline.tsv`

with exactly one column:

`canonical_genbank_assembly_accession`

Rows are sorted lexicographically.

The row count must be exactly:

`15,445`

The artifact receives:

- a whole-artifact SHA256;
- an accession membership SHA256.

This reconstructed artifact remains outside Git.

Its identities must not be printed to stdout or stderr.

## External decision holdout definition

The external decision holdout is exactly:

`complete eligible fresh universe`
INTERSECT
`reconstructed retained_absent_from_baseline`

No random sampling or downsampling is permitted.

No candidate may enter or leave the holdout because of:

- species identity;
- organism name;
- clinical relevance;
- publication status;
- structural-feature values;
- OPS distance;
- SR distance;
- panel membership;
- assembler behavior;
- expected selector performance.

Baseline membership has no effect on complete-universe membership.

## External decision holdout artifact

Stage 5B writes the identity-bearing scratch-only artifact:

`external-decision-holdout.tsv`

with exactly these columns:

1. `canonical_genbank_assembly_accession`
2. `species_taxid`

Rows are sorted lexicographically by canonical accession.

Every row must exist identically in the finalized Stage 5A complete-universe
artifact.

Every holdout accession must exist in the reconstructed absent-from-baseline
membership.

Every holdout species TaxID is inherited unchanged from the frozen complete
eligible universe.

The holdout count is not prospectively assumed.

The holdout distinct species count is not prospectively assumed.

Neither value may be inspected before Stage 5B executes under this frozen
method.

## Holdout membership fingerprints

Stage 5B freezes:

- external holdout row count;
- external holdout distinct species-TaxID count;
- external holdout whole-artifact SHA256;
- external holdout accession membership SHA256;
- reconstructed absence whole-artifact SHA256;
- reconstructed absence accession membership SHA256.

Genome or species identities remain outside Git.

## Adequacy gate

After holdout membership is fixed, but before structural features are
calculated, Stage 5B evaluates the already-frozen adequacy gate.

The holdout must contain at least:

- 1,000 genomes;
- 200 distinct resolved species groups.

If both thresholds are met:

`ADEQUACY_PASS`

and structural-feature execution may be designed as the next prospective stage.

If either threshold is not met:

`ADEQUACY_FAIL_NO_SELECTOR_DECISION`

and:

- no holdout structural features are calculated;
- no OPS/SR distances are calculated;
- no selector-resolution score is calculated;
- selector-v1 remains unresolved;
- the experiment waits for a later fresh snapshot.

There is no alternative adequacy threshold.

There is no secondary selector rule.

## Stage 5B finalization

A successful Stage 5B run must write, before atomic finalization:

- `stage5b-predecision-provenance.json`;
- `reconstructed-retained-absent-from-baseline.tsv`;
- `external-decision-holdout.tsv`;
- `stage5b-input-evidence-manifest.tsv`;
- `stage5b-execution-provenance.json`;
- `stage5b-aggregate-summary.json`;
- `stage5b-content-manifest.tsv`.

The finalized Stage 5B artifact set is exactly those seven files.

No additional scientific Stage 5B artifact is permitted without a prospective
method amendment made before production Stage 5B execution.

The final output directory is atomically promoted only after every artifact is
complete and internally consistent.

A failed run preserves partial evidence.

A failed or partial output is never reinterpreted as final.

## Git boundary

Identity-bearing Stage 5A and Stage 5B artifacts remain outside Git.

Git may freeze only blinded information, including:

- complete-universe count;
- complete-universe distinct species count;
- complete-universe membership SHA256;
- complete-universe artifact SHA256;
- final composition aggregate counts;
- reconstructed absence count;
- reconstructed absence membership SHA256;
- reconstructed absence artifact SHA256;
- historical reconstruction aggregate counts;
- external holdout count;
- external holdout distinct species count;
- external holdout membership SHA256;
- external holdout artifact SHA256;
- adequacy result;
- input and provenance fingerprints.

Git must not contain:

- complete-universe accessions;
- reconstructed absent-from-baseline accessions;
- holdout accessions;
- species TaxID identities;
- BioSample identities;
- organism identities;
- OPS or SR panel identities.

## Standard-output boundary

Production stdout and stderr may report only identity-safe aggregate values,
artifact fingerprints, counts, status values, and scratch paths.

They must not print:

- candidate accessions;
- species TaxIDs;
- organism TaxIDs;
- BioSample identifiers;
- organism names;
- panel identities.

Any unexpected exception reaching the production entry point is converted to a
generic fail-closed error message without candidate identity.

## Testing boundary

Until the Stage 5 implementation, tests, and production wrapper for the
relevant phase are frozen in Git:

- tests are synthetic only;
- no real Stage 1–4 decision artifact is parsed;
- no real raw source record is parsed;
- no real baseline matrix row is parsed;
- no real complete-universe membership is generated;
- no real historical absence membership is reconstructed;
- no real holdout membership is generated.

Synthetic tests must cover at least:

- exact chained stage membership;
- duplicate accession rejection;
- invalid canonical accession rejection;
- impossible stage-transition rejection;
- terminal composition precedence;
- terminal reason preservation;
- eligible species TaxID requirement;
- deterministic sorting;
- exact accession-membership fingerprint semantics;
- Stage 5A prohibition on baseline access;
- Stage 5A expected 68,480 accounting closure;
- complete-universe derivation from eligible records only;
- historical metadata reconstruction;
- historical baseline reconstruction;
- exact 70,477 / 55,032 / 15,445 / 274 aggregate reproduction;
- failure on any historical aggregate mismatch;
- holdout exact set intersection;
- species mapping inheritance;
- adequacy pass;
- adequacy genome-count failure;
- adequacy species-count failure;
- identity-safe aggregate outputs;
- atomic finalization;
- failed partial preservation.

## Structural-feature prohibition

Stage 5 never calculates structural features.

No Stage 5 implementation may import or invoke:

- holdout structural-feature calculators;
- baseline percentile transforms for unseen genomes;
- OPS distance calculations;
- SR distance calculations;
- selector-resolution scoring.

Structural-feature calculation becomes scientifically permissible only after:

1. Stage 5A complete-universe membership is frozen;
2. Stage 5B holdout membership is frozen;
3. the adequacy gate passes;
4. Stage 5 completion evidence is committed and pushed;
5. the next prospective structural-feature execution method is frozen.

## Blinding

Genome and species identities remain blinded throughout Stage 5.

The user-visible and Git-visible scientific evidence before selector decision
is restricted to counts, fingerprints, anonymous artifact identities, adequacy
statistics, and provenance.

No Stage 5 output may unblind OPS or SR panel membership.

No selector outcome is generated.

## Completion boundary

Stage 5 is scientifically complete only when:

- Stage 5A has a finalized complete eligible fresh universe;
- Stage 5B has exactly reconstructed the frozen historical metadata-stage
  absence membership;
- the external holdout has been finalized;
- the adequacy gate has been evaluated;
- identity-bearing outputs remain scratch-only;
- blinded completion evidence is frozen in Git.

Only then may the next prospectively frozen holdout structural-feature stage
begin, and only if adequacy passes.
