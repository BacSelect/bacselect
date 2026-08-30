# Prospective Stage 7 selector-resolution execution

## Status

**PROSPECTIVE METHOD — NO STAGE 7 OUTCOME HAS BEEN CALCULATED**

This document freezes the execution contract for applying the already frozen
BacSelect selector-resolution rule to the already frozen external holdout.

At the time this method is created:

- Stage 6 raw structural features are complete and frozen;
- the external holdout contains 12,952 genomes in 3,542 resolved species
  groups;
- the Stage 6 raw-feature matrix is frozen but has not been opened for Stage 7;
- holdout percentile coordinates have not been calculated;
- holdout OPS/SR nearest-panel distances have not been calculated;
- no Stage 7 primary metric has been calculated;
- no Stage 7 exact six-size product has been calculated;
- no selector outcome has been generated;
- OPS versus SR therefore remains unresolved.

No production Stage 7 execution is permitted until this method and its
implementation are separately committed, tested, audited and pushed.

## Governing prospective design

The scientific decision rule remains exactly the rule frozen in:

`validation/selector-v1/prospective-selector-resolution-design.md`

SHA256:

`2584fddf1f06562d48abd990372ec70ea1f48da0962b1f710afb1d93e2c3223a`

This Stage 7 method operationalizes that design. It does not alter it.

If any implementation choice conflicts with the prospective selector-resolution
design, the prospective selector-resolution design takes precedence and Stage 7
must fail closed.

## Stage 6 prerequisite

Stage 7 is bound to:

`validation/selector-v1/stage6-structural-feature-completion-evidence.json`

SHA256:

`8c3c166f2861e09d74e1d2656d30f2a0739bb4d411c785fab9be6daff18cd299`

The Stage 6 evidence freezes:

- holdout genomes: 12,952;
- holdout species groups: 3,542;
- holdout membership SHA256:
  `0998a65f617e6c1b951b52990c0e2cf8110b6327992110d862d9338f0fa06bbd`;
- raw feature matrix SHA256:
  `8bb29e3b8cb98be1f21fe31fb5774b47a36835ebe75ef05fc59c7fe097b7eaf5`;
- raw feature numeric float64 C-order SHA256:
  `d2a02dcd6b2ff81d99479ed57b35c1a04d39e4e2eafbf15d7efd798bc242675b`;
- structural features calculated: true;
- percentile coordinates calculated: false;
- OPS/SR distances calculated: false;
- panel identities generated: false;
- selector outcomes calculated: false.

Stage 7 must not add, remove, replace, downsample or reclassify a holdout
member.

Any mismatch against the frozen Stage 6 evidence is fatal.

## Frozen baseline foundation

The holdout is projected into the already frozen 55,306-genome,
13,765-species 300/2400 baseline geometry.

The baseline inputs are frozen by:

`validation/selector-v1/final-feature-space-inputs.tsv`

SHA256:

`512d466ff6b8af3e51eb91db715d5fc5c76995892a4c1b18489d922a0414f0f2`

Required baseline artifact identities are:

- raw 12-feature matrix SHA256:
  `86c0c3d49317dfc3cc452114e3863666fe2112b6a3ae8dae2090b60a2a598948`;
- species-balanced percentile matrix SHA256:
  `f48e20b28ee89988e7abb42488a35c62fbfa4a538c15c8d2d70b6b5ba7ae83c1`;
- species mapping SHA256:
  `f0343238930e957f82bc28997a216ab3a8967d007b3d3471679e3f054c76af6c`;
- canonical baseline percentile float64 C-order SHA256:
  `9a4a120562ff1151fd8c83e831eb81362b2372844f7dd7407746554af49cda67`.

The 12 feature columns and their order are unchanged from Stage 6.

The baseline geometry is never recomputed using holdout genomes.

## Final frozen selector ladders

Only the final deterministic OPS and SR N=500 ladders are permitted.

Their identity-blinded ordered fingerprints are:

- OPS:
  `c81d9fd30cda2d49f0f6c81d4bf99dace9fff811c7612036d9265ef90707fa13`;
- SR:
  `3c703f5f898e0a13c6eb8568c0b83f5b0d19d4e374155d2d3a8a4e20378bd51f`.

