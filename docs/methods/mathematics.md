# Mathematics

This page explains the current selector-v1 validation geometry in plain terms.
The [scientific specification](../scientific-specification.md) remains the
formal source of truth.

## Species-balanced percentile coordinates

Suppose species \(s\) has \(n_s\) eligible genomes.

Each genome from that species receives weight:

\[
w_i = \frac{1}{n_s}
\]

Each species therefore contributes total weight 1, regardless of how many
eligible genomes it contains.

If there are \(S\) species, the total weight across the source universe is
\(S\).

For one feature and a genome with value \(x\), BacSelect uses the midpoint
weighted empirical percentile:

\[
p(x) =
\frac{W_{<}(x) + \frac{1}{2}W_{=}(x)}{S}
\]

where:

- \(W_{<}(x)\) is the total species-balanced weight of genomes with smaller
  feature values;
- \(W_{=}(x)\) is the total species-balanced weight of genomes tied at \(x\).

All genomes tied at the same raw value therefore receive the same percentile
coordinate.

If every eligible genome has the same value for a feature, every genome receives
coordinate 0.5 for that feature.

## Why transform features?

The raw features have different units and scales.

Genome length is measured in bases, GC content is a proportion, replicon counts
are integers, and repeat measures have their own numerical ranges.

The percentile transformation places them on a common 0-to-1 scale while
controlling the contribution of species abundance to the empirical
distribution.

## Distance

In the current selector-v1 validation geometry, genomes are compared in the
multidimensional percentile feature space using Euclidean distance.

For genomes \(i\) and \(j\), with coordinates \(p_{if}\) and \(p_{jf}\) for
feature \(f\):

\[
d(i,j) =
\sqrt{
\sum_f
\left(p_{if} - p_{jf}\right)^2
}
\]

The current validation design gives the included features equal weight.

The final feature schema remains subject to the prospective validation
programme, including repeat-scale validation.

## Nearest-panel distance

For an eligible genome \(i\) and selected panel \(P\):

\[
D(i,P) = \min_{j \in P} d(i,j)
\]

This asks a simple question:

> How far is this genome from the most structurally similar genome already in
> the panel?

BacSelect evaluates that quantity across the eligible evaluation universe.

## Summary statistics

The planned primary summaries include:

- species-balanced median nearest-panel distance;
- species-balanced 95th-percentile nearest-panel distance;
- maximum nearest-panel distance across all eligible genomes.

The first two control species abundance during summarisation. The maximum is an
unweighted worst-case value across the complete eligible evaluation universe.

## Selector mathematics are not frozen yet

The feature geometry and the selector are separate parts of the design.

BacSelect has prospectively compared alternative selector strategies using the
same evaluation framework. The final selector-v1 species-representation rule
remains unresolved until the required validation is complete.

This page will be updated when that decision is frozen.
