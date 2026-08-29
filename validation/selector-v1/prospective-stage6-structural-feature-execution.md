# BacSelect selector-v1 Stage 6 structural-feature execution

## Status

**PROSPECTIVE STAGE 6 METHOD — NO PRODUCTION STRUCTURAL FEATURES YET**

This record freezes the Stage 6 structural-feature execution method before the
external decision-holdout membership, authoritative package manifests,
sequence-report rows, or genomic FASTA sequence are parsed for Stage 6
production execution.

Stage 5B is formally closed.

Stage 6 does not alter eligibility, taxonomy, holdout membership, repeat-scale
selection, or the OPS-versus-SR selector decision rule.

## Frozen Stage 5B input

Stage 5B closure commit:

`b69b4cfebd0b65be0f1c9462bb68e5397aa1fcf9`

Stage 5B completion-evidence SHA256:

`a8969754ee928bbfe31c5b10c51ac72d3602533ee411e01cd290048f2acf1a2b`

The frozen external decision holdout contains:

- genomes: `12952`;
- distinct canonical species groups: `3542`;
- holdout artifact SHA256:
  `ed0950e973d7d1bd2e7d294d1e5fde9cb7087e41cd54f021ac2ffe94262716c3`;
- holdout membership SHA256:
  `0998a65f617e6c1b951b52990c0e2cf8110b6327992110d862d9338f0fa06bbd`;
- adequacy status: `ADEQUACY_PASS`.

The accession-bearing holdout artifact remains outside Git in scratch storage.

Stage 6 must verify its whole-file SHA256 before reading any holdout row.

The complete Stage 6 input membership is exactly the frozen Stage 5B holdout.
Stage 6 may not add, remove, replace, downsample, promote, or otherwise change a
holdout member.

## Scientific specification binding

The BacSelect scientific specification used by this method has SHA256:

`93114676f8510e9df57459153316266f7d57b7cfe380e09849bddf8e62d2cddf`

The final selector-v1 structural schema contains exactly twelve raw
sequence-derived coordinates in this order:

1. `01_total_genome_length`;
2. `02_whole_genome_gc_fraction`;
3. `03_replicon_count`;
4. `04_non_chromosomal_replicon_count`;
5. `05_non_chromosomal_sequence_fraction`;
6. `06_non_unique_canonical_300mer_fraction`;
7. `07_non_unique_canonical_2400mer_fraction`;
8. `08_maximum_canonical_300mer_multiplicity`;
9. `09_maximum_canonical_2400mer_multiplicity`;
10. `10_longest_exact_repeat_length`;
11. `11_inter_replicon_shared_canonical_300mer_fraction`;
12. `12_inter_replicon_shared_canonical_2400mer_fraction`.

No additional coordinate is permitted.

No coordinate may be omitted, rescaled, clipped, winsorized, transformed,
imputed, rounded for calculation, or redefined during Stage 6.

Stage 6 produces raw structural features only.

Species-balanced percentile geometry is explicitly downstream and must not be
calculated in Stage 6.

## Frozen repeat-scale decision

The frozen repeat-scale method has SHA256:

`2897282450221e662bb1d6c1142da7c999e07e23c21d66f265cbf2fe13313d01`

The Stage 6 repeat scales are exactly:

- `300`;
- `2400`.

The earlier Project Finch 150/400 scales are historical validation anchors and
are not Stage 6 production coordinates.

Stage 6 must not rerun repeat-scale selection or choose k values after observing
holdout features.

## Frozen scientific implementation

Stage 6 reuses the already-vendored Project Finch structural-feature
implementation without modifying its scientific mathematics.

Frozen structural-feature driver:

`vendor/project-finch/experiment-0/compute_structural_features.py`

SHA256:

`e4d76a44731000dc8330d6f3289aca76ce6562329dd371f6f63ec090ab42db50`

Frozen basic-feature implementation:

`vendor/project-finch/experiment-0/basic_structural_features.py`

SHA256:

`30bc3f52fdf68cf7b6433262935b3ed2bb189b256672687bea56f3a4f4cc043a`

Frozen topology-aware repeat/longest-repeat engine source:

`vendor/project-finch/experiment-0/structural_features_fast.cpp`

SHA256:

