# Selector-v1 leave-one-feature-out method

## Status

PROSPECTIVE IMPLEMENTATION CLARIFICATION

This record defines the leave-one-feature-out implementation before any
11-feature OPS or SR selector is calculated.

The selector-v1 design prospectively requires OPS and SR to be repeated after
removing each of the 12 architecture dimensions in turn.

For every ablation and validation panel size, the design requires:

- the pre-specified primary coverage metric;
- all pre-specified secondary coverage metrics;
- panel overlap with the corresponding full 12-feature ladder.

Panel identities remain blinded.

## Selection geometry

For one leave-one-feature-out analysis, exactly one of the 12 frozen
species-balanced percentile coordinates is removed.

OPS and SR are then run in the resulting 11-dimensional geometry.

The species-balanced percentile transform is defined independently for each
feature column. Therefore removing a coordinate from the completed
12-dimensional geometry is equivalent to removing that raw feature first and
then transforming the remaining 11 dimensions.

No remaining coordinate is rescaled or otherwise reweighted after ablation.

## Coverage evaluation geometry

All ablated panels are evaluated in the complete frozen 12-dimensional
species-balanced architecture geometry.

The removed feature is therefore unavailable to the selector but remains part
of the coverage objective used to evaluate the resulting panel.

Using one common evaluation geometry keeps coverage values directly comparable
across all 12 ablations and against the frozen base-12 selector results.

Coverage is not evaluated solely in each 11-dimensional selection geometry,
because doing so would change the distance definition between ablations and
would mechanically remove one contribution to Euclidean distance.

The same 55,306-genome evaluation universe, species-balanced evaluation
weights, inverse-ECDF quantile conventions, and ten pre-specified coverage
metrics used for the base-12 OPS/SR comparison are retained.

## Panel overlap

For selector S and panel size N, overlap is the unordered set intersection
between:

1. the first N genomes of the frozen base-12 S ladder; and
2. the first N genomes of the corresponding leave-one-feature-out S ladder.

Report:

- `overlap_count`;
- `overlap_fraction`, written exactly as `overlap_count/N`.

Both panels contain N unique genomes, so these quantities fully describe the
requested same-size panel overlap.

No positional-match score, Jaccard statistic, or additional overlap metric is
introduced.

## Output and blinding

For every removed feature, selector, and N, report:

- removed feature name;
- selector;
- N;
- blinded N=500 ablated-ladder SHA256 fingerprint;
- overlap count;
- exact overlap fraction;
- all ten pre-specified coverage metrics.

No genome accession, species identifier, species name, or other organism
identity is included in the report.

## Interpretation boundary

Leave-one-feature-out analysis is a sensitivity analysis.

It does not introduce a new OPS-versus-SR selector decision rule.

No feature is automatically retained or removed because of one ablation
result.

The complete leave-one-feature-out evidence will be interpreted together with
the separately pre-specified grouped-ablation and repeat-scale analyses before
architecture schema v1 is frozen.

Identity blinding remains in force.