These are the final deterministic fingerprints frozen in:

`validation/selector-v1/results/final300-2400-determinism-ladders.tsv`

SHA256:

`c0f17aaa2c92c27f0b4f3aebd9ffd1be73cc403c80700b93a1b2d5786fb6b0da`

Earlier intermediate OPS/SR ladder fingerprints are not valid Stage 7 inputs.

The six evaluated prefixes are exactly:

`N = 10, 20, 50, 100, 200, 500`

The ladders may be reconstructed only from the frozen baseline foundation with
the already frozen selector implementations and tie rules, then must match the
final fingerprints above before any holdout distance is calculated.

The holdout must never participate in ladder generation, representative
selection or ladder tie-breaking.

## Frozen implementation primitives

Stage 7 is prospectively bound to the following current primitives unless a
separately frozen implementation replaces them before production:

- `src/bacselect/geometry.py`
  SHA256
  `fbebf436d049be063817b717878330f38e09b3e7cb79f9dbc1b8f704af6a0d69`;
- `src/bacselect/metrics.py`
  SHA256
  `c83219404c627c71c900aafbb165e0a8dead27f3f04f073dbb7ce86437bb3af2`;
- `src/bacselect/ops.py`
  SHA256
  `eb6c1b8edab3e694b0f3825bb5ab0eaf44fdd95fdbb6a6e3e41439c18c828c0f`;
- `src/bacselect/sr.py`
  SHA256
  `7d3faf8a89605599e2306eea8d2d56ad690c4a588897b7446983a60e0729693b`;
- `validation/selector-v1/final_coverage_common.py`
  SHA256
  `c5f10b13158704d25e9bf48988695b1720ad776871869adfeb542919e23ed808`;
- `validation/selector-v1/final_geometry_common.py`
  SHA256
  `c2534c1a8522e29362109b82416364f40cb9a8a6c4f536758867916cbe81d9f1`.

The frozen tests establishing the relevant geometry and weighted-quantile
semantics are:

- `tests/test_geometry.py`
  SHA256
  `8c215ea881985a8d7fd83b59ee3a9ce4e1ebe5a0ffe64352d2077f098ecedec1`;
- `tests/test_metrics.py`
  SHA256
  `80b4a8f111af9c1ebd739fd99adfb9a6b656e014bf5239f767f73ae599b036ad`.

Stage 7 implementation may add dedicated holdout-projection and cross-matrix
distance functions, but those functions must preserve the scientific
definitions frozen here and must be prospectively tested before production.

## Identity blinding

Genome and species identities remain blinded throughout Stage 7 outcome
generation and selector resolution.

No scientific outcome artifact may contain:

- GCA accessions;
- GCF accessions;
- organism names;
- species names;
- species TaxIDs.

Baseline and holdout identities may be loaded internally by frozen code only
where required to:

- validate frozen membership;
- join already frozen input rows;
- obtain species grouping for exact species-balanced weights;
- reconstruct and cryptographically verify the already frozen baseline ladders.

Such identities are computational keys only. They must not be printed,
reported, copied into Stage 7 scientific outputs, or manually inspected during
outcome generation.

Where a genome-level Stage 7 artifact requires a row key, use a deterministic
anonymous row key derived from canonical matrix order, such as fixed-width
`H00000001` through `H00012952`.

No nearest-panel genome identity is required in any scientific output.

## Stage 7 predecision checkpoint

Every production or rebuild execution must first write a run-specific
predecision provenance artifact before opening the Stage 6 raw-feature matrix.

The checkpoint must bind at minimum:

- BacSelect Git commit;
- this Stage 7 method SHA256;
- prospective selector-resolution design SHA256;
- Stage 6 completion-evidence SHA256;
- Stage 6 matrix artifact SHA256;
- Stage 6 matrix numeric-array SHA256;
- frozen holdout count, species count and membership SHA256;
- frozen baseline manifest and artifact SHA256 values;
- final OPS and SR ladder fingerprints;
- exact implementation/test SHA256 values;
- Python, NumPy and SciPy versions;
- execution mode: production or independent rebuild.

At predecision creation the following state flags must all be false:

