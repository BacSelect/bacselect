# Final 300/2400 leave-one-feature-out interpretation

## Status

**NO FEATURE REMOVED**

The canonical identity-blind final-schema leave-one-feature-out (LOFO)
evidence was frozen and independently reproduced before interpretation.

Canonical artifact:

`final300-2400-lofo.tsv`

SHA256:

`91d231c823a0b4f812a1163fe5e440d9bf4a69d13d146f85e11b10c5ef4ee030`

Genome and species identities remain blinded.

## Primary metric

The pre-specified primary coverage metric is the species-balanced weighted
95th percentile nearest-panel distance. Lower values indicate better
structural coverage.

No single feature can be removed without worsening this primary metric
somewhere across the pre-specified selector and panel-size grid.

In particular:

- removing `06_non_unique_canonical_300mer_fraction` increases weighted-p95
  for OPS at all six N values;
- removing `09_maximum_canonical_2400mer_multiplicity` increases weighted-p95
  for OPS at all six N values;
- removing `02_whole_genome_gc_fraction` increases weighted-p95 at five of six
  N values for both OPS and SR;
- removing `08_maximum_canonical_300mer_multiplicity` increases weighted-p95
  at five of six N values for OPS and four of six for SR;
- removing `12_inter_replicon_shared_canonical_2400mer_fraction` increases
  weighted-p95 at four of six N values for OPS and five of six for SR.

Other coordinates show more mixed primary effects. Local improvements after an
ablation are not interpreted as evidence that the removed coordinate is
dispensable.

For example, removing `03_replicon_count` at N=500 lowers weighted-p95 from
0.43309233197078495 to 0.42795474197287808 for OPS and from
0.43074575053129432 to 0.42835039462867142 for SR. However, the same ablation
raises `max_species_mean` from 0.48015738364190547 to
0.59870075224508568 for OPS and from 0.48112164810669067 to
0.59270583561181089 for SR. For SR it also raises `max_species_max` from
0.65697253253486343 to 0.72078043223430988.

The primary and secondary effects therefore cannot be reduced to a simple
"improved after removal" interpretation.

## Secondary coverage metrics

The ten pre-specified coverage metrics remain mixed across features, selectors,
and panel sizes.

Some ablations improve central-distance summaries while worsening tail or
extreme-distance summaries. Others show the opposite pattern. This is expected
when removing one coordinate changes the selected ladder but evaluation remains
in the complete frozen 12-dimensional geometry.

The final LOFO evidence therefore does not identify a coordinate whose removal
produces a uniformly preferable coverage profile.

No new aggregate score, metric weighting, equivalence margin, or post-hoc
threshold is introduced to rank the ablations.

## Panel composition

Single-feature removal changes panel membership substantially.

Across the 24 ablated N=500 ladders, overlap with the corresponding
full-feature ladder ranges from 106/500 to 158/500, or 21.2% to 31.6%, with a
median overlap of 26.9%.

Across all 24 ablations, the median overlap fraction is:

| N | Median overlap |
|---:|---:|
| 10 | 20.0% |
| 20 | 15.0% |
| 50 | 12.0% |
| 100 | 15.5% |
| 200 | 19.0% |
| 500 | 26.9% |

Low overlap is not interpreted as stochastic instability. Both selectors are
deterministic, and the production and independent rebuild reports are
byte-identical.

Instead, the overlap results show feature-schema sensitivity: removing a
single architecture coordinate can redirect the deterministic selection
trajectory even when aggregate coverage remains similar.

Panel overlap is descriptive sensitivity evidence and is not a coverage metric
or selector decision rule.

## Interpretation

The final 300/2400 LOFO analysis does not justify removing any of the 12 frozen
architecture coordinates.

Several dimensions show clear loss of coverage under particular selectors and
panel sizes when removed. Other dimensions show smaller or mixed primary
effects, but their secondary metrics and panel composition still change
substantially.

Conversely, negative LOFO deltas at individual N values do not establish that a
coordinate is unnecessary. The ablated selector can compensate through the
remaining correlated or related dimensions, and such compensation can improve
one coverage summary while degrading another.

Accordingly, **no feature is removed on the basis of LOFO**.

Grouped feature-family ablation remains necessary to test whether apparently
compensated single-feature effects reflect redundancy within related feature
families.

## Selector decision boundary

LOFO is a feature-sensitivity analysis. It does not introduce a new
OPS-versus-SR decision criterion.

The previously frozen final 300/2400 coverage-stage OPS-versus-SR decision
therefore remains:

**UNRESOLVED**

LOFO does not select OPS, does not select SR, and does not alter the
pre-specified condition for rejecting the one-per-species hypothesis.

Genome and species identities remain blinded.

## Next validation step

The next pre-specified analysis is final-schema grouped feature-family
ablation, using the same frozen 300/2400 geometry and the already defined four
feature families.

The grouped-ablation evidence must be generated prospectively, frozen, and
independently reproduced before interpretation.