`bea979167a353c41e51bb96c83acebfb8e8136269d2902d99142c0780bf46925`

Frozen Python semantic reference used for differential validation:

`vendor/project-finch/experiment-0/structural_features.py`

SHA256:

`c1e7388ba7db82d1b937a16e1a1be9e8c65d8779ce8691a2f0097cb5b6af6786`

The semantic reference is a validation oracle and is not an alternative
production feature definition.

The historical validated compiled engine identity is:

`e0b5ea3a892aee3f9af80e5676010f1e1145563ca900058485e07d6433988968`

The frozen repeat environment lock SHA256 is:

`aa6984b17e86f7d0627379e295fabed837cf7d43cc6a9fd80f32b7092ac5f64f`

The Stage 6 production engine must be compiled from the exact frozen C++ source
inside the exact frozen repeat environment using the already validated compile
contract.

Before any production holdout sequence is processed, the compiled executable
must have SHA256 exactly:

`e0b5ea3a892aee3f9af80e5676010f1e1145563ca900058485e07d6433988968`

A different binary identity fails closed.

No alternative compiler, library, optimization setting, Python implementation,
or fallback repeat algorithm may be substituted during production.

## Prior engine validation

The frozen BacSelect repeat-scale worker has SHA256:

`49f4ffd22edb1116fc34e520c9eb1094f837b9d2c2a24780138fd2fee5011527`

The frozen BacSelect differential repeat-engine validator has SHA256:

`9b1f79380c61a461309fb8db9f5f1e826ea632a6b033529725ad9ce1d4e42ba4`

Existing validation established equivalence between the frozen C++ engine and
the frozen Python semantic reference across deliberate edge cases and
deterministic randomized multi-replicon cases.

Existing historical production additionally anchored the same engine lineage
against the frozen Project Finch 150/400 structural-feature matrix.

Stage 6 does not reinterpret those completed validation results.

The new Stage 6 adapter must receive its own synthetic-only tests before
production execution.

## Features 1–5

Features 1–5 are calculated only by the frozen
`basic_structural_features.basic_structural_features(...)` implementation.

For the exact retained Primary Assembly replicons:

- total genome length is the sum of retained nucleotide sequence lengths;
- whole-genome GC fraction is calculated directly from retained FASTA sequence;
- replicon count is the number of retained Primary Assembly replicons;
- a replicon is non-chromosomal when its exact NCBI
  `assignedMoleculeLocationType` value is not `Chromosome`;
- non-chromosomal sequence fraction is the summed length of those
  non-chromosomal replicons divided by total genome length.

The Stage 6 adapter must not independently reimplement these calculations.

NCBI summary `gcCount` is descriptive metadata only and must not replace the
sequence-derived GC calculation.

## Repeat coordinates 6–9 and 11–12

For each retained genome the frozen C++ engine is invoked on the exact retained
replicon sequences and topologies for k values exactly `300` and `2400`.

The engine input contains, for each retained replicon:

- component name;
- topology exactly `linear` or `circular`;
- retained nucleotide sequence.

Canonical k-mers treat a sequence and its reverse complement as equivalent.

Circular replicons remain topology-aware across the recorded FASTA origin.

For each k, Stage 6 obtains:

- valid source-coordinate start count;
- non-unique source-coordinate start count;
- non-unique fraction;
- maximum canonical multiplicity;
- inter-replicon shared source-coordinate start count;
- inter-replicon shared fraction.

The six Stage 6 repeat coordinates are copied directly from the frozen engine
results at k=300 and k=2400.

No Stage 6 code may independently implement canonicalization, topology-aware
start generation, multiplicity, or inter-replicon sharing.

## Feature 10

`10_longest_exact_repeat_length` is calculated only by the frozen C++ engine
using its existing `--longest-repeat` implementation.

When the engine emits longest-repeat values on both k=300 and k=2400 output
rows, the values must be identical.

Any disagreement fails closed.

No alternative longest-repeat implementation is permitted in production.

## Authoritative package population

Stage 6 must reconstruct the already-authoritative source package population
using the same frozen Stage 1/Stage 2 population reconstruction used for Stage
3.

The operational Stage 1 wrapper identity is:

`59dd3ea140ee9a49c86dbed810639728000add8ac30121ab41d2c59e328961d5`