- `holdout_raw_feature_matrix_opened`;
- `holdout_percentile_coordinates_calculated`;
- `holdout_ops_sr_distances_calculated`;
- `holdout_primary_metrics_calculated`;
- `selector_products_calculated`;
- `selector_outcome_generated`.

The predecision checkpoint is run-specific provenance and is not required to
be byte-identical between production and rebuild.

## Verification of the frozen baseline geometry

Before any holdout projection:

1. verify the baseline input manifest SHA256;
2. verify raw matrix, percentile matrix and species mapping SHA256 values;
3. verify 55,306 baseline rows;
4. verify 13,765 baseline species groups;
5. verify the exact 12-feature column order;
6. recompute the baseline species-balanced percentile matrix with the frozen
   exact geometry primitive;
7. require the recomputed float64 C-order array SHA256 to equal
   `9a4a120562ff1151fd8c83e831eb81362b2372844f7dd7407746554af49cda67`;
8. require the frozen percentile matrix representation to agree with the
   recomputed baseline geometry under the already frozen serialization
   contract.

A failure at any step aborts Stage 7 before holdout outcome calculation.

## Verification of final OPS and SR ladders

Using the verified baseline geometry only:

1. reconstruct the OPS N=500 ladder with the frozen OPS implementation;
2. fingerprint its ordered baseline accession sequence using the frozen
   namespace:
   `BacSelect-selector-v1|OPS|ladder|N=500`;
3. require fingerprint
   `c81d9fd30cda2d49f0f6c81d4bf99dace9fff811c7612036d9265ef90707fa13`;
4. reconstruct the SR N=500 ladder with the frozen SR implementation;
5. fingerprint its ordered baseline accession sequence using:
   `BacSelect-selector-v1|SR|ladder|N=500`;
6. require fingerprint
   `3c703f5f898e0a13c6eb8568c0b83f5b0d19d4e374155d2d3a8a4e20378bd51f`;
7. require every evaluated prefix to be the literal first N rows of the
   corresponding verified N=500 ladder.

The reconstructed accession sequences are not scientific output artifacts and
must never be displayed during the blinded Stage 7 analysis.

## Holdout raw-feature verification

Only after all predecision, baseline and ladder checks pass may Stage 7 open the
frozen Stage 6 raw-feature matrix.

It must then verify, without changing membership:

- exactly 12,952 rows;
- exactly 3,542 species groups;
- exact holdout membership SHA256
  `0998a65f617e6c1b951b52990c0e2cf8110b6327992110d862d9338f0fa06bbd`;
- matrix artifact SHA256
  `8bb29e3b8cb98be1f21fe31fb5774b47a36835ebe75ef05fc59c7fe097b7eaf5`;
- float64 C-order numeric-array SHA256
  `d2a02dcd6b2ff81d99479ed57b35c1a04d39e4e2eafbf15d7efd798bc242675b`;
- exact 12-feature column order;
- all feature values finite;
- no duplicate holdout accession;
- candidate-evidence membership and order remain concordant with the matrix.

Stage 7 cannot exclude a row because of a feature value or projected outcome.

Any discrepancy fails the complete Stage 7 execution.

## Projection of unseen holdout genomes

For each of the 12 features independently, let the frozen baseline contain
values `b_i` and baseline species labels `s_i`.

If baseline species `s` contains `n_s` genomes, each baseline genome has exact
weight:

`w_i = 1 / n_s`

Let `S = 13,765`, the total baseline species-balanced weight.

For each holdout raw value `x`, calculate with exact rational weight arithmetic:

`W_less(x) = sum(w_i for b_i < x)`

`W_equal(x) = sum(w_i for b_i = x)`

and:

`p(x) = [W_less(x) + 0.5 * W_equal(x)] / S`

This is a projection through the **baseline** empirical distribution.

The holdout never contributes weight to this transform.

Consequences are fixed:

- below the baseline minimum: `0`;
- above the baseline maximum: `1`;
- between observed baseline values: cumulative baseline weight strictly below
  `x`;
- exactly tied to baseline values: midpoint tie coordinate;
- no interpolation between observed raw values;
- a baseline constant feature retains the same midpoint convention.

Exact rational coordinates are converted to IEEE-754 binary64 only at the
defined output boundary.

