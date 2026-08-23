# BacSelect selector v1 prospective validation design

## Status

Prospective validation design.

This design must be committed before BacSelect candidate panel identities are
generated or inspected.

The purpose is to evaluate alternative selector designs and the inherited
Project Finch structural-feature system without choosing methods after seeing
which organisms they select.

## Frozen validation foundation

Validation uses the Project Finch corrected eligible universe recorded in:

`validation/finch-foundation/inputs.tsv`

The foundation contains:

- 55,306 eligible genomes;
- 13,765 species groups;
- 12 raw structural features;
- deterministic genome-to-species assignments.

The raw feature matrix is the starting point for BacSelect geometry.

The Project Finch percentile matrix is retained for provenance and comparison
but is not assumed to be the BacSelect scaling method.

## Identity blinding

Selector-development reports must not use:

- species names;
- organism names;
- pathogen status;
- clinical relevance;
- publication status;
- downstream assembler performance;
- Project Finch panel membership.

During method comparison, genomes and species should be represented by
identity-neutral internal identifiers.

Canonical accessions may be retained in sealed machine-readable outputs for
reproducibility but should not appear in the initial comparison reports.

Panel identities are inspected only after the selector decision is frozen.

## Candidate architecture geometry

The initial validation geometry uses the 12 raw Project Finch structural
features.

For each raw feature, BacSelect recalculates species-balanced percentile
coordinates.

For species s with n_s eligible genomes, every genome in that species has
weight:

    w_i = 1 / n_s

Each species therefore contributes total weight 1 to the empirical
distribution of each feature.

For raw value x:

    W_less(x)  = sum of weights for observations < x
    W_equal(x) = sum of weights for observations = x

and:

    p(x) = [W_less(x) + 0.5 * W_equal(x)] / S

where S is the number of eligible species groups.

Tied raw values receive identical percentile coordinates.

A constant feature maps to 0.5.

All 12 dimensions initially receive equal weight.

## Distance

All candidate selectors use squared Euclidean distance for selection in the
12-dimensional species-balanced percentile space.

Reported structural distances use Euclidean distance.

No organism identity enters the distance calculation.

## Deterministic tie-breaking

Exact numerical ties must not be resolved using species names, TaxID numeric
magnitude, biological metadata, or downstream results.

A stable identity-neutral tie key is derived from:

    SHA256("BacSelect-selector-v1|" + canonical_accession)

The hash is used only after scientific selection scores are exactly tied.

The tie key is never interpreted as a scientific variable.

## Panel sizes

Primary validation is performed at:

- N = 10
- N = 20
- N = 50
- N = 100
- N = 200
- N = 500

All deterministic candidate selectors must produce nested panels.

The N=10 panel must be an exact prefix of N=20, and so forth.

## Candidate A: OPS

OPS means one-per-species.

### Species representative

For each species:

1. calculate the centroid of all member genomes in the species-balanced
   percentile geometry;
2. calculate squared Euclidean distance from every member genome to that
   centroid;
3. choose the genome nearest the centroid;
4. resolve an exact tie using the frozen SHA-256 tie key.

This produces exactly one candidate representative per species.

### Global ladder

Calculate the centroid of all species representatives.

The first selected representative is the genome nearest that centroid.

For every subsequent step:

1. calculate each unselected representative's minimum squared distance to the
   selected panel;
2. select the representative maximizing that minimum distance;
3. resolve an exact tie using the frozen SHA-256 tie key.

Continue until all species representatives are ranked.

OPS therefore selects exactly N species for panel size N.

## Candidate B: SR

SR means species-residual selection.

SR is designed to test whether permitting more than one genome from a species
materially improves structural coverage while preventing heavily sequenced
species from dominating simply through abundance.

### First genome

Calculate the centroid of each species in the species-balanced percentile
geometry.

Calculate the global centroid giving each species centroid equal weight.

Choose the species whose centroid is nearest that global centroid.

Within that species, choose the genome nearest the global centroid.

