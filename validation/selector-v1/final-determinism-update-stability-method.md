# Selector-v1 final deterministic rebuild and update-stability method

## Status

PROSPECTIVE FINAL-SCHEMA VALIDATION

This record defines the remaining selector-level deterministic rebuild and
historical/update-stability validation before either analysis is run.

The final feature-sensitivity stage is already complete. This validation does
not alter the frozen 12-coordinate 300/2400 structural feature schema and does
not introduce a new OPS-versus-SR selector decision rule.

Genome and species identities remain blinded in scientific reports.

## Frozen foundation

Both analyses consume the frozen final selector-v1 foundation:

- 55,306 genomes;
- 13,765 species groups;
- 12 final structural coordinates;
- selected repeat scales 300 bp and 2400 bp;
- frozen raw matrix SHA256
  `86c0c3d49317dfc3cc452114e3863666fe2112b6a3ae8dae2090b60a2a598948`;
- frozen percentile matrix SHA256
  `f48e20b28ee89988e7abb42488a35c62fbfa4a538c15c8d2d70b6b5ba7ae83c1`;
- frozen species mapping SHA256
  `f0343238930e957f82bc28997a216ab3a8967d007b3d3471679e3f054c76af6c`;
- frozen environment lock SHA256
  `f6f4a19c44a759705682ba4199207eaef5c2435e1b6feeddc1e4654686bc2a8c`.

The final raw float64 C-order array identity is
`2a0dbd5809fa4d5d77ab6e2d5255ddec9bb933a94be6c270260ec81758d8cbd6`.

The final percentile float64 C-order array identity is
`9a4a120562ff1151fd8c83e831eb81362b2372844f7dd7407746554af49cda67`.

## Already completed input-order invariance

Input-order invariance is not redefined here.

The frozen final geometry baseline already requires and records identical OPS,
SR, AG, and random scientific ladder identities after deterministic input-row
permutation.

This remaining work addresses broader repeated-execution determinism and
behaviour under explicitly changed source universes.

# Part A: broader deterministic rebuild

## Objective

Independent repeated executions using identical frozen inputs and software
must produce byte-identical scientific outputs for:

1. a recomputed species-balanced percentile matrix;
2. OPS, SR, and AG selector ladders;
3. coverage summaries;
4. the deterministic validation report.

Runtime metadata such as Slurm job ID, host, timestamps, and output path is
written only to a separate provenance artifact and is not part of the
scientific byte-identity comparison.

## Recomputed percentile matrix

The 12 raw structural features are loaded from the frozen final raw matrix.

Species-balanced midpoint percentile coordinates are recalculated from the raw
features and species mapping using the committed exact-rational geometry
implementation.

The recalculated float64 matrix must first reproduce the frozen final
percentile-array SHA256 exactly.

A canonical blinded matrix is then serialized for repeated-execution
comparison:

- rows are sorted by the frozen genome `tie_key`;
- no genome identifier or per-genome hash is written;
- columns are the 12 final structural features in frozen order;
- float64 values are serialized with `.17g`;
- delimiter is tab;
- line ending is `\n`.

The deterministic sort establishes a stable row order without exposing
per-genome pseudonyms that could be mapped back to public accessions.

This canonical serialization is a determinism artifact. It does not replace
the already frozen feature-space artifact.

## Selector ladders

OPS, SR, and AG are each rebuilt to N=500 from the recalculated final
coordinates.

For OPS and SR, the already frozen final N=500 reference fingerprints must be
reproduced exactly:

- OPS:
  `c81d9fd30cda2d49f0f6c81d4bf99dace9fff811c7612036d9265ef90707fa13`;
- SR:
  `3c703f5f898e0a13c6eb8568c0b83f5b0d19d4e374155d2d3a8a4e20378bd51f`.

The canonical ladder artifact reports only:

- selector;
- maximum ladder size;
- one SHA256 fingerprint of the complete ordered N=500 accession sequence.