The projected coordinate matrix must contain exactly 12,952 × 12 finite
binary64 values in the frozen feature order.

The scientific projected-coordinate artifact must use anonymous holdout row
keys only.

## Projected-coordinate serialization

The canonical blinded projected-coordinate matrix is a tab-separated UTF-8
artifact with:

- anonymous holdout row key;
- the 12 frozen feature-coordinate columns in frozen order.

Coordinates are serialized using deterministic `.17g` binary64 text.

The matrix is ordered by canonical Stage 6 matrix row order.

Its whole-file SHA256 and float64 C-order numeric-array SHA256 are frozen.

No accession or species identity may appear in this artifact.

## Cross-matrix nearest-panel distance

The existing frozen `evaluate_ladder()` helper evaluates a panel whose indices
refer to the same coordinate matrix being evaluated.

Stage 7 is different: holdout query rows and baseline panel rows are in
different matrices.

Therefore Stage 7 must not call same-matrix `evaluate_ladder()` as though
holdout rows were baseline rows.

For each holdout coordinate vector `h`, selector `S`, and panel size `N`, let
`B(S,N)` be the first N baseline rows from the verified frozen selector ladder.

For baseline panel vector `b`, define:

`D(h,b) = sqrt(sum over j=1..12 of (h_j - b_j)^2)`

The per-holdout nearest-panel distance is:

`d_min(h,S,N) = min over b in B(S,N) of D(h,b)`

All 12 dimensions have equal weight.

The panel is never augmented with a holdout genome.

A dedicated cross-matrix function must be implemented and prospectively tested
against a simple synthetic oracle before production.

The implementation may process query rows in deterministic chunks for memory
control, but the arithmetic for a given row and panel must not depend on chunk
membership.

The scientific genome-level distance artifact may contain:

- anonymous holdout row key;
- selector (`OPS` or `SR`);
- N;
- nearest-panel distance.

It must not contain the identity of the nearest baseline panel genome.

Distances use deterministic `.17g` binary64 serialization.

## Species-balanced weighted-p95 primary metric

At each selector and N, the primary metric is calculated from the 12,952
holdout nearest-panel distances using the holdout species grouping only for
weights.

The frozen primitive is:

`bacselect.metrics.species_balanced_weighted_quantile`

with:

`P95 = Fraction(19, 20)`

For holdout species `s` containing `n_s` holdout genomes, each genome has exact
weight `1 / n_s`.

The implementation uses exact integer weight units derived from the least
common multiple of species sizes and returns the first observed distance whose
cumulative exact species-balanced weight reaches or exceeds the 19/20
threshold.

There is:

- no interpolation;
- no floating-point weight accumulation;
- no tolerance;
- no alternative percentile definition.

The returned primary metric is one observed binary64 nearest-panel distance.

Lower is better.

## Descriptive diagnostics

The following frozen descriptive diagnostics may also be calculated:

- weighted mean nearest-panel distance;
- weighted median nearest-panel distance;
- unweighted maximum nearest-panel distance;
- holdout genome count;
- holdout species count;
- counts belonging to species represented or absent in the baseline;
- coordinate below-range and above-range counts per feature;
- blinded selector-specific nearest-panel distance distributions.

Diagnostics may not alter the primary metric, exact product, or winner.

No random comparator is calculated in Stage 7.

## Primary-metric artifact

The canonical primary-metric table contains exactly 12 rows:

- 2 selectors × 6 panel sizes.

Columns are:

1. `selector`;
2. `N`;
3. `weighted_p95`.

Rows are ordered:

- OPS N=10,20,50,100,200,500;
- SR N=10,20,50,100,200,500.

`weighted_p95` is serialized with deterministic `.17g` binary64 text.

The production and independent-rebuild primary-metric tables must be
byte-identical.

## Exact six-size selector products

Let the stored binary64 primary value for selector `S` and panel size `N` be
`d(S,N)`.

For each of the six stored binary64 values:

`Fraction.from_float(float(d(S,N)))`

must be used.

For selector `S`, calculate:

`P(S) = product over N in {10,20,50,100,200,500} of Fraction.from_float(d(S,N))`

The multiplication is exact rational arithmetic.

