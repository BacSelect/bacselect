# Selector-v1 random baseline freeze

The identity-blind species-balanced random baseline was frozen before
OPS or SR was compared against the random distributions.

## Production run

- Slurm job: `2492482`
- generating BacSelect commit:
  `d642c97fadcecbb038f8ab85265f6fb5f26b9d05`
- replicates: `1000`
- nested panel sizes: `10, 20, 50, 100, 200, 500`
- master seed: `20260824`
- RNG: `numpy.random.Generator(PCG64)`
- environment lock SHA256:
  `f6f4a19c44a759705682ba4199207eaef5c2435e1b6feeddc1e4654686bc2a8c`

The production job completed successfully with empty stderr.

## Frozen random ladders

Complete 1000 x 500 ordered ladder-set SHA256:

`9394a26ded92fb2baafea0101b837335e9d434f4cd3d8c6484ef61bbf0741719`

The previously frozen first-five coverage-metric fingerprint was reproduced:

`9b6667407f676af1e6554c1ed81c902a4861acb500184e7605bb9799c10302dd`

## Frozen result artifacts

| Artifact | SHA256 |
| --- | --- |
| `random-coverage-replicates.tsv` | `86104d1ff9a3c619cdfa10e9839bf486b0ee1e77eccc758d93ea3ad9cc42a4a9` |
| `random-coverage-summary.tsv` | `247e7c248803226a378168f1f944b788bd056851bb475367ed08ae119a1657dc` |
| `random-coverage-provenance.tsv` | `450bf925999734f7a69dd4e5fda262f565fd4dc0feb224e34bc139fa674f1021` |

The replicate artifact contains 1000 replicates at each of the six panel
sizes. The summary contains the pre-specified empirical 2.5th percentile,
median, and 97.5th percentile for each coverage metric and panel size.

No genome or species identities are present in these result artifacts.

## Prospective boundary

At the time this random baseline was frozen, no OPS-versus-random or
SR-versus-random comparison had been performed.

The existing blinded OPS-versus-SR comparison remained unresolved because
their primary coverage curves were not uniformly ordered across all six
panel sizes.

The random baseline is therefore an independently frozen validation input,
not a post hoc benchmark selected after inspecting candidate performance.