No per-genome accession, species identity, or individually mappable accession
hash is written.

OPS and SR use their already frozen final 300/2400 fingerprint namespaces.
AG uses the corresponding final 300/2400 AG namespace for repeated-execution
comparison.

## Coverage summaries

For OPS, SR, and AG, calculate the same ten frozen coverage metrics at:

- N = 10;
- N = 20;
- N = 50;
- N = 100;
- N = 200;
- N = 500.

OPS and SR must reproduce the already frozen final coverage table exactly.

AG is included in repeated-execution byte comparison as the unrestricted
diagnostic selector but does not enter the OPS-versus-SR decision rule.

## Determinism criterion

Run the complete deterministic rebuild twice in independent output
directories from the same committed code, inputs, and environment.

Require byte-identical:

- canonical recomputed percentile matrix;
- canonical blinded ladder table;
- canonical coverage table;
- canonical validation JSON.

The two provenance files are expected to differ in run-specific metadata.

A mismatch is a validation failure and is not interpreted scientifically.

# Part B: update stability

## Objective

Evaluate how final OPS and SR prefix membership responds to deterministic
changes in the source universe.

This is sensitivity analysis. There is no pass/fail overlap threshold and no
new selector-decision threshold.

For each scenario, the raw 12-feature universe is changed first and the
species-balanced percentile geometry is recomputed from that changed universe.
The selector is never run by merely editing the already frozen percentile
matrix.

## Synthetic shadow genomes

Prospective update scenarios require future genomes that do not yet exist.

To avoid inventing speculative bacterial architecture, a synthetic "shadow"
genome copies all 12 raw structural feature values from a deterministically
selected existing template genome.

A shadow genome receives:

- a deterministic synthetic accession beginning `BSUPD_`;
- either the template species assignment or a prospectively defined synthetic
  species assignment, depending on scenario.

Shadow accessions and synthetic species identifiers are used only internally.
Scientific reports contain hashes/counts, not those identifiers.

Because shadow genomes reproduce observed structural profiles exactly, this
experiment tests source-universe membership, species-weight, taxonomy, and
deterministic tie effects without inventing new feature values.

## Stable perturbation ranking

All selections of templates, genomes, or species are fixed by SHA256 using the
namespace:

`BacSelect-selector-v1|update-stability-v1|`

No PRNG is used.

Each scenario receives one aggregate SHA256 fingerprint that binds its complete
perturbed universe after canonical sorting, including genome identity-neutral
tie order, species assignment, synthetic/baseline status, and all 12 raw
structural feature values. No per-genome fingerprint is written.

When abundance is part of the scenario definition, species are ordered first
by the stated abundance rule and then by frozen identity-neutral species
`species_tie_key`.

## Pre-specified update scenarios

### 1. General addition: `add_general_500`

Add 500 shadow genomes.

Templates are the 500 baseline genomes with smallest scenario-specific SHA256
rank across the complete universe.

Each shadow retains its template species assignment.

Purpose: deterministic addition of new genomes distributed across the existing
source universe without inventing new architecture values.

### 2. Removal: `remove_500`

Remove the 500 baseline genomes with smallest scenario-specific SHA256 rank.

No replacement is added.

Purpose: deterministic removal of existing source records.

### 3. Replacement: `replace_500`

Choose 500 baseline genomes by a separate scenario-specific SHA256 rank.

For each chosen genome:

- remove the original accession;
- add one shadow genome with identical raw features;
- retain the same species assignment.

The feature multiset and species membership are therefore unchanged; only
record identity and tie keys change.

Purpose: isolate accession/record replacement effects from geometry change.

### 4. Heavy-species addition: `add_heavy_species_500`

Identify the ten most heavily sampled baseline species.

Abundance ties are resolved with `species_tie_key`.

The frozen baseline contains exactly ten species with at least 500 genomes, so
each selected species has enough distinct templates for this protocol.