Resolve exact ties using the frozen SHA-256 tie key.

This two-stage rule prevents a heavily sampled species from gaining more
opportunities to supply the first genome merely because it contains more
eligible assemblies.

### Subsequent genomes

Maintain the nearest-panel squared distance for every eligible genome.

At each step:

1. calculate the mean current nearest-panel squared distance separately for
   each species;
2. choose the species with the largest mean residual distance;
3. within that species, choose the genome with the largest current
   nearest-panel squared distance;
4. resolve exact ties using the frozen SHA-256 tie key;
5. update nearest-panel distances.

Because every species contributes one species-level residual score regardless
of its number of deposited genomes, species abundance does not directly
determine the next selected species.

A species may be selected more than once when substantial within-species
structural diversity remains uncovered.

SR must also produce one deterministic nested ladder.

## Diagnostic selector: AG

AG means all-genome maximin.

AG operates directly over every eligible genome with no species balancing in
candidate availability.

It uses the same farthest-first selection rule as OPS but allows all 55,306
genomes to compete directly.

AG is not a preferred BacSelect candidate.

Its purpose is to quantify what happens when heavily sampled species are not
controlled.

## Random baseline

A species-balanced random baseline is generated for every validation N.

For each replicate:

1. sample species uniformly without replacement;
2. sample one genome uniformly from each sampled species;
3. preserve the generated order so panels are nested.

Use 1,000 deterministic replicates.

Master random seed:

    20260824

Random generation must use a recorded algorithm and software version.

Random baseline identities remain blinded during selector evaluation.

## Evaluation universe

Coverage is evaluated over all 55,306 eligible genomes, not only species
representatives.

This is essential because evaluating OPS only against its representative set
would conceal structural diversity within species.

Every genome receives evaluation weight:

    w_i = 1 / n_s

Therefore every species contributes equal total evaluation weight.

## Primary coverage metric

The primary metric is the species-balanced weighted 95th percentile of
nearest-panel Euclidean distance across all eligible genomes.

Lower values indicate better structural coverage.

The metric is calculated independently for each validation N.

## Secondary coverage metrics

For every panel size report:

- species-balanced weighted mean nearest-panel distance;
- species-balanced weighted median nearest-panel distance;
- species-balanced weighted 95th percentile nearest-panel distance;
- unweighted maximum nearest-panel distance.

Also calculate, for each species:

- mean nearest-panel distance among its member genomes;
- maximum nearest-panel distance among its member genomes.

Across species report:

- median species mean distance;
- 95th percentile species mean distance;
- maximum species mean distance;
- median species maximum distance;
- 95th percentile species maximum distance;
- maximum species maximum distance.

## Random-baseline comparison

For every N and metric, report:

- candidate-selector value;
- random median;
- random 2.5th percentile;
- random 97.5th percentile;
- empirical rank among the 1,000 random replicates.

No candidate is accepted merely because it beats a single random panel.

## OPS versus SR decision rule

The primary comparison uses the weighted 95th percentile nearest-panel
distance at all six pre-specified N values.

If one candidate has a lower primary metric at all six N values, that candidate
is preferred on structural coverage.

If OPS and SR cross across the six N values, there is no automatic winner.

In that case:

- inspect the pre-specified secondary metrics;
- do not inspect organism identities;
- do not introduce a new metric after seeing the result;
- record the selector decision as unresolved if the evidence remains mixed.

If structural performance is effectively indistinguishable without an
unambiguous winner, the simpler selector may be preferred, but the rationale
must be documented before panel identities are unblinded.

## One-per-species hypothesis

OPS is not assumed to be correct.

It is supported only if the prospective comparison does not show a consistent
structural-coverage advantage for the species-balanced SR design.

If SR consistently outperforms OPS, the one-genome-per-species constraint is
rejected for BacSelect selector v1.

## Species-abundance diagnostic

For OPS, SR, and AG, report at every N:

- number of distinct species selected;
- maximum number of selected genomes from one species;
- distribution of selected genomes per species.

