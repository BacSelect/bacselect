# BacSelect monthly source/cache/acquisition orchestration

## Status

**PROSPECTIVE MONTHLY STAGE 2 ORCHESTRATION — SYNTHETIC INPUTS ONLY**

This method defines the portable monthly Stage 2 planning boundary before any
canonical monthly source snapshot or genome sequence is acquired.

## Relationship to selector-v1 validation

Historical Project Finch cache verification, the frozen selector-resolution
acquisition manifest, and the historical fresh-sequence execution remain valid
validation evidence.

They are not monthly production dependencies.

Monthly production must not inherit:

- historical source-snapshot identities;
- historical accession manifests;
- historical population counts;
- historical batch counts;
- Project Finch storage;
- institution-specific filesystem paths;
- Slurm execution;
- a historically named Conda environment.

Those historical files remain unchanged.

## Current monthly source universe

Stage 2 consumes metadata assessments derived from the exact successful monthly
Stage 1 raw source snapshot.

Only records retained by the frozen BacSelect metadata-eligibility semantics
enter Stage 2.

No expected monthly population count is encoded.

The retained count is an observed property of that month's source snapshot.

## Monthly cache evidence

Cache reuse is optional.

A monthly cache record is eligible for planning only after a separate
verification layer has bound it to the current monthly source snapshot.

The planner therefore consumes already-verified cache evidence containing at
least:

- canonical GenBank assembly accession.version;
- BioSample;
- current monthly source-snapshot identity;
- component-identity SHA256;
- assembly sequence fingerprint;
- source-evidence SHA256;
- package-manifest SHA256;
- cache-verification-record SHA256.

Accession identity by itself is never sufficient.

Malformed cache evidence fails closed.

Missing, stale or metadata-mismatched cache evidence does not exclude a genome.
It sends that genome to fresh acquisition.

## First monthly release

No historical Project Finch package is an operational dependency of monthly
production.

Therefore, before BacSelect has its own verified persistent monthly cache, the
first monthly release has an empty monthly cache input.

Every metadata-retained source in that first release is consequently planned
for fresh acquisition.

This is a production-architecture property, not a frozen population count.

## Fresh acquisition planning

Fresh acquisition targets are:

- sorted lexicographically by canonical GCA accession.version;
- unique;
- exhaustive with cache reuse over the retained monthly source universe;
- disjoint from cache reuse.

Fresh targets are partitioned deterministically into batches of 500.

The final batch size and total batch count are derived from the observed monthly
fresh-acquisition count and are never frozen globally.

Stage 2 writes no network result and performs no source download.

## Network boundary

`src/bacselect/monthly_sequence_plan.py` is a pure planning layer.

It must not:

- invoke NCBI Datasets;
- perform HTTP requests;
- open selector outputs;
- calculate structural features;
- perform taxonomy resolution;
- execute OPS;
- publish a release.

Stage 3 will consume the resulting fresh-acquisition manifests only after its
portable worker and persistent evidence boundary have been separately frozen
and synthetically tested.

## Persistent cache boundary

This Stage 2 primitive deliberately does not choose a storage vendor.

The later monthly cache verifier must be able to verify BacSelect-owned
persisted source evidence independently of runner-local state.

Transient GitHub Actions storage and workflow caches are not authoritative
monthly cache evidence.

## Prospectivity

At this checkpoint:

- no monthly Stage 1 source query is enabled;
- no real monthly cache index has been consumed;
- no monthly fresh-acquisition manifest has been generated from real data;
- no monthly genome sequence has been downloaded;
- no release publication is enabled.
