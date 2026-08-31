# BacSelect monthly chromosome-integrity execution

**PROSPECTIVE PORTABLE EXECUTION CONTRACT**

This method defines the portable production executor for the already-frozen
pure monthly chromosome-component-integrity contract.

The scientific rule is not reimplemented here.

## Position

The executor runs after monthly repeated-BioSample reconciliation.

Only Stage 5 `CONTINUE` accessions enter this stage.

The executor publishes:

- `chromosome-integrity/chromosome-integrity-decisions.tsv`;
- `chromosome-integrity/monthly-chromosome-integrity-record.json`;
- sibling `chromosome-integrity-completion.json`.

Partial execution uses:

- `chromosome-integrity.partial/`;
- `chromosome-integrity-materialization.partial/`;
- `.chromosome-integrity-completion.json.tmp`.

## Frozen scientific authority

The monthly pure contract is:

`src/bacselect/monthly_chromosome_integrity.py`

SHA256:

`2ad69041143e10f19501406aac59bee4c071f2e2139a2ad2641ba54c1395a749`

The chromosome primitive is:

`src/bacselect/source_chromosome_integrity.py`

SHA256:

`04f1b580ec9480a20f3679b7eb996da08a074c48ff246549df2e0ed20b97b9c0`

The frozen evidence reconstruction and evaluation helper is:

`src/bacselect/source_chromosome_integrity_execution.py`

SHA256:

`187816b76ae804ad2e682e036a5fb76528ac1762d6535062a566edd2fe6e4b9c`

Production execution must call
`evaluate_stage3_candidate()` for every Stage 5 `CONTINUE` accession.

## Stage 5 authentication

The Stage 5 executor is frozen at:

`validation/selector-v1/run_monthly_biosample_reconciliation.py`

SHA256:

`0787b77f2e0e734a0ec164fd9c020fd51fd8237355ae48c45e5c225666b9ee95`

The chromosome executor does not merely trust the Stage 5 completion receipt.

It reloads the authenticated Stage 4 context and reconstructs the frozen Stage
5 population and reconciliation from:

- Stage 4 decisions;
- current retained metadata;
- serialized Stage 5 decision rows.

The Stage 5 decision rows contain the exact BioSample, source-evidence SHA256
and topology-aware assembly fingerprint required to reconstruct the frozen
Stage 5 build.

The reconstructed Stage 5 decision bytes and record bytes must be byte-exact
matches to the published Stage 5 artifacts.

The Stage 5 completion receipt is then reconstructed from those independently
authenticated inputs and must also match byte-for-byte.

## Monthly package provenance is not Project Finch provenance

The cumulative monthly sequence-cache catalogue records BacSelect monthly
acquisition provenance:

- monthly release;
- source snapshot;
- Git commit;
- acquisition batch;
- sequence-acquisition completion;
- package-file manifest and readback identity.

It does not prove that a package is the historical Project Finch package.

A prior monthly BacSelect cache entry is therefore not classified as a
historical Project Finch package.

No accession is classified as historical merely because the same accession
existed in Project Finch.

The portable monthly executor supplies explicit historical evidence:

`uses_historical_project_finch_package = False`

for every monthly candidate.

Consequently, a currently triggered candidate that lacks another nonhistorical
resolution path is reported by the frozen primitive as:

`REVIEW_UNRESOLVED / NOT_HISTORICAL_PROJECT_FINCH_PACKAGE`.

Historical Project Finch adjudication is not loaded by monthly production.

The monthly executor has no Project Finch repository, historical package root,
historical cache-verification TSV, or historical adjudication artifact input.

## Current-origin package reconstruction

A current-origin accession is identified only when its catalogue provenance
release equals the current release.

The executor reuses the frozen Stage 4 `_current_batch_evidence()` authority.

The candidate bridge is rebuilt through the frozen Stage 4
`validate_candidate_bridge()` helper.

Every accession-scoped package row in the authenticated package manifest is
resolved beneath the current acquisition batch using the frozen manifest-path
resolver.

Every resolved file must be:

- a regular non-symlink file;
- exactly the authenticated size;
- exactly the authenticated SHA256.

The frozen evaluator then receives a `CandidateAudit` whose `batch_dir` is the
real current batch directory.

## Prior-origin package reconstruction

A prior-origin accession is one whose authenticated catalogue provenance
release predates the current release.

Future-origin provenance fails closed.

Prior batch evidence is loaded only through the mandatory authoritative-object
`load_batch_evidence()` route.

