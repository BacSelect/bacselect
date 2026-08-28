# BacSelect selector-v1 Stage 3 chromosome-integrity execution

**PROSPECTIVE EXECUTION METHOD - NO STAGE 3 OUTCOME GENERATED**

This method is frozen before BacSelect selector-v1 Stage 3 chromosome-integrity
execution is performed on any real Stage 3 candidate.

It does not change the previously frozen chromosome-integrity scientific rule,
closure predicate, historical-adjudication reuse rule, repeated-BioSample
precedence, taxonomy rule, final-universe rule, holdout rule, structural-feature
definition, selector rule, or blinding boundary.

Its purpose is to define how the already-frozen chromosome-integrity primitive
is supplied with verified evidence during production Stage 3 execution.

## Parent checkpoint

Parent BacSelect commit:

`4705dfc1eb6b815fa806f937e04c66ba32260b23`

The parent commit freezes successful Stage 2 repeated-BioSample completion
evidence.

Stage 2 completion-evidence SHA256:

`d00801b1833c6c3cdee44a8c981d9eb1fc900f6becabc6d59e996877462d76a6`

No Stage 3 chromosome-integrity outcome has been generated at this checkpoint.

## Frozen scientific dependencies

Post-sequence eligibility design SHA256:

`2c3222421d6b7bb0adbf86a6eb44dae0d0ec7fa1fffcec8bdc1bbf6a0c5d9460`

Post-sequence provenance-refinement SHA256:

`1113bc8b95f60288c8a4767481467f9b2585969f1b8ea3dbd418caa91710df5`

Chromosome-integrity implementation clarification SHA256:

`c13114780c6788f4b9541d6428edf1d2e0827ff3797541b848ec1570a57ac30b`

Post-sequence composition clarification SHA256:

`e1399bd9d8a9f62c6cdb855a334da29840cb05df27724f08d6e010b56b7a332c`

Frozen chromosome-integrity implementation:

`src/bacselect/source_chromosome_integrity.py`

SHA256:

`04f1b580ec9480a20f3679e7eb996da08a074c48ff246549df2e0ed20b97b9c0`

Frozen chromosome-integrity tests SHA256:

`94d4eb099ec3812a40fdd11780f82fb65042203bae425ab14e4ec5b184971697`

Stage 3 delegates the scientific classification for each candidate to this
frozen chromosome-integrity implementation.

No independent reimplementation of the trigger, closure predicate, historical
reuse rule, or historical outcome mapping is permitted.

## Frozen upstream execution dependencies

The reusable Stage 1 evidence loader and verifier is:

`src/bacselect/source_truth_execution.py`

SHA256:

`83b8ec7fce774c0b68cb2af982aef13904c6b64b3ee695512c578f98e5de9b92`

The frozen fresh sequence-validation implementation from which the package
evidence was generated is:

`validation/selector-v1/fresh_sequence_validation_batch.py`

SHA256:

`f8430ea18ca4b192ac4b98f74329eed41c85bc3d7999379eda75d8464ac0c9ef`

Stage 3 must reuse the already-frozen Stage 1/Stage 2 acquisition and evidence
resolution boundaries. It must not independently discover candidate packages
by recursively walking scratch directories or choosing files heuristically.

## Stage 2 input binding

The authoritative successful Stage 2 decision artifact has SHA256:

`3613195996b8d8d1a5d6cbb23976a5418d97666054aa8ef33601b5ac31a7979a`

The Stage 2 completion evidence records:

- Stage 2 input candidate count: `68,359`;
- `CONTINUE`: `68,278`;
- `NONREPRESENTATIVE`: `6`;
- `REVIEW_UNRESOLVED`: `75`.

Only the exact `68,278` candidates whose Stage 2 status is `CONTINUE` may enter
Stage 3.

The six `NONREPRESENTATIVE` candidates and 75 `REVIEW_UNRESOLVED` candidates
are terminal at the repeated-BioSample layer and must not be evaluated by
Stage 3.

Stage 3 must read the authoritative Stage 2 decision artifact only after this
method, the Stage 3 implementation, and the Stage 3 production wrapper have
all been prospectively frozen.

The Stage 3 implementation must verify the authoritative Stage 2 decision-file
SHA256 before reading its rows.

It must require exactly one Stage 2 decision per Stage 2 candidate and exactly
`68,278` rows with status `CONTINUE`.

The canonical versioned GCA accession is the Stage 3 candidate identity.

## Stage 3 input membership freeze

Before the first chromosome-integrity decision is calculated, production
execution must:

