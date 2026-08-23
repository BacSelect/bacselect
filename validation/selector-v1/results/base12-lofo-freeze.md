# Base-12 leave-one-feature-out freeze

This record freezes the first canonical identity-blind selector-v1
leave-one-feature-out (LOFO) report before any reported coverage metric or
panel-overlap value is inspected or interpreted.

## Prospective boundary

The LOFO method and implementation were committed and pushed before any
11-feature OPS or SR selector was calculated.

Method and implementation commit:

`fcc2baf29dd29ca01437e845e06eb9bd392b77ab`

Production Slurm wrapper commit:

`c06aaf4db740b7162d355922d5125d381adc5856`

The prospective LOFO convention is:

- remove one of the 12 frozen structural dimensions at a time;
- perform selection in the resulting 11-dimensional geometry;
- derive that geometry by removing the corresponding coordinate from the
  frozen species-balanced percentile representation;
- evaluate every ablated panel against the common frozen 12-dimensional
  coverage geometry;
- evaluate OPS and SR separately at N = 10, 20, 50, 100, 200, and 500;
- quantify overlap with the corresponding full 12-feature ladder as unordered
  set intersection;
- report overlap as both count and the exact `count/N` fraction;
- retain the pre-specified ten coverage metrics;
- introduce no new selector decision rule.

Genome and species identities remain blinded.

## Implementation provenance

Generating commit:

`c06aaf4db740b7162d355922d5125d381adc5856`

LOFO runner SHA256:

`0a4a801821ca0a188d202992d902d8cea0881a28edc8a124b1db3ea61fb6459b`

LOFO Slurm wrapper SHA256:

`efbba36dcf820bc3dec98624e1e210d6ddcbae758a7bc35993c5466c81e6c39e`

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

`base12-lofo.tsv`

SHA256:

`9419b28ec1b1ab1b953b88fe14425943b9d8c7f19372c3ac5436f19aabc7cd24`

Dimensions:

- 12 removed structural features;
- 2 candidate selectors;
- 6 pre-specified panel sizes;
- 144 identity-blind result rows plus one header row.

Each result row records:

- removed structural feature;
- selector;
- panel size;
- blinded N=500 ablation-ladder fingerprint;
- overlap count with the corresponding full 12-feature ladder;
- exact overlap fraction;
- the ten pre-specified coverage metrics.

Coverage is evaluated in the frozen full 12-dimensional geometry.

## Production execution

Production Slurm job:

`2492483`

Production provenance artifact:

`base12-lofo-provenance.tsv`

Production provenance SHA256:

`8156c7b01655b172e5a158ecad9c71a923bc97afe76dec151d026712150097f1`

The production execution:

- verified the immutable 55,306-genome, 13,765-species, 12-feature universe;
- verified the frozen environment lock;
- reconstructed and verified the frozen OPS and SR reference ladders;
- produced all 24 blinded N=500 LOFO ladder fingerprints;
- produced all 144 required selector/feature/N combinations;
- produced a 145-line report;
- emitted zero bytes to stderr;
- reached `PASS | LOFO validation job completed`.

## Independent deterministic rebuild

A second execution was performed from the same frozen generating commit in a
separate output directory.

Rebuild Slurm job:

`2492484`

Rebuild provenance artifact:

`base12-lofo-rebuild-provenance.tsv`

Rebuild provenance SHA256:

`af83b6600ab76f4a5680dc69008ae52e4a96f3ab191978170887100aeb8e18c4`

The rebuilt report reproduced SHA256:

`9419b28ec1b1ab1b953b88fe14425943b9d8c7f19372c3ac5436f19aabc7cd24`

The production and rebuild reports were byte-identical under `cmp`.

The rebuild also emitted zero bytes to stderr and reached
`PASS | LOFO validation job completed`.

The production and rebuild provenance files intentionally differ because they
contain run-specific execution metadata such as Slurm job identifiers.

Slurm accounting through `sacct` was unavailable during the post-run check
because the cluster accounting database connection failed. Completion evidence
therefore comes from the fail-closed job wrapper, expected output structure,
artifact hashes, empty stderr, and the independent byte-identical rebuild.

## Interpretation boundary

No LOFO coverage metric or panel-overlap value had been inspected when this
canonical report was frozen.

LOFO is a pre-specified feature-sensitivity analysis. This freeze record does
not select between OPS and SR, does not introduce a new selector decision
criterion, and does not itself remove any structural dimension.

Grouped feature-family ablation and repeat-scale validation remain separate
prospective analyses.

Genome and species identities remain blinded.
