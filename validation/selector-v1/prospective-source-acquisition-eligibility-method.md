# BacSelect selector-v1 prospective source acquisition and eligibility method

## Status

**PROSPECTIVE METHOD — NO FRESH BACSELECT SOURCE SNAPSHOT QUERIED**

This method freezes the BacSelect-specific source acquisition and eligibility
rules needed by the external OPS-versus-SR selector-resolution experiment.

The repository identity immediately before this method is installed is:

`12ce2ba94c6c998775e84cca54987118b2cb7d66`

The prospective selector-resolution design SHA256 is:

`2584fddf1f06562d48abd990372ec70ea1f48da0962b1f710afb1d93e2c3223a`

No fresh BacSelect NCBI source-universe query has been executed for the
selector-resolution experiment at the time this method is frozen.

## Reuse of Project Finch source validation

BacSelect reuses the validated source-genome concepts developed in Project
Finch where those concepts are independent of the historical GTDB R232
candidate-discovery step:

- canonical versioned GenBank assembly accessions;
- explicit accession reconciliation;
- repeated-BioSample reconciliation;
- NCBI `Primary Assembly` as the source-genome boundary;
- component accession, sequence, checksum, length and topology validation;
- A/C/G/T-only eligibility for structural calculations;
- exact duplicate Primary Assembly component exclusion;
- fully contained linear Primary Assembly component exclusion;
- topology-aware source-genome fingerprints;
- chromosome-component integrity review triggers;
- fail-closed handling of unresolved source truth.

BacSelect does not reuse the Project Finch GTDB R232 discovery pool. BacSelect
discovers its fresh source universe directly through NCBI Datasets.

## Frozen NCBI Datasets client

The selector-resolution source snapshot uses:

`ncbi-datasets-cli 18.35.0`

The historical Project Finch environment definition used to establish this
pin has SHA256:

`a573221740b5c479e3078d13885ce91727eb882dde070ff4ba57ee641ffc4b71`

The Project Finch explicit linux-64 environment lock copied into the BacSelect
repository has SHA256:

`6d965c7c4f7db0464e4fba2434f85f1b7da3f7136790babca444888b6e6096cd`

BacSelect owns its copied lock after this prospective method is committed.
The external holdout snapshot must not silently upgrade to a later Datasets
client.

## Candidate discovery query

The taxon is NCBI Taxonomy ID `2` (Bacteria).

The exact discovery command, apart from paths and the environment launcher, is:

```
datasets summary genome taxon 2 \
    --assembly-source GenBank \
    --assembly-level complete \
    --assembly-version current \
    --mag exclude \
    --exclude-multi-isolate \
    --limit all \
    --as-json-lines
```

The command does **not** use `--exclude-atypical`.

The raw JSON Lines response is retained byte-for-byte as source provenance.

Standard error is retained separately.

The acquisition record must bind:

- BacSelect Git commit;
- prospective method SHA256;
- NCBI Datasets version;
- environment-lock SHA256;
- exact command;
- start and finish UTC timestamps;
- raw stdout SHA256 and byte count;
- raw stderr SHA256 and byte count;
- exit status.

A non-zero exit status fails closed and the incomplete snapshot is not eligible
for downstream use.

## Assembly-status correction frozen before acquisition

The BacSelect scientific specification previously stated that the returned
assembly status must be `latest`.

That statement is incorrect for the NCBI Datasets genome assembly report
schema used here.

The current NCBI Datasets schema defines the `assemblyInfo.assemblyStatus`
enumeration as:

- `current`;
- `previous`;
- `suppressed`;
- deprecated `retired`;
- unknown.

Project Finch frozen NCBI records also used `current`.

For BacSelect v1 the discovery query still uses CLI
`--assembly-version current`, but a retained record must additionally have:

`assemblyInfo.assemblyStatus == "current"`

Any returned `previous`, `suppressed`, `retired`, unknown, missing or
unrecognized status is ineligible and is recorded explicitly.

This correction is frozen before the first fresh source-universe query and
before any external-holdout selector outcome exists.

## Canonical assembly identity

Only a versioned GenBank accession matching:

`^GCA_[0-9]+\.[0-9]+$`

is eligible as the canonical BacSelect assembly identifier.

