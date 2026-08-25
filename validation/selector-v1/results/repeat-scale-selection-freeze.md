# Repeat-scale selection evidence freeze

This record freezes the first deterministic BacSelect selector-v1 repeat-scale
selection result produced from the validated full-universe alternative-k dataset.

## Frozen inputs

- Analysis commit: `3c77cd33902bde25571aa4c04ab8d2e528bbec97`
- Production commit: `83516de6cd3713415e78502ba58db072fa6b38f9`
- Genomes: 55,306
- Species groups: 13,765
- k grid: 50, 75, 100, 150, 200, 300, 400, 600, 800, 1200, 1600, 2400, 3200
- Repeat feature families:
  - non_unique_fraction
  - maximum_multiplicity
  - inter_replicon_shared_fraction
- Species mapping SHA256:
  `f0343238930e957f82bc28997a216ab3a8967d007b3d3471679e3f054c76af6c`
- Full-universe audit summary SHA256:
  `40ce0b77936d69c039474256c904f16cb204ec4040f05c190619708547dc6dc1`
- Production-file manifest SHA256:
  `75fd427a28b712b1c76ebe93722d2c6baac1e3d1bccedf63a00de71bebea5b84`
- Repeat-scale method SHA256:
  `2897282450221e662bb1d6c1142da7c999e07e23c21d66f265cbf2fe13313d01`
- Repeat-scale module SHA256:
  `7dcd0cab3da9698ca4a697315326bc303e30c96d3b3ed12e48b627287a3b6f6c`

## Deterministic result

The frozen selector-v1 minimax repeat-scale rule selected:

- selected pair: `(300, 2400)`
- selected R_max: `0.16255877925735962`
- selected R_mean: `0.0891272863055269`
- inherited `(150, 400)` rank: `59 / 78`
- inherited R_max: `0.2660464094870586`
- inherited R_mean: `0.1035710924240693`
- selected pair differs from inherited pair: `true`

The six scale-dependent repeat coordinates therefore move from 150/400 to
300/2400 under the prospectively frozen rule. Geometry-dependent selector
validation must be rerun before any selector decision is treated as final.

## Array identities

- raw-value tensor SHA256:
  `85526951115c3dc6e51a96bfce8fa9f143ccd588abad6852eed2ccce26559484`
- percentile tensor SHA256:
  `4b9da24839d2b4a9e5b361511cfcfa9f415d67c24afcad33c75777f0f0076a5c`
- 13 x 13 distance matrix array SHA256:
  `c198f68a39d1526eb38a079a0c227dd00c28bfc4babb298044296d2ffb01cfe3`

## Output files

- distance matrix SHA256:
  `97c2395dc13fbb98c5b3689b5a7d7e0ebdd0803c51fd5afa1ee75320c55e27f6`
- all 78 pair scores SHA256:
  `b868cdc33f6835a8b41d2a860cc4dedc9978955e95fb240fd96d7b4cb5f91e9f`
- selection summary SHA256:
  `beced81273c05bf039d6630ea2b173ce4485bdd4042546c781ee64aa2a785bcf`

The selection was produced by the committed BacSelect repeat-scale functions.
The analysis driver did not reimplement percentile transformation, scale
distance, pair scoring, or pair selection.
