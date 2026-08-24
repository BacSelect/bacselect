# Selector v1 repeat-scale validation

## Status

Prospective.

This experiment is defined before any alternative repeat-scale feature is
calculated for the BacSelect foundation universe.

Genome and species identities remain blinded during analysis.

## Purpose

The current base-12 structural-feature schema contains repeat features at
150 bp and 400 bp.

Those scales were inherited from Project Finch, where they represented the
frozen PE150 read length and approximate 400-bp fragment span.

They are not automatically accepted as general bacterial genome-architecture
scales for BacSelect.

The purpose of this experiment is to determine, prospectively and
identity-blind, which two sequence scales best summarize repeat architecture
across the frozen BacSelect foundation universe.

Scale choice is made independently of OPS or SR panel performance.

## Frozen source universe

The experiment uses exactly the existing corrected BacSelect foundation:

- 55,306 corrected eligible genomes;
- 13,765 species-rank groups;
- the frozen canonical GenBank assembly-accession set;
- the frozen species mapping;
- the frozen audited source sequences inherited from Project Finch.

No genome is added, removed, replaced or reclassified for this experiment.

Each of the 55,306 corrected eligible genomes has been reconciled to exactly
one frozen Project Finch source location containing:

- the audit-selected genomic FASTA;
- the frozen sequence report;
- a passing candidate sequence audit.

The Project Finch source snapshot is input provenance. It is not itself a
BacSelect release.

## Repeat-feature semantics

Alternative scales use the already validated Project Finch repeat-feature
semantics.

For a nucleotide sequence and k-mer length k, the canonical representation is
the lexicographically smaller of the forward sequence and its reverse
complement.

Occurrences are defined by distinct source-coordinate starts.

Multiplicity is calculated across all retained Primary Assembly replicons
belonging to one source-genome unit.

For circular replicons:

- origin-spanning k-mers are included;
- exactly one start is represented per underlying source coordinate;
- artificial duplication across the FASTA origin is not introduced.

For linear replicons, only k-mers fully contained within the recorded
sequence are included.

For each k, three scale-dependent quantities are calculated:

1. non-unique canonical k-mer fraction;
2. maximum canonical k-mer multiplicity;
3. inter-replicon shared canonical k-mer fraction.

The non-unique fraction is the fraction of valid source-coordinate starts
whose canonical k-mer has multiplicity greater than one anywhere in the
source-genome unit.

Maximum multiplicity is the greatest number of distinct source-coordinate
starts represented by any canonical k-mer.

The inter-replicon shared fraction is the fraction of valid source-coordinate
starts whose canonical k-mer occurs on at least one different retained
replicon in the same source-genome unit.

Single-replicon genomes have inter-replicon shared fraction zero.

## Reference-scale concordance gate

The new multi-k production calculation must include k=150 and k=400 as
internal positive controls.

Before any alternative-scale value is inspected or used for scale selection,
the recalculated 150-bp and 400-bp raw features must reproduce the
corresponding frozen base-12 values for all 55,306 corrected eligible genomes.

The following must agree genome by genome:

- non-unique canonical 150-mer fraction;
- non-unique canonical 400-mer fraction;
- maximum canonical 150-mer multiplicity;
- maximum canonical 400-mer multiplicity;
- inter-replicon shared canonical 150-mer fraction;
- inter-replicon shared canonical 400-mer fraction.

Integer multiplicities must agree exactly.

Fraction values must reproduce the same binary64 values obtained from the
frozen canonical matrix under the recorded deterministic serialization and
parsing conventions.

The accession set and order must also match the frozen corrected foundation
exactly.

Failure of any reference-scale concordance check stops the experiment before
alternative-scale analysis.

The production provenance must record at least:

- exact repeat-engine source SHA-256;
- compiled repeat-engine binary SHA-256;
- generating BacSelect Git commit;
- software/environment lock;
- frozen Project Finch source-snapshot provenance;
- frozen corrected foundation hashes;
- complete recalculated multi-k output SHA-256.

This concordance gate verifies that recalculation from frozen source sequences
has preserved the already validated repeat-feature semantics before the new
scales are considered.

## Features that do not change

The following base-12 dimensions remain frozen and are not recalculated for
scale selection:

1. total genome length;
2. whole-genome GC fraction;
3. replicon count;
4. non-chromosomal replicon count;
5. non-chromosomal sequence fraction;
6. longest exact repeat length.

Longest exact repeat is scale-independent and remains the already frozen
value.

Only the six coordinates currently represented by the 150-bp and 400-bp
versions of the three k-dependent repeat measures are candidates for
replacement.

## Prospective k grid

The following sequence scales are fixed before calculation:

- 50 bp;
- 75 bp;
- 100 bp;
- 150 bp;
- 200 bp;
- 300 bp;
- 400 bp;
- 600 bp;
- 800 bp;
- 1200 bp;
- 1600 bp;
- 2400 bp;
- 3200 bp.

The grid spans a 64-fold sequence-length range.

It contains a doubling backbone:

- 50;
- 100;
- 200;
- 400;
- 800;
- 1600;
- 3200 bp;

with intermediate values:

- 75;
- 150;
- 300;
- 600;
- 1200;
- 2400 bp.

This provides regular multi-scale sampling while retaining both inherited
reference values, 150 bp and 400 bp.

The lower and upper grid limits are analysis bounds, not proposed biological
thresholds. Exact-repeat structure beyond 3200 bp remains represented
separately by the frozen longest-exact-repeat feature.

No additional k value may be introduced after the alternative-scale values
have been inspected as part of selector-v1 scale selection.

## Species-balanced transformation

