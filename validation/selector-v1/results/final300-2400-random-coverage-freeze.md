# Final selector-v1 300/2400 random coverage freeze

This record freezes the 1,000-replicate species-balanced random coverage
baseline recalculated in the final 300/2400 feature geometry.

## Analysis identity

- analysis commit: `81d7f62c3aa59b851848be9ce2afeb3b33839980`
- panel sizes: 10, 20, 50, 100, 200, 500
- random replicates: 1,000
- master seed: 20260824
- RNG: `numpy.random.Generator(PCG64)`
- replicate protocol: one generator, sequential replicates
- maximum N: 500
- quantile method: empirical inverse CDF without interpolation
- quantile thresholds: 1/40, 1/2, 39/40

## Frozen random membership identity

The random ladder membership set matched the previously frozen identity:

`9394a26ded92fb2baafea0101b837335e9d434f4cd3d8c6484ef61bbf0741719`

Coverage distances were recalculated because the feature geometry changed to
the final 300/2400 schema.

## Deterministic repeat check

The first five replicate coverage results were evaluated twice. Both
fingerprints were:

`dee5f11d07588372b12372bd1b6bb8c1a5f5f1928d725cc1d9a23c97b804fce8`

## Structural checks

The replicate table contains 1,000 replicates x 6 panel sizes = 6,000 unique
data rows plus one header. The summary contains 6 panel sizes x 10 frozen
coverage metrics = 60 data rows plus one header.

## Output identities

- replicate metrics:
  `d86d572c22931c4440edceda25b17de2a02f586309611dc497b70dcdbb1a2c5f`
- random summary:
  `a1e0bf78d4be461a0de74ea8a06e103ccfeaafd394308b7ffe580f9cce96efda`
- provenance:
  `7ada89bc210a561f29a9957180695395b6f8e4253d6d4e05268c3bdf9707c63a`
- output hash manifest:
  `f009a033bc91140a7817ee3fd9f5fefe18afdab6f60244d681769150edea5a31`

Measured runtimes are execution metadata rather than deterministic scientific
identities.

## Decision boundary

This random baseline does not choose between OPS and SR and introduces no new
selector decision criterion.

Candidate-versus-random empirical ranks have not yet been calculated at this
checkpoint.

Before empirical ranks are calculated, the final comparator must be corrected
so that it binds the frozen OPS/SR evidence to its own analysis commit and the
frozen random evidence to its own analysis commit, rather than requiring both
independent evidence sets to share one commit.
