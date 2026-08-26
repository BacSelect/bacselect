# BacSelect selector-v1 prospective source-truth execution

## Status

**PROSPECTIVE STAGE 1 EXECUTION METHOD - NO REAL SOURCE-TRUTH OUTCOME GENERATED**

This method defines execution of Stage 1 of the frozen BacSelect selector-v1
post-sequence eligibility composition.

It is frozen before any current source-truth classification is generated for
the real provisional sequence-eligible universe.

This method does not alter any scientific eligibility, precedence, BioSample,
chromosome-integrity, taxonomy, baseline, holdout, feature, or selector rule.

## Repository binding

BacSelect parent commit before this execution method:

`ad67d34396f84c781fcd9f3c095539e057ebbba9`

Frozen BacSelect source-truth implementation:

- path: `src/bacselect/source_truth.py`
- SHA256: `6aac349e591daebfc2569c14633cc807b5d7186ed4ed3e79f37f6627f5184486`

Frozen post-sequence eligibility design SHA256:

`2c3222421d6b7bb0adbf86a6eb44dae0d0ec7fa1fffcec8bdc1bbf6a0c5d9460`

Frozen post-sequence composition clarification SHA256:

`e1399bd9d8a9f62c6cdb855a334da29840cb05df27724f08d6e010b56b7a332c`

Frozen post-sequence provenance refinement SHA256:

`1113bc8b95f60288c8a4767481467f9b2585969f1b8ea3dbd4183caa91710df5`

Frozen inherited Project Finch implementation-reference table SHA256:

`64ce497a58e344e0c7136db1aa1a48c5cefda3996c759ae10f18f30a12ff8638`

Frozen transitive Project Finch implementation-reference table SHA256:

`3b53fbf0ec945c1d7f5d4504028ba4d7f38a004764d45abd43cd149c12d62229`

Frozen final acquisition evidence SHA256:

`e4f4c354f5a78f4efc123eede2dbee475440785fa72cc59d233b4406e64103bc`

Frozen historical cache-verification evidence SHA256:

`a90c22713fa736dad2f8b5d7b0726c56a5735f4be3050ec2dbcc910391ca219e`

Frozen acquisition-unavailable recovery evidence SHA256:

`b9f773c031be0ee837f01163d054dc54176b4bf45be91c2cddb58989df221bec`

Frozen completed fresh sequence-validation recovery summary:

`/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/fresh-sequence-validation-recovery/f9bfb99ff163a73899ebb53ad7e1eff69a1f492e/source-7aba4b0a2aa22c05ce808bf9b5811606bd3d2293/fresh-sequence-validation-recovery-summary.json`

Frozen completed fresh sequence-validation recovery summary SHA256:

`e1a5eac79f62ae95651a4f83bff44636d7d0221c46b63c39490432eec67aa876`

The frozen completed summary records:

- acquisition available: 15,319;
- acquisition unavailable: 7;
- sequence eligible: 13,335;
- sequence ineligible: 1,984;
- component records: 35,227;
- package content verified: true;
- selector outcome generated: false.


## Scientific stage

This execution performs only:

1. reconstruction of retained Primary Assembly source components for each
   current sequence-eligible candidate;
2. exact complete-molecule duplicate assessment;
3. full-component containment assessment;
4. application of the already frozen BacSelect source-truth adjudication
   precedence.

It does not perform repeated-BioSample reconciliation.

It does not perform chromosome-integrity adjudication.

It does not perform taxonomy resolution.

It does not calculate structural features.

It does not read or calculate OPS or SR selector outcomes.

## Input population

The Stage 1 population is exactly the frozen provisional sequence-eligible
candidate universe:

- historical Project Finch cache sequence eligible: 55,145;
- fresh BacSelect sequence eligible: 13,335;
- total Stage 1 candidates: 68,480.

The 68,480 count is an execution invariant.

No candidate outside those already frozen sequence-eligible sets may enter
Stage 1.

No sequence-eligible candidate may be silently omitted.

The larger audit populations are evidence sources, not the Stage 1 population:

- historical candidate-sequence audit rows: 55,426;
- fresh candidate-sequence audit rows: 15,319.

Candidates already classified as sequence ineligible remain outside Stage 1.

The Stage 1 implementation must reconstruct the fresh 13,335-member
sequence-eligible set directly from the 31 accepted frozen
`candidate-sequence-audit.tsv` files and verify that:

- exactly 15,319 acquisition-available fresh candidate records are represented;
- exactly 13,335 have frozen `sequence_eligibility` equal to eligible;
- exactly 1,984 have frozen `sequence_eligibility` equal to ineligible;
- the two counts sum exactly to 15,319;
- the resulting fresh Stage 1 membership contains exactly 13,335 unique
  canonical versioned GCA accessions.

