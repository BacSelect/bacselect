# Final 300/2400 leave-one-feature-out evidence freeze

This record freezes the canonical identity-blind final-schema leave-one-feature-out
(LOFO) report before any LOFO coverage effect or panel-overlap result is inspected
or interpreted.

## Prospective boundary

The final-schema LOFO method and implementation were committed and pushed before
any 11-feature OPS or SR selector was calculated.

Generating commit:

`955119f517d9bb1eab897974ae4d7ba625fe6766`

The prospective convention retained the already frozen LOFO method and bound it
to the final 300/2400 architecture geometry:

- remove one of the 12 frozen final coordinates at a time;
- run OPS and SR in the resulting 11-dimensional selection geometry;
- do not rescale or reweight the remaining coordinates;
- evaluate every ablated panel in the complete frozen final 12-dimensional
  300/2400 coverage geometry;
- evaluate N = 10, 20, 50, 100, 200, and 500;
- report overlap with the corresponding full-feature final selector ladder;
- retain all ten pre-specified coverage metrics;
- retain identity blinding;
- introduce no new OPS-versus-SR selector decision rule.

Verification-only mode passed under the committed implementation before the
first 11-feature selector was calculated. It rebuilt the full-feature OPS and SR
reference ladders and reproduced the already frozen final OPS/SR coverage
evidence exactly.

## Implementation provenance

LOFO runner SHA256:

`6256d4dcf94d10b742cd31a24d77cdf134004440de7ed0b987162d402d254df6`

LOFO Slurm wrapper SHA256:

`7ae1b92e5e1fcfc2d5811bf8dc6f550a12ab2c8901aafe9d909b0d0f0097e9df`

Environment lock SHA256:

`f6f4a19c44a759705682ba4199207eaef5c2435e1b6feeddc1e4654686bc2a8c`

Final feature-space input manifest SHA256:

`512d466ff6b8af3e51eb91db715d5fc5c76995892a4c1b18489d922a0414f0f2`

Frozen final percentile matrix SHA256:

`f48e20b28ee89988e7abb42488a35c62fbfa4a538c15c8d2d70b6b5ba7ae83c1`

Frozen species mapping SHA256:

`f0343238930e957f82bc28997a216ab3a8967d007b3d3471679e3f054c76af6c`

Frozen full-feature reference coverage metrics SHA256:

`9cd2cc838cb74a044e356a1a418633ef2bdc89c4e9f71f924e4c1c0a79073388`

Frozen full-feature reference coverage summary SHA256:

`4908739ac15bd2e842acb83bba6588ad7c2dc29be78a6a57b500709b33e16cf6`

Rebuilt blinded full-feature N=500 ladder fingerprints:

- OPS: `c81d9fd30cda2d49f0f6c81d4bf99dace9fff811c7612036d9265ef90707fa13`
- SR: `3c703f5f898e0a13c6eb8568c0b83f5b0d19d4e374155d2d3a8a4e20378bd51f`

## Canonical report

Artifact:

`final300-2400-lofo.tsv`

SHA256:

`91d231c823a0b4f812a1163fe5e440d9bf4a69d13d146f85e11b10c5ef4ee030`

Dimensions:

- 12 removed final structural features;
- 2 candidate selectors;
- 6 pre-specified panel sizes;
- 144 identity-blind result rows plus one header row.

Each result row records:

- removed structural feature;
- selector;
- panel size;
- blinded N=500 ablation-ladder fingerprint;
- overlap count with the corresponding full-feature final ladder;
- exact overlap fraction;
- all ten pre-specified coverage metrics.

Coverage is evaluated in the frozen complete final 300/2400 12-dimensional
geometry.

## Production execution

Production Slurm job:

`2504378`

Production provenance artifact:

`final300-2400-lofo-provenance.tsv`

Production provenance SHA256:

`e185a4e961a6572b1c6a8955c1c8d72e1610238061b06d2fd40d098b0cb44222`

The production execution:

- verified the immutable 55,306-genome, 13,765-species final validation
  universe;
- verified the frozen final percentile geometry, species mapping, environment
  lock, input manifest, and reference coverage evidence;
- rebuilt the full-feature OPS and SR reference ladders;
- reproduced all frozen full-feature OPS/SR coverage metrics exactly;
- produced all 24 blinded N=500 LOFO ladder fingerprints;
- produced all 144 required selector/feature/N combinations;
- produced a 145-line identity-blind report;
- emitted zero bytes to stderr;
- reached `PASS | final LOFO validation job completed`.

## Independent deterministic rebuild

A second execution was performed from the same frozen generating commit in a
separate output directory.

Rebuild Slurm job:

`2504379`

Rebuild provenance artifact:

`final300-2400-lofo-rebuild-provenance.tsv`

Rebuild provenance SHA256:

`814ea90bd1cf1aea34e96158fa2a6e4a62da7e3d1cd85628e92a41b9416ddaf3`

The rebuilt report reproduced SHA256:

`91d231c823a0b4f812a1163fe5e440d9bf4a69d13d146f85e11b10c5ef4ee030`

The production and rebuild reports were byte-identical under `cmp`.

The rebuild emitted zero bytes to stderr and reached
`PASS | final LOFO validation job completed`.

The production and rebuild provenance artifacts intentionally differ because
they contain run-specific metadata such as Slurm job identifiers.

## Interpretation boundary

No final-schema LOFO coverage effect or panel-overlap value had been inspected
or interpreted when this canonical report was frozen.

LOFO remains a pre-specified feature-sensitivity analysis. This freeze record
does not select between OPS and SR, does not introduce a new selector decision
criterion, and does not itself remove any structural feature.

Grouped feature-family ablation remains a separate pre-specified final-schema
analysis.

Genome and species identities remain blinded.
