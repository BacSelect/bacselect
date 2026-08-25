# Final selector-v1 deterministic rebuild evidence freeze

## Status

**PASS — broader selector-level deterministic rebuild requirement complete**

This record freezes the outcome of the prospectively defined final
deterministic-rebuild validation for the 300/2400 selector-v1 geometry.

The generating code and method were frozen before either outcome-producing run
at Git commit:

`d5fae16bf33dd3245e8faae2bffcc44ebde72130`

No update-stability outcome had been calculated when this deterministic
evidence was frozen.

## Frozen foundation

The rebuild consumed the already frozen final selector-v1 foundation:

- genomes: 55,306;
- species groups: 13,765;
- structural coordinates: 12;
- repeat scales: 300 bp and 2400 bp;
- final raw feature matrix SHA256:
  `86c0c3d49317dfc3cc452114e3863666fe2112b6a3ae8dae2090b60a2a598948`;
- final raw float64 C-order array SHA256:
  `2a0dbd5809fa4d5d77ab6e2d5255ddec9bb933a94be6c270260ec81758d8cbd6`;
- final species-balanced percentile float64 C-order array SHA256:
  `9a4a120562ff1151fd8c83e831eb81362b2372844f7dd7407746554af49cda67`;
- species mapping SHA256:
  `f0343238930e957f82bc28997a216ab3a8967d007b3d3471679e3f054c76af6c`;
- final feature-space input manifest SHA256:
  `512d466ff6b8af3e51eb91db715d5fc5c76995892a4c1b18489d922a0414f0f2`;
- frozen OPS/SR reference coverage SHA256:
  `9cd2cc838cb74a044e356a1a418633ef2bdc89c4e9f71f924e4c1c0a79073388`.

Environment:

- Python 3.11.16;
- NumPy 2.4.6;
- environment lock SHA256:
  `f6f4a19c44a759705682ba4199207eaef5c2435e1b6feeddc1e4654686bc2a8c`.

## Frozen implementation

- method SHA256:
  `b19048e091d71e0241b7f153dcb6edc5e5e1205f54bbc33a3a82868a0207266a`;
- deterministic-rebuild runner SHA256:
  `2963b9478f95cd153bcacbd1ddc1ecff432829ed033c5d9991842fc741be87be`;
- Slurm wrapper SHA256:
  `dd865823928d71e5219027d324d630a55c2708dde34265fb2a631ee44efba5a2`.

## Production execution

Slurm job:

`2504388`

The production run passed all frozen reference gates:

- recomputed species-balanced percentile array exactly reproduced
  `9a4a120562ff1151fd8c83e831eb81362b2372844f7dd7407746554af49cda67`;
- OPS N=500 ladder exactly reproduced
  `c81d9fd30cda2d49f0f6c81d4bf99dace9fff811c7612036d9265ef90707fa13`;
- SR N=500 ladder exactly reproduced
  `3c703f5f898e0a13c6eb8568c0b83f5b0d19d4e374155d2d3a8a4e20378bd51f`;
- all frozen OPS/SR coverage values reproduced exactly:
  2 selectors × 6 panel sizes × 10 metrics;
- stderr contained zero bytes.

The unrestricted AG diagnostic N=500 ladder fingerprint produced by the
rebuild was:

`289a81b6d91f89be7b5476c628273e2cc6ca4995968f2dae0b3d6499972d28ec`

## Independent rebuild

Slurm job:

`2504389`

The independent rebuild passed the same frozen reference gates and produced the
same four scientific artifact identities.

Production and rebuild were then compared directly with `cmp`.

All four scientific artifacts were byte-identical:

| Scientific artifact | SHA256 |
| --- | --- |
| canonical recomputed percentile matrix | `4676b33ffd7f16084a2c37751cc5ede35ba9966b1860e339cd007e96fbb0684a` |
| blinded selector-ladder fingerprints | `c0f17aaa2c92c27f0b4f3aebd9ffd1be73cc403c80700b93a1b2d5786fb6b0da` |
| deterministic coverage table | `a276043636b64dd6d508aa48a414a9da63a474719f47018cb8d890d65dc3771a` |
| deterministic validation report | `e247e8872254d89e28cde10d913c5fb0ed7a11fa033ecf552fd34bb7f9d4348a` |

Artifact dimensions were:

- canonical percentile matrix: 55,307 lines including header;
- ladder fingerprint table: 4 lines including header;
- coverage table: 19 lines including header.

The 13.3 MB canonical percentile matrix is not copied into the Git repository.
Its SHA256 above is the frozen scientific identity, and both independent
scratch copies were compared byte-for-byte before this evidence record was
created.

## Provenance

Production provenance SHA256:

`28177a4841f0fd6ac5595ea89692dc4dc62309f1ed70b1d6caf91565d850ec05`

Independent rebuild provenance SHA256:

`d2a4eb1b8e260351448bef373be7a2cb3ebbe769ba86a2d98047f76195c5431f`

The provenance artifacts differ because they contain run-specific metadata,
including Slurm job identity. This difference is expected and is outside the
scientific byte-identity requirement.

Both provenance records bind the same generating Git commit, runner, wrapper,
method, environment lock, and four scientific output hashes.

## Identity blinding

The committed scientific outputs contain no GCA/GCF accession strings.

No individually mappable per-genome accession hash is written.

Genome and species identities remain blinded.

## Interpretation

The prospectively defined broader deterministic-rebuild requirement is
**satisfied**.

Independent repeated executions from the same frozen inputs, committed
software, and environment produced byte-identical:

- recalculated canonical species-balanced percentile matrix;
- selector ladder-fingerprint table;
- coverage table;
- validation report.

This evidence establishes deterministic reconstruction of the final
selector-v1 scientific computation under the tested software/environment
identity.

It does not assess behaviour under a changed source universe.

Update-stability validation remains a separate prospective analysis and had
not been calculated when this evidence was frozen.

This deterministic result does not select OPS, does not select SR, and does not
alter the frozen coverage-stage status:

**UNRESOLVED**

No new selector criterion, aggregate score, significance threshold,
equivalence margin, or stability threshold is introduced.
