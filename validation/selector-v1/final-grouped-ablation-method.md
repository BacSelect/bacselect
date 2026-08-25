# Selector-v1 final 300/2400 grouped feature-ablation method

## Status

PROSPECTIVE FINAL-SCHEMA REVALIDATION

This record defines the grouped feature-family ablation on the frozen final
300/2400 structural-feature geometry before any reduced-feature grouped OPS or
SR selector is calculated.

The four feature families were pre-specified in the selector-v1 design. The
historical grouped-ablation implementation and its 150/400 evidence remain
unchanged. This final-schema pathway substitutes the selected 300/2400 repeat
coordinates for the six scale-dependent 150/400 coordinates and otherwise
retains the prospective grouped-ablation method.

Identity blinding remains in force.

## Frozen final feature geometry

The selection and evaluation universe contains:

- 55,306 eligible genomes;
- 13,765 species groups;
- 12 frozen species-balanced percentile coordinates;
- selected repeat scales 300 bp and 2400 bp.

The final 12 coordinates are:

1. `01_total_genome_length`;
2. `02_whole_genome_gc_fraction`;
3. `03_replicon_count`;
4. `04_non_chromosomal_replicon_count`;
5. `05_non_chromosomal_sequence_fraction`;
6. `06_non_unique_canonical_300mer_fraction`;
7. `07_non_unique_canonical_2400mer_fraction`;
8. `08_maximum_canonical_300mer_multiplicity`;
9. `09_maximum_canonical_2400mer_multiplicity`;
10. `10_longest_exact_repeat_length`;
11. `11_inter_replicon_shared_canonical_300mer_fraction`;
12. `12_inter_replicon_shared_canonical_2400mer_fraction`.

The analysis loads the already frozen final species-balanced percentile matrix
directly. It does not recompute the final transform from the historical
150/400 raw feature matrix.

## Pre-specified feature groups

### Basic genome properties

Remove together:

- `01_total_genome_length`;
- `02_whole_genome_gc_fraction`.

The resulting selection geometry contains 10 dimensions.

### Replicon architecture

Remove together:

- `03_replicon_count`;
- `04_non_chromosomal_replicon_count`;
- `05_non_chromosomal_sequence_fraction`.

The resulting selection geometry contains 9 dimensions.

### Repeat architecture

Remove together:

- `06_non_unique_canonical_300mer_fraction`;
- `07_non_unique_canonical_2400mer_fraction`;
- `08_maximum_canonical_300mer_multiplicity`;
- `09_maximum_canonical_2400mer_multiplicity`;
- `10_longest_exact_repeat_length`.

The resulting selection geometry contains 7 dimensions.

### Inter-replicon sharing

Remove together:

- `11_inter_replicon_shared_canonical_300mer_fraction`;
- `12_inter_replicon_shared_canonical_2400mer_fraction`.

The resulting selection geometry contains 10 dimensions.

The four groups partition all 12 final structural dimensions exactly once.

## Selection geometry

For one grouped ablation, every coordinate belonging to the pre-specified
feature family is removed simultaneously from the frozen final 12-dimensional
species-balanced percentile geometry.

OPS and SR are then run in the resulting reduced geometry.

No remaining coordinate is rescaled, retransformed, or reweighted after
grouped removal.

## Coverage evaluation geometry

Every final grouped-ablation panel is evaluated in the complete frozen final
12-dimensional 300/2400 species-balanced architecture geometry.

The removed feature family is unavailable during selection but remains part of
the common coverage objective used to evaluate the resulting panel.

This retains direct comparability:

- among the four final grouped ablations;
- against the corresponding final 300/2400 leave-one-feature-out results;
- against the frozen full 12-feature final OPS and SR results.

The same 55,306-genome evaluation universe, species-balanced evaluation
weights, inverse-ECDF quantile conventions, and ten pre-specified coverage
metrics are retained.

Coverage is not evaluated only in the reduced selection geometry.

## Frozen full-feature reference gate

Before any grouped reduced-feature selector is calculated, the implementation
must:

1. verify the committed final feature-space input manifest and its immutable
   files;
2. verify the frozen final 300/2400 percentile matrix and species mapping;
3. reconstruct the full-feature OPS and SR N=500 ladders;
4. reproduce their frozen blinded fingerprints exactly;
5. recompute all ten full-feature coverage metrics at N = 10, 20, 50, 100,
   200, and 500;
6. reproduce the frozen final OPS/SR reference-metrics table exactly.

A `--verify-inputs-only` mode performs these gates and exits before any grouped
reduced-feature selector is calculated.

## Panel sizes and selectors

Evaluate OPS and SR separately at:

- N = 10;
- N = 20;
- N = 50;
- N = 100;
- N = 200;
- N = 500.

The analysis therefore contains:

4 feature groups x 2 selectors x 6 panel sizes = 48 result rows.

## Panel overlap

For selector S and panel size N, overlap is the unordered set intersection
between:

1. the first N genomes of the frozen final full 12-feature S ladder; and
2. the first N genomes of the corresponding final grouped-ablation S ladder.

Report:

- `overlap_count`;
- `overlap_fraction`, written exactly as `overlap_count/N`.

No positional-match score, Jaccard statistic, or additional overlap measure is
introduced.

## Blinded ladder fingerprints

Each N=500 grouped-ablation ladder is fingerprinted from its ordered accession
sequence with SHA256 under the namespace:

`BacSelect-selector-v1|FINAL300-2400|GROUPED|remove=<group>|<selector>|ladder|N=500`

The fingerprint is reported; the accession sequence is not.

## Output and blinding

For every removed group, selector, and N, report:

- stable removed-group identifier;
- exact removed feature names;
- number of remaining selection dimensions;
- selector;
- N;
- blinded N=500 grouped-ablation ladder SHA256 fingerprint;
- overlap count;
- exact overlap fraction;
- all ten pre-specified coverage metrics.

No genome accession, species identifier, species name, or other organism
identity is included.

The canonical report contains 48 result rows plus one header row.

## Interpretation boundary

Grouped feature ablation is a sensitivity analysis.

It does not introduce a new OPS-versus-SR selector decision rule.

A feature family is not automatically retained or removed because of one
grouped-ablation result.

The final grouped evidence will be interpreted together with the already
frozen final 300/2400 leave-one-feature-out evidence and the separately frozen
repeat-scale evidence.

The coverage-stage OPS-versus-SR decision remains governed only by its
pre-specified rule. Grouped ablation must not be used to invent an aggregate
score, equivalence margin, significance threshold, or other post-hoc selector
criterion.

Deterministic rebuild and update-stability validation remain separately
pre-specified requirements.

Panel identities remain blinded.