For each of the ten species, add 50 shadows copied from 50 distinct members
chosen by scenario-specific SHA256 rank.

Total addition: 500 genomes.

Purpose: test whether additional sampling of already dominant species changes
species-balanced geometry or selector prefixes.

### 5. Previously absent species: `add_new_species_100`

Choose 100 baseline template genomes by scenario-specific SHA256 rank.

Add one shadow copy of each template and assign each shadow to its own unique
synthetic species not present in the baseline.

Total addition:

- 100 genomes;
- 100 previously absent species.

Purpose: test addition of new species without inventing structural profiles.

### 6. Taxonomy split: `taxonomy_split_500`

Identify the single most heavily sampled baseline species; abundance ties are
resolved with `species_tie_key`.

The frozen baseline maximum species size is 4,388.

Choose 500 members of that species by scenario-specific SHA256 rank and
reassign those existing genomes to one new synthetic species.

No genome or feature row is added or removed.

Purpose: test a substantial deterministic species split.

### 7. Taxonomy merge: `taxonomy_merge_100_singletons`

Identify all baseline singleton species.

Choose 100 singleton species by scenario-specific species SHA256 rank.

Reassign their 100 existing genomes to one common new synthetic species.

No genome or feature row is added or removed.

The scenario reduces the species count by 99.

Purpose: test deterministic merger/reclassification of previously separate
species groups.

## Stability outputs

For every scenario and for OPS and SR, report at each N:

- baseline prefix size;
- perturbed prefix size;
- unordered overlap count;
- changed count, defined as `N - overlap_count`;
- exact overlap fraction;
- number of synthetic genomes in the perturbed prefix;
- number of baseline prefix genomes unavailable after the perturbation;
- first positional divergence rank.

No acceptance threshold is applied.

## Algorithmic explanation

For each scenario and selector, report one blinded first-divergence trace.

The trace is calculated under the perturbed selector trajectory and records:

- first divergence rank;
- whether the baseline choice remains available;
- whether it remains an eligible candidate;
- selection stage;
- selected primary algorithmic score;
- baseline-choice primary score when defined;
- selected secondary score when the selector has one;
- baseline-choice secondary score when defined;
- score relation;
- a categorical reason derived from the actual selector rule.

OPS score stages are:

- rank 1: minimum squared distance to the global centroid of species
  representatives;
- ranks 2-500: maximum current nearest-panel squared distance among species
  representatives.

SR score stages are:

- rank 1 primary: minimum species-centroid squared distance to the global
  centroid;
- rank 1 secondary: minimum genome squared distance to the global centroid
  within the chosen species;
- ranks 2-500 primary: maximum species mean current nearest-panel squared
  distance;
- ranks 2-500 secondary: maximum current nearest-panel squared distance within
  the chosen species.

The traced implementation must assert that its complete selected ladder is
identical to the committed OPS or SR implementation before the trace is
accepted.

## Geometry-shift diagnostics

For baseline accessions retained by a scenario, report:

- number of shared baseline accessions;
- mean absolute change across their 12 percentile coordinates;
- maximum absolute change across their 12 percentile coordinates.

These diagnostics explain geometry changes; they are not selector-decision
metrics.

## Stability determinism

Run the complete update-stability analysis twice from the same committed code,
inputs, environment, and perturbation definitions.

Require the canonical scenario, prefix, first-divergence, and summary reports
to be byte-identical.

Run-specific provenance is kept separately.

## Interpretation boundary

Update stability does not select OPS or SR.

No minimum acceptable overlap, maximum acceptable changed count, significance
threshold, equivalence margin, or aggregate stability score is defined.

Results are interpreted descriptively with respect to the deterministic
algorithmic mechanisms above.

The already frozen coverage-stage OPS-versus-SR decision remains
**UNRESOLVED** unless changed by its own pre-specified rule, which this analysis
does not modify.

Genome and species identities remain blinded.
