# Final selector-v1 300/2400 OPS-versus-SR coverage freeze

This record freezes the final-schema OPS-versus-SR coverage comparison
calculated under the prospectively committed coverage protocol.

## Analysis identity

- analysis commit: `ea547dbe7eeffbd5ce426c7ca5cb4347d8a1bc9d`
- panel sizes: 10, 20, 50, 100, 200, 500
- primary metric: species-balanced weighted 95th percentile nearest-panel
  distance (`weighted_p95`)
- lower values are better
- automatic-winner rule: one candidate must have the lower primary metric at
  all six panel sizes

The OPS and SR ladders were reconstructed from the frozen final 300/2400
foundation and required to match their previously frozen identity-blind
fingerprints before coverage was evaluated.

## Frozen ladder identities

- OPS N=500:
  `ab5d75b2d35b9577bcf84acceb8e10d847e983e04a8e4aa5859fd0bde1ae2834`
- SR N=500:
  `080cbaf23d9259610d59fc1ef5a3164329e0bbbe9016b21590c0b34ad2da1b97`

## Primary comparison

| N | OPS weighted-p95 | SR weighted-p95 | Lower |
|---:|---:|---:|:---|
| 10 | 1.0701206478524528 | 1.0791288858498906 | OPS |
| 20 | 0.89252997471251772 | 0.91939205019899828 | OPS |
| 50 | 0.74313774471022076 | 0.74606507938350264 | OPS |
| 100 | 0.63304147792300747 | 0.66100228500446578 | OPS |
| 200 | 0.53824904262036088 | 0.53263327330770305 | SR |
| 500 | 0.43309233197078495 | 0.43074575053129432 | SR |

The primary curves are not uniformly ordered.

Frozen primary status:

`PRIMARY_CURVES_NOT_UNIFORMLY_ORDERED`

Automatic primary winner:

`NONE`

## Decision boundary

This freeze records the output of the pre-specified automatic-winner rule only.

No new selector decision criterion was introduced. No aggregate score or
post-hoc significance threshold was constructed. The secondary metrics were
calculated as pre-specified evidence, but secondary interpretation was not
performed by the comparison script.

The selector-v1 decision therefore remains open at this checkpoint.

## Output identities

- primary table:
  `18349c559862cdb35a2453c1dd97c9b3f6e844ff0665e4c7b0ba79a019bf6211`
- complete pre-specified metrics:
  `9cd2cc838cb74a044e356a1a418633ef2bdc89c4e9f71f924e4c1c0a79073388`
- summary:
  `4908739ac15bd2e842acb83bba6588ad7c2dc29be78a6a57b500709b33e16cf6`
- output hash manifest:
  `54a126b5bfdaa0feba583e8a8420c05c2f4a87bc53bd9355cd7ade559777a410`

Measured runtimes in the summary are execution metadata rather than
deterministic scientific identities.

## Next stage

The prospectively frozen random-baseline protocol can now be run in the final
300/2400 geometry. Candidate-versus-random empirical ranks remain descriptive
support and do not create a new OPS-versus-SR decision criterion.