The product artifact must store for each selector:

- exact numerator;
- exact denominator.

A decimal approximation may be included only as a diagnostic and is not used
for comparison.

Decision relation:

- `P(OPS) < P(SR)` → OPS;
- `P(SR) < P(OPS)` → SR;
- exact equality → UNRESOLVED.

There is no tolerance, significance threshold, equivalence margin or secondary
tie-breaker.

## Separation of analysis from final decision freeze

Stage 7 outcome generation has two computational analysis executions:

1. production;
2. independent rebuild.

Each may calculate the blinded projected coordinates, cross-matrix distances,
per-N primary metrics and exact selector products.

Neither run may publish or unblind a selector ladder.

Production logs and rebuild logs must not print:

- holdout identities;
- baseline panel identities;
- raw holdout feature values;
- projected genome-level coordinates;
- genome-level distances;
- per-N OPS/SR primary values;
- exact selector products;
- a winner.

The run wrappers should report only status, counts and cryptographic artifact
identities.

After both runs complete, their scientific artifacts are compared
byte-for-byte.

Only after byte identity is proven may a separately frozen finalization step
read the exact product artifact and create the selector-decision record.

Thus execution authorization and selector-decision authorization remain
separate gates.

## Production and independent rebuild

Production and independent rebuild must use:

- identical frozen baseline inputs;
- identical final OPS/SR ladder fingerprints;
- identical Stage 6 holdout matrix;
- identical Stage 7 implementation;
- identical software environment;
- identical deterministic serialization rules.

Run-specific scratch roots and scheduler metadata may differ.

The following scientific artifacts must be byte-identical between production
and independent rebuild:

1. blinded projected-coordinate matrix;
2. blinded nearest-panel distance table;
3. primary-metric table;
4. descriptive-diagnostic artifact;
5. exact selector-product artifact;
6. blinded selector-resolution analysis summary.

Run-specific provenance artifacts are excluded from byte-identity comparison.

A mismatch in any scientific artifact blocks the selector decision.

## Stage 7 scientific artifact contract

Each Stage 7 analysis run must produce the following finalized scientific
artifacts:

1. `blinded-holdout-projected-coordinates.tsv`;
2. `blinded-holdout-nearest-panel-distances.tsv`;
3. `selector-primary-metrics.tsv`;
4. `selector-descriptive-diagnostics.json`;
5. `selector-exact-products.json`;
6. `selector-resolution-analysis-summary.json`.

Each run also produces run-specific provenance:

7. `stage7-predecision-provenance.json`;
8. `stage7-execution-provenance.json`;
9. `stage7-content-manifest.tsv`.

Final files are written through a `.partial` execution directory and become
visible under the finalized run directory only after every scientific and
provenance validation passes.

Finalized files are never silently overwritten.

Failed `.partial` evidence is preserved.

## Analysis summary restrictions

The blinded selector-resolution analysis summary may bind:

- frozen input identities;
- holdout counts;
- holdout membership fingerprint;
- baseline artifact fingerprints;
- final OPS/SR ladder fingerprints;
- projected-coordinate artifact hashes;
- distance artifact hashes;
- primary-metric table hash;
- diagnostic artifact hash;
- exact-product artifact hash;
- implementation/environment identities;
- completion flags.

To avoid premature outcome disclosure through ordinary logs or routine
completion checks, it should not duplicate per-N primary values or exact product
numerators/denominators.

Those values remain in their dedicated blinded scientific artifacts until the
byte-identity gate passes.

## Cross-run byte-identity verification

After both finalized runs exist, a separate read-only verifier must compare the
six scientific artifacts with byte-level `cmp`.

It then writes a selector-resolution byte-identity record containing:

- production run identity;
- rebuild run identity;
- SHA256 of each of the six production scientific artifacts;
- SHA256 of each corresponding rebuild artifact;
- byte-identical boolean for each artifact;
- aggregate `all_scientific_artifacts_byte_identical` boolean;
- production and rebuild provenance SHA256 values.

The verification record contains no genome or species identity and no
per-genome feature or distance values.

The selector-decision finalizer is blocked unless all six booleans are true.

## Selector-decision finalization

A separate prospectively frozen finalizer performs the only authorized decision
read.

