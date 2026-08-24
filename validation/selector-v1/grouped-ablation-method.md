# Selector-v1 grouped feature-ablation method

## Status

PROSPECTIVE IMPLEMENTATION CLARIFICATION

This record defines the grouped feature-ablation implementation before any
reduced-feature grouped OPS or SR selector is calculated.

The selector-v1 design prospectively requires removal of four feature families
to determine whether the selector depends disproportionately on one family.

The groups and their membership were specified before this implementation.

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

- `06_non_unique_canonical_150mer_fraction`;
- `07_non_unique_canonical_400mer_fraction`;
- `08_maximum_canonical_150mer_multiplicity`;
- `09_maximum_canonical_400mer_multiplicity`;
- `10_longest_exact_repeat_length`.

The resulting selection geometry contains 7 dimensions.

### Inter-replicon sharing

Remove together:

- `11_inter_replicon_shared_canonical_150mer_fraction`;
- `12_inter_replicon_shared_canonical_400mer_fraction`.

The resulting selection geometry contains 10 dimensions.

The four groups partition all 12 frozen structural dimensions exactly once.

## Selection geometry

For one grouped ablation, all coordinates belonging to the pre-specified
feature family are removed simultaneously from the frozen 12-dimensional
species-balanced percentile geometry.

OPS and SR are then run in the resulting reduced geometry.

The species-balanced percentile transform is defined independently for each
feature column. Removing a group after the complete 12-dimensional transform
is therefore equivalent to removing those raw features first and transforming
the remaining dimensions.

No remaining coordinate is rescaled or reweighted after grouped removal.

## Coverage evaluation geometry

Every grouped-ablation panel is evaluated in the complete frozen
12-dimensional species-balanced architecture geometry.

The removed feature family is unavailable during selection but remains part
of the common coverage objective used to evaluate the resulting panel.

This retains direct comparability:

- among the four grouped ablations;
- against the corresponding leave-one-feature-out results;
- against the frozen full 12-feature OPS and SR results.

The same 55,306-genome evaluation universe, species-balanced evaluation
weights, inverse-ECDF quantile conventions, and ten pre-specified coverage
metrics are retained.

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

1. the first N genomes of the frozen full 12-feature S ladder; and
2. the first N genomes of the corresponding grouped-ablation S ladder.

Report:

- `overlap_count`;
- `overlap_fraction`, written exactly as `overlap_count/N`.

No positional-match score, Jaccard statistic, or additional overlap measure
is introduced.

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

## Interpretation boundary

Grouped feature ablation is a sensitivity analysis.

It does not introduce a new OPS-versus-SR selector decision rule.

A feature family is not automatically retained or removed because of one
grouped-ablation result.

The grouped evidence will be interpreted together with the already frozen
leave-one-feature-out evidence and the separately pre-specified repeat-scale
analysis before the structural-feature schema is frozen.

Input-order invariance, rebuild determinism, and update-stability validation
remain separately pre-specified requirements and are not silently treated as
completed by this analysis.

Identity blinding remains in force.
