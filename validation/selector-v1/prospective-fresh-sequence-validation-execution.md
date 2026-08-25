# Prospective fresh sequence acquisition and validation execution

## Status

**PROSPECTIVE EXECUTION LAYER — NO FRESH BACSELECT SEQUENCE DOWNLOADED**

This checkpoint freezes the code and scheduler contract that will acquire and
validate the 15,326 accessions in the already frozen fresh-acquisition
manifest.

The execution layer is developed and committed locally first. It is pushed once
immediately before network retrieval because a pushed clean commit is a
production precondition.

## Frozen target inputs

Fresh target manifest SHA256:

`1c9a73231d6b8ebfed76fb60621616588a4f51b1144e5d7880f14ddf26d1863b`

Fresh batch index SHA256:

`2a52f7ba3b23867bfe85078b47b840e5a1e240b09187d130fb0578087b483c4a`

The frozen acquisition set contains 15,326 targets in 31 batches. Batches
001–030 contain 500 accessions each and batch 031 contains 326. Every target
has acquisition reason `not_in_historical_cache`.

## Validation-engine provenance

The BacSelect worker is vendored from the frozen Project Finch sequence
validator:

`780f8aabe2e6d9b4425498ee1f0170e3b0d55328100a4aea02efc875d4d29665`

The derivation tool refuses any different source identity.

The BacSelect copy is adapted before use: target count changes from 55,426 to
15,326; batch count changes from 111 to 31; the target becomes the frozen
BacSelect fresh-download manifest; `fresh_biosample` is supplied to the frozen
validation engine through an internal `source_biosample` compatibility alias;
only `not_in_historical_cache` is accepted; the output namespace becomes
BacSelect-specific; and the redundant historical `--assembly-source GenBank`
download argument is removed so the Datasets download vector matches the
previously frozen BacSelect acquisition design.

The resulting worker is committed into BacSelect. Project Finch is not a
runtime code dependency.

## NCBI environment

NCBI Datasets is exactly version 18.35.0. BacSelect owns the explicit
environment lock with SHA256:

`6d965c7c4f7db0464e4fba2434f85f1b7da3f7136790babca444888b6e6096cd`

For this prospective selector-resolution experiment, the existing conda
environment name `finch-ncbi-datasets` may execute that exact lock. Scientific
identity is the explicit lock and Datasets version, not the local environment
name.

## Acquisition contract

Each batch retrieves genome, GBFF, and sequence-report payloads. Retrieval is
dehydated first and then rehydrated. The inherited validator retains targeted
per-accession rehydration recovery for incomplete payloads.

If the Datasets package cannot supply a required GBFF payload, the inherited
validator may use its exact NCBI EFetch nuccore fallback. That fallback is
identity-scoped and provenance is recorded. It does not change the requested
assembly identity.

## Sequence validation

The vendored validation engine preserves checks for current assembly accession,
current assembly status, Complete Genome assembly level, expected versus
observed BioSample, Primary Assembly component membership, FASTA/GBFF sequence
agreement, sequence-report component agreement, component length, ACGT versus
ambiguous nucleotide content, topology, and cryptographic file identities.

An ambiguous nucleotide is scientific sequence ineligibility, not an
acquisition failure.

## Retry boundary

The worker itself performs targeted hydration retries for unresolved
accessions. The Slurm task wrapper permits at most three whole-batch attempts,
separated by 60 seconds. A valid `.partial` directory is resumed. Failed partial
state is preserved for inspection. No automatic deletion or silent restart of
a failed partial batch is allowed.

## Scheduler contract

Fresh retrieval uses Slurm array `1-31%2`, so at most two batches execute
concurrently. Each task requests `prod`, 2 CPUs, 8 GiB memory, and 24 hours.
The cap is deliberately conservative because each active batch may use up to
ten Datasets rehydration workers.

Each task requires at least 500 GiB free on shared scratch before retrieval or
retry.

## Output namespace

Outputs are commit-scoped under:

`/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/fresh-sequence-validation/<production-commit>`

Each batch finalizes atomically from `batch-NNN.partial` to `batch-NNN`. The
worker refuses to overwrite completed output.

## Batch and aggregate audit

After each successful worker completion, the BacSelect auditor verifies the
exact frozen batch accession SHA and order, expected fresh BioSample, current
accession/status/assembly level, summary identities, and candidate/component
row counts. A completed batch is skipped only after this audit passes.

The aggregate job runs only after the array succeeds. It repeats all batch
checks and additionally re-hashes every hydrated package file recorded in each
`package-files.tsv`. The aggregate output is a count/hash summary.

## Git boundary

Local development commits do not need to be pushed after every checkpoint.
Network retrieval is different. The submission helper requires a clean
repository and `HEAD == origin/main`, so the accumulated local checkpoints are
pushed once before submission. No extra remote query is required after that
push; local `HEAD` and `origin/main` equality is the production gate.

## Blinding and scientific boundary

This stage acquires source sequence evidence only. It does not consume baseline
membership as an acquisition criterion, structural features, OPS identity, SR
identity, panel membership, or selector distances.

No prospective selector outcome is generated here.

The selector-resolution decision remains unresolved.