The operational Stage 2 wrapper identity is:

`5e5f51891e5348e62bc53dfacc28f57216f2e0f38ef69d3ce686121ed6aff355`

The Stage 6 implementation must invoke the frozen Stage 2
`reconstruct_stage1_population(...)` contract with explicitly supplied:

- historical snapshot root;
- cache-reuse accession manifest;
- cache-reuse manifest;
- historical cache-verification artifact;
- ordinary-fresh execution root;
- accepted fresh-recovery root.

Stage 6 must not recursively discover package directories, select the newest
file, infer package provenance from paths, or choose between multiple candidate
packages heuristically.

Accepted package classes remain exactly:

1. verified historical Project Finch cache;
2. ordinary BacSelect fresh acquisition;
3. accepted BacSelect fresh recovery.

A fresh-recovery package remains fresh recovery.

Package class has no effect on feature mathematics.

## Frozen source-evidence primitives

Stage 6 remains bound to the existing upstream source-evidence semantics.

Frozen source-truth execution helper SHA256:

`83b8ec7fce774c0b68cb2af982aef13904c6b64b3ee695512c578f98e5de9b92`

Frozen topology-aware source fingerprint SHA256:

`6c994d243709abdbe9d7c8949e156009b9f31f3fcef3247cc3c5679e2fff41c9`

Frozen chromosome-integrity execution helper SHA256:

`187816b76ae804ad2e682e036a5fb76528ac1762d6535062a566edd2fe6e4b9c`

These upstream implementations define the already-validated package evidence
and Primary Assembly component universe.

Stage 6 must not reopen eligibility decisions or derive an alternative component
universe.

## Holdout-to-package join

Only after Stage 6 predecision provenance has been finalized may production
execution:

1. parse the frozen holdout rows;
2. reconstruct the authoritative source package population;
3. join every holdout accession to exactly one authoritative package;
4. require that every holdout accession is present exactly once;
5. require that no non-holdout accession enters Stage 6 feature calculation.

The Stage 6 package join is identity-based only.

Species TaxID, feature values, package class, genome size, taxonomy,
clinical metadata, and later selector information must not affect package
selection.

The exact Stage 6 accession membership after package resolution must still have
count `12952` and membership SHA256:

`0998a65f617e6c1b951b52990c0e2cf8110b6327992110d862d9338f0fa06bbd`

Any mismatch fails closed before the first structural feature is calculated.

## Frozen Finch loader

For each holdout member Stage 6 uses the frozen Finch
`load_replicons(...)` implementation from
`compute_structural_features.py`.

The loader must verify, before feature calculation:

- candidate-audit membership;
- genomic FASTA file existence;
- genomic FASTA SHA256;
- sequence-report file existence;
- sequence-report SHA256;
- component-audit membership;
- exact Primary Assembly component set;
- exact component sequence SHA256;
- component lengths;
- topology;
- NCBI `assignedMoleculeLocationType`;
- candidate total sequence length;
- candidate FASTA-record count;
- candidate Primary Assembly record count;
- circular topology count;
- linear topology count.

Only Primary Assembly components enter the structural feature calculation.

A FASTA record outside the retained component audit is permitted only when the
matching sequence-report row explicitly classifies it as non-Primary Assembly.

Missing, duplicate, additional, contradictory, or unverified Primary Assembly
component evidence fails closed.

## No new eligibility decision

Stage 6 occurs after the complete eligible universe and external decision
holdout have been frozen.

Therefore a Stage 6 feature-computation failure is **not** a new biological or
metadata exclusion criterion.

Stage 6 may not remove a genome because a feature cannot be computed.

If any frozen holdout member cannot be resolved to its authoritative package,
cannot be loaded by the frozen loader, or cannot produce all twelve frozen
coordinates, the Stage 6 production execution fails and downstream selector
evaluation remains blocked.

There is no partial Stage 6 eligible subset.

There is no replacement genome.

There is no imputation.

## Stage 6 predecision provenance

Before parsing holdout rows or authoritative source-package manifest rows,
production execution must write deterministic predecision provenance binding:

