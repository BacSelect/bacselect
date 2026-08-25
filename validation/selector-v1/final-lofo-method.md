# Selector-v1 final 300/2400 leave-one-feature-out revalidation

## Status

PROSPECTIVE FINAL-SCHEMA BINDING

This record binds the already frozen selector-v1 leave-one-feature-out (LOFO)
method to the final 300/2400 architecture geometry before any final-schema
11-feature OPS or SR selector is calculated.

It does not replace or reinterpret the historical base-12 LOFO evidence.

## Scientific method retained unchanged

The prospective LOFO convention remains:

- remove exactly one of the 12 frozen architecture coordinates at a time;
- run OPS and SR in the resulting 11-dimensional selection geometry;
- do not rescale or otherwise reweight the remaining coordinates;
- evaluate every ablated panel in the complete frozen 12-dimensional geometry;
- evaluate N = 10, 20, 50, 100, 200, and 500;
- retain the ten pre-specified coverage metrics;
- report unordered overlap with the corresponding full-feature selector ladder;
- retain identity blinding;
- introduce no new selector decision rule.

The only architecture change is the already frozen replacement of the inherited
150/400 repeat-scale coordinates by the selected 300/2400 coordinates.

## Frozen final geometry

The final feature order is:

1. `01_total_genome_length`
2. `02_whole_genome_gc_fraction`
3. `03_replicon_count`
4. `04_non_chromosomal_replicon_count`
5. `05_non_chromosomal_sequence_fraction`
6. `06_non_unique_canonical_300mer_fraction`
7. `07_non_unique_canonical_2400mer_fraction`
8. `08_maximum_canonical_300mer_multiplicity`
9. `09_maximum_canonical_2400mer_multiplicity`
10. `10_longest_exact_repeat_length`
11. `11_inter_replicon_shared_canonical_300mer_fraction`
12. `12_inter_replicon_shared_canonical_2400mer_fraction`

The selection and evaluation universe remains 55,306 genomes assigned to
13,765 species groups.

The canonical final species-balanced percentile matrix has SHA256:

`f48e20b28ee89988e7abb42488a35c62fbfa4a538c15c8d2d70b6b5ba7ae83c1`

The canonical species mapping has SHA256:

`f0343238930e957f82bc28997a216ab3a8967d007b3d3471679e3f054c76af6c`

## Final full-feature references

Before any ablated selector is calculated, the implementation rebuilds the
full-feature OPS and SR N=500 ladders from the frozen final 300/2400 geometry.

Those rebuilt ladders are evaluated at all six N values and all ten coverage
metrics. Every value must reproduce the already frozen final OPS/SR coverage
artifact exactly:

`final300-2400-ops-vs-sr-metrics.tsv`

SHA256:

`9cd2cc838cb74a044e356a1a418633ef2bdc89c4e9f71f924e4c1c0a79073388`

The associated frozen summary must also match SHA256:

`4908739ac15bd2e842acb83bba6588ad7c2dc29be78a6a57b500709b33e16cf6`

and its evidence-generation commit must remain:

`ea547dbe7eeffbd5ce426c7ca5cb4347d8a1bc9d`

This binds LOFO overlap to full-feature references that reproduce the frozen
final coverage evidence before any 11-feature result exists.

## Selection geometry

For each LOFO analysis, one coordinate is removed directly from the completed
final 12-dimensional species-balanced percentile matrix.

Because the percentile transform is defined independently for each feature,
this retains the scientific convention frozen for the historical LOFO method.

The remaining 11 coordinates are not rescaled.

## Coverage geometry

Every LOFO panel is evaluated in the complete frozen final 300/2400
12-dimensional species-balanced percentile geometry.

The removed coordinate therefore remains part of the coverage objective.

This keeps all LOFO coverage values directly comparable with each other and
with the frozen full-feature final OPS/SR coverage evidence.

## Panel overlap

For selector S and panel size N, overlap remains the unordered set intersection
between:

1. the first N genomes of the rebuilt, verified full-feature final S ladder;
2. the first N genomes of the corresponding final-schema LOFO S ladder.

Only `overlap_count` and the exact `overlap_count/N` fraction are reported.

No positional-match score, Jaccard statistic, or other overlap statistic is
introduced.

## Output and blinding

The canonical report contains exactly 144 result rows plus one header row:

- 12 removed features;
- 2 selectors;
- 6 panel sizes.

Every row contains:

- removed feature;
- selector;
- N;
- blinded N=500 ablation-ladder SHA256 fingerprint;
- overlap count;
- exact overlap fraction;
- all ten pre-specified coverage metrics.

No accession, species identifier, species name, or other organism identity is
included.

## Verification-only boundary

The runner supports `--verify-inputs-only`.

That mode:

- verifies the exact final input identities;
- loads the frozen final percentile geometry and species mapping;
- rebuilds the full-feature OPS and SR ladders;
- verifies their complete coverage outputs against the frozen final OPS/SR
  metrics;
- calculates no 11-feature OPS or SR selector.

The verification-only step must pass under committed code before production
LOFO execution.

## Interpretation boundary

Final-schema LOFO remains a feature-sensitivity analysis.

It does not resolve the already frozen coverage-stage OPS-versus-SR decision,
does not introduce a new OPS-versus-SR decision rule, and does not
automatically retain or remove a feature.

The canonical final LOFO result must be frozen and independently reproduced
before interpretation.

Grouped feature-family ablation remains a separate pre-specified analysis.

Genome and species identities remain blinded.
