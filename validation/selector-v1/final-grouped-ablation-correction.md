# Final 300/2400 grouped-ablation implementation correction

## Status

PROSPECTIVE IMPLEMENTATION CORRECTION BEFORE OUTCOME GENERATION

The first committed final-schema grouped-ablation implementation was:

`82274ee9f8e98f31435f582353375c94a2645661`

Its first `--verify-inputs-only` execution passed the frozen final input
manifest, validation-universe, percentile-matrix, float64-array, species-mapping,
and environment-lock gates, then failed at the full-feature OPS reference-ladder
fingerprint gate.

The failure occurred before `build_report()` and before any grouped
reduced-feature OPS or SR selector was calculated.

## Cause

The grouped-ablation runner reconstructed the correct frozen final 300/2400
full-feature OPS ladder but hashed it under the historical reference namespace:

`BacSelect-selector-v1|OPS|ladder|N=500`

The already frozen final 300/2400 reference fingerprint uses:

`BacSelect-selector-v1|final300-2400|OPS|ladder|N=500`

The same namespace mismatch applied to SR.

The expected fingerprint constants themselves were the correct frozen final
300/2400 values:

- OPS: `c81d9fd30cda2d49f0f6c81d4bf99dace9fff811c7612036d9265ef90707fa13`
- SR: `3c703f5f898e0a13c6eb8568c0b83f5b0d19d4e374155d2d3a8a4e20378bd51f`

## Correction

Only the full-feature reference-ladder fingerprint namespace is corrected to
match the already frozen final LOFO/reference convention:

- `BacSelect-selector-v1|final300-2400|OPS|ladder|N=500`
- `BacSelect-selector-v1|final300-2400|SR|ladder|N=500`

The grouped-ablation selection method, four feature families, 300/2400 feature
schema, panel sizes, OPS and SR implementations, full-12 evaluation geometry,
coverage metrics, overlap definition, blinding, and interpretation boundary are
unchanged.

The grouped-ablation ladder namespace remains separately namespaced as:

`BacSelect-selector-v1|FINAL300-2400|GROUPED|remove=<group>|<selector>|ladder|N=500`

No grouped reduced-feature selector had been calculated when this correction
was made.

## Required next gate

After this correction is committed and pushed, `--verify-inputs-only` must be
rerun under the corrected committed identity.

It must reproduce both frozen final reference-ladder fingerprints and all
2 selectors x 6 panel sizes x 10 frozen reference coverage metrics exactly
before any grouped reduced-feature selector is calculated.

Identity blinding remains in force. No selector decision rule is introduced.
