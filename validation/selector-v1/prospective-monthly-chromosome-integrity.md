# BacSelect monthly chromosome-integrity contract

**PROSPECTIVE MONTHLY CONTRACT**

This contract freezes the pure monthly chromosome-component-integrity handoff
before a portable production executor is implemented.

It does not change the frozen BacSelect chromosome-integrity scientific rule.

## Position in the monthly release

The monthly order is:

1. metadata and sequence eligibility;
2. source truth, including duplicate and containment structural rules;
3. repeated-BioSample reconciliation;
4. chromosome-component integrity;
5. taxonomy resolution.

Only Stage 5 `CONTINUE` candidates enter chromosome-component integrity.

A Stage 5 `NONREPRESENTATIVE` or `REVIEW_UNRESOLVED` candidate must not be
evaluated here, and a later chromosome outcome must never promote it.

## Frozen scientific authority

The chromosome-integrity primitive remains:

`src/bacselect/source_chromosome_integrity.py`

Frozen SHA256:

`04f1b580ec9480a20f3679b7eb996da08a074c48ff246549df2e0ed20b97b9c0`

The evidence-reconstruction/evaluation helper remains:

`src/bacselect/source_chromosome_integrity_execution.py`

Frozen SHA256:

`187816b76ae804ad2e682e036a5fb76528ac1762d6535062a566edd2fe6e4b9c`

No monthly code may independently reimplement the closure predicate, trigger,
historical reuse rule, or historical outcome mapping.

## Frozen trigger

The review trigger is true only when:

1. at least two Primary Assembly components have molecule class exactly
   `Chromosome`; and
2. at least one such chromosome component lacks closure evidence.

Closure evidence remains present when either:

- GenBank topology is `circular`; or
- the GenBank DEFINITION contains the standalone word `complete`,
  case-insensitively.

The trigger is a review condition, not evidence of fragmentation.

## Frozen outcomes

The chromosome layer statuses remain:

- `PASS`;
- `EXCLUDE_SOURCE_REPLICON_INTEGRITY`;
- `REVIEW_UNRESOLVED`.

The exact accepted decision combinations are frozen by the monthly contract.

A non-triggered candidate is:

`PASS / NO_CHROMOSOME_INTEGRITY_TRIGGER`.

Exactly reusable historical Project Finch adjudication may produce:

- `PASS / HISTORICAL_RETAIN_CONFIRMED_MULTIPARTITE`;
- `EXCLUDE_SOURCE_REPLICON_INTEGRITY /
  HISTORICAL_FRAGMENTED_CHROMOSOME_SET`;
- `REVIEW_UNRESOLVED / HISTORICAL_UNRESOLVED`.

A currently triggered candidate without reusable historical adjudication
remains unresolved. The frozen unresolved reasons are retained without
reinterpretation.

## Historical reuse remains execution evidence

This pure monthly contract does not decide whether a package qualifies as a
historical Project Finch package and does not inspect the historical
adjudication artifact.

Those responsibilities remain execution-layer provenance.

Historical reuse remains permitted only under the already-frozen rule:
exact accession.version, historical Project Finch package origin, verified
historical cache content, current trigger still present, and exact accession
present in the frozen historical adjudication artifact.

Fresh, recovered-fresh, fallback-to-fresh, unverified, changed-version, and
unmatched candidates do not gain historical adjudication reuse.

## Stage 5 authentication

The monthly chromosome population is derived only from the authenticated Stage
5 BioSample decision artifact.

The exact Stage 5 decision SHA256 supplied by the authenticated Stage 5
completion receipt must equal the bytes supplied to this contract.

The chromosome population contains exactly the Stage 5 `CONTINUE` accessions.

For every continuing accession, the Stage 5 `source_evidence_sha256` is carried
forward unchanged.

The standalone chromosome decision auditor also revalidates every canonical
GenBank assembly accession using the frozen monthly Stage 5 accession
validator. Malformed, unversioned, non-GenBank or empty assembly identities
fail closed.

## Frozen evaluation object

The pure monthly contract accepts only
`source_chromosome_integrity_execution.Stage3CandidateEvaluation` objects.

The future executor must generate each object by calling the frozen
`evaluate_stage3_candidate()` helper against authenticated package evidence.

`Stage3CandidateEvaluation` is a data object, not proof of its own provenance.
Production execution must therefore never treat an arbitrarily constructed or
deserialized instance as scientific evidence. For every monthly candidate, the
executor must construct the evaluation directly from the frozen helper after
authenticating and reconstructing the required package evidence.

The pure contract verifies:

- exact Stage 5 population equality;
- sorted unique accession membership;
- exact Stage 5 source-evidence SHA256 equality;
- positive Primary Assembly component count;
- non-negative chromosome and closure counts;
- closure-supported plus closure-unsupported equals chromosome count;
- chromosome count does not exceed Primary Assembly count;
- chromosome/closure count accounting is internally consistent;
- decision trigger equals TriggerAssessment;
- the scientific trigger predicate itself is not recalculated by the monthly
  layer;
- the exact frozen status/reason/trigger/reuse combination.

## Monthly decision table

The deterministic table fields are:

- `canonical_genbank_assembly_accession`;
- `source_evidence_sha256`;
- `biosample_status`;
- `primary_component_count`;
- `chromosome_component_count`;
- `closure_supported_chromosome_count`;
- `closure_unsupported_chromosome_count`;
- `chromosome_integrity_triggered`;
- `historical_adjudication_reused`;
- `chromosome_integrity_status`;
- `chromosome_integrity_reason`.

`biosample_status` is always `CONTINUE`.

Boolean fields are serialized as `0` or `1`.

Integer fields use canonical decimal representation.

## Monthly record

Schema:

`bacselect-monthly-chromosome-integrity-record-v1`

Status:

`MONTHLY_CHROMOSOME_INTEGRITY_COMPLETE`

The record binds:

- release ID;
- source snapshot ID;
- origin Git commit;
- authenticated Stage 5 decision SHA256;
- Stage 5 monthly record SHA256;
- Stage 5 completion SHA256;
- exact Stage 5 CONTINUE count and membership SHA256;
- chromosome decision count and SHA256;
- triggered and non-triggered counts;
- historical-adjudication reuse count;
- chromosome status counts;
- chromosome reason counts.

The auditor reconstructs evaluation-shaped objects from the canonical decision
table only for structural, population, accounting and canonicalization checks.
Those reconstructed objects are not treated as proof that the frozen
chromosome evaluator generated the scientific result. The auditor requires
byte-exact record reproduction but does not claim to reproduce the scientific
trigger without the authenticated component evidence owned by the execution
layer.

## Execution boundary

This pure contract performs no:

- filesystem package discovery;
- sequence-report parsing;
- GBFF parsing;
- FASTA reconstruction;
- package-origin classification;
- historical-cache verification;
- historical adjudication lookup;
- network access;
- publication;
- cloud access;
- Slurm execution.

A separate portable monthly executor will authenticate and reconstruct those
inputs and call the frozen `evaluate_stage3_candidate()` helper.

## Downstream boundary

Only chromosome-integrity `PASS` candidates may proceed to monthly taxonomy
resolution.

`EXCLUDE_SOURCE_REPLICON_INTEGRITY` is terminal exclusion.

`REVIEW_UNRESOLVED` is terminal withholding for that monthly release.

A chromosome-integrity outcome must never promote a Stage 5 nonrepresentative
or unresolved candidate.