1. reconstruct the exact set of `68,278` Stage 2 `CONTINUE` candidates;
2. sort their canonical versioned GCA accessions lexicographically;
3. calculate a deterministic SHA256 membership identity over that ordered
   membership;
4. write the candidate count and membership SHA256 to predecision provenance;
5. cryptographically bind every authoritative upstream evidence artifact used
   to reconstruct the candidate population;
6. record that no chromosome-integrity outcome has yet been generated.

The identity-bearing Stage 3 membership itself remains scratch-only.

Only its aggregate count and cryptographic fingerprint may later be frozen in
Git.

## Authoritative package evidence

For every Stage 3 candidate, current component evidence must be reconstructed
only from the already-frozen package selected by the Stage 1/Stage 2 evidence
resolution contract.

The accepted package classes are:

1. verified historical Project Finch cache packages;
2. ordinary BacSelect fresh-acquisition packages;
3. BacSelect fresh-recovery packages accepted by the frozen recovery evidence
   contract.

Stage 3 must preserve the exact distinction between these package classes.

A recovered fresh package remains a fresh package. Recovery does not make it
eligible for historical Project Finch adjudication reuse.

### Historical package evidence

Historical packages remain bound by the frozen historical cache-verification
artifact.

Historical cache-verification SHA256:

`7b2fa38ff2c1f43fc0536cabfa68091fdde9d4d3677092d49405bbac113fd752`

A historical package is eligible for historical adjudication reuse only when
its accession-level `cache_content_verification` state is exactly `pass`.

### Ordinary fresh package evidence

Ordinary fresh packages use their frozen candidate audit, component audit and
package-files evidence through the same verification contract already used by
Stage 1 and Stage 2.

### Recovered fresh package evidence

Recovered fresh packages use the frozen recovery evidence contract already
implemented and consumed by Stage 1.

The recovery evidence contains, per recovered batch:

- `candidate-sequence-audit.tsv`;
- `component-sequence-audit.tsv`;
- `acquisition-status.tsv`;
- `source-package-files.tsv`;
- `recovery-package-files.tsv`;
- `recovery-summary.json`.

Stage 1 already verifies the frozen recovery-summary identities, package
manifest identities, accepted batch set, candidate evidence and component
evidence before accepting a recovered candidate.

Stage 3 must reuse that same recovery-provider resolution and verification
boundary.

It must not substitute the ordinary-fresh `package-files.tsv` layout for the
recovery layout.

## Stage 1 source-evidence binding

Every Stage 3 candidate must remain bound to the source evidence already
verified in Stage 1 and carried into Stage 2.

The Stage 2 decision row contains the candidate's frozen
`source_evidence_sha256`.

Stage 3 must recompute the Stage 1 source-evidence SHA256 using the frozen
Stage 1 implementation and require exact equality with the value carried in
the Stage 2 decision row before chromosome evidence is interpreted.

This binds the Stage 3 package to the same candidate FASTA, package manifest,
Primary Assembly component identities, component lengths, component
topologies, and component sequence SHA256 values already used upstream.

A mismatch is a run-level fail-closed error.

## Primary Assembly component set

For each Stage 3 candidate, Stage 3 must reconstruct the package's
`sequence_report.jsonl`.

Every sequence-report row used by Stage 3 must report the exact current
canonical assembly accession.

Only rows whose assembly unit is exactly `Primary Assembly` are used as
chromosome-integrity component evidence.

Each such row must contain a non-empty versioned GenBank component accession.

Duplicate Primary Assembly component accessions are an error.

The set of Primary Assembly GenBank component accessions reconstructed from
`sequence_report.jsonl` must exactly equal the component set in the already
verified component-sequence audit for that candidate.

Missing components, additional components, duplicate components or component
version disagreement are errors.

Component accession matching for current BacSelect evidence is exact
versioned-accession matching.

Stage 3 must not weaken this to base-accession matching.

## Molecule-class evidence

For every Primary Assembly component, Stage 3 reads molecule classification
from the matching `sequence_report.jsonl` row.

The source field is NCBI sequence-report
`assignedMoleculeLocationType`.

The value supplied to
`source_chromosome_integrity.PrimaryComponentEvidence.molecule_class`
must be a non-empty string.

The frozen chromosome primitive recognizes chromosome components only when
this value is exactly:

`Chromosome`

Stage 3 must not infer chromosome identity from component names, accession
prefixes, organism identity, sequence length, GBFF definition text, or any
other field.

Missing, empty or malformed molecule-class evidence is a fail-closed error.