The identity-bearing reconstructed membership remains outside Git. Its
deterministically ordered SHA256 fingerprint must be recorded in production
provenance before source-truth classification begins.

No accession may enter or leave the reconstructed fresh Stage 1 population
because of a source-truth result.

## Historical evidence root

Canonical historical sequence-evidence root:

`/NGS/scratch/EXT/Rhys_wkdir/project-finch/experiment-0/ncbi-sequence-validation-snapshot`

Expected historical evidence structure:

- 111 `candidate-sequence-audit.tsv` files;
- 111 `component-sequence-audit.tsv` files;
- 111 `package-files.tsv` files.

Frozen historical candidate-audit aggregate identity:

`e6aad9f3adef78f8ce12228eee7d61d801643dd3cfbf11087f41b76c3bad7d37`

The completed BacSelect historical-cache content-verification artifact is:

`/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/historical-cache-verification/e6ab34e64cdb949813e533550e19dababd1d80ab/aggregate/historical-cache-content-verification.tsv`

Its frozen SHA256 is:

`7b2fa38ff2c1f43fc0536cabfa68091fdde9d4d3677092d49405bbac113fd752`

A historical candidate may enter Stage 1 only when its frozen candidate audit
is sequence eligible and its historical package remains covered by the frozen
successful BacSelect cache-content verification.

## Fresh evidence roots

Ordinary fresh production root:

`/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/fresh-sequence-validation/7aba4b0a2aa22c05ce808bf9b5811606bd3d2293`

Ordinary accepted batches are:

- `batch-001` through `batch-023`;
- `batch-025` through `batch-027`;
- `batch-029` through `batch-031`.

Those 29 accepted batch directories contain:

- `candidate-sequence-audit.tsv`;
- `component-sequence-audit.tsv`;
- `package-files.tsv`.

The accepted recovery root is:

`/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/fresh-sequence-validation-recovery/f9bfb99ff163a73899ebb53ad7e1eff69a1f492e/source-7aba4b0a2aa22c05ce808bf9b5811606bd3d2293`

The recovery root contributes exactly:

- `batch-024`;
- `batch-028`.

The misspelled path component
`fresh-sequence-valdation-recovery` is not an accepted evidence root.

## Recovery evidence identities

For `batch-024`:

- candidate audit SHA256:
  `9c202f0610450df68ffc966274846ba72a55b6f0a4ff8ff54476f8fef0ca344e`;
- component audit SHA256:
  `a02c64c5d36e63bd5b1bc361441660c330be55a9a3d18d6fd314fff8274057c5`;
- source package manifest SHA256:
  `b5d7983fe6387d71cb528fed7b1faf0501102a167d2fc52e6750266771f6ae7f`;
- recovery package manifest SHA256:
  `b5d7983fe6387d71cb528fed7b1faf0501102a167d2fc52e6750266771f6ae7f`;
- recovery summary SHA256:
  `ffa558518e70f14631696421f01619696aad4dc36cb84ae2e9a00a635cd2995d`.

For `batch-028`:

- candidate audit SHA256:
  `11ceb2c7dbe3c10b3a8d20432b3b7b9dc50fb92177e81955339425d70cd1ad1e`;
- component audit SHA256:
  `8df7fd0989d8f42f2e8475454ed11101077ffff2dedbcc1035b8f9291fdda38f`;
- source package manifest SHA256:
  `667eb533e8936432fa57d4cebc546eb85fb70c7efcd3a039e517da210cc3ab37`;
- recovery package manifest SHA256:
  `667eb533e8936432fa57d4cebc546eb85fb70c7efcd3a039e517da210cc3ab37`;
- recovery summary SHA256:
  `6856e521986693c12faf4e0da0e5063871eaceac817fb46b925b9c4d64eabe36`.

For each recovery batch, the source and recovery package manifests must remain
byte-identical at execution preflight.

## Source evidence reconstruction

Source truth is evaluated over the candidate's retained NCBI
`Primary Assembly` components only.

Auxiliary assembly-unit components must not enter source-truth comparison.

The execution implementation must reconstruct the actual Primary Assembly
component sequences from the frozen, content-verified source package.

The implementation must not infer source truth from component hashes alone.

Before classification, source sequence evidence must be checked against the
frozen sequence-validation evidence, including component identity, sequence
length, topology, and SHA256.

Any disagreement between the live scratch evidence and its frozen audit or
package manifest is a run-level fail-closed error.

No changed source package may silently be accepted.

## Frozen source-truth semantics

For every candidate, all retained Primary Assembly components are compared
under the frozen BacSelect implementation.

The complete-molecule duplicate semantics include:

- exact forward equivalence;
- exact reverse-complement equivalence;
- circular rotation equivalence;
- circular reverse-complement rotation equivalence.

