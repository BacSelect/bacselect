# Base-12 feature-correlation interpretation

## Status

DESCRIPTIVE VALIDATION RESULT

Genome and species identities remain blinded.

This interpretation uses only the frozen selector-v1 feature-correlation
matrix:

`base12-feature-correlation.tsv`

SHA256:

`d2a97e705939b5775c251dab1979fe52b65e63cf77953f5fe179e7a7177d2927`

No correlation threshold, feature-removal rule, or new selector criterion is
introduced.

## Overall pattern

Several of the 12 structural dimensions show substantial rank
association.

The strongest Spearman correlations occur primarily between related
measurements of the same or closely related aspects of genome architecture.

The largest correlation is between non-unique canonical 150-mer fraction and
non-unique canonical 400-mer fraction:

`rho = 0.98060461260835463`

The inter-replicon shared canonical 150-mer and 400-mer fractions are also
strongly correlated:

`rho = 0.978686`

Replicon architecture forms another strongly correlated group. Replicon count
and non-chromosomal replicon count have:

`rho = 0.975430`

Non-chromosomal replicon count and non-chromosomal sequence fraction have:

`rho = 0.954310`

Replicon count and non-chromosomal sequence fraction have:

`rho = 0.930444`

Maximum canonical 150-mer and 400-mer multiplicity are also strongly
correlated:

`rho = 0.883248`

## Cross-group relationships

Replicon-count and non-chromosomal-sequence features also show substantial
positive correlations with inter-replicon shared-sequence fractions.

For example:

- replicon count versus inter-replicon shared 150-mer fraction:
  `rho = 0.821003`;
- replicon count versus inter-replicon shared 400-mer fraction:
  `rho = 0.791955`;
- non-chromosomal sequence fraction versus inter-replicon shared 150-mer
  fraction: `rho = 0.786196`;
- non-chromosomal sequence fraction versus inter-replicon shared 400-mer
  fraction: `rho = 0.758432`.

Repeat-fraction and repeat-multiplicity dimensions show moderate positive
relationships with one another rather than near-perfect correspondence.

Total genome length and whole-genome GC fraction have a positive correlation
of:

`rho = 0.624769`

## Negative correlations

Strong negative correlations are absent from the frozen matrix.

The most negative coefficient is between whole-genome GC fraction and
non-unique canonical 400-mer fraction:

`rho = -0.22495329563867203`

Whole-genome GC fraction otherwise shows weak relationships with many of the
structural architecture dimensions.

## Interpretation boundary

The matrix identifies substantial overlap in rank information among several
related feature dimensions, particularly:

- the 150-mer and 400-mer non-unique fractions;
- the 150-mer and 400-mer inter-replicon shared fractions;
- the replicon-count and non-chromosomal replicon measures;
- the 150-mer and 400-mer maximum multiplicity measures.

Correlation alone does not establish that any of these dimensions is
dispensable.

A correlated pair can still differ in its contribution to distances,
extremes, selected-panel membership, or sensitivity to other dimensions.

No dimension is therefore removed on the basis of this diagnostic.

The consequences of individual and grouped feature removal will be evaluated
using the prospectively specified leave-one-feature-out and grouped-ablation
analyses.

The OPS-versus-SR selector decision remains **UNRESOLVED**.

Identity blinding remains in force.