- Stage 5B completion evidence;
- frozen holdout artifact SHA256;
- frozen holdout count;
- frozen holdout species count;
- frozen holdout membership SHA256;
- this Stage 6 method SHA256;
- Stage 6 execution commit;
- Stage 6 implementation SHA256;
- Stage 6 production-wrapper SHA256;
- Stage 1/Stage 2 operational reconstruction identities;
- frozen source-evidence implementation identities;
- Finch driver SHA256;
- Finch basic-feature SHA256;
- Finch semantic-reference SHA256;
- repeat-engine source SHA256;
- compiled repeat-engine SHA256;
- repeat environment-lock SHA256.

The predecision record must explicitly state that:

- holdout rows have not been parsed;
- source-package manifests have not been parsed for Stage 6;
- FASTA sequence has not been opened for Stage 6;
- sequence-report rows have not been opened for Stage 6;
- structural features have not been calculated;
- percentile coordinates have not been calculated;
- OPS/SR distances have not been calculated;
- panel identities have not been generated;
- selector outcomes have not been calculated.

Whole-file SHA256 verification and physical file checks are permitted before
predecision provenance.

## Raw structural-feature matrix

Successful Stage 6 execution writes one canonical raw feature matrix in scratch:

`structural-feature-matrix-300-2400.tsv`

Columns are exactly:

1. `canonical_genbank_assembly_accession`;
2. `species_taxid`;
3. the twelve frozen structural-feature columns in their specified order.

Rows are sorted lexicographically by canonical versioned GCA accession.

`species_taxid` is copied unchanged from the frozen Stage 5B holdout.

Integer-valued coordinates are serialized as base-10 integers.

Floating-point coordinates are serialized deterministically with Python
`.17g`.

Line endings are `\n`.

Delimiter is tab.

The matrix must contain exactly `12952` data rows and exactly
`3542` distinct species TaxIDs.

The accession membership SHA256 calculated from the completed matrix must equal:

`0998a65f617e6c1b951b52990c0e2cf8110b6327992110d862d9338f0fa06bbd`

## Per-candidate execution evidence

Successful Stage 6 execution also writes a deterministic identity-bearing
candidate evidence artifact in scratch.

At minimum it records for every holdout member:

- canonical accession;
- authoritative source package class;
- authoritative batch/source identifier;
- upstream source-evidence SHA256;
- genomic FASTA SHA256;
- sequence-report SHA256;
- retained Primary Assembly replicon count;
- total retained sequence length;
- circular replicon count;
- linear replicon count;
- deterministic feature-record SHA256.

This artifact is provenance only.

Package class and provenance fields do not become structural coordinates.

## Numeric validation

Before a candidate feature row is accepted, Stage 6 must require:

- exactly twelve feature fields;
- all feature values finite;
- total genome length positive;
- replicon count positive;
- non-chromosomal replicon count between zero and replicon count inclusive;
- GC fraction in `[0, 1]`;
- non-chromosomal sequence fraction in `[0, 1]`;
- both non-unique fractions in `[0, 1]`;
- both inter-replicon shared fractions in `[0, 1]`;
- both maximum multiplicities are non-negative integers;
- longest exact repeat length is a non-negative integer;
- for each repeat scale, count/fraction relationships agree with the frozen
  engine output.

These are execution-consistency checks only.

They do not define new eligibility rules.

Any failure aborts Stage 6.

## Deterministic identity

After successful production execution Stage 6 records, without printing genome
identities or feature values:

- raw feature-matrix artifact SHA256;
- raw feature-matrix membership SHA256;
- raw feature-matrix row count;
- distinct species count;
- SHA256 of the C-order float64 numeric array containing the twelve feature
  columns in canonical matrix row order;
- candidate-evidence artifact SHA256;
- input-evidence manifest SHA256;
- execution-provenance SHA256;
- aggregate-summary SHA256;
- content-manifest SHA256.

The numeric-array SHA is an identity of the produced feature values, not a
feature summary.

No feature minima, maxima, means, medians, quantiles, outliers, rankings, or
candidate identities are printed or frozen in Git before the selector decision
checkpoint.

## Identity-bearing output boundary

Accession-bearing, species-bearing, package-bearing, and raw-feature-bearing
Stage 6 outputs remain outside Git in scratch storage.

Git may later freeze only aggregate Stage 6 evidence such as:

