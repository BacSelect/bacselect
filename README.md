# BacSelect

**Bacterial genome diversity, at the scale you need.**

BacSelect is being developed as a reproducible system for selecting compact
panels of complete bacterial genomes that span genome architecture.

A user chooses the number of genomes, N. BacSelect will return a deterministic,
versioned panel from a defined public complete-genome universe.

## Status

BacSelect is under prospective development and validation.

No BacSelect scientific panel has been released yet.

The current work is focused on freezing and validating:

- the genome-architecture feature schema;
- species-abundance control;
- the arbitrary-N selection algorithm;
- structural coverage metrics; and
- release reproducibility.

## Repository structure

- `docs/` — scientific specification
- `src/bacselect/` — selector implementation
- `tests/` — automated tests
- `validation/` — prospective validation designs and evidence

Website: https://bacselect.github.io
