# Final selector-v1 update-stability evidence freeze

## Status

**PASS — prospective update-stability analysis and independent rebuild complete**

This record freezes the outcome of the prospectively defined final
update-stability validation for the 300/2400 selector-v1 geometry.

The update-stability method and implementation were frozen before any
outcome-producing run. The generating repository identity was:

`5f0f78f8f99c410ed32078e707ee342e84a7455e`

The underlying prospective method itself was introduced at
`d5fae16bf33dd3245e8faae2bffcc44ebde72130` and was unchanged by the
intervening deterministic-rebuild evidence commit.

## Frozen implementation

- method SHA256:
  `b19048e091d71e0241b7f153dcb6edc5e5e1205f54bbc33a3a82868a0207266a`;
- update-stability runner SHA256:
  `0fce32551dac0e74d2f3a150c45424502e86a1177f12497ffaceeac34fbecf76`;
- Slurm wrapper SHA256:
  `89d217e81618ea12dc1872c5270f2d155f21c3a6b1cf2aa1722054a4bf1b2d33`;
- environment lock SHA256:
  `f6f4a19c44a759705682ba4199207eaef5c2435e1b6feeddc1e4654686bc2a8c`.

## Prospective scenarios

The seven pre-specified deterministic perturbations were:

1. `add_general_500`
2. `remove_500`
3. `replace_500`
4. `add_heavy_species_500`
5. `add_new_species_100`
6. `taxonomy_split_500`
7. `taxonomy_merge_100_singletons`

No PRNG was used.

The frozen scenario fingerprints were:

| Scenario | Fingerprint |
| --- | --- |
| add_general_500 | `8abd0be337af05b6b160a57eb1f7f5679a74ea83af2147c40643d385cb4a8e03` |
| remove_500 | `ccd45f95b84ce161c0477d4c87fbedd5570c04d7e8da2721b3c46dae2af5b8b7` |
| replace_500 | `da49e84831a1fce5a397b690072850a2e63d0f33e75536df9ed884bb023f2ad4` |
| add_heavy_species_500 | `d29123eb4c2c61904972e220b7b2f1ca64c8a2f6e8905c1396ed97de4116ea64` |
| add_new_species_100 | `85df808edf8d1864d0c3c88f7e17b4f05300ac3a75cc3fe6ec8d107c45a0c4ea` |
| taxonomy_split_500 | `331af2a6046ae8abdf89d0f0da0579e98c8799022cc1d071adc54aa71e8d7542` |
| taxonomy_merge_100_singletons | `1dc487b6b3ea6020c619d00f5ce07f3c37619f7a525faaf22a64736d75756ee6` |

## Production execution

Production Slurm job:

`2504390`

All seven scenarios completed successfully.

Scientific artifact SHA256 values:

| Artifact | SHA256 |
| --- | --- |
| scenario table | `a6b7cf5bddbc7b4a1bb58f9a7c4993e1a4db3c7307c217cd960814c7c2d2ae47` |
| prefix-stability table | `cacb5fc513a2bb752c9e4d6df8b48013bfdcd9f940898bae580bb58d28cad23b` |
| first-divergence table | `bf8550b2796f56b3e5a5e81c2f8244c0d6330c50b2097a4973f3effd1a600573` |
| summary JSON | `d75368eeb90b80aa97a81d9ace83e7e854bee967b47bebaaf7fb57d95820f327` |

Artifact dimensions:

- scenario table: 8 lines including header;
- prefix-stability table: 85 lines including header;
- first-divergence table: 15 lines including header.

Production provenance SHA256:

`6b095e8038bfd5c0b3e104a78cdb2b29323541dd410ba1bd2d63647330618bbb`

Production stderr contained zero bytes.

## Independent rebuild

Independent rebuild Slurm job:

`2504391`

All seven scenarios completed successfully again.

The production and rebuild copies of all four scientific artifacts were
compared directly with `cmp`.

All four were byte-identical:

- scenario table;
- prefix-stability table;
- first-divergence table;
- summary JSON.

The independent rebuild produced the same four scientific SHA256 identities
listed above.

Rebuild provenance SHA256:

`3a921d5181e0a77f9f3ad8b55d8e782e48d4d7d7e9b79d71de3e197a668a5c78`

The rebuild provenance differs from production because it contains
run-specific metadata. This is expected.

Rebuild stderr contained zero bytes.

## Observed stability evidence

This section records the blinded numerical results only. Interpretation is
kept separate.

At N=500, unordered prefix overlap with the frozen baseline panel was:

| Scenario | OPS overlap | SR overlap |
| --- | ---: | ---: |
| add_general_500 | 173/500 | 499/500 |
| remove_500 | 177/500 | 381/500 |
| replace_500 | 493/500 | 494/500 |
| add_heavy_species_500 | 139/500 | 500/500 |
| add_new_species_100 | 166/500 | 163/500 |
| taxonomy_split_500 | 157/500 | 500/500 |
| taxonomy_merge_100_singletons | 237/500 | 145/500 |

The complete six-N results for both selectors are frozen in the committed
prefix-stability table.

The complete blinded first-divergence score traces are frozen in the committed
first-divergence table.

## Identity blinding

No GCA/GCF accession strings were present in the scientific outputs.

Genome and species identities remain blinded.

## Interpretation boundary

The update-stability method prospectively defined no pass/fail overlap
threshold, no aggregate stability score, no significance threshold, and no
equivalence margin.

This evidence therefore does not by itself select OPS or SR.

The previously frozen OPS-versus-SR selector decision remains:

**UNRESOLVED**

No new selector criterion is introduced by this evidence freeze.

A separate interpretation checkpoint may describe the observed stability
patterns, but it must not create a post-hoc selector decision rule.