Full containment uses the frozen orientation- and topology-aware BacSelect
semantics, including origin-independent treatment of circular molecules.

The adjudication precedence is exactly:

1. one or more exact duplicate complete molecules:
   `EXCLUDE_SOURCE_TRUTH / EXACT_DUPLICATE_PRIMARY_COMPONENTS`;
2. otherwise, at least one fully contained linear inner component:
   `EXCLUDE_SOURCE_TRUTH / LINEAR_COMPONENT_FULLY_CONTAINED`;
3. otherwise, containment involving only circular inner components:
   `SUITABLE / CIRCULAR_CONTAINMENT_RETAINED`;
4. otherwise, unclassifiable containment topology:
   `REVIEW_UNRESOLVED / UNRESOLVED_SOURCE_TRUTH`;
5. otherwise:
   `SUITABLE / NO_SOURCE_REDUNDANCY`.

No threshold based on genome size, component size, containment fraction,
organism identity, species identity, accession identity, architecture class,
baseline membership, panel membership, or selector outcome may alter the
classification.

## Project Finch provenance boundary

The Project Finch references frozen in the two post-sequence implementation
tables are algorithmic provenance only.

Historical Project Finch source-truth membership is not imported.

The current BacSelect 68,480-candidate universe is recomputed prospectively.

Before production execution, the Stage 1 implementation must verify the frozen
Project Finch source-truth worker, aggregate, adjudicator, containment driver,
production wrapper, and associated tests against their recorded commit and
SHA256 identities.

## Stage 1 implementation boundary

A dedicated BacSelect Stage 1 implementation must be written and tested on
synthetic fixtures before it is allowed to read real candidate rows.

The implementation must be Git-frozen before production execution.

Synthetic tests must cover at least:

- no redundancy;
- exact duplicate;
- reverse-complement duplicate;
- circular-rotation duplicate;
- circular reverse-complement duplicate;
- contained linear inner component;
- contained circular inner component;
- containment across a circular outer origin;
- unresolved containment topology;
- multiple-component precedence;
- malformed sequence;
- unsupported topology;
- sequence-evidence SHA mismatch;
- missing package evidence;
- auxiliary Assembly-unit exclusion;
- deterministic output ordering;
- exact Stage 1 population accounting.

Tests must include independent-oracle checks that are not simple calls back
into the production adjudication function.

No real candidate row may be processed while this implementation is being
developed or tested.

## Production output

All identity-bearing Stage 1 outputs are written outside Git under a new,
commit-bound scratch execution root.

At minimum the production output must contain:

- one deterministic candidate-level source-truth decision table;
- sufficient deterministic relation evidence to reproduce each decision;
- a content/provenance manifest;
- aggregate summary;
- execution provenance.

Candidate-level output must preserve:

- canonical versioned GCA accession;
- frozen source-evidence identity;
- Primary Assembly sequence-set fingerprint;
- duplicate relation count;
- containment relation count;
- source-truth status;
- source-truth reason.

Identity-bearing Stage 1 output must not be committed to Git.

## Determinism and completeness

Candidate-level output is ordered deterministically by canonical versioned GCA
accession.

Relation evidence has a documented deterministic ordering.

Exactly 68,480 candidates must receive exactly one Stage 1 terminal status.

The aggregate counts across:

- `SUITABLE`;
- `EXCLUDE_SOURCE_TRUTH`;
- `REVIEW_UNRESOLVED`

must sum exactly to 68,480.

Any duplicate accession, missing accession, unexpected accession, evidence
mismatch, malformed required field, or incomplete classification fails the run.

## Blinding boundary

Stage 1 must not use:

- BioSample identity for any scientific decision;
- organism TaxID;
- species identity;
- taxonomy-resolution output;
- chromosome-integrity outcome;
- baseline membership;
- external holdout membership;
- structural features;
- OPS ladder membership;
- SR ladder membership;
- OPS/SR distances;
- panel identities;
- selector coverage;
- selector outcome.

Accessions are permitted only as source-evidence keys and for deterministic
output identity/order.

No Stage 2 repeated-BioSample result may be generated during Stage 1.

## Git freeze after successful execution

After production execution and independent audit, Git may contain only
non-identity-bearing Stage 1 evidence such as:

- Stage 1 candidate count;
- status and reason counts;
- SHA256 of the identity-bearing candidate decision table;
- SHA256 of relation evidence;
- SHA256 of production provenance;
- implementation and execution identities;
- explicit statements that Stage 2, chromosome integrity, taxonomy,
  complete-universe membership, holdout membership, structural features and
  selector outcomes have not been generated.

No accession, BioSample, organism TaxID, species identity or candidate-level
source-truth outcome is committed before the blinded selector decision.
