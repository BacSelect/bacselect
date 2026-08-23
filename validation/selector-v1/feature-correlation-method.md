# Selector-v1 feature-correlation method

## Status

PROSPECTIVE IMPLEMENTATION CLARIFICATION

This record defines the feature-correlation implementation before the
correlation coefficients for the frozen BacSelect foundation are calculated
or inspected.

The selector-v1 design prospectively requires pairwise Spearman correlations
among all 12 candidate architecture dimensions and a complete correlation
matrix.

## Evaluation rows

The analysis uses all 55,306 eligible genomes in the frozen Finch foundation.

Each genome contributes one row with equal weight.

No species weighting or species-level aggregation is applied to this
diagnostic.

## Feature values

Correlations are calculated from the 12 raw structural-feature columns in:

`corrected-eligible-structural-feature-matrix.tsv`

Frozen source SHA256:

`fd264bedda627d737a647de601c8b835f53baeca246724e9aafb73fd50c9d656`

The exact feature names and ordering are taken from the frozen matrix header.

## Correlation definition

For every pair of feature columns, calculate the ordinary Spearman rank
correlation coefficient across the 55,306 genome rows.

The implementation uses:

`scipy.stats.spearmanr(..., axis=0, nan_policy="raise")`

Standard Spearman tied-rank handling is therefore retained.

Only the correlation coefficients are reported. P-values are not used for
feature selection or selector evaluation.

The calculation is performed on the raw structural dimensions rather than
introducing a new species-weighted correlation statistic.

## Validation

The complete 12 by 12 matrix must:

- contain only finite values;
- be symmetric;
- have a unit diagonal;
- reproduce identically within the frozen software environment.

No genome accession, species identifier, species name, or other organism
identity is included in the report.

## Interpretation boundary

Correlation is a diagnostic for redundancy and sensitivity analysis.

No dimension is removed solely because it is correlated with another.

Any sensitivity to individual or grouped dimensions is evaluated separately
by the pre-specified leave-one-feature-out and grouped-ablation analyses.
