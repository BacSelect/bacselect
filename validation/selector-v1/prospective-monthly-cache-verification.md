# Prospective monthly cache verification

## Status

This document defines the pure evidence contract by which previously acquired
BacSelect sequence evidence may become eligible for reuse by the monthly
Stage 2 sequence planner.

It does not define filesystem discovery or execution.

It does not modify the frozen Stage 2 planner.

It performs no network retrieval, NCBI query, sequence download, archive
publication, taxonomy, structural-feature computation, or selector analysis.

## Purpose

The frozen Stage 2 planner accepts `VerifiedMonthlyCacheEvidence`.

The planner deliberately does not define how those cryptographic fields are
constructed.

This contract supplies those semantics.

A previous accession is reusable only after its evidence has been verified
again for the current source snapshot.

## Current-snapshot binding

Every cache-verification run is bound to:

- the current source-snapshot ID;
- the current source-snapshot-record SHA256;
- the current metadata-eligibility record SHA256;
- the current metadata-eligibility completion SHA256;
- the current metadata-retained count.

A candidate accession must belong to the current metadata-retained universe.

Its previously recorded BioSample must equal the current metadata BioSample.

## Candidate origin

Every cache candidate carries provenance from the previous sequence evidence:

- origin release ID;
- origin source-snapshot ID;
- origin Git commit;
- origin batch-summary SHA256;
- origin candidate-audit SHA256;
- origin component-audit SHA256;
- origin package-files SHA256.

These identities are provenance.

They are not substituted for the per-accession Stage 2 cache identities.

## Batch-common verification

A candidate cannot be reused unless its complete origin batch provenance has
already been verified.

This includes shared transport evidence that cannot safely be represented as a
per-accession identity.

The pure contract receives this as an explicit boolean prerequisite.

The filesystem executor must establish that boolean from independently audited
and re-hashed persisted evidence.

A false value produces fresh acquisition.

## File read-back verification

For every persisted package file considered by the executor, the pure contract
receives:

- expected size;
- expected SHA256;
- observed size;
- observed SHA256.

A missing file, size mismatch, or SHA256 mismatch prevents reuse for that
candidate.

Malformed observations fail closed.

## Component identity

`component_identity_sha256` is the SHA256 of canonical JSON containing:

- canonical GenBank assembly accession;
- every Primary Assembly component, sorted by component accession;
- component GenBank accession;
- component length;
- topology;
- raw sequence SHA256.

The identity is per accession.

It is independent of acquisition-batch membership and filesystem location.

## Assembly fingerprint

`assembly_fingerprint` uses the already-frozen
`source_fingerprint.assembly_fingerprint()` semantics.

For each reconstructed Primary Assembly component:

1. the raw reconstructed sequence is checked against the frozen component
   sequence SHA256;
2. the sequence is canonicalised according to linear or circular topology;
3. its canonical component sequence hash is calculated;
4. the assembly fingerprint is calculated from the topology/hash pairs.

No second assembly-fingerprint definition is introduced here.

## Source-evidence identity

`source_evidence_sha256` uses the already-frozen
`source_truth_execution.source_evidence_sha256()` implementation.

It binds:

- canonical assembly accession;
- candidate FASTA filename;
- candidate FASTA SHA256;
- Primary Assembly component count;
- the matching package FASTA path, size and SHA256;
- every sorted Primary Assembly component accession, length, topology and raw
  sequence SHA256.

The cache contract does not reimplement this identity.

## Per-accession package identity

`package_manifest_sha256` is a per-accession identity.

It is the SHA256 of canonical JSON containing every persisted package-manifest
row beneath:

`ncbi_dataset/data/<canonical GCA>/`

Each row binds:

- POSIX-relative path;
- expected file size;
- expected SHA256.

Rows are sorted by path.

Batch-common package rows, including the shared assembly-data report, are not
included in this per-accession hash.

Their integrity is covered by the separate batch-common provenance gate.

