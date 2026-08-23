# Base-12 feature-correlation freeze

This record freezes the first canonical selector-v1 feature-correlation
matrix before individual correlation coefficients are inspected or
interpreted.

## Method

The pre-specified selector-v1 validation design requires pairwise Spearman
correlations among all 12 candidate structural dimensions and reporting of
the complete correlation matrix.

The implementation convention was frozen before production output:

- all 55,306 eligible genomes contribute one row with equal weight;
- the 12 raw structural-feature columns are used;
- no species weighting or species-level aggregation is applied;
- each of the 66 unique feature pairs is evaluated once with
  `scipy.stats.spearmanr`;
- the same coefficient is written to both symmetric matrix positions;
- the diagonal is exactly one;
- no p-value threshold or correlation threshold is used for feature removal.

No genome or species identities are included in the output.

## Implementation provenance

Canonical correlation implementation commit:

`f9351c4f4ab20fdd0ccfb38bcbdb2626baadfe4c`

Environment:

- Python 3.11.16
- NumPy 2.4.6
- SciPy 1.17.1

Frozen environment-lock SHA256:

`f6f4a19c44a759705682ba4199207eaef5c2435e1b6feeddc1e4654686bc2a8c`

Frozen raw structural-feature matrix SHA256:

`fd264bedda627d737a647de601c8b835f53baeca246724e9aafb73fd50c9d656`

## Canonical matrix

Artifact:

`base12-feature-correlation.tsv`

SHA256:

`d2a97e705939b5775c251dab1979fe52b65e63cf77953f5fe179e7a7177d2927`

Dimensions:

- 12 feature rows;
- 12 feature columns;
- 66 unique off-diagonal feature pairs.

The written matrix was validated as:

- finite;
- exactly symmetric;
- exactly unit diagonal;
- identical feature ordering on rows and columns;
- deterministic under repeated calculation.

## Earlier failed execution

The initially frozen implementation calculated a multivariate Spearman matrix
in memory but stopped before writing an artifact because it required exact
binary symmetry.

The maximum mirrored floating-point difference was
`1.1102230246251565e-16`.

No matrix artifact was written by that attempt and no individual correlation
coefficients were displayed or inspected.

The implementation was then corrected prospectively to evaluate each unique
feature pair once and construct an exactly symmetric canonical matrix.

## Interpretation boundary

No individual correlation coefficient had been inspected when this canonical
matrix was frozen.

Correlation remains a diagnostic for redundancy and sensitivity analysis.

No structural dimension is removed solely because it is correlated with
another. Feature sensitivity is evaluated separately by the pre-specified
leave-one-feature-out and grouped-ablation analyses.

Genome and species identities remain blinded.
