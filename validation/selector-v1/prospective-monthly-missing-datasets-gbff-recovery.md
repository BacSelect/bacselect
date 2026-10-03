# Monthly missing-Datasets-GBFF recovery

## Status

**PROSPECTIVE RECOVERY CORRECTION — SELECTOR OUTCOME STILL BLOCKED**

This recovery design is frozen after a production Stage 3B transport package
exposed a previously unrepresented NCBI Datasets payload state, but before any
recovery EFetch request is executed and before any selector outcome is
generated.

The source monthly production execution remains immutable.

## Scope

The correction addresses an identity-independent acquisition condition in which
NCBI Datasets successfully returns and hydrates a requested Complete Genome
assembly, including genomic FASTA and sequence report, but the dehydrated
Datasets manifest itself contains no GBFF fetch entry and therefore no Datasets
GBFF can be hydrated.

This is an acquisition-source limitation. It is not sequence ineligibility and
does not change the frozen Stage 2 target set.

No accession-specific exception is permitted.

## Source evidence

The original failed monthly Stage 3B `.partial` directory is immutable source
evidence.

Recovery must never:

- edit the source package;
- add files to the source package;
- rename files inside the source package;
- delete the source partial;
- reinterpret the source package as successfully completed; or
- disguise recovered EFetch evidence as an NCBI Datasets GBFF.

Before recovery, a complete source-package content manifest must be recorded.
The source package must be re-hashed during recovery audit.

## Recovery trigger

A target is eligible for this recovery transport only when all of the following
are established from the preserved source evidence:

1. the accession belongs to the frozen monthly Stage 2 target batch;
2. monthly metadata validation succeeds for the target;
3. exactly one genomic FASTA is present after exclusion of NCBI-derived
   CDS/RNA FASTAs;
4. exactly one non-empty `sequence_report.jsonl` is present;
5. zero NCBI Datasets GBFF files are present;
6. the frozen NCBI Datasets `fetch.txt` contains no GBFF destination for the
   accession;
7. all fetch entries that are present for the accession are completely
   hydrated;
8. the sequence report supplies GenBank component accessions;
9. the failure is therefore missing requested annotation transport rather than
   incomplete hydration.

Any other state remains fatal.

The trigger is defined by evidence state, never by accession identity.

## Recovery workspace

Recovery is additive.

The preserved source package is copied into a commit-scoped recovery workspace
outside the ordinary `sequence-acquisition/` batch namespace.

The recovery root is:

`sequence-acquisition-recovery/<recovery-commit>/source-<source-production-commit>/`

All writes, including recovered sequence annotation and provenance, occur only
inside that recovery workspace.

## EFetch transport

The only additional transport authorized by this correction is NCBI EFetch
against `nuccore`.

Requests are constructed from the exact GenBank component accessions recorded
by the preserved NCBI Datasets sequence report.

The retrieval uses:

- database: `nuccore`;
- return type: `gbwithparts`;
- return mode: `text`;
- bounded request chunks;
- bounded retry attempts;
- explicit request/response provenance;
- SHA256 for every response and for the combined recovered GBFF;
- atomic `.partial` file replacement.

The recovered files retain explicit recovery identities:

- `<GCA>_efetch_components.gbff`;
- `<GCA>_efetch_components.json`.

They must never be renamed to `genomic.gbff`.

## Recovery scientific validation

The ordinary monthly Stage 3A validator remains unchanged.

A separate recovery validator must apply the same scientific invariants while
explicitly accepting the recovery GBFF source.

For every recovered candidate it must prove:

1. sequence-report component set equals FASTA component set;
2. recovered GBFF component set equals the sequence-report component set;
3. FASTA and recovered GBFF component lengths agree exactly;
4. any supplied sequence-report lengths agree;
5. FASTA sequence and recovered GBFF ORIGIN sequence agree exactly for every
   component;
6. topology is derived from the recovered GBFF using the same vocabulary and
   rules as ordinary monthly Stage 3A;
7. ambiguous-nucleotide and topology eligibility rules are unchanged.

Recovery changes annotation transport only. It does not change sequence
eligibility mathematics.

## Batch validation

A recovered batch must still account for every frozen Stage 2 target in its
original order.

Candidates not requiring recovery must reproduce the ordinary monthly Stage 3A
candidate and component audit rows exactly.

The recovered candidate must use the same audit schemas and scientific fields,
with its GBFF provenance remaining explicitly recoverable from the recovery
package and recovery record.

A complete recovery package manifest must be generated after recovery.

The recovery directory is finalized atomically only after full pre-final
validation passes, and the finalized directory is then re-audited.

## Monthly Stage 3 authority resolution

The ordinary monthly completion executor currently requires one ordinary final
directory for every expected batch and rejects all partials.

This correction therefore requires an explicit recovery-aware authority
resolver.

For each expected monthly batch, exactly one authoritative evidence provider
must be selected:

- `fresh`: an ordinary successfully finalized Stage 3B batch; or
- `fresh-recovery`: an accepted recovery overlay bound to one preserved failed
  source partial.

The resolver must fail closed for:

- neither provider;
- both providers;
- multiple recovery providers;
- a recovery without its exact preserved source partial;
- a recovery whose source fingerprints differ;
- an unexpected partial;
- an unexpected batch;
- a recovery for a batch whose ordinary source execution finalized.

No provider is selected by modification time, directory ordering or heuristic
discovery.

## Completion and cache catalogue

The monthly acquisition-completion and cache-catalogue execution layers must
use the same authoritative batch-resolution contract.

Both layers must independently revalidate the resolved batch evidence.

The completion evidence must preserve whether each batch was supplied by
`fresh` or `fresh-recovery` and cryptographically bind the recovery record when
recovery is used.

Cache-catalogue provenance must preserve that source class.

A recovered fresh package remains fresh recovery downstream.

## Downstream compatibility

Existing downstream BacSelect contracts already recognize `fresh-recovery` as
a distinct fresh-package class.

Recovery does not make a candidate historical and must never make it eligible
for historical Project Finch adjudication reuse.

The recovered package remains subject to independent downstream component,
length, topology, source-evidence and package-integrity checks.

## Prospectivity and blinding

At this checkpoint:

- no recovery EFetch request has been executed;
- no recovered monthly package has been generated;
- no selector outcome has been generated;
- no structural feature has been generated from the recovery;
- the frozen Stage 2 target population is unchanged;
- the ordinary monthly Stage 3A validator is unchanged;
- the production Stage 3B source evidence is unchanged.

Implementation and synthetic tests are developed only after this recovery
contract is frozen.