A paired RefSeq `GCF_` record is not an independent candidate.

The discovery output must contain unique retained canonical GCA accessions after
all reconciliation stages.

## Complete-genome and source-category checks

A candidate retained from the discovery response must independently reconcile
to the intended query:

- bacterial taxon descendant of taxid 2;
- GenBank source;
- assembly level Complete Genome;
- current assembly status;
- non-MAG;
- non-multi-isolate.

If the returned metadata cannot establish the required state, the candidate
fails closed.

## Atypical assembly warnings

BacSelect does not exclude all assemblies marked atypical.

NCBI Genome Notes currently defines, among others, the warning categories
`Chimeric`, `Contaminated`, and `Mixed culture`.

Historical frozen Project Finch NCBI records contained lower-case warning
strings including `contaminated`.

For BacSelect warning comparison, each value in
`assemblyInfo.atypical.warnings` is normalized by:

1. requiring a string;
2. removing leading and trailing ASCII whitespace;
3. applying Unicode `casefold()`.

No punctuation, internal whitespace or semantic rewriting is performed.

The automatic exclusion set is exactly:

- `chimeric`;
- `contaminated`;
- `mixed culture`.

A candidate carrying any of these normalized warnings is ineligible.

Other atypical warnings are retained at this stage unless another frozen
eligibility rule excludes the candidate.

In particular, unusual genome length, environmental origin, unverified source
organism, low-quality-sequence metadata, or an atypical flag by itself is not
an automatic BacSelect exclusion.

All raw atypical metadata and warnings are preserved.

An unrecognized warning is recorded but does not automatically alter
eligibility. The warning vocabulary may not be expanded after holdout outcomes
are known.

## BioSample requirement

Every candidate must carry exactly one usable accession-like INSDC BioSample
identifier matching one of:

- `SAMN[0-9]+`;
- `SAMEA[0-9]+`;
- `SAMD[0-9]+`.

Missing, malformed, or ambiguous BioSample identity fails closed.

## Repeated BioSamples

Repeated BioSample identity is a reconciliation trigger, not proof of duplicate
biological material.

After source sequences are frozen, all current eligible assemblies within a
repeated-BioSample group receive topology-aware source-genome fingerprints over
their retained Primary Assembly components.

If all candidate source-genome fingerprints in the group are exactly
identical, retain one deterministic representative: the lexicographically
smallest canonical GCA accession. Record the remaining accessions as duplicate
representations.

If candidate source-genome fingerprints differ, the group is unresolved for
the blinded selector-resolution experiment and all members of that repeated
BioSample group are withheld from the decision holdout.

No manual accession- or organism-aware reconciliation is introduced after
selector outcomes are known.

A future production release may use a separately frozen reconciliation
procedure, but that procedure cannot retroactively change this external
holdout.

## Source-genome boundary

The BacSelect source genome consists only of nucleotide components assigned by
NCBI to the canonical GenBank assembly's `Primary Assembly` unit.

Additional assembly units in the data package are preserved as provenance but
do not contribute to structural features, source-genome fingerprints or
selection geometry.

## Sequence eligibility

Every retained Primary Assembly component must:

- reconcile to the expected assembly component;
- have a stable accession.version;
- have a frozen sequence checksum and length;
- contain only A, C, G and T for primary structural calculations;
- have sufficient topology metadata;
- have sufficient assigned-molecule/location metadata for the frozen structural
  definitions.

Any unresolved component fails closed.

## Source structural-integrity rules

The following Project Finch source-truth rules are carried forward unchanged:

1. exact duplicate Primary Assembly components:
   `EXCLUDE_SOURCE_TRUTH`;
2. a fully contained inner Primary Assembly component with linear topology:
   `EXCLUDE_SOURCE_TRUTH`;
3. full containment where all contained inner components are circular:
   retained by this rule;
4. no duplicate components and no full component containment:
   retained by this rule;
5. otherwise:
   unresolved and fail closed.

The evaluation occurs before structural-feature coverage outcomes.

## Chromosome-component integrity trigger

A candidate triggers chromosome-component integrity review when:

1. its Primary Assembly has at least two components classified as Chromosome;
   and
2. at least one chromosome component lacks closure evidence.