For every accession-scoped package row, the executor calls
`read_required_object()` with exact SHA256 and size.

There is no optional-object fallback.

The complete accession-scoped package is materialized beneath an isolated
candidate root as:

`<candidate-root>/package/<manifest path>`

using exclusive no-clobber writes.

The `CandidateAudit.audit_path` is placed directly beneath the candidate root,
making `CandidateAudit.batch_dir` exactly the candidate root.

The frozen resolver can therefore resolve exactly the accepted
`batch/package/<manifest path>` layout.

The materialized candidate root is deleted after evaluation.

## Full package, not FASTA-only

Stage 5 needed only the candidate FASTA to calculate the assembly fingerprint.

Chromosome-component integrity additionally requires the sequence report and
GBFF.

The Stage 6 executor therefore authenticates and, for prior-origin candidates,
materializes every accession-scoped package row.

The frozen evaluator remains responsible for selecting exactly one:

- `sequence_report.jsonl`; and
- accepted GBFF:
  - `genomic.gbff`, or
  - `<GCA>_efetch_components.gbff`.

It also independently verifies the FASTA, source-evidence SHA256, Primary
Assembly component set, component lengths, topology, molecule class and GBFF
component set.

## Scientific evaluation provenance

`Stage3CandidateEvaluation` is not accepted from disk and is not deserialized
from the monthly decision artifact.

Each evaluation object exists only as the direct return value of the frozen
`evaluate_stage3_candidate()` call made during the current executor run.

The pure monthly contract then validates the exact evaluation population,
source-evidence identities, accounting and allowed outcomes.

## Publication stability

Before publication and again at publication readback, the executor reloads and
reconstructs Stage 5.

The Stage 5 identity must remain byte-identical.

The executor also reauthenticates:

- every current-origin package file by path, size and SHA256;
- every prior-origin authoritative package object by size and SHA256;
- every current-origin batch through `_current_batch_evidence()`;
- every prior-origin batch through `load_batch_evidence()`.

A mutation in any of these inputs fails publication.

## Publication semantics

Scientific artifacts are first written to the partial stage with exclusive
creation and fsync.

Publication uses hard links into the canonical final stage.

No rename or replace operation is used.

The published files are read back and audited before the partial links are
removed.

If stage publication fails after the canonical directory is created, the
executor removes only hard links whose device and inode identities prove they
were created from the current partial artifacts. The partial artifacts are
preserved. An empty canonical directory created by the failed invocation is
then removed, allowing a deterministic retry. Unexpected or identity-changed
paths are never deleted automatically and cause cleanup to fail closed.

The completion receipt uses the same no-clobber, fsync, hard-link and readback
model. If completion publication fails, a canonical hard link is removed only
when its identity proves that it is the link created from the current temporary
receipt. The unchanged executor-created temporary receipt is then removed after
successful cleanup so that the completion step can be retried.

## Completion receipt

Schema:

`bacselect-monthly-chromosome-integrity-completion-v1`

Status:

`CHROMOSOME_INTEGRITY_EXECUTION_COMPLETE`

The receipt binds:

- release ID;
- source snapshot ID;
- execution Git commit;
- Stage 5 decision SHA256;
- Stage 5 record SHA256;
- Stage 5 completion SHA256;
- Stage 5 CONTINUE count and membership SHA256;
- chromosome decision count;
- triggered and non-triggered counts;
- historical-adjudication reuse count;
- PASS count;
- exclusion count;
- unresolved count;
- chromosome decision SHA256;
- chromosome record SHA256.

For portable monthly production,
`historical_adjudication_reuse_count` must be exactly zero.

## Downstream boundary

Only chromosome-integrity `PASS` rows may enter monthly taxonomy resolution.

`EXCLUDE_SOURCE_REPLICON_INTEGRITY` is terminal.

`REVIEW_UNRESOLVED` is withheld from downstream production selection.

No Stage 6 outcome can promote a Stage 5 `NONREPRESENTATIVE` or
`REVIEW_UNRESOLVED` accession.

## Portability and publication safety

The executor contains no:

- NCBI network access;
- Project Finch runtime dependency;
- historical Project Finch package root;
- historical adjudication lookup;
- Slurm command;
- institution-specific filesystem path;
- cloud-provider-specific API;
- optional authoritative-object fallback;
- automatic workflow enablement.

Real execution requires explicit:

`--authorize-real-execution`

The existing monthly GitHub workflow remains preflight-only until a later,
separate orchestration gate is intentionally frozen.