## GBFF record binding

For each Primary Assembly component, Stage 3 must resolve exactly one matching
GBFF record.

The current BacSelect sequence validator already requires the complete set of
GBFF `VERSION` accessions to equal the complete set of sequence-report GenBank
accessions.

Stage 3 preserves that exact versioned-accession matching rule.

Each matched GBFF record must therefore have a `VERSION` value exactly equal
to the sequence-report component accession.

Duplicate GBFF `VERSION` accessions, missing records, additional records or
version disagreement are errors.

## GBFF topology evidence

Stage 3 obtains current topology from the matched GBFF `LOCUS` record using
the already-frozen BacSelect sequence-validation semantics.

The topology must agree exactly with the topology stored in the verified
component-sequence audit.

Because all Stage 3 candidates have already passed sequence eligibility,
unsupported or unresolved topology must not be silently reinterpreted.

Any current disagreement between GBFF topology and frozen component-audit
topology is a fail-closed error.

## GBFF DEFINITION reconstruction

The current frozen sequence validator does not retain the GBFF `DEFINITION`
field in the component-sequence audit.

Stage 3 therefore reconstructs this field from the same already-verified GBFF
record.

This is an evidence-reconstruction step. It does not change the frozen
chromosome-integrity closure rule.

For one matched GBFF record, the `DEFINITION` value is reconstructed as
follows:

1. locate the record line whose field label is `DEFINITION` in the GenBank
   twelve-column field layout;
2. take the text following the first twelve columns on that line;
3. append immediately following continuation lines whose first twelve columns
   are spaces;
4. strip surrounding whitespace from each collected segment;
5. discard empty continuation segments;
6. join the collected non-empty segments with one ASCII space.

The resulting definition must be a non-empty string.

Missing, empty, duplicated or structurally malformed `DEFINITION` evidence is
a fail-closed error.

No substring rule is implemented by this reconstruction layer.

The completed definition string is passed unchanged to the frozen
chromosome-integrity primitive.

## Closure predicate

Stage 3 does not implement its own closure predicate.

The reconstructed topology and definition are supplied to the frozen
`source_chromosome_integrity` implementation.

That implementation defines closure support as:

- topology exactly equivalent to `circular` under its frozen normalization; or
- the standalone word `complete` in the GenBank definition,
  case-insensitively.

In particular, `incomplete`, `incompletely`, `completion` and `completely`
do not satisfy the standalone-word definition criterion.

The broader historical Project Finch substring test is not reused as the
current BacSelect closure predicate.

## Trigger

Stage 3 does not independently implement the chromosome-integrity trigger.

The frozen primitive triggers review only when:

1. the Primary Assembly contains at least two components whose molecule class
   is exactly `Chromosome`; and
2. at least one such chromosome component lacks closure evidence.

A trigger is a review condition and is not itself evidence that the deposited
chromosome set is fragmented.

A non-triggered candidate passes the chromosome-integrity layer without
consulting historical adjudication evidence.

## Frozen Project Finch adjudication artifact

The only historical chromosome-integrity adjudication artifact eligible for
reuse is:

Project Finch commit:

`24c75483c8fa6d1bcbaa9e32fe6c4c85efae0d97`

Artifact:

`validation/experiment-0/source-replicon-integrity-adjudications.tsv`

SHA256:

`def13131598e351d06c943f8a8e614e49b2c0b4bc55210ac7c9efd20f1f58828`

Before parsing any historical adjudication rows, Stage 3 must materialize or
read the artifact from that exact Project Finch commit and verify the exact
SHA256 above.

No network retrieval is required or permitted for this evidence.

The expected historical adjudication schema is:

- `review_order`;
- `canonical_genbank_assembly_accession`;
- `outcome`;
- `adjudication_reason`.

The canonical GenBank assembly accession is the lookup identity.

Duplicate canonical accessions are an error.

Only the frozen `outcome` field is supplied to the chromosome-integrity
primitive.

The historical adjudication reason is provenance only and does not alter the
BacSelect classification.

## Historical adjudication reuse

Historical Project Finch adjudication is considered only for a currently
triggered candidate.

Reuse requires all of the following:

1. the current canonical versioned GCA accession exactly matches the historical
   adjudication accession;
2. the candidate uses the verified historical Project Finch cache package;
3. accession-level historical cache verification is exactly `pass`;
4. the current candidate still triggers under the frozen BacSelect trigger and
   closure rule;
5. the exact accession is present in the frozen Project Finch adjudication
   artifact.

Fresh ordinary packages are not eligible for reuse.