It must verify:

- this Stage 7 method identity;
- Stage 7 implementation identity;
- both finalized analysis runs;
- exact scientific-artifact byte identity;
- exact primary-metric table schema and 12-row contract;
- exact selector-product artifact schema;
- OPS and SR final ladder fingerprints;
- no identity-bearing fields in the decision inputs.

It then compares the two exact rational products once and writes the
selector-decision record.

The selector-decision record may contain:

- decision status;
- `OPS`, `SR` or `UNRESOLVED`;
- exact OPS product numerator and denominator;
- exact SR product numerator and denominator;
- SHA256 identities of the primary metric, product, byte-identity and analysis
  summary artifacts;
- all frozen design and implementation identities.

It must not contain any genome or species identity.

If the exact products tie, the record is `UNRESOLVED`.

No fallback criterion is permitted.

## Post-decision boundary

Only after the selector-decision record itself is committed and pushed may
BacSelect:

- unblind the winning frozen baseline ladder for audit;
- generate official selector-v1 nested panels;
- package a public selector-v1 release;
- enable publishing automation.

Until that point:

- panel identities remain blinded;
- no official BacSelect panel is published;
- no monthly selector publication is enabled.

## Required implementation tests

Before Stage 7 production authorization, synthetic tests must cover at minimum:

1. baseline projection below minimum maps to 0;
2. baseline projection above maximum maps to 1;
3. between-value projection uses cumulative weight with no interpolation;
4. exact baseline ties use the midpoint rule;
5. unequal baseline species sizes use exact `1/n_s` weights;
6. constant baseline feature reproduces the midpoint convention;
7. holdout rows never alter the baseline transform;
8. cross-matrix Euclidean distance matches a hand-calculated oracle;
9. cross-matrix nearest-panel selection uses only frozen baseline panel rows;
10. panel prefixes are literal nested prefixes;
11. weighted-p95 uses exact holdout species balancing;
12. weighted-p95 uses inverse ECDF with no interpolation;
13. exact threshold ties select the first observed distance reaching the
    threshold;
14. exact six-size products use `Fraction.from_float`;
15. exact product equality returns `UNRESOLVED`;
16. no secondary tie-breaker exists;
17. identity-bearing fields are rejected from scientific outcome artifacts;
18. production and rebuild scientific serialization is byte-deterministic;
19. finalization fails if any scientific artifact differs;
20. finalization fails unless the final OPS/SR fingerprints are exactly
    `c81d9fd...` and `3c703f5f...`.

Tests must use synthetic fixtures only.

Real Stage 6 holdout data must not be opened during implementation testing.

## Failure semantics

Stage 7 fails closed if any frozen identity, schema, count, membership,
geometry, ladder, serialization, determinism or byte-identity requirement is
violated.

A failure does not authorize:

- exclusion of an inconvenient holdout genome;
- replacement of a holdout genome;
- downsampling;
- imputation;
- ladder regeneration using holdout data;
- a changed percentile rule;
- a changed weighted-p95 rule;
- a changed panel size;
- a secondary selector criterion;
- manual interpretation as a substitute for the exact rule.

The failed evidence is preserved and the selector remains unresolved.

## Required completion evidence

Before selector-decision authorization, Git must freeze aggregate-only evidence
binding:

- Stage 7 method SHA256;
- Stage 7 implementation/test SHA256 values;
- production scientific artifact SHA256 values;
- rebuild scientific artifact SHA256 values;
- production and rebuild provenance SHA256 values;
- byte-identity verification record SHA256;
- `all_scientific_artifacts_byte_identical=true`;
- identity-bearing outputs committed to Git: false;
- selector-decision finalized: false.

Only after that completion evidence is committed and pushed may the
selector-decision finalization gate be authorized.

## Current authorization boundary

At this method freeze:

`STAGE7_IMPLEMENTATION_AUTHORIZED=no`

`STAGE7_PRODUCTION_EXECUTION_AUTHORIZED=no`

`STAGE7_INDEPENDENT_REBUILD_AUTHORIZED=no`

`SELECTOR_DECISION_AUTHORIZED=no`

No Stage 7 outcome-producing execution is authorized by this document alone.
