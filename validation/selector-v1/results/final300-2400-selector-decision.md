# Final 300/2400 OPS versus SR selector-decision checkpoint

## Status

**UNRESOLVED**

Identity blinding remains in force.

No BacSelect selector is chosen at this checkpoint.

This record applies the prospectively defined OPS-versus-SR decision framework
to the frozen final 300/2400 coverage evidence. It does not introduce a new
metric, score, threshold, weighting, or post-hoc decision criterion.

## Primary comparison

The pre-specified primary metric is the species-balanced weighted 95th
percentile nearest-panel Euclidean distance. Lower values indicate better
structural coverage.

| N | Lower primary metric |
|---:|:---|
| 10 | OPS |
| 20 | OPS |
| 50 | OPS |
| 100 | OPS |
| 200 | SR |
| 500 | SR |

The primary curves are therefore not uniformly ordered.

Under the prospective decision rule, this does not produce an automatic
selector winner.

## Pre-specified secondary metrics

The secondary evidence is also mixed across panel sizes.

At N=10 and N=20, every pre-specified secondary coverage metric is lower for
OPS.

At N=50, OPS has lower weighted mean, weighted median, weighted p95, and most
species-level summaries. SR has lower unweighted maximum and maximum species
maximum distance.

At N=100, OPS has lower weighted mean, weighted median, weighted p95, and
several species-level summaries. SR has lower unweighted maximum, maximum
species mean, and maximum species maximum distance.

At N=200, SR has lower weighted mean, weighted median, weighted p95, and most
species-level summaries. OPS has lower unweighted maximum and maximum species
maximum distance.

At N=500, SR has lower values for every pre-specified secondary metric except
maximum species mean, for which OPS is slightly lower.

The direction of the secondary evidence therefore changes with panel size
rather than showing a consistent structural-coverage advantage for one
candidate across the full validation range.

## Random-baseline comparison

The empirical-rank comparison is descriptive validation evidence and is not an
additional selector decision rule.

For the primary weighted-p95 metric, the frozen empirical ranks are:

| N | OPS rank | SR rank |
|---:|---:|---:|
| 10 | 505 | 546 |
| 20 | 167 | 397 |
| 50 | 82 | 101 |
| 100 | 2 | 96 |
| 200 | 1 | 1 |
| 500 | 1 | 1 |

At a given N, OPS and SR are compared against the same random distribution.
These ranks therefore reflect the already observed primary ordering at that N
and do not supply an independent OPS-versus-SR decision criterion.

The random comparison does not resolve the crossing primary curves.

## One-per-species hypothesis

The pre-specified rejection condition for the OPS one-genome-per-species
constraint is not met.

SR does not consistently outperform OPS across the six primary comparisons.
OPS is lower at N=10, 20, 50, and 100, while SR is lower at N=200 and 500.

This means the one-per-species hypothesis is **not rejected** by the final
coverage comparison. It does not, by itself, select OPS.

## Simplicity preference

The design permits the simpler selector to be preferred if structural
performance is effectively indistinguishable without an unambiguous winner.

No prospective equivalence margin or quantitative threshold for "effectively
indistinguishable" was defined. Invoking a numerical equivalence threshold now
would therefore introduce a post-hoc criterion.

The simplicity preference is not used to force a selector choice at this
checkpoint.

## Decision

The final 300/2400 coverage-stage OPS-versus-SR decision remains
**UNRESOLVED**.

OPS has the structural-coverage advantage across the primary metric at
N=10-100, while SR has the advantage at N=200-500. The secondary metrics also
change direction across panel sizes. The random-baseline ranks do not create a
new selector criterion, and the pre-specified condition for rejecting the
one-per-species OPS constraint is not met.

No new aggregate score, significance threshold, equivalence margin, or
post-hoc decision rule is introduced.

Genome and species identities remain blinded.

## Remaining validation

This is a coverage-stage decision checkpoint, not the final selector-v1 release
decision.

The remaining pre-specified validation sequence is:

1. recalculate and freeze leave-one-feature-out analysis;
2. recalculate and freeze grouped feature-family ablation;
3. complete deterministic rebuild validation;
4. complete update-stability validation;
5. only then treat the selector-v1 decision as final for release.

Those analyses assess robustness and release readiness under the already frozen
selector framework. They must not be used to invent a new OPS-versus-SR
decision criterion after the coverage result.