Fresh recovery packages are not eligible for reuse.

Fallback-to-fresh packages are not eligible for reuse.

Unverified historical packages are not eligible for reuse.

Different assembly versions are not eligible for reuse.

Triggered candidates absent from the historical adjudication artifact are not
eligible for reuse.

No equivalence between different packages or assembly versions may be inferred.

## Historical outcome mapping

Stage 3 delegates historical outcome interpretation to the frozen chromosome
primitive.

The frozen mappings are:

- `RETAIN_CONFIRMED_MULTIPARTITE`
  -> chromosome-integrity `PASS`;
- `EXCLUDE_FRAGMENTED_CHROMOSOME_SET`
  -> `EXCLUDE_SOURCE_REPLICON_INTEGRITY`;
- `UNRESOLVED`
  -> `REVIEW_UNRESOLVED`.

A currently triggered candidate without exactly reusable historical
adjudication is `REVIEW_UNRESOLVED`.

No new manual, organism-aware, literature-based or identity-aware adjudication
is permitted during Stage 3.

## Candidate evaluation

After all current evidence has been verified and reconstructed, Stage 3
constructs one
`source_chromosome_integrity.PrimaryComponentEvidence`
object per Primary Assembly component.

The only values supplied are:

- `molecule_class`;
- `topology`;
- `definition`.

Before classification, Stage 3 calls the frozen
`source_chromosome_integrity.assess_trigger(...)`
function on the same `PrimaryComponentEvidence` collection to obtain the
trigger-accounting evidence retained in the Stage 3 decision table.

Stage 3 must not independently reimplement the chromosome-component or
closure-support counts.

The returned `TriggerAssessment` supplies:

- `chromosome_component_count`;
- `closure_supported_chromosome_count`;
- `closure_unsupported_chromosome_count`;
- `triggered`.

Stage 3 must require:

`closure_supported_chromosome_count + closure_unsupported_chromosome_count
== chromosome_component_count`

Where applicable, Stage 3 constructs
`source_chromosome_integrity.HistoricalReuseEvidence`
from the frozen package-source class, historical cache-verification state, and
frozen Project Finch adjudication artifact.

Stage 3 then calls the frozen
`source_chromosome_integrity.evaluate(...)`
function exactly once for each of the `68,278` Stage 3 candidates using the
same `PrimaryComponentEvidence` collection.

The returned `ChromosomeIntegrityDecision.triggered` value must exactly equal
the previously obtained `TriggerAssessment.triggered` value.

A disagreement is a run-level fail-closed error.

Each candidate must receive exactly one Stage 3 decision.

## Stage 3 decision output

Identity-bearing Stage 3 candidate decisions are scratch-only.

The production decision table must retain sufficient evidence for deterministic
audit, including at minimum:

- canonical versioned GCA accession;
- Stage 1 `source_evidence_sha256`;
- Stage 2 status;
- chromosome-component count;
- closure-supported chromosome-component count;
- closure-unsupported chromosome-component count;
- whether the chromosome-integrity trigger fired;
- whether historical adjudication was reused;
- Stage 3 status;
- Stage 3 reason.

The Stage 3 decision table must not be committed to Git before the selector
blinding boundary permits identity disclosure.

## Aggregate Stage 3 summary

After all candidate decisions are complete, the aggregate Stage 3 summary may
contain only non-identity-bearing information.

It must include at minimum:

- Stage 3 input candidate count;
- Stage 3 input membership SHA256;
- total decision count;
- triggered candidate count;
- non-triggered candidate count;
- historical-adjudication reuse count;
- counts by Stage 3 status;
- counts by Stage 3 reason;
- cryptographic identities of Stage 3 artifacts;
- explicit downstream-stage boundary flags.

The status accounting must satisfy:

`PASS + EXCLUDE_SOURCE_REPLICON_INTEGRITY + REVIEW_UNRESOLVED = 68,278`

The trigger accounting must satisfy:

`triggered + non-triggered = 68,278`

## Predecision provenance

Before evaluating the first candidate, production must atomically write
predecision provenance that binds:

- the production BacSelect commit;
- this prospective Stage 3 execution method identity;
- Stage 2 completion-evidence identity;
- Stage 2 decision-artifact identity;
- Stage 3 input count;
- Stage 3 input membership SHA256;
- Stage 1 source-evidence implementation identity;
- chromosome-integrity implementation identity;
- chromosome-integrity clarification identity;
- historical cache-verification identity;
- Project Finch historical adjudication artifact identity;
- authoritative acquisition/recovery evidence identities;
- the exact Stage 3 production implementation and wrapper identities.

