# Final 300/2400 grouped feature-ablation evidence freeze

This record freezes the canonical identity-blind final-schema grouped
feature-ablation report before any grouped-ablation coverage effect or panel
overlap result is inspected or interpreted.

## Prospective boundary

The final-schema grouped-ablation method was committed before any grouped
reduced-feature OPS or SR selector was calculated.

An initial verification-only run under commit
`82274ee9f8e98f31435f582353375c94a2645661` failed closed at the frozen
full-feature OPS ladder fingerprint gate because the runner used the historical
reference fingerprint namespace rather than the frozen final 300/2400
namespace. The failure occurred before `build_report()` and before any grouped
reduced-feature selector was calculated.

That namespace-only implementation defect was documented and corrected before
outcome generation.

The corrected generating commit is:

`113dcffd3961183800c2496def6bf675e1d7e9c6`

The grouped-ablation scientific method was not changed by the correction.

## Frozen method

The four pre-specified feature families are:

- basic genome properties: features 01-02;
- replicon architecture: features 03-05;
- repeat architecture: features 06-10 using the selected 300/2400 scales;
- inter-replicon sharing: features 11-12 using the selected 300/2400 scales.

For each family:

- remove the complete family simultaneously from selection;
- run OPS and SR in the resulting reduced-dimensional geometry;
- do not rescale, retransfrom, or reweight the remaining coordinates;
- evaluate every resulting panel in the complete frozen final 12-dimensional
  300/2400 geometry;
- evaluate N = 10, 20, 50, 100, 200, and 500;
- report unordered overlap with the corresponding frozen full-feature final
  selector ladder;
- retain all ten pre-specified coverage metrics;
- retain identity blinding;
- introduce no OPS-versus-SR selector decision rule.

## Implementation provenance

Grouped-ablation runner SHA256:

`2f63b9519525bfc1d5e194b6b1f6db840738eabd529de0cd6be57ec9b57ea9df`

Grouped-ablation Slurm wrapper SHA256:

`12fad6d49ad635c6ff46b41f18b9cdd8ec3ddfa83f6efeee14f669cb8a0e308a`

Grouped-ablation method SHA256:

`2caa8982c20ca03b70c1fffa0fa0e63d25bac450a96f7e0acc0c8b64e2e80da4`

Prospective namespace-correction record SHA256:

`265091244a088e43bdad462a6675dbf059b163b5576531602240cd034ccdf95e`

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

Frozen full-feature N=500 ladder fingerprints:

- OPS: `c81d9fd30cda2d49f0f6c81d4bf99dace9fff811c7612036d9265ef90707fa13`
- SR: `3c703f5f898e0a13c6eb8568c0b83f5b0d19d4e374155d2d3a8a4e20378bd51f`

Before outcome generation, verification-only mode under the corrected committed
identity reproduced both frozen reference ladder fingerprints and all
2 selectors x 6 panel sizes x 10 frozen reference coverage metrics exactly.

## Canonical report

Artifact:

`final300-2400-grouped-ablation.tsv`

SHA256:

`e65eac3c3b37273ec2d486932f3f946aca4d6b6595e48c2d8236f9e9254e701e`

Dimensions:

- 4 pre-specified removed feature families;
- 2 candidate selectors;
- 6 pre-specified panel sizes;
- 48 identity-blind result rows plus one header row.

Coverage is evaluated in the frozen complete final 300/2400 12-dimensional
geometry.

## Production execution

Production Slurm job:

`2504385`

Production provenance artifact:

`final300-2400-grouped-ablation-provenance.tsv`

Production provenance SHA256:

`00d5d423e2fd9df1d123be8a435e5cadc2826b971ee38d6b2f47ea68043b32be`

The production execution:

- reproduced the frozen full-feature final reference ladders;
- reproduced all frozen full-feature OPS/SR coverage metrics exactly;
- produced all eight blinded N=500 grouped-ablation ladder fingerprints;
- produced all 48 required group/selector/N combinations;
- produced a 49-line identity-blind report;
- emitted zero bytes to stderr;
- reached `PASS | final grouped feature-ablation job completed`.

## Independent deterministic rebuild

A second execution was performed from the same corrected frozen generating
commit in a separate output directory.

Rebuild Slurm job:

`2504386`

Rebuild provenance artifact:

`final300-2400-grouped-ablation-rebuild-provenance.tsv`

Rebuild provenance SHA256:

`a6d8139b713a40d125cf419bfd7615bd2d540df001829412dc24d7f4a15a4c38`

The rebuilt report reproduced SHA256:

`e65eac3c3b37273ec2d486932f3f946aca4d6b6595e48c2d8236f9e9254e701e`

The production and rebuild reports were byte-identical under `cmp`.

The rebuild emitted zero bytes to stderr and reached
`PASS | final grouped feature-ablation job completed`.

The production and rebuild provenance artifacts intentionally differ because
they contain run-specific metadata such as Slurm job identifiers.

## Interpretation boundary

No final-schema grouped-ablation coverage effect or panel-overlap value had
been inspected or interpreted when this canonical report was frozen.

Grouped feature-family ablation remains a pre-specified feature-sensitivity
analysis. This freeze record does not select between OPS and SR, does not
introduce a new selector decision criterion, and does not itself remove any
feature family or individual structural coordinate.

The previously frozen coverage-stage OPS-versus-SR decision remains
**UNRESOLVED**.

Genome and species identities remain blinded.
