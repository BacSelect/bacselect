# Fresh sequence acquisition-unavailable recovery design

## Status

**PROSPECTIVE RECOVERY CORRECTION — SELECTOR OUTCOME STILL BLOCKED**

The corrected fresh-sequence acquisition execution finalized 29 of 31 batches.
Two batches remained partial because one target in each batch could not supply
the sequence evidence required by the frozen validator.

The original source execution root is immutable for this recovery. Its 29
finalized batches and two failed `.partial` directories remain unchanged.

## Observed source condition

For each failed batch, the bulk NCBI Datasets download completed and targeted
rehydration recovery was exhausted. One assembly remained unresolved.

The frozen dehydrated package represented the unresolved target with exactly
one fetch destination:

`sequence_report.jsonl`

The expected size recorded by NCBI Datasets was zero. No genomic FASTA or GBFF
payload was present for that target.

Independent fresh single-accession controls on the validated acquisition node
returned successful, CRC-valid Datasets ZIP files but no candidate directory,
genomic FASTA, GBFF, or sequence report for either unresolved target. NCBI
summary metadata still described both records as current Complete Genome
assemblies.

This is therefore treated as source payload availability, not sequence
ineligibility.

## Terminal acquisition-unavailable rule

An unresolved target is classified as `acquisition_unavailable` only when all
of the following are true after the original recovery attempts:

1. the dehydrated package has exactly one fetch entry for the accession;
2. that entry is `data/<accession>/sequence_report.jsonl`;
3. NCBI Datasets records expected size zero for the entry;
4. the destination remains missing or empty;
5. no genomic FASTA is present for the accession;
6. no non-empty genomic GBFF is present.

Any other unresolved state remains fatal.

The rule is identity-independent. No accession-specific exception exists.

## Scientific boundary

`acquisition_unavailable` is not a form of sequence ineligibility. No sequence
eligibility decision is made for an unavailable target.

All 15,326 frozen requested targets remain explicitly accounted for as either:

- acquisition available, followed by sequence eligibility assessment; or
- acquisition unavailable, with sequence eligibility not assessed.

Only acquisition-available, sequence-eligible genomes can enter later
eligibility stages.

## Recovery architecture

Recovery is additive and does not modify the original execution evidence.

For each failed source batch, the recovery layer first fingerprints the
preserved source package and then copies that package into a commit-scoped
recovery workspace. All frozen candidate validation, including any inherited
GBFF EFetch fallback, operates only on the recovery copy.

The source package and the recovery package receive separate complete
file/hash manifests. Aggregate verification re-hashes both.

Target rows are obtained through the frozen worker's own `load_targets()`
function. This preserves its manifest validation and the internal
`source_biosample` compatibility alias used by the inherited validation engine,
rather than duplicating that adapter in the recovery layer.

Within the recovery copy the layer:

1. loads and normalizes targets through the frozen worker;
2. revalidates frozen metadata and fetch structure;
3. applies the terminal availability rule;
4. validates all acquisition-available targets with the frozen sequence
   validator;
5. writes an acquisition-status row for every requested accession;
6. writes candidate/component audits only for acquisition-available targets;
7. performs a full pre-final content audit against the `.partial` recovery
   directory;
8. atomically renames the recovery directory only after that audit passes;
9. re-audits the finalized recovery path.

The complete aggregate audit combines the 29 original finalized batches with
the two recovery overlays and re-hashes package content.

The aggregate must satisfy:

`requested = acquisition_available + acquisition_unavailable`

and:

`acquisition_available = sequence_eligible + sequence_ineligible`

before the stage can be frozen.

No structural features, selector identities, panel memberships, or selector
distances are used or generated.