AG provides the principal diagnostic for whether unrestricted candidate
availability concentrates selections in heavily sequenced species.

No species identities are shown in the initial report.

## Feature correlation

Before architecture schema v1 is frozen, calculate pairwise Spearman
correlations among all 12 candidate dimensions.

Report the complete correlation matrix.

No dimension is removed solely because it is correlated with another.

Correlation is a diagnostic for redundancy and sensitivity analysis.

## Leave-one-feature-out analysis

Repeat OPS and SR after removing each of the 12 feature dimensions in turn.

For each ablation report:

- primary coverage metrics;
- secondary coverage metrics;
- panel overlap with the full 12-feature ladder at each N.

Panel identities remain blinded.

## Grouped feature ablation

Also evaluate removal of the following pre-specified groups:

### Basic genome properties

- total genome length;
- whole-genome GC fraction.

### Replicon architecture

- replicon count;
- non-chromosomal replicon count;
- non-chromosomal sequence fraction.

### Repeat architecture

- non-unique canonical 150-mer fraction;
- non-unique canonical 400-mer fraction;
- maximum canonical 150-mer multiplicity;
- maximum canonical 400-mer multiplicity;
- longest exact repeat length.

### Inter-replicon sharing

- inter-replicon shared canonical 150-mer fraction;
- inter-replicon shared canonical 400-mer fraction.

The purpose is to determine whether the selector depends disproportionately on
one feature family.

## Repeat-scale validation

The inherited 150-bp and 400-bp repeat features were chosen for Project Finch
because of its PE150 / approximate 400-bp fragment model.

They are not automatically accepted as general BacSelect architecture scales.

A separate prospective repeat-scale experiment must be completed before
architecture schema v1 is frozen.

That experiment may require recalculation from source sequences and is not
silently substituted with the existing Project Finch features.

## Input-order invariance

For OPS and SR:

1. run from the authoritative input row order;
2. deterministically permute input rows;
3. rerun the selector;
4. require byte-identical scientific ladder output after canonical output
   ordering.

Defined SHA-256 tie-breaking must make results independent of input row order.

## Rebuild determinism

Independent repeated executions using identical inputs and software must
produce byte-identical:

- species-balanced percentile matrices;
- selector ladders;
- coverage summaries;
- validation reports.

## Historical/update stability

Before selector v1 is frozen, evaluate behaviour under changing source
universes.

At minimum test:

- deterministic addition of new genomes;
- replacement/removal of existing genomes;
- addition of genomes to heavily sampled species;
- addition of previously absent species;
- taxonomy reassignment scenarios.

Report how many prefix selections change at each N and why according to the
algorithmic scores.

Organism identity remains blinded during this evaluation.

## Project Finch comparison

After BacSelect selector and architecture decisions are frozen, compare the
BacSelect N=40 panel with the frozen Project Finch 40-genome / 25-species panel.

This comparison is retrospective validation only.

Project Finch panel membership must not influence:

- selector choice;
- feature choice;
- species-balancing choice;
- tie-breaking;
- coverage-metric choice.

## Unblinding

Panel identities may be inspected only after:

1. this validation design is committed;
2. candidate selector implementations pass unit tests;
3. all pre-specified primary comparisons are complete;
4. the selector decision is documented without organism identities.

Unblinding is an audit and interpretation step, not an algorithm-tuning step.

## Required validation outputs

The selector-v1 validation run must produce at minimum:

- frozen software/environment provenance;
- species-balanced percentile matrix hash;
- blinded OPS ladder;
- blinded SR ladder;
- blinded AG diagnostic ladder;
- random-baseline summary;
- coverage metrics for all N;
- species-abundance diagnostics;
- feature-correlation matrix;
- leave-one-feature-out results;
- grouped-ablation results;
- input-order invariance evidence;
- deterministic rebuild evidence;
- update-stability evidence;
- selector decision record.

No BacSelect release is created by this validation run.
