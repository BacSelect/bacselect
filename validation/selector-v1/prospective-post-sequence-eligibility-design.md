# BacSelect selector-v1 prospective post-sequence eligibility design

## Status

**PROSPECTIVE DOWNSTREAM ELIGIBILITY DESIGN — NO POST-SEQUENCE OUTCOME GENERATED**

This checkpoint freezes the remaining source-eligibility operations for the
external OPS-versus-SR selector-resolution experiment after completion of
sequence acquisition and sequence eligibility.

## Frozen upstream state

The BacSelect repository identity immediately before this prospective
checkpoint is:

`f9bfb99ff163a73899ebb53ad7e1eff69a1f492e`

The upstream evidence identities are:

- `source-eligibility-v1.tsv`:
  `f5737812ae2a314a93893a5d0cee30747e3892bae6bfc8100a680073ea6b32b3`
- `prospective-source-acquisition-eligibility-method.md`:
  `ea444212eecf9f6f86c478a1d4e71f86bb216ed166aa2449bcc13daddff6351a`
- `prospective-selector-resolution-design.md`:
  `2584fddf1f06562d48abd990372ec70ea1f48da0962b1f710afb1d93e2c3223a`
- `final-acquisition-manifest-evidence.json`:
  `e4f4c354f5a78f4efc123eede2dbee475440785fa72cc59d233b4406e64103bc`
- completed fresh-sequence recovery summary:
  `e1a5eac79f62ae95651a4f83bff44636d7d0221c46b63c39490432eec67aa876`

The recovery summary identity must equal the already audited value
`e1a5eac79f62ae95651a4f83bff44636d7d0221c46b63c39490432eec67aa876`.

At this checkpoint:

- fresh acquisition accounting is complete;
- historical cache verification is complete;
- sequence eligibility has been calculated;
- no current repeated-BioSample fingerprint outcome has been generated;
- no current source structural-integrity outcome has been generated;
- no BacSelect chromosome-integrity outcome has been generated;
- no BacSelect taxonomy snapshot has been acquired for this stage;
- no current taxonomy/species-resolution result has been generated;
- no final eligible fresh-universe manifest has been generated;
- no final external-holdout membership has been generated;
- no structural feature has been calculated for the external holdout;
- no OPS/SR external-holdout outcome has been calculated.

## Sequence-eligible input boundary

The completed sequence-evidence accounting contains:

- 55,145 historically cached sequence-eligible assemblies;
- 13,335 freshly acquired sequence-eligible assemblies.

The provisional sequence-eligible pool is therefore 68,480 assemblies.

This is not yet the complete eligible fresh universe.

## Project Finch algorithm provenance

Machine algorithms inherited from Project Finch are bound by
`post-sequence-inherited-implementation-references.tsv`.

Only the explicitly identified algorithmic semantics are inherited.
Historical Project Finch candidate membership, GTDB membership, manual
repeated-BioSample adjudications and selector outcomes are not inherited.

## Source structural integrity

All current sequence-eligible candidates are assessed under the already frozen
identity-independent source-truth rules:

1. exact duplicate Primary Assembly components -> exclude;
2. any fully contained linear Primary Assembly component -> exclude;
3. containment involving only circular inner components -> retain by this rule;
4. no duplicate/full-containment finding -> retain by this rule;
5. missing, contradictory or unclassifiable required source evidence -> withhold
   unresolved.

No accession identity, organism identity, species identity, genome-size
threshold, component-size threshold, containment-fraction threshold,
architecture flag or selector outcome may affect this classification.

The current BacSelect universe is recomputed under these rules. Historical
Project Finch source-truth membership is not imported as the current outcome.

## Repeated-BioSample reconciliation

Repeated-BioSample groups are evaluated from current sequence-eligible source
evidence using the frozen topology-aware sequence fingerprint semantics
`project-finch-topology-aware-sequence-v1`.

For each Primary Assembly component:

- sequence identity is canonicalized with topology-aware sequence semantics;
- the canonical sequence is SHA256 hashed.

For each assembly:

- `[topology, sequence_hash]` pairs are lexicographically sorted;
- the compact ASCII JSON representation is SHA256 hashed.

For a repeated-BioSample group:

- if every current eligible member has the same assembly fingerprint, retain
  exactly the lexicographically smallest canonical versioned GCA accession and
  mark the other representations non-representative;
- if two or more distinct assembly fingerprints exist, withhold every member
  of the group as unresolved.

No historical identity-aware or organism-aware repeated-BioSample adjudication
is reused.

## Chromosome-component integrity

A candidate triggers chromosome-component integrity review when:

1. the Primary Assembly has at least two components classified as Chromosome;
   and
2. at least one chromosome component lacks closure evidence.

Closure evidence is present when GenBank topology is circular or the GenBank
definition explicitly identifies a complete sequence.

For a triggered candidate, an historical Project Finch adjudication may be
reused only when:

- the canonical accession.version is identical;
- the candidate uses the already content-verified historical Project Finch
  sequence package;
- the relevant Primary Assembly component identities, sequences, topology and
  closure evidence are therefore unchanged.

A triggered candidate without such an exact unchanged historical evidence
match is withheld unresolved.

Historical manual adjudication is not generalized to another accession,
another assembly version, or changed source evidence.

## Taxonomy

BacSelect will acquire and freeze its own NCBI Taxonomy `new_taxdump` snapshot
before taxonomy resolution.

The Project Finch taxonomy resolver provides algorithmic provenance only.

For every otherwise eligible candidate:

1. start from the structured NCBI organism TaxID frozen in the BacSelect source
   snapshot;
2. normalize merged TaxIDs using the frozen BacSelect taxonomy snapshot;
3. reject deleted, missing, cyclic or otherwise unresolved TaxIDs;
4. traverse the lineage;
5. use the first ancestral node whose rank is exactly `species`.

The species TaxID is the grouping identity. Species names are descriptive.

No live taxonomy lookup is permitted after the taxonomy snapshot is frozen.

## Complete eligible fresh universe

A candidate can enter the complete eligible fresh universe only if it:

- passed frozen metadata eligibility;
- has acquisition-available, sequence-eligible source evidence;
- survives repeated-BioSample reconciliation;
- satisfies source structural-integrity rules;
- is not unresolved under chromosome-component integrity;
- has resolved species taxonomy.

The complete eligible fresh-universe identity-bearing manifest is written
outside the repository and frozen by count plus SHA256 fingerprint before any
structural-feature outcome is generated.

## External decision holdout

External decision-holdout membership is then the complete eligible fresh
universe intersected with the already frozen
`retained_absent_from_baseline` membership.

Baseline membership does not alter acquisition, sequence validation,
source-truth classification, BioSample reconciliation or taxonomy resolution.

The identity-bearing holdout manifest remains outside the repository.

Only blinded counts, adequacy statistics and cryptographic fingerprints are
committed before selector outcomes are calculated.

## Blinding boundary

This implementation must not read:

- OPS ladder membership;
- SR ladder membership;
- OPS/SR distances;
- structural-feature selector results;
- panel identities;
- any external-holdout selector outcome.

No source-eligibility rule may be altered after external-holdout structural
outcomes are known.