Closure evidence is present when either:

- GenBank LOCUS topology is circular; or
- the GenBank definition explicitly indicates a complete sequence.

The absence of closure evidence is a review trigger, not direct evidence of
fragmentation.

For the blinded external selector-resolution experiment:

- an exact cached adjudication may be reused only for the identical canonical
  assembly accession.version and unchanged relevant source evidence;
- otherwise a newly triggered candidate is classified unresolved and withheld
  from the decision holdout.

This deliberately fails closed rather than introducing new identity-aware
manual adjudication during the blinded selector-resolution phase.

## Species resolution

Species grouping is resolved using a frozen NCBI Taxonomy snapshot acquired for
the same fresh source snapshot.

For each retained candidate:

1. begin from its structured NCBI Taxonomy ID;
2. normalize merged TaxIDs through the frozen taxonomy snapshot;
3. traverse the lineage;
4. use the first ancestral taxon whose rank is exactly `species`.

Deleted, missing, cyclic or otherwise unresolved taxonomy fails closed.

Species names are descriptive only. The species TaxID is the grouping identity
and never a numerical selector score.

The taxonomy snapshot identity and acquisition provenance must be frozen before
the holdout adequacy gate and before structural-feature selector outcomes.

## Resolution-holdout eligibility boundary

The external decision holdout contains only fresh-snapshot candidates that:

1. satisfy every frozen source-discovery rule;
2. satisfy accession and warning rules;
3. satisfy BioSample reconciliation;
4. satisfy Primary Assembly sequence eligibility;
5. satisfy source structural-integrity rules;
6. do not remain unresolved under the chromosome-component trigger;
7. have resolved frozen species taxonomy; and
8. are absent from the frozen 55,306-genome BacSelect baseline.

No candidate is included or excluded using OPS/SR distance or any structural
coverage outcome.

The complete eligible fresh-universe manifest and the external-holdout
membership must be frozen before structural-feature outcome generation.

## Final 300/2400 feature architecture

The production BacSelect selector-v1 structural feature schema uses the final
prospectively selected repeat scales 300 bp and 2400 bp, not the historical
Project Finch 150/400 scales.

The final twelve coordinates are:

1. total genome length;
2. whole-genome GC fraction;
3. replicon count;
4. non-chromosomal replicon count;
5. non-chromosomal sequence fraction;
6. non-unique canonical 300-mer fraction;
7. non-unique canonical 2400-mer fraction;
8. maximum canonical 300-mer multiplicity;
9. maximum canonical 2400-mer multiplicity;
10. longest exact repeat length;
11. inter-replicon shared canonical 300-mer fraction;
12. inter-replicon shared canonical 2400-mer fraction.

The public scientific specification is corrected to this final architecture
before the fresh selector-resolution source snapshot is queried.

## Required implementation validation

Before first network execution, the BacSelect implementation must test at
minimum:

- exact construction of the frozen Datasets query;
- Datasets version mismatch fails closed;
- GCA accession validation;
- `current` assembly status retained;
- `previous`, `suppressed`, `retired`, missing and unknown statuses excluded;
- automatic exclusion of normalized `chimeric`, `contaminated`, and
  `mixed culture`;
- non-listed atypical warnings are not automatically excluded;
- malformed BioSample fails closed;
- exact repeated-BioSample fingerprints deduplicate deterministically;
- nonidentical repeated-BioSample groups are withheld;
- Primary Assembly boundary excludes auxiliary assembly units;
- non-ACGT sequence fails closed;
- exact duplicate components are excluded;
- contained linear components are excluded;
- novel chromosome-integrity triggers fail closed;
- cached adjudications require exact accession.version/source evidence;
- no source rule consumes an OPS/SR score or panel identity.

Tests must use synthetic/local fixtures and perform no network requests.

## Prospectivity statement

At the time this method is frozen:

- no fresh BacSelect NCBI source-universe query has been executed for the
  selector-resolution experiment;
- no fresh external holdout has been inspected;
- no fresh structural features have been generated;
- no holdout OPS/SR distances have been calculated;
- the OPS-versus-SR decision remains unresolved.

Any later implementation refinement required to execute this method must be
documented and frozen before the first outcome-producing selector-resolution
calculation.
