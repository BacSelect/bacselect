# Base-12 grouped feature-ablation freeze

This record freezes the first canonical identity-blind selector-v1 grouped
feature-ablation report before any reported coverage metric or panel-overlap
value is inspected or interpreted.

## Prospective boundary

The grouped feature-ablation method and implementation were committed and
pushed before any grouped reduced-feature OPS or SR selector was calculated.

Method and implementation commit:

`886dc952514203c9e0fa0d084acb3dcfeca6df24`

Production Slurm wrapper commit:

`6baef9ea5c1a836b554a8810c61faae2202b7548`

The four feature families were pre-specified in the selector-v1 validation
design.

### Basic genome properties

Removed together:

- `01_total_genome_length`;
- `02_whole_genome_gc_fraction`.

Remaining selection dimensions: 10.

### Replicon architecture

Removed together:

- `03_replicon_count`;
- `04_non_chromosomal_replicon_count`;
- `05_non_chromosomal_sequence_fraction`.

Remaining selection dimensions: 9.

### Repeat architecture

Removed together:

- `06_non_unique_canonical_150mer_fraction`;
- `07_non_unique_canonical_400mer_fraction`;
- `08_maximum_canonical_150mer_multiplicity`;
- `09_maximum_canonical_400mer_multiplicity`;
- `10_longest_exact_repeat_length`.

Remaining selection dimensions: 7.

### Inter-replicon sharing

Removed together:

- `11_inter_replicon_shared_canonical_150mer_fraction`;
- `12_inter_replicon_shared_canonical_400mer_fraction`.

Remaining selection dimensions: 10.

The four groups partition the 12 frozen structural dimensions exactly once.

## Selection and evaluation conventions

For each grouped ablation:

- all coordinates belonging to one pre-specified feature family are removed
  simultaneously;
- OPS and SR operate in the resulting reduced selection geometry;
- remaining coordinates are not rescaled or reweighted;
- coverage is evaluated in the complete frozen 12-dimensional
  species-balanced architecture geometry;
- OPS and SR are evaluated separately;
- panel sizes are N = 10, 20, 50, 100, 200, and 500;
- overlap is measured against the corresponding full base-12 selector prefix;
- overlap is unordered set intersection;
- all ten pre-specified coverage metrics are retained;
- no new selector decision rule is introduced.

Genome and species identities remain blinded.

## Implementation provenance

Generating commit:

`6baef9ea5c1a836b554a8810c61faae2202b7548`

Grouped-ablation runner SHA256:

`402ddbc38b77b05df2cf16145adadc0952485489277472211f10d1c3c6fc58ca`

Grouped-ablation Slurm wrapper SHA256:

`bda970c75672f021d4b8506328b65201b5e0eee2a1981d7df817290bc27886e3`

Environment:

- Python 3.11.16
- NumPy 2.4.6
- SciPy 1.17.1

Frozen environment-lock SHA256:

`f6f4a19c44a759705682ba4199207eaef5c2435e1b6feeddc1e4654686bc2a8c`

Frozen raw structural-feature matrix SHA256:

`fd264bedda627d737a647de601c8b835f53baeca246724e9aafb73fd50c9d656`

Frozen species mapping SHA256:

`f0343238930e957f82bc28997a216ab3a8967d007b3d3471679e3f054c76af6c`

Frozen full 12-dimensional coordinate SHA256:

`618877ff239d07f60466baf577acfc8576fd16a0cb2673a6d7102eb90018832c`

Frozen full-feature OPS N=500 ladder fingerprint:

`3f9a7c4557268fad829b078de9679cda4ee26a81982c1aed71fc066f8290f3b8`

Frozen full-feature SR N=500 ladder fingerprint:

`dbe0174a5e96202e7d755ac616318c5e6007939b5062a3f5b9dabea0a8bfe5e8`

## Canonical report

Artifact:

`base12-grouped-ablation.tsv`

SHA256:

`ac753b9c240aa33b11f70a875ef8584814a5cc4185e7c686f5f114483eb66962`

Dimensions:

- 4 pre-specified feature families;
- 2 candidate selectors;
- 6 pre-specified panel sizes;
- 48 identity-blind result rows plus one header row.

Each result row records:

- removed feature-family identifier;
- exact removed feature names;
- number of remaining selection dimensions;
- selector;
- panel size;
- blinded N=500 grouped-ablation ladder fingerprint;
- overlap count with the corresponding full base-12 ladder;
- exact overlap fraction;
- the ten pre-specified coverage metrics.

Coverage is evaluated in the frozen full 12-dimensional geometry.

## Production execution

Production Slurm job:

`2495279`

Production provenance artifact:

`base12-grouped-ablation-provenance.tsv`

Production provenance SHA256:

`b13a82e3bb388c4adc54707611b15a714bdcb83e25b229bb3468df78c29c3f3c`

The production execution:

- verified the four frozen grouped-ablation definitions;
- verified the immutable 55,306-genome, 13,765-species, 12-feature universe;
- verified the frozen environment lock;
- reconstructed and verified the frozen OPS and SR reference ladders;
- produced all 8 blinded N=500 grouped-ablation ladder fingerprints;
- produced all 48 required group/selector/N combinations;
- produced a 49-line report;
- emitted zero bytes to stderr;
- reached `PASS | grouped feature-ablation job completed`.

## Independent deterministic rebuild

A second execution was performed from the same frozen generating commit in a
separate output directory.

Rebuild Slurm job:

`2495280`

Rebuild provenance artifact:

`base12-grouped-ablation-rebuild-provenance.tsv`

Rebuild provenance SHA256:

`b64091e2e918f65969ac3b4d2c59bb1a8dd9e72ed4379cb297a8a71b446e07a4`

The rebuilt report reproduced SHA256:

`ac753b9c240aa33b11f70a875ef8584814a5cc4185e7c686f5f114483eb66962`

The production and rebuild reports were byte-identical under `cmp`.

The rebuild emitted zero bytes to stderr and reached
`PASS | grouped feature-ablation job completed`.

The production and rebuild provenance files intentionally differ because they
contain run-specific execution metadata such as Slurm job identifiers.

## Interpretation boundary

No grouped-ablation coverage metric or panel-overlap value had been inspected
when this canonical report was frozen.

Grouped feature ablation is a pre-specified feature-family sensitivity
analysis.

This freeze record does not:

- select between OPS and SR;
- introduce a new selector decision criterion;
- automatically retain or remove a feature family;
- freeze the structural-feature schema.

The grouped-ablation evidence will be interpreted together with the already
frozen leave-one-feature-out evidence.

Repeat-scale validation, input-order invariance, deterministic rebuild
validation at the broader selector-validation level, and update-stability
analysis remain separately pre-specified work before selector v1 and the
structural-feature schema are frozen.

Genome and species identities remain blinded.
