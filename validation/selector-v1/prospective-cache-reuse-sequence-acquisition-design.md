# BacSelect prospective cache-reuse and incremental sequence-acquisition design

## Status

**PROSPECTIVE CACHE-REUSE DESIGN — NO BACSELECT GENOME SEQUENCE FETCHED**

This design replaces an earlier uncommitted draft that proposed reacquiring all
70,477 metadata-retained assemblies.

That rejected draft was installed only as untracked local files, executed no
network request, generated no real sequence manifest, and was removed before
staging or commit.

No BacSelect genome sequence has yet been fetched for the selector-resolution
experiment.

## Frozen upstream state

The fresh NCBI source snapshot contains 70,850 records.

Frozen metadata eligibility retains 70,477 assemblies.

Frozen baseline membership identifies 15,445 metadata-retained assemblies
absent from the historical 55,306-genome BacSelect baseline.

Historical Project Finch sequence evidence contains 55,426 unique assembly
accessions.

The cache-overlap audit establishes:

- 55,151 current metadata-retained assemblies are present in the historical
  sequence snapshot;
- 15,326 current metadata-retained assemblies are not present in that snapshot;
- all 55,151 overlapping assemblies have historical candidate-sequence audit
  rows;
- 55,145 are historically sequence-eligible;
- 6 are historically sequence-ineligible because of ambiguous nucleotide
  content.

The six historical ineligible results remain valid source evidence if their
cache integrity passes. Reusing an ineligible result does not turn it into an
eligible genome.

## Scientific source universe versus acquisition mechanism

The scientific source-eligibility universe remains all 70,477
metadata-retained fresh-snapshot assemblies.

Cache reuse changes only how immutable sequence evidence is obtained.

It does **not** make baseline membership, historical cache membership, or
Project Finch membership into a BacSelect scientific eligibility criterion.

Every assembly is evaluated under the same frozen BacSelect sequence and source
rules whether its bytes come from verified historical evidence or a fresh
download.

## Historical cache candidates

The 55,151 overlapping canonical GCA accession.versions are **cache
candidates**, not automatically reusable evidence.

Historical evidence may be reused only after all of the following pass:

1. exact canonical GCA accession.version match;
2. fresh metadata says `current`;
3. fresh metadata says `Complete Genome`;
4. fresh BioSample matches historical expected BioSample;
5. fresh BioSample matches historical observed BioSample;
6. historical package/audit provenance is structurally complete;
7. every package file required by the historical `package-files.tsv` manifest
   exists at the recorded size;
8. every such package file is re-hashed and matches its recorded SHA256;
9. all batch-level provenance hashes reconcile;
10. the recorded historical snapshot-script identity is recoverable from
    Project Finch Git.

Failure of cache verification does **not** exclude the assembly. It moves that
assembly to the fresh-acquisition set.

## Historical cache evidence established before this design

Read-only audits established:

- 111/111 batches contain all required provenance/audit files;
- 55,426 candidate rows are unique;
- 166,844 package-manifest rows reconcile to existing files at recorded sizes;
- all 111 batches use NCBI Datasets 18.35.0;
- all 111 batches use environment lock SHA256
  `6d965c7c4f7db0464e4fba2434f85f1b7da3f7136790babca444888b6e6096cd`;
- all batch-level hashes for accession manifests, candidate audits, component
  audits, package-file manifests, dehydrated ZIPs, and attempt-origin records
  verify;
- four historical snapshot-script SHA256 identities are recorded, and all are
  recoverable from Project Finch Git.

The historical cache is referenced in place. BacSelect does not copy the
historical FASTA, GBFF, or sequence-report files into a second data tree.

## Fresh acquisition set

Before expensive content re-hashing, the provisional fresh-acquisition set is
15,326 assemblies.

Any cache candidate that fails full content verification is added to this
fresh-acquisition set before download manifests are frozen.

Thus:

`final_fresh_download_count = 15,326 + failed_cache_verification_count`

The design does not assume that `failed_cache_verification_count` is zero.

## Baseline-independent acquisition

The 15,445 assemblies absent from the historical BacSelect baseline are not the
download target definition.

This is important because:

- 119 assemblies absent from the frozen BacSelect baseline are already present
  in the historical Project Finch sequence snapshot;
- repeated-BioSample groups can cross the historical-cache/fresh-download
  boundary.

Cache status is therefore treated as an operational provenance property only.

## Repeated BioSamples

The fresh metadata universe contains:

- 47 repeated-BioSample groups;
- 96 members;
- 10 groups / 20 members entirely outside the historical cache;
- 37 groups / 76 members crossing the cache/fresh boundary;
- zero groups entirely within the cache.