Each scale-dependent feature at each k is transformed independently using the
same frozen species-balanced midrank-percentile convention used by selector
v1.

For genome g belonging to species s with n_s genomes, the genome weight is:

    w_g = 1 / n_s

Each species therefore contributes total weight one.

For a feature value x, its percentile coordinate is:

    (W_less + 0.5 * W_equal) / S

where:

- W_less is the summed genome weight for values strictly below x;
- W_equal is the summed genome weight for values equal to x;
- S is the number of species.

Exact rational arithmetic is used for the weighted-rank intermediate before
conversion to float64, consistent with selector v1.

## Distance between repeat scales

Scale choice is based only on how well two k values represent the complete
pre-specified repeat-scale grid.

For each k, let the three species-balanced percentile vectors represent:

- non-unique fraction;
- maximum multiplicity;
- inter-replicon shared fraction.

For two scales a and b, their squared scale distance is defined as the mean of
the species-balanced weighted squared coordinate differences across the three
repeat-feature families.

Genome weights are 1/n_s, so each species has equal total contribution.

Formally:

    d(a,b)^2 =
        (1 / 3) *
        sum_f [
            sum_g w_g * (P[g,f,a] - P[g,f,b])^2
            / sum_g w_g
        ]

where f ranges over the three scale-dependent repeat-feature families.

The reported scale distance is sqrt(d(a,b)^2).

No organism identity, selector ladder or panel-coverage result enters this
distance.

## Selection of two architecture scales

Every unordered pair of distinct k values from the prospective grid is
evaluated.

For candidate pair {a,b}, each k in the full grid is assigned the distance to
its nearer candidate scale:

    r(k | a,b) = min(d(k,a), d(k,b))

The primary pair-selection objective is minimax scale coverage:

    R_max(a,b) = max_k r(k | a,b)

The selected pair is the pair with the smallest R_max.

If more than one pair has exactly the same primary objective, the first
secondary criterion is the mean nearest-scale distance across all grid values:

    R_mean(a,b) = mean_k r(k | a,b)

The tied pair with smaller R_mean is preferred.

If a tie remains after both numerical criteria, choose the lexicographically
smallest numerical pair `(a,b)` with `a < b`.

The rule is deterministic.

The inherited pair `(150,400)` receives no preference and no penalty. It is
treated as one candidate pair among all pairs from the fixed grid.

## Why selector performance is not the scale-selection criterion

OPS and SR operate on the structural-feature geometry being defined.

Choosing repeat scales because they improve OPS or SR coverage would therefore
tune the feature definition to the candidate selector.

Repeat scales are instead selected from the multi-scale feature structure
itself, before any selector comparison on a potentially revised schema.

This keeps feature-definition choice separate from selector choice.

## Scale-selection outputs

The identity-blind repeat-scale analysis must report at least:

- the complete prospective k grid;
- the three scale-dependent feature distributions at every k;
- deterministic hashes for the recalculated multi-k feature data;
- the complete pairwise scale-distance matrix;
- R_max for every candidate pair;
- R_mean for every candidate pair;
- the deterministically selected two-scale pair;
- the rank and objective values of the inherited `(150,400)` pair;
- deterministic provenance sufficient to reproduce the calculation.

Genome or species identities are not included in public interpretation
outputs.

## Schema consequence

If the deterministically selected pair is `(150,400)`, the existing base-12
feature schema is retained.

If the selected pair differs from `(150,400)`, the six scale-dependent
coordinates are replaced by the corresponding three features at each selected
scale.

The schema continues to contain exactly 12 structural dimensions:

- five non-repeat structural dimensions;
- two non-unique-fraction coordinates;
- two maximum-multiplicity coordinates;
- one longest-exact-repeat coordinate;
- two inter-replicon-sharing coordinates.

No additional scale coordinates are added to selector v1.

## Consequence of a changed scale pair

If the selected scale pair differs from `(150,400)`, existing validation that
depends on the full feature geometry is not silently transferred to the
revised schema.

The revised schema must receive new deterministic validation wherever the
scientific result depends on the feature geometry.

This includes:

- species-balanced percentile coordinates;
- feature-correlation analysis;
- OPS and SR ladders;
- OPS-versus-SR coverage summaries and selector comparison;
- the species-balanced random-baseline coverage comparison;
- the species-representation diagnostic, including AG;
- leave-one-feature-out analysis;
- grouped feature-family ablation.

The pre-specified OPS-versus-SR decision rule is then applied again to the
final schema.

No geometry-dependent result from the superseded schema is treated as evidence
for the revised schema merely because the source-genome universe is unchanged.

The selector decision remains open until validation of the final schema is
complete.

If `(150,400)` is retained, the already frozen base-12 evidence remains the
coordinate-specific selector-v1 evidence unless a separate validation
requirement explicitly calls for repetition.

## Interpretation boundaries

The selected scales are representative coordinates for bacterial repeat
architecture within the frozen source universe.

They are not claimed to be universal biological thresholds.

The experiment does not establish that repeats below one selected scale are
resolvable or that repeats above another are unresolvable.

The experiment does not optimize for:

- assembler performance;
- sequencing platform;
- read length;
- fragment length;
- organism identity;
- pathogen status;
- clinical importance;
- publication status;
- OPS performance;
- SR performance.

The result applies to the defined BacSelect source universe and the frozen
repeat-feature semantics.

## Remaining validation

Repeat-scale selection does not by itself freeze selector v1.

Input-order invariance, broader rebuild determinism and historical/update
stability remain separately pre-specified validation requirements.

OPS versus SR also remains unresolved unless subsequent validation of the final
feature schema resolves the pre-specified selector comparison.
