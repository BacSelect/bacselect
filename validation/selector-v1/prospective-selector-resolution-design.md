# BacSelect selector-v1 prospective selector-resolution design

## Status

**PROSPECTIVE DESIGN — NO NEW HOLDOUT OUTCOMES EXAMINED**

This document defines the new experiment that will resolve the final OPS-versus-SR
selector ambiguity without reinterpreting the completed 55,306-genome validation.

The repository identity immediately before this design was installed is:

`2c4557591dc32dfa986aee5b78407d6d31b8d2a0`

The release-final selector audit bound to this design has SHA256:

`501f287e389bd8ebd9a16b25044da6f435110e27705e6aa5bacea74400aa7a6a`

The completed validation decision is `UNRESOLVED`.

No fresh NCBI holdout snapshot is queried, inspected, or analysed by this design
package.

## Scientific question

Which frozen candidate selector, OPS or SR, produced panels that better cover
eligible bacterial complete genomes that were not present in the frozen
55,306-genome development and validation universe?

This is an external generalization test.

It is not a re-analysis of the completed coverage experiment and it is not an
update-stability experiment.

## Why new data are required

The completed OPS-versus-SR comparison crossed with panel size:

- OPS had lower primary weighted-p95 distance at N=10,20,50,100;
- SR had lower primary weighted-p95 distance at N=200,500.

The prospective decision rule for that experiment therefore produced no winner.

No new metric may now be applied retrospectively to those already observed
results.

The resolution experiment instead uses genomes absent from the frozen
development universe and defines its single overall decision rule before those
new outcomes are generated.

## Frozen baseline

The resolution experiment is bound to the final 300/2400 BacSelect foundation:

- baseline genomes: 55,306;
- baseline species groups: 13,765;
- final raw 12-feature matrix SHA256:
  `86c0c3d49317dfc3cc452114e3863666fe2112b6a3ae8dae2090b60a2a598948`;
- final species-balanced percentile matrix SHA256:
  `f48e20b28ee89988e7abb42488a35c62fbfa4a538c15c8d2d70b6b5ba7ae83c1`;
- species mapping SHA256:
  `f0343238930e957f82bc28997a216ab3a8967d007b3d3471679e3f054c76af6c`;
- final feature-space input manifest SHA256:
  `512d466ff6b8af3e51eb91db715d5fc5c76995892a4c1b18489d922a0414f0f2`.

The final 12-coordinate structural schema is unchanged.

The frozen candidate ladder fingerprints are:

- OPS N=500 ladder:
  `c81d9fd30cda2d49f0f6c81d4bf99dace9fff811c7612036d9265ef90707fa13`;
- SR N=500 ladder:
  `3c703f5f898e0a13c6eb8568c0b83f5b0d19d4e374155d2d3a8a4e20378bd51f`.

The six evaluated prefixes are:

`N = 10, 20, 50, 100, 200, 500`.

The frozen baseline ladders are evaluated as-is. They are not regenerated after
the holdout genomes are obtained.

## Holdout source

After this prospective design is committed and pushed, obtain a fresh public
NCBI Datasets snapshot of bacterial complete assemblies using the same
BacSelect source-eligibility rules intended for the production source universe.

The acquisition step must record, before structural-feature outcomes are
calculated:

- NCBI Datasets version;
- acquisition UTC timestamp;
- exact command/configuration;
- raw metadata/report SHA256 identities;
- eligible fresh-universe manifest SHA256;
- canonical accession policy;
- software/container identity used for eligibility filtering.

GCA is the canonical assembly accession representation.

The complete fresh eligible universe must be frozen before feature calculation.

## Holdout membership

The decision holdout is the complete set of eligible canonical accessions in
the fresh snapshot that are absent from the frozen 55,306-genome baseline.

No random sampling or downsampling is permitted.

No holdout genome may be selected or excluded because of:

