# Stage 7 final-ladder fingerprint namespace correction

## Status

**PROSPECTIVE IMPLEMENTATION CORRECTION BEFORE HOLDOUT ANALYSIS**

The first frozen BacSelect selector-v1 Stage 7 production execution attempted
under Git commit:

`e85afe64f7f3c2fb92175641c0c0dcf4180f7f65`

failed closed while verifying the frozen final OPS ladder fingerprint.

The failure occurred after:

- the Stage 7 predecision provenance checkpoint had been written;
- the frozen baseline feature space had been verified;
- the baseline OPS and SR ladders had been reconstructed.

The failure occurred before:

- the real Stage 6 holdout feature matrix was opened;
- any holdout percentile coordinate was calculated;
- any holdout-to-panel distance was calculated;
- any Stage 7 primary metric was calculated;
- either exact six-panel-size selector product was calculated;
- any selector outcome was generated.

The failed scratch `.partial` execution directory is retained as evidence and
must not be deleted, reused, or reinterpreted as a successful execution.

## Frozen predecision state

The preserved failed-run `stage7-predecision-provenance.json` records:

- `holdout_raw_feature_matrix_opened = false`;
- `holdout_percentile_coordinates_calculated = false`;
- `ops_sr_distances_calculated = false`;
- `primary_metrics_calculated = false`;
- `exact_selector_products_calculated = false`;
- `selector_outcome_generated = false`.

Therefore no external holdout result had been generated when this correction
was defined.

## Observed failure

The frozen Stage 7 execution adapter reconstructed the expected baseline OPS
and SR ladders, but fingerprinted them using the historical selector-v1 ladder
namespace:

`BacSelect-selector-v1|{selector}|ladder|N=500`

Under that namespace, the reconstructed ladders produced:

- OPS:
  `ab5d75b2d35b9577bcf84acceb8e10d847e983e04a8e4aa5859fd0bde1ae2834`;
- SR:
  `080cbaf23d9259610d59fc1ef5a3164329e0bbbe9016b21590c0b34ad2da1b97`.

These are the already known historical pre-final fingerprints.

Stage 7 correctly expected the frozen final 300/2400 fingerprints:

- OPS:
  `c81d9fd30cda2d49f0f6c81d4bf99dace9fff811c7612036d9265ef90707fa13`;
- SR:
  `3c703f5f898e0a13c6eb8568c0b83f5b0d19d4e374155d2d3a8a4e20378bd51f`.

## Diagnostic confirmation

The frozen baseline contained:

- 55,306 genomes;
- 13,765 species groups;
- 12 structural coordinates.

Both the stored and independently recomputed species-balanced percentile
coordinate matrices reproduced the frozen binary64 C-order array SHA256:

`9a4a120562ff1151fd8c83e831eb81362b2372844f7dd7407746554af49cda67`

The stored and recomputed baseline coordinate matrices were bitwise identical.

The accession order and species order were also identical between those two
baseline loading modes.

Using the same reconstructed OPS and SR ladders, changing only the fingerprint
namespace from the historical namespace to the frozen final 300/2400 namespace:

`BacSelect-selector-v1|final300-2400|{selector}|ladder|N=500`

reproduced exactly:

- OPS:
  `c81d9fd30cda2d49f0f6c81d4bf99dace9fff811c7612036d9265ef90707fa13`;
- SR:
  `3c703f5f898e0a13c6eb8568c0b83f5b0d19d4e374155d2d3a8a4e20378bd51f`.

Therefore the selector ladder content itself is unchanged.

The discrepancy is fully explained by the fingerprint namespace alone.

## Authoritative final namespace

The frozen final deterministic-rebuild implementation:

`validation/selector-v1/run_final_determinism.py`

SHA256:

`2963b9478f95cd153bcacbd1ddc1ecff432829ed033c5d9991842fc741be87be`

defines the final reference-ladder namespace as:

`BacSelect-selector-v1|final300-2400|{selector}|ladder|N=500`

The final deterministic rebuild prospectively reproduced the frozen OPS and SR
ladder fingerprints under that namespace in both production and independent
rebuild executions.

The frozen ladder-fingerprint manifest is:

`validation/selector-v1/results/final300-2400-determinism-ladders.tsv`

SHA256:

`c0f17aaa2c92c27f0b4f3aebd9ffd1be73cc403c80700b93a1b2d5786fb6b0da`

## Prior equivalent correction

The final grouped-ablation validation previously encountered the same class of
implementation defect: the correct final ladder was fingerprinted under the
historical namespace rather than the frozen `final300-2400` namespace.

That earlier defect was corrected prospectively before grouped reduced-feature
outcome generation, without changing the selector algorithm, geometry,
features, or scientific interpretation.

The Stage 7 correction follows the same boundary.

## Correction

Only the Stage 7 final reference-ladder fingerprint namespace may change.

The Stage 7 execution adapter must change its OPS/SR final-ladder fingerprint
namespace from:

`BacSelect-selector-v1|{selector}|ladder|N=500`

to:

`BacSelect-selector-v1|final300-2400|{selector}|ladder|N=500`

No selector algorithm may change.

No structural feature may change.

No baseline geometry may change.

No baseline accession ordering may change.

No species assignment or ordering may change.

No holdout membership may change.

No panel size may change.

No Stage 7 distance, quantile, diagnostic, product, or decision rule may
change.

No tolerance, secondary criterion, or alternative selector criterion may be
introduced.

## Frozen implementation affected

The namespace correction is required in:

`src/bacselect/selector_resolution_execution.py`

The pre-correction frozen adapter SHA256 is:

`e9c685bc82950479589447c73733c54e175e327a1ae2975e8604fbf90a56ddae`

Because the frozen production wrapper binds the execution-adapter SHA256, the
wrapper's dependency identity must subsequently be updated to the corrected,
prospectively frozen adapter identity.

The pre-correction production wrapper is:

`validation/selector-v1/run_selector_resolution_execution.py`

SHA256:

`5cddf06d072d210f2b72088908dd2a71600dc9f3b095a1d3152ad6599fa22c43`

The wrapper's scientific dispatch logic must not otherwise change as part of
this correction.

## Required validation before another production attempt

Before Stage 7 production may be rerun:

1. this correction record must be committed and pushed;
2. the execution adapter must be corrected only at the final ladder namespace
   boundary;
3. synthetic tests must demonstrate that the corrected namespace is exactly
   `BacSelect-selector-v1|final300-2400|{selector}|ladder|N=500`;
4. synthetic and regression tests must demonstrate no change to ladder
   construction, Stage 6 verification, blinding, atomic finalization, or
   selector-decision exclusion;
5. the corrected execution adapter and its tests must be committed and pushed;
6. the production wrapper must be updated only as required to bind the new
   frozen execution-adapter identity;
7. the corrected wrapper and its tests must be committed and pushed;
8. a new production authorization preflight must pass;
9. the original failed `.partial` execution must remain preserved;
10. the rerun must use a new, unused execution namespace rather than deleting,
    overwriting, or reusing the failed production attempt.

The independent rebuild remains unauthorized until a successful corrected
production execution has been finalized.

## Interpretation boundary

This correction does not provide any evidence favoring OPS or SR.

It does not inspect the external holdout.

It does not alter the prospective Stage 7 scoring rule.

It does not alter the exact-product decision rule.

It does not generate or authorize a selector outcome.

The Stage 7 selector-resolution state remains blinded and unresolved.
