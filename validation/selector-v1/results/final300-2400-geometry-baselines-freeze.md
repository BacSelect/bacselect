# Final selector-v1 300/2400 geometry baseline freeze

This record freezes the first geometry-dependent baseline analysis performed
after the final selector-v1 300/2400 feature space was frozen.

## Analysis identity

- analysis commit: `6efbce9fdcd5e40914fd6adcbed1ab8123cbbeee`
- genomes: 55,306
- species groups: 13,765
- structural dimensions: 12
- panel sizes: 10, 20, 50, 100, 200, 500
- final repeat scales: 300 bp and 2400 bp

The analysis recalculated and verified the frozen species-balanced percentile
matrix before deriving any selector-specific result.

## Frozen final-foundation identities

- final feature-space input manifest:
  `512d466ff6b8af3e51eb91db715d5fc5c76995892a4c1b18489d922a0414f0f2`
- raw matrix file:
  `86c0c3d49317dfc3cc452114e3863666fe2112b6a3ae8dae2090b60a2a598948`
- raw float64 C-order array:
  `2a0dbd5809fa4d5d77ab6e2d5255ddec9bb933a94be6c270260ec81758d8cbd6`
- percentile matrix file:
  `f48e20b28ee89988e7abb42488a35c62fbfa4a538c15c8d2d70b6b5ba7ae83c1`
- percentile float64 C-order array:
  `9a4a120562ff1151fd8c83e831eb81362b2372844f7dd7407746554af49cda67`
- species mapping:
  `f0343238930e957f82bc28997a216ab3a8967d007b3d3471679e3f054c76af6c`

## Frozen baseline identities

OPS:

- 13,765 species representatives
- representative fingerprint:
  `0d10a37be3af5e8f487226103ff75c5f87905ddd7aef412d0956848307f9151e`
- N=500 ladder fingerprint:
  `ab5d75b2d35b9577bcf84acceb8e10d847e983e04a8e4aa5859fd0bde1ae2834`

SR:

- N=500 ladder fingerprint:
  `080cbaf23d9259610d59fc1ef5a3164329e0bbbe9016b21590c0b34ad2da1b97`

AG:

- N=500 ladder fingerprint:
  `a1df33566be62cdff70d6d0722815eef65193d8d4bca698a613beb38e3c8ccd7`

Species-balanced random baseline:

- 1,000 ladders of maximum length 500
- master seed: 20260824
- ladder-set fingerprint:
  `9394a26ded92fb2baafea0101b837335e9d434f4cd3d8c6484ef61bbf0741719`
- this matches the historical random-membership identity, as expected because
  the genome universe, species mapping, random protocol, and seed are unchanged.

## Species-abundance diagnostic

OPS and SR each represent exactly one species per selected genome at every
evaluated panel size through N=500.

AG begins repeating species by N=50. At N=500 it represents 409 distinct
species, with a maximum of nine selected genomes from one species.

These are descriptive diagnostics only. They do not determine the selector
choice.

## Feature correlation

The final 12 x 12 Spearman correlation matrix is finite, exactly symmetric,
and has an exact unit diagonal.

The complete matrix is frozen as an output artifact rather than reduced to a
thresholded interpretation before subsequent selector validation.

## Determinism

The analysis passed input-order invariance for:

- OPS;
- SR;
- AG;
- the full 1,000-member random ladder set.

## Output identities

- feature-correlation matrix:
  `56a666965adc51dee18a41118eeb6300ad3c7c3db1f93f2ee439154af26bf26f`
- species-abundance diagnostic:
  `c6669de3fa32986d2c4fc847edc264f351747ac8bb95ba4dc058d5ed0205396c`
- baseline summary:
  `e5181e9c0dcd729553c3f357034a4c58b7e620334adeef8db9fdb89b83fdeb06`
- baseline output hash manifest:
  `3f49e13a843b95f12c03b8922670a8632abbc4875b36517d3f86cd76be9c4cfe`

The summary contains measured runtimes. Those timing values are run metadata,
not deterministic scientific identities. The frozen ladder fingerprints,
diagnostics, correlation matrix, input identities, and output file hashes are
the evidence used for subsequent validation.

## Decision status

OPS-versus-SR coverage was not evaluated in this baseline analysis. No
selector-v1 decision is made by this freeze.

The next geometry-dependent stage may use the frozen OPS and SR ladder
fingerprints above as prospective expected identities while calculating the
final-schema coverage comparison and random-baseline coverage distributions.