- input count;
- input membership SHA256;
- distinct species count;
- successful feature-row count;
- matrix artifact SHA256;
- matrix membership SHA256;
- matrix numeric-array SHA256;
- candidate-evidence artifact SHA256;
- provenance identities;
- deterministic validation status.

No accession, species TaxID, package identity, or raw feature value may be
committed to Git as Stage 6 completion evidence.

## Atomic production output

The Stage 6 production wrapper must use a commit-specific scratch directory.

It must write first to a `.partial` directory.

Successful execution must finalize atomically only after all membership,
package, feature, schema, count, fingerprint, and provenance checks pass.

Failed `.partial` evidence is preserved.

Existing finalized Stage 6 output is never overwritten.

## Required successful output set

The initial production implementation must finalize exactly these seven files:

1. `stage6-predecision-provenance.json`;
2. `structural-feature-matrix-300-2400.tsv`;
3. `stage6-candidate-evidence.tsv`;
4. `stage6-input-evidence-manifest.tsv`;
5. `stage6-execution-provenance.json`;
6. `stage6-aggregate-summary.json`;
7. `stage6-content-manifest.tsv`.

The content manifest covers the preceding six files and excludes itself.

The implementation may not silently add identity-bearing debug outputs to the
finalized directory.

## Implementation testing

Before production execution, the new Stage 6 adapter and wrapper must be frozen
in Git.

Testing before that freeze is synthetic-only.

Synthetic tests must cover at least:

- historical package resolution;
- ordinary-fresh package resolution;
- fresh-recovery package resolution;
- duplicate package resolution failure;
- missing holdout package failure;
- unexpected non-holdout package isolation;
- FASTA SHA mismatch;
- sequence-report SHA mismatch;
- component-set mismatch;
- component-sequence SHA mismatch;
- unsupported topology;
- missing molecule-location type;
- exact basic features 1–5;
- exact k=300 coordinates;
- exact k=2400 coordinates;
- exact longest-repeat propagation;
- inconsistent longest-repeat rows;
- matrix schema and ordering;
- `.17g` floating serialization;
- holdout membership preservation;
- species TaxID preservation;
- atomic finalization;
- preservation of failed partial evidence;
- identity-safe standard output and standard error;
- prohibition of selector/coverage dependencies.

The existing frozen differential engine validator must also pass unchanged
before production is authorized.

No real Stage 6 holdout row or production sequence is opened during
implementation testing.

## Blinding

Before the formal selector decision checkpoint, human-visible Stage 6 output is
limited to:

- counts;
- cryptographic fingerprints;
- execution status;
- provenance identities;
- validation pass/fail state.

The workflow must not print or otherwise surface:

- holdout accessions;
- species identities;
- package identities;
- raw structural-feature values;
- percentile coordinates;
- OPS/SR distances;
- OPS/SR ladder membership;
- panel identities;
- panel coverage;
- selector outcomes.

Identity-bearing scratch artifacts may be machine-read by the frozen execution
and audit code but are not manually inspected.

## Downstream boundary

Stage 6 ends after the complete raw 12-coordinate holdout feature matrix is
successfully frozen in scratch and aggregate completion evidence is committed.

Stage 6 must not calculate:

- species-balanced percentile coordinates;
- OPS distances;
- SR distances;
- OPS or SR ladders;
- panel coverage;
- selector scores;
- selector outcomes.

A successful Stage 6 result authorizes only the separately prospectively frozen
downstream geometry stage.

It does not itself authorize a selector decision.

## Prospectivity statement

At the time this method is frozen:

- Stage 5B is formally closed;
- the external holdout is fixed at `12952` genomes across
  `3542` species;
- the exact holdout identities remain uninspected by the human operator;
- the Project Finch/BacSelect structural-feature engine is already frozen and
  validated;
- Stage 6 production code does not yet exist;
- no Stage 6 holdout row has been parsed;
- no Stage 6 source-package manifest has been parsed;
- no Stage 6 genomic FASTA sequence has been opened;
- no Stage 6 sequence-report row has been opened;
- no Stage 6 structural feature has been calculated;
- no percentile coordinate has been calculated;
- no selector outcome has been calculated.

This method is frozen prospectively before implementation and production.