This prevents the per-accession package identity from changing solely because
different unrelated accessions happened to share an acquisition batch.

## Verification-record identity

For a successfully verified candidate, the contract constructs a canonical
per-accession verification record.

It binds:

- current verified source-snapshot ID;
- canonical accession;
- BioSample;
- cache-origin release, snapshot and Git commit;
- origin batch-summary, candidate-audit, component-audit and package-files
  SHA256 identities;
- component identity SHA256;
- assembly fingerprint;
- source-evidence SHA256;
- per-accession package-manifest SHA256;
- verified status.

`verification_record_sha256` is the SHA256 of those canonical record bytes.

The record is reconstructable from the persisted verification-result row.

## Ordinary reuse failure

A structurally valid candidate does not become verified cache evidence when:

- batch-common provenance was not verified;
- its current BioSample changed;
- a package file is missing;
- a package file size changed;
- a package file SHA256 changed;
- a reconstructed component no longer matches its recorded raw sequence SHA;
- a component cannot produce the frozen topology-aware fingerprint.

Such candidates are recorded as requiring fresh acquisition.

They are not scientifically excluded.

## Malformed evidence

Malformed verification evidence fails closed for the verification run.

Examples include:

- invalid accession;
- invalid BioSample;
- invalid SHA256;
- unsafe package path;
- duplicate package path;
- duplicate component;
- inconsistent Primary Assembly component count;
- unsupported component topology;
- malformed package observation;
- candidate outside the current metadata-retained universe;
- duplicate candidate accession.

These conditions are not silently converted into cache misses.

## Persisted pure-contract artifacts

The contract defines three canonical payloads:

1. cache-verification results JSONL;
2. verified-cache evidence JSONL;
3. cache-verification record JSON.

The first artifact records every candidate examined.

The second contains only rows suitable for direct reconstruction as
`VerifiedMonthlyCacheEvidence`.

The third binds both payloads to the current source and metadata evidence.

## Explicit zero-candidate input state

The pure verifier permits an empty candidate input.

The canonical pure-contract state is:

- candidate input count: zero;
- verified cache count: zero;
- fallback-to-fresh count: zero;
- empty cache-verification results payload;
- empty verified-cache evidence payload.

The cache-verification record explicitly binds both empty-payload SHA256 values
to the current source snapshot and metadata stage.

This proves that the verifier received and processed an explicitly empty
candidate input. It does not, by itself, prove that no authoritative previous
monthly sequence evidence exists.

For the first production release, the filesystem executor must separately prove
that no eligible prior monthly cache catalogue or authoritative monthly sequence
evidence exists before supplying the empty candidate input.

For later releases, that executor must prove that the candidate input is a
complete deterministic reconstruction of the authoritative prior cache universe.

Candidate discovery and completeness are therefore execution-provenance
responsibilities, not properties inferred by this pure contract.

## Stage 2 consumption

Only the verified-cache evidence payload is converted into
`VerifiedMonthlyCacheEvidence`.

Stage 2 then applies its already-frozen rules.

A retained accession without verified evidence becomes a fresh acquisition
target with the existing `no_verified_cache` reason.

## Historical isolation

Historical Project Finch cache-verification code remains historical evidence.

This monthly contract does not import or encode:

- historical batch counts;
- historical accession counts;
- historical script allowlists;
- historical filesystem layouts;
- institution-specific paths;
- Slurm;
- Project Finch cache semantics.

## Next boundary

After this pure contract is frozen, a separate portable filesystem executor
must:

1. audit current Stage 1 and completed metadata eligibility;
2. locate authoritative previous BacSelect sequence evidence;
3. audit batch provenance;
4. re-hash persisted package files;
5. reconstruct Primary Assembly sequence components from the cached FASTA;
6. call this pure contract;
7. atomically publish and read-back audit the three cache-verification
   artifacts.

Only after that executor is frozen should the monthly Stage 2 sequence-plan
writer be implemented.
