# Final selector-v1 geometry revalidation plan

The prospectively selected repeat scales `(300,2400)` changed six of the
twelve structural dimensions. Geometry-dependent evidence from the historical
150/400 schema is therefore not transferred to the final selector-v1 schema.

## Historical evidence

Existing files with the `base12-` prefix and the existing 150/400 validation
scripts remain historical evidence. They are not overwritten by this
revalidation.

## Final foundation

Every new geometry-dependent analysis must consume
`validation/selector-v1/final-feature-space-inputs.tsv` and therefore bind
itself to:

- 55,306 genomes;
- 13,765 species groups;
- the final 300/2400 raw matrix SHA256
  `86c0c3d49317dfc3cc452114e3863666fe2112b6a3ae8dae2090b60a2a598948`;
- the final species-balanced percentile matrix SHA256
  `f48e20b28ee89988e7abb42488a35c62fbfa4a538c15c8d2d70b6b5ba7ae83c1`;
- the unchanged species mapping SHA256
  `f0343238930e957f82bc28997a216ab3a8967d007b3d3471679e3f054c76af6c`.

## Revalidation order

1. Derive and freeze final geometry baselines:
   - exact final-foundation reconstruction;
   - feature-correlation matrix;
   - OPS representatives and OPS N=500 ladder;
   - SR N=500 ladder;
   - AG N=500 diagnostic ladder;
   - species-abundance diagnostics at N=10,20,50,100,200,500;
   - unchanged species-balanced random ladder-set identity;
   - input-order invariance.

2. Freeze those baseline identities before computing coverage outcomes.

3. Recalculate and freeze:
   - OPS-versus-SR coverage metrics;
   - random-baseline coverage distributions;
   - OPS/SR versus random empirical ranks;
   - the prospectively defined OPS-versus-SR decision rule.

4. Recalculate and freeze:
   - leave-one-feature-out analysis;
   - grouped feature-family ablation.

5. Complete deterministic rebuild and update-stability validation before the
   selector-v1 decision is treated as final for release.

The random ladder set is the sole historical identity expected to remain
unchanged at step 1 because random membership depends only on the unchanged
genome universe, species mapping, frozen seed, and random-sampling protocol.
No historical OPS, SR, AG, correlation, coverage, LOFO, or grouped-ablation
result is assumed to carry over.

No genome or species identities are included in the interpretation outputs.
