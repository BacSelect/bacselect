# Final selector-v1 300/2400 feature-space evidence freeze

This record freezes the revised BacSelect selector-v1 12-dimensional feature
space after the prospectively defined repeat-scale rule selected `(300, 2400)`.

## Identity

- Repository commit used to build the feature space:
  `0f75c51edc37259f168ad10faf44d536dd9b75a5`
- Alternative-k production commit:
  `83516de6cd3713415e78502ba58db072fa6b38f9`
- Genomes: 55,306
- Species groups: 13,765
- Dimensions: 12
- Selected repeat scales: 300 bp and 2400 bp

## Schema

The six non-scale-dependent dimensions are unchanged:

1. total genome length
2. whole-genome GC fraction
3. replicon count
4. non-chromosomal replicon count
5. non-chromosomal sequence fraction
10. longest exact repeat length

The six scale-dependent dimensions are:

6. non-unique canonical 300-mer fraction
7. non-unique canonical 2400-mer fraction
8. maximum canonical 300-mer multiplicity
9. maximum canonical 2400-mer multiplicity
11. inter-replicon shared canonical 300-mer fraction
12. inter-replicon shared canonical 2400-mer fraction

The genome universe, genome order, and species mapping are unchanged from the
frozen selector-v1 foundation.

## Frozen matrix identities

Raw structural feature matrix:

- path:
  `/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/final-feature-space/0f75c51edc37259f168ad10faf44d536dd9b75a5/structural-feature-matrix-300-2400.tsv`
- file SHA256:
  `86c0c3d49317dfc3cc452114e3863666fe2112b6a3ae8dae2090b60a2a598948`
- float64 C-order array SHA256:
  `2a0dbd5809fa4d5d77ab6e2d5255ddec9bb933a94be6c270260ec81758d8cbd6`

Species-balanced percentile feature matrix:

- path:
  `/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/final-feature-space/0f75c51edc37259f168ad10faf44d536dd9b75a5/species-balanced-percentile-feature-matrix-300-2400.tsv`
- file SHA256:
  `f48e20b28ee89988e7abb42488a35c62fbfa4a538c15c8d2d70b6b5ba7ae83c1`
- float64 C-order array SHA256:
  `9a4a120562ff1151fd8c83e831eb81362b2372844f7dd7407746554af49cda67`

The matrices are not duplicated in Git. Their exact byte identities are frozen
by SHA256, and the deterministic builder plus row-level provenance audit are
stored with this evidence.

## Provenance identities

- historical 150/400 raw matrix:
  `fd264bedda627d737a647de601c8b835f53baeca246724e9aafb73fd50c9d656`
- canonical species mapping:
  `f0343238930e957f82bc28997a216ab3a8967d007b3d3471679e3f054c76af6c`
- frozen repeat-scale selection summary:
  `beced81273c05bf039d6630ea2b173ce4485bdd4042546c781ee64aa2a785bcf`
- frozen repeat-scale production-file manifest:
  `75fd427a28b712b1c76ebe93722d2c6baac1e3d1bccedf63a00de71bebea5b84`
- frozen full-universe repeat-scale audit summary:
  `40ce0b77936d69c039474256c904f16cb204ec4040f05c190619708547dc6dc1`
- geometry module used for percentile transformation:
  `fbebf436d049be063817b717878330f38e09b3e7cb79f9dbc1b8f704af6a0d69`

## Build validation

The build verified:

- all 55,639 frozen alternative-k production files;
- exactly 55,306 genomes and 13,765 species groups;
- exact preservation of the six unchanged dimensions;
- replacement of only the six scale-dependent coordinates;
- finite 55,306 x 12 raw and percentile matrices;
- preservation of distinct raw-value ordering under float64 conversion;
- species-balanced percentile values in `[0,1]`;
- preservation of unique-value counts through the percentile transform;
- deterministic permutation invariance with seed `20260825`;
- exact round-trip of both written matrices to the in-memory float64 arrays.

Output identities:

- row-level provenance audit:
  `2155a672c676f99e546909ab4bedf1245c953ccadf82276be75303bcf121fcc7`
- feature-space summary:
  `212303b00e520fd8c85a4f360f53dfa2a52adbf1cf6380bc5ac23f731dec7a30`
- feature-space SHA256 manifest:
  `d8f9b4e45ab4fed070eb38408a23ebe8bdae7e7ee71593f8cf2949e5301e4146`

## Validation consequence

This feature-space freeze does not transfer any geometry-dependent result from
the superseded 150/400 schema.

Feature correlation, OPS and SR ladders, OPS-versus-SR coverage and selector
comparison, species-balanced random-baseline coverage, species representation
including AG, leave-one-feature-out analysis, and grouped feature-family
ablation must be recalculated on this frozen 300/2400 feature space before the
selector-v1 decision is final.