- species identity;
- pathogen or clinical relevance;
- publication status;
- structural-feature values;
- OPS/SR distance;
- assembler performance;
- expected effect on the selector decision.

Any exclusion must arise only from the prospectively frozen BacSelect source
eligibility and feature-completeness rules and must be recorded before selector
coverage outcomes are calculated.

## Adequacy gate

The holdout must contain at least:

- 1,000 eligible genomes; and
- 200 resolved species groups.

The 200-species minimum ensures that the upper five per cent of a
species-balanced distribution corresponds to approximately ten or more species
rather than only a handful of groups.

If either minimum is not met:

**NO SELECTOR DECISION IS CALCULATED.**

The experiment waits for the first later fresh snapshot that satisfies both
requirements.

The adequacy gate is evaluated from holdout membership and taxonomy only,
before structural-feature coverage outcomes are generated.

## Identity blinding

Genome and species identities remain blinded throughout outcome generation and
the selector decision.

Scientific outcome artifacts must not contain:

- GCA/GCF accession strings;
- organism names;
- species names;
- species taxids.

Whole-artifact fingerprints, counts, anonymous keys, and aggregate values are
permitted.

Unblinding occurs only after the selector decision is frozen.

## Holdout structural features

For every eligible holdout genome, calculate the same frozen 12 raw structural
features used by the final 300/2400 foundation:

1. total genome length;
2. whole-genome GC fraction;
3. replicon count;
4. non-chromosomal replicon count;
5. non-chromosomal sequence fraction;
6. non-unique canonical 300-mer fraction;
7. non-unique canonical 2400-mer fraction;
8. maximum canonical 300-mer multiplicity;
9. maximum canonical 2400-mer multiplicity;
10. longest exact repeat length;
11. inter-replicon shared canonical 300-mer fraction;
12. inter-replicon shared canonical 2400-mer fraction.

Feature definitions, sequence handling, and repeat-scale semantics are not
changed for this experiment.

## Coordinate transform for unseen genomes

The frozen OPS and SR panels live in the baseline species-balanced percentile
geometry.

Therefore the holdout does **not** cause the baseline percentile geometry to be
recomputed.

Each holdout raw feature value is projected through the frozen baseline
species-balanced empirical distribution for that feature.

For a holdout raw value `x`, its percentile coordinate is:

`weight(baseline values < x) + 0.5 * weight(baseline values = x)`

where each baseline genome has the same species-balanced weight used in the
frozen final geometry.

The common normalization is the total baseline species-balanced weight.

Consequences:

- values below the baseline minimum map to 0;
- values above the baseline maximum map to 1;
- values between observed baseline values map to the cumulative baseline weight
  below `x`;
- values exactly tied to baseline values use the same midpoint tie convention
  as the frozen geometry.

There is no interpolation between observed raw feature values.

This extension is frozen before holdout outcomes are examined.

## Per-genome coverage

For each selector and each panel size N, calculate for every holdout genome the
Euclidean distance in the frozen 12-dimensional percentile geometry to its
nearest member of the corresponding frozen baseline panel prefix.

Lower distance means better structural coverage.

The panel itself is never updated with holdout genomes during this experiment.

## Per-N primary metric

At each N, the primary holdout metric is the same species-balanced weighted
95th percentile nearest-panel distance used in the completed selector
comparison.

Within the holdout:

- each species contributes equal total weight;
- genomes within a species divide that species weight equally;
- lower weighted-p95 distance is better.

The implementation must reuse or exactly reproduce the already frozen
weighted-p95 definition. No new interpolation rule is introduced.

## Single prospective selector-resolution score

The six panel sizes must contribute equally to the final selector decision.

For selector `S`, let `d(S,N)` be its holdout species-balanced weighted-p95
nearest-panel distance at panel size N.

Define the exact six-size product:

`P(S) = product over N in {10,20,50,100,200,500} of d(S,N)`

The comparison is equivalent to comparing the geometric mean of the six
per-N distances, but no root is required.

