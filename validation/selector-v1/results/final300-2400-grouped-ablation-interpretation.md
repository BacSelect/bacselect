# Final 300/2400 grouped feature-ablation interpretation

## Status

**NO FEATURE FAMILY REMOVED**

The canonical identity-blind final-schema grouped feature-ablation evidence was
frozen and independently reproduced before interpretation.

Canonical artifact:

`final300-2400-grouped-ablation.tsv`

SHA256:

`e65eac3c3b37273ec2d486932f3f946aca4d6b6595e48c2d8236f9e9254e701e`

Genome and species identities remain blinded.

## Primary metric

The pre-specified primary coverage metric is the species-balanced weighted
95th percentile nearest-panel distance. Lower values indicate better
structural coverage.

Grouped removal worsens this primary metric for:

- basic genome properties in 10 of 12 selector-by-N comparisons;
- replicon architecture in 11 of 12 comparisons;
- repeat architecture in all 12 comparisons;
- inter-replicon sharing in 9 of 12 comparisons.

No feature family therefore shows a primary-coverage pattern that supports
removal.

### Repeat architecture

Repeat architecture gives the clearest family-level result.

Removing the five repeat coordinates worsens weighted-p95 for both OPS and SR
at every pre-specified panel size.

At N=500:

- OPS increases from `0.43309233197078495` to
  `0.60822374382837108`;
- SR increases from `0.43074575053129432` to
  `0.63638740937506932`.

The same ablation also worsens every one of the ten pre-specified coverage
metrics for OPS at N=20, 50, 100, 200, and 500, and for SR at N=200 and 500.

This strongly rejects the interpretation that the repeat-architecture family
is redundant within the final structural geometry.

### Replicon architecture

Removing the three replicon-architecture coordinates worsens weighted-p95 in
11 of 12 comparisons. The only exception is OPS at N=10, where weighted-p95
decreases slightly from `1.0701206478524528` to `1.0602821231803961`.

At N=500, weighted-p95 increases to:

- OPS: `0.50741114238400431`;
- SR: `0.48665619995992837`.

The family-level result therefore shows information that can be partly
compensated in individual-feature LOFO analyses but is not recoverable when
the complete replicon-architecture family is removed.

### Basic genome properties

Removing genome length and whole-genome GC fraction worsens weighted-p95 in
10 of 12 comparisons. The two exceptions are both at N=10.

At N=500, weighted-p95 increases to:

- OPS: `0.4974637173633491`;
- SR: `0.51893839229637695`.

Several panel sizes also show worsening across all ten pre-specified coverage
metrics. The grouped evidence does not support removing basic genome
properties.

### Inter-replicon sharing

Inter-replicon sharing has the smallest and most mixed family-level primary
effect, but removal still worsens weighted-p95 in 9 of 12 comparisons.

The three primary improvements occur at OPS N=10 and SR N=10 and N=100. At
N=500, weighted-p95 nevertheless increases from:

- OPS: `0.43309233197078495` to `0.44819568159837275`;
- SR: `0.43074575053129432` to `0.45491120072303165`.

Secondary metrics are mixed, and no prospective equivalence margin was defined.
The grouped analysis therefore provides no basis for declaring this family
dispensable.

## Panel composition

Grouped removal substantially redirects the deterministic selection trajectory.

At N=500, overlap with the corresponding full-feature ladder is:

| Removed family | OPS | SR |
|---|---:|---:|
| Basic genome properties | 106/500 (21.2%) | 123/500 (24.6%) |
| Replicon architecture | 95/500 (19.0%) | 115/500 (23.0%) |
| Repeat architecture | 76/500 (15.2%) | 89/500 (17.8%) |
| Inter-replicon sharing | 121/500 (24.2%) | 124/500 (24.8%) |

Across all eight grouped ablations, median N=500 overlap is 22.1%.

Across the eight grouped ablations, median overlap by panel size is:

| N | Median overlap |
|---:|---:|
| 10 | 10.0% |
| 20 | 7.5% |
| 50 | 9.0% |
| 100 | 10.0% |
| 200 | 14.5% |
| 500 | 22.1% |

The minimum observed overlap is 0/10 for OPS after removal of repeat
architecture. The maximum is 5/10 for SR after removal of inter-replicon
sharing.

Because the production and independent rebuild reports are byte-identical,
these changes are not stochastic instability. They are deterministic
sensitivity to the structural feature family available during selection.

Panel overlap remains descriptive sensitivity evidence and is not a coverage
metric or selector decision rule.

## Joint interpretation with LOFO

The final LOFO analysis found no individual coordinate that could be removed
without worsening the primary metric somewhere across the selector-by-N grid.

Grouped ablation strengthens that conclusion.

In particular, the strong degradation after removal of the complete repeat
family shows that mixed or locally favourable single-feature LOFO effects can
reflect compensation among related repeat coordinates rather than absence of
information.

The same pattern is present, though less strongly, for replicon architecture
and basic genome properties.

Inter-replicon sharing remains the least damaging family to remove, but its
primary and secondary effects are still mixed and its removal substantially
changes panel composition. Without a prospectively defined equivalence
criterion, that is not evidence for removal.

Accordingly, **no feature family and no individual structural coordinate is
removed on the basis of the final LOFO and grouped-ablation sensitivity
analyses**.

The 12-coordinate final 300/2400 structural feature schema therefore remains
intact.

## Selector decision boundary

Grouped feature ablation is a feature-sensitivity analysis. It does not
introduce a new OPS-versus-SR decision criterion.

The previously frozen final 300/2400 coverage-stage OPS-versus-SR decision
remains:

**UNRESOLVED**

Grouped ablation does not select OPS, does not select SR, and does not alter
the pre-specified condition for rejecting the one-per-species hypothesis.

No aggregate score, significance threshold, equivalence margin, or other
post-hoc selector criterion is introduced.

Genome and species identities remain blinded.

## Remaining validation

The feature-sensitivity stage is complete with the final LOFO and grouped
feature-family ablation evidence interpreted without feature removal.

Separately pre-specified selector validation requirements, including broader
deterministic rebuild validation and update-stability validation, remain
outstanding before a release-final selector decision.