At that predecision checkpoint it must explicitly state:

- chromosome-integrity outcomes have not yet been generated;
- taxonomy resolution has not been generated;
- the complete eligible universe has not been generated;
- holdout membership has not been generated;
- structural features have not been calculated;
- selector outcomes have not been calculated.

## Atomic execution

Production Stage 3 execution must use a new commit-specific output directory.

An existing final output directory is an error.

An existing partial directory is an error unless a separately frozen recovery
method explicitly authorizes its treatment.

Outputs are written to a partial directory first.

Only after complete internal validation may the partial directory be atomically
renamed to the final Stage 3 directory.

A failed or interrupted partial execution is preserved as evidence and is not
deleted, rewritten or silently reused.

## Fail-closed conditions

Production Stage 3 fails closed on any ambiguity that prevents deterministic
evaluation.

Run-level errors include, but are not limited to:

- Stage 2 decision SHA mismatch;
- Stage 2 candidate accounting mismatch;
- Stage 3 input count other than `68,278`;
- duplicate or malformed canonical GCA accession;
- source-evidence SHA mismatch;
- unresolved authoritative package provider;
- package-manifest identity mismatch;
- missing package evidence;
- package-file SHA or size mismatch;
- sequence-report assembly-accession mismatch;
- missing or duplicate Primary Assembly component;
- component-set mismatch;
- missing or malformed molecule class;
- GBFF component-set mismatch;
- GBFF VERSION mismatch;
- topology disagreement;
- missing, empty, duplicated or malformed GBFF DEFINITION;
- malformed historical cache-verification evidence;
- historical adjudication artifact SHA mismatch;
- duplicate historical adjudication accession;
- unknown historical adjudication outcome;
- malformed chromosome-integrity primitive input;
- incomplete decision accounting;
- attempted later-stage processing before Stage 3 completion.

No malformed evidence is converted into a candidate-level PASS.

## Blinding boundary

Stage 3 must not read or use:

- OPS identities;
- SR identities;
- selector distances;
- selector panels;
- selector panel membership;
- selector coverage results;
- selector outcome comparisons;
- structural-feature values;
- taxonomy outcomes not yet generated;
- final holdout membership not yet generated.

Organism identity, species identity, taxonomic name and literature knowledge are
not used for chromosome-integrity adjudication.

Identity-bearing Stage 2 rows may be read only by the frozen Stage 3 production
execution after the Stage 3 method, implementation and wrapper are frozen.

Candidate identities must not be printed by normal production logging.

Aggregate counts and cryptographic identities may be logged.

## Implementation and testing boundary

The Stage 3 production implementation must be developed and tested with
synthetic fixtures only.

Synthetic tests must cover at minimum:

- exact Stage 2 `CONTINUE` filtering;
- Stage 2 membership accounting;
- exact source-evidence SHA rebinding;
- ordinary fresh package resolution;
- recovered fresh package resolution;
- historical package resolution;
- exact versioned component matching;
- sequence-report/GBFF component-set disagreement;
- missing molecule class;
- non-`Chromosome` molecule classes;
- multiline GBFF DEFINITION reconstruction;
- missing DEFINITION;
- empty DEFINITION;
- exact standalone-word `complete` semantics through delegation to the frozen
  primitive;
- topology disagreement;
- non-triggered PASS;
- triggered historical reusable retain;
- triggered historical reusable exclusion;
- triggered historical reusable unresolved;
- triggered historical accession mismatch;
- triggered historical adjudication absence;
- triggered fresh package unresolved;
- triggered recovered-fresh package unresolved;
- triggered fallback-to-fresh package unresolved;
- malformed cache-verification state;
- malformed historical outcome;
- poisoned later-stage inputs that must never be consulted;
- deterministic output ordering;
- exact aggregate accounting;
- atomic finalization safeguards.

No real Stage 3 candidate may be evaluated during implementation testing.

The implementation, its tests and the production wrapper must each be frozen in
Git before production execution begins.

## Completion boundary

Successful Stage 3 execution does not authorize taxonomy execution by itself.

After production completion:

1. identity-bearing Stage 3 outputs remain scratch-only;
2. aggregate outputs and cryptographic identities are independently audited;
3. blinded Stage 3 completion evidence is generated;
4. that completion evidence is reviewed and frozen in Git;
5. only then may prospective Stage 4 taxonomy production execution begin.

No structural-feature calculation, holdout construction or selector-resolution
analysis is permitted during Stage 3.
