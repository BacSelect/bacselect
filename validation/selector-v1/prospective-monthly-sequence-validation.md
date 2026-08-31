# BacSelect monthly sequence-evidence validation

## Status

**PROSPECTIVE MONTHLY STAGE 3A VALIDATION — SYNTHETIC INPUTS ONLY**

This method freezes the pure validation boundary for already hydrated monthly
sequence evidence before any canonical monthly sequence acquisition is enabled.

## Upstream identity

Stage 3A consumes the exact identity-bearing Stage 2 fresh-acquisition targets.

For each target the expected identity includes:

- canonical GenBank assembly accession.version;
- source BioSample;
- acquisition reason.

The current Stage 1 source-snapshot identity is carried by Stage 2 and will be
bound by the later Stage 3 execution provenance layer.

## Reused scientific semantics

Stage 3A preserves the validated complete-local-payload semantics established by
the frozen selector-v1 fresh-sequence implementation.

The monthly implementation retains the same audit field contracts for:

- candidate sequence evidence;
- Primary Assembly component evidence;
- package-file identity.

For a complete payload it requires:

- exact target accession membership;
- exact expected BioSample;
- assembly status `current`;
- current accession equal to the canonical accession.version;
- assembly level `Complete Genome`;
- at least one Primary Assembly component;
- exactly one genomic FASTA after excluding NCBI derived CDS/RNA FASTAs;
- exactly one NCBI Datasets GBFF;
- sequence-report, FASTA and GBFF component sets to agree;
- FASTA and GBFF component lengths to agree;
- FASTA sequence and GBFF ORIGIN sequence to agree exactly;
- any supplied sequence-report length to agree;
- topology to derive from GBFF;
- Primary Assembly ambiguous nucleotide content to remain an ineligibility;
- unspecified Primary Assembly topology to remain an ineligibility.

## Deliberate separation from historical transport

The historical selector-v1 execution could invoke an NCBI EFetch fallback when
Datasets did not supply GBFF.

That behaviour is not part of monthly Stage 3A validation.

Stage 3A performs no retrieval.

If the hydrated monthly package does not contain the required NCBI Datasets
GBFF, Stage 3A fails closed.

Historical EFetch fallback payloads or provenance files are not accepted by the
monthly pure validator.

Any future decision to support an additional acquisition transport must be
defined, versioned and tested prospectively as transport. It must not be hidden
inside scientific validation.

## Network boundary

`src/bacselect/monthly_sequence_validation.py` must not:

- invoke NCBI Datasets;
- invoke EFetch;
- perform HTTP requests;
- execute subprocesses;
- locate Conda or Micromamba;
- depend on Project Finch;
- depend on institution-specific storage;
- contain historical target or batch counts;
- perform taxonomy;
- calculate structural features;
- execute selector logic;
- publish a release.

## Parity proof

Synthetic complete local payloads are evaluated by both:

1. the frozen historical selector-v1 validator; and
2. the new monthly Stage 3A validator.

Candidate-audit rows, component-audit rows and package-file manifests must be
identical for the complete local-payload path.

The parity test itself performs no network access.

## Stage 3B boundary

Stage 3B will provide transport and execution provenance separately.

It will receive dynamic Stage 2 manifests, an explicit absolute `datasets`
executable and a fresh output root.

Stage 3B must produce a complete local hydrated package before Stage 3A
validation is called.

Stage 3A must never repair missing transport evidence.

## Prospectivity

At this checkpoint:

- monthly Stage 1 acquisition remains disabled;
- no real monthly Stage 2 manifest has been generated;
- no real monthly genome sequence has been downloaded;
- no monthly EFetch fallback is authorized;
- no Stage 3B transport implementation has been enabled;
- no release publication is enabled.