All members of a repeated-BioSample group are fingerprinted together under the
same frozen topology-aware BacSelect rule after their sequence evidence has
passed either cache verification or fresh acquisition validation.

The source of the bytes does not alter fingerprint semantics.

## Pinned fresh-download software

NCBI Datasets CLI:

`18.35.0`

Environment lock SHA256:

`6d965c7c4f7db0464e4fba2434f85f1b7da3f7136790babca444888b6e6096cd`

The fresh sequence bundle is exactly:

- `genome`;
- `gbff`;
- `seq-report`.

Fresh download uses deterministic lexicographic GCA ordering and batches of
500 accessions.

At the provisional 15,326-target count this is 31 batches:

- 30 full 500-accession batches;
- one final 326-accession batch.

If failed cache verification increases the target count, the final deterministic
batch count is recalculated and frozen before network acquisition.

## Fresh download protocol

The exact scientific download arguments, excluding executable/environment
launcher and absolute paths, are:

```
download genome accession
--inputfile accessions.txt
--include genome,gbff,seq-report
--dehydrated
--no-progressbar
--filename dehydrated.zip
```

The dehydrated ZIP is integrity-checked before extraction.

Rehydration uses:

```
rehydrate
--directory package
--max-workers 10
--no-progressbar
```

Worker count is an operational transport setting, not a scientific source
criterion.

## Sequence validation

Whether cached or freshly acquired, every candidate must satisfy the already
frozen BacSelect sequence contract.

Only `Primary Assembly` components contribute to the source genome.

Every retained Primary Assembly component must reconcile:

- stable accession.version;
- sequence-report component identity;
- FASTA sequence;
- GBFF sequence;
- sequence length;
- topology;
- assigned molecule/location evidence required by the frozen structural
  definitions.

FASTA and GBFF nucleotide content must agree exactly.

Primary structural calculations require only A, C, G and T.

Non-ACGT Primary Assembly sequence is ineligible.

## Source structural integrity

The previously frozen Project Finch-derived rules remain unchanged:

1. exact duplicate Primary Assembly components: exclude;
2. fully contained linear Primary Assembly component: exclude;
3. full containment with all contained inner components circular: retained by
   this rule;
4. no duplicate/full containment: retained by this rule;
5. otherwise unresolved and fail closed.

## Chromosome-integrity cache

Historical chromosome-integrity adjudications may be reused only under the
already frozen requirement of identical canonical accession.version and
unchanged relevant source evidence.

No new identity-aware manual adjudication is introduced during the blinded
selector-resolution experiment.

## Storage and cleanup policy

BacSelect does not duplicate historical Project Finch sequence packages.

The historical snapshot remains immutable source evidence for this experiment.

Do not remove files referenced by historical package manifests or batch
provenance while BacSelect depends on them.

Temporary BacSelect download/extraction paths are removed after successful
atomic finalization.

Failed or partial fresh downloads are kept only long enough to preserve the
minimal failure record needed for diagnosis; incomplete sequence packages
cannot enter scientific analysis.

The historical `dehydrated.zip` files occupy negligible space relative to
FASTA/GBFF evidence and are retained because batch provenance binds them.

No obvious retry/partial debris was present in the historical snapshot at the
time of this design.

## Portability boundary

Project Finch cache reuse is an optimization for this prospective
selector-resolution experiment on the current validation backend.

It is **not** a dependency of the eventual BacSelect monthly public release
pipeline.

The production monthly release architecture must be able to acquire and
validate its own public NCBI inputs on a clean machine using project-controlled
code/environment/container identities.

## Required implementation gates before fresh download

Before any fresh BacSelect genome sequence is fetched:

1. freeze the full historical cache content-verification implementation;
2. re-hash all required historical package files;
3. freeze cache-pass/cache-fallback aggregate counts and whole-manifest hashes;
4. construct the final fresh-download accession manifests;
5. freeze and synthetically validate the fresh acquisition/sequence validator;
6. verify no implementation consumes OPS/SR panel identity or distance.

Only then may the incremental genome download begin.

## Prospectivity statement

At this design freeze:

- no BacSelect fresh genome sequence has been downloaded;
- the historical cache has not yet passed full file-content re-hashing;
- no fresh sequence-eligibility result has been generated;
- no repeated-BioSample fingerprint result has been generated;
- no fresh source structural-integrity result has been generated;
- no fresh taxonomy/species result has been generated;
- no structural-feature result has been generated;
- no OPS/SR external-holdout distance has been calculated;
- the selector-resolution decision remains unresolved.