For the decision calculation, each stored floating-point `d(S,N)` value must
be converted with `Fraction.from_float` and the six values multiplied exactly.
This prevents rounding in the final OPS-versus-SR product comparison.

The decision rule is:

- if `P(OPS) < P(SR)`: **OPS wins**;
- if `P(SR) < P(OPS)`: **SR wins**;
- if the exact products are equal: **UNRESOLVED**.

There is no tolerance, equivalence margin, significance threshold, or secondary
tie-breaker.

This score is used only on the new external holdout.

It must never be applied retrospectively to the already observed 55,306-genome
coverage results.

## Why the six-size product is used

The unresolved validation showed that selector performance can change with N.

The new rule therefore:

- retains all six pre-specified BacSelect panel sizes;
- gives every evaluated panel size one equal multiplicative contribution;
- uses the same primary metric at every N;
- avoids selecting a single favourable N after outcomes are seen;
- avoids introducing secondary coverage metrics;
- yields one deterministic comparison for the independent holdout.

## Descriptive diagnostics

The following may be reported for interpretation but cannot change the
decision:

- per-N OPS and SR weighted-p95 values;
- per-N OPS/SR distance ratios;
- weighted mean and median nearest-panel distance;
- unweighted maximum nearest-panel distance;
- holdout genome count;
- holdout species count;
- counts belonging to species represented or absent in the baseline;
- coordinate out-of-range counts by feature;
- selector-specific nearest-panel distance distributions.

No diagnostic becomes a fallback selector rule.

## No random comparator

No new random-panel comparator is required for the selector-resolution
decision.

Random panels answered a different question in the completed validation:
whether OPS and SR outperform species-balanced random selection.

The new question is only which of the two already validated candidate
selectors generalizes better to unseen eligible genomes.

## Determinism and independent rebuild

The complete holdout resolution analysis must be run twice with:

- the same frozen fresh-universe manifest;
- the same holdout membership;
- the same raw holdout feature matrix;
- the same frozen baseline transform;
- the same frozen OPS/SR ladders;
- the same software environment.

The scientific artifacts from production and independent rebuild must be
byte-identical before the selector decision is frozen.

Run-specific provenance may differ.

## Required scientific artifacts

At minimum freeze:

1. fresh-snapshot provenance;
2. blinded eligible fresh-universe manifest fingerprint;
3. blinded holdout membership fingerprint and adequacy counts;
4. holdout raw-feature matrix fingerprint;
5. holdout projected-coordinate matrix fingerprint;
6. per-N OPS/SR primary metrics;
7. exact six-size product comparison;
8. selector-resolution summary;
9. production provenance;
10. independent-rebuild provenance;
11. byte-identity verification record;
12. selector-decision record.

Large genome-level matrices may remain outside Git if their SHA256 identities
and reconstruction provenance are frozen.

## Outcome interpretation

If OPS wins under the exact frozen rule, OPS becomes the BacSelect selector-v1
algorithm.

If SR wins under the exact frozen rule, SR becomes the BacSelect selector-v1
algorithm.

If the exact products tie, or if the adequacy gate is not met, selector v1
remains unresolved.

No secondary criterion may be invented after the holdout outcomes are known.

## After a winner is frozen

Only after a selector winner is committed and frozen may BacSelect proceed to:

1. unblind the selected ladder for audit;
2. generate and verify the official nested selector-v1 panels;
3. package the first public BacSelect release;
4. enable monthly fail-closed panel publication.

Monthly automation may be developed earlier only in non-publishing/test mode.

## Prospectivity statement

At the time this design is frozen:

- the completed 55,306-genome OPS/SR outcomes are known;
- the new external holdout has not been queried or inspected for this
  resolution experiment;
- no holdout structural features have been generated;
- no holdout OPS/SR distances have been calculated;
- no new selector-resolution outcome has been observed.

The rule above is therefore frozen before the evidence to which it will be
applied is generated.
