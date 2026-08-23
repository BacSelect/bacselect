# Base-12 leave-one-feature-out interpretation

This record interprets the frozen identity-blind selector-v1
leave-one-feature-out (LOFO) analysis.

Canonical LOFO artifact:

`base12-lofo.tsv`

SHA256:

`9419b28ec1b1ab1b953b88fe14425943b9d8c7f19372c3ac5436f19aabc7cd24`

The interpretation below was made only after the canonical report had been
frozen, independently rebuilt byte-for-byte, committed, and pushed.

Genome and species identities remain blinded.

## Primary metric

The pre-specified primary coverage metric is the species-balanced weighted
95th percentile of nearest-panel distance.

LOFO effects vary with panel size and selector. At small panel sizes, removal
of individual dimensions can either increase or decrease weighted-p95,
consistent with changes to the deterministic selection trajectory in a sparse
panel.

At N = 500, a clearer common pattern is present. Removing:

- total genome length;
- whole-genome GC fraction; or
- longest exact repeat length

increases weighted-p95 for both OPS and SR.

Removing maximum canonical 150-mer multiplicity also increases weighted-p95
for both selectors at N = 500.

Several replicon and inter-replicon-sharing dimensions have little effect on
weighted-p95 at N = 500 when removed individually. This does not establish
that those dimensions are dispensable, because LOFO allows information in
the remaining 11 dimensions to compensate and because weighted-p95 is only
one pre-specified view of coverage.

## Secondary coverage metrics

The secondary metrics show that apparent neutrality under weighted-p95 does
not imply neutrality across the full validation framework.

At N = 500, removal of every one of the 12 structural dimensions increases
`max_species_mean` for both OPS and SR.

The magnitude varies substantially by feature and selector. In particular,
dimensions with very small weighted-p95 effects can still have appreciable
effects on the mean nearest-panel distance of the worst-covered species.

This indicates that individual structural dimensions can contribute to
species-level extreme coverage even when broad distributional summaries are
largely preserved by the remaining feature space.

`unweighted_max` and `max_species_max` are numerically identical by
construction and are retained as two pre-specified reporting views rather
than treated as independent evidence.

These individual-genome extreme metrics do not always move in the same
direction as `max_species_mean`. An ablation can therefore improve the
distance of the single worst-covered genome while worsening the average
coverage of the worst-covered species.

## Panel composition

Feature removal substantially changes panel composition.

At N = 500, overlap between an ablated panel and the corresponding full
12-feature panel ranges from 132 to 174 of 500 genomes for OPS and from
129 to 185 of 500 genomes for SR.

Thus, panels with similar aggregate coverage can contain substantially
different genomes.

This is feature-schema sensitivity, not stochastic instability: OPS and SR
are deterministic for a fixed input universe, feature schema, selector
version, and panel size.

## Interpretation

The LOFO analysis does not identify a single structural dimension that can
currently be removed from architecture schema v1 without qualification.

Some dimensions appear individually substitutable for broad coverage
summaries, particularly at larger panel sizes, but the secondary metrics and
panel-overlap results show that such removals can still alter species-level
extreme coverage and panel composition substantially.

Conversely, negative LOFO deltas at some panel sizes are not interpreted as
evidence that the removed dimension is harmful. Removing a dimension changes
the deterministic selection trajectory, and an ablated trajectory can
occasionally produce a lower value for an individual coverage summary when
evaluated in the full 12-dimensional geometry.

Accordingly, no feature is removed on the basis of LOFO alone.

Grouped feature-family ablation remains necessary to test whether related
dimensions collectively carry information that is obscured by single-feature
redundancy. Repeat-scale validation remains a separate prospective analysis
before the structural-feature schema is frozen.

## Selector decision boundary

LOFO is a feature-sensitivity analysis and does not introduce a selector
decision criterion.

The previously frozen OPS-versus-SR decision therefore remains:

`UNRESOLVED`

Genome and species identities remain blinded.
