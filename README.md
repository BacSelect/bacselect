# BacSelect

**Bacterial genome diversity, at the scale you need.**

BacSelect is being developed to select compact, reproducible panels of complete
bacterial genomes from a defined public genome universe.

A user chooses the number of genomes, **N**. BacSelect will return a
deterministic, versioned panel designed to span bacterial genome architecture
while controlling the influence of heavily represented species.

## Status

BacSelect is under prospective development and validation.

**No BacSelect scientific panel has been released yet.**

Selector v1, the architecture feature schema, structural-distance metrics and
release process must pass their required validation before the first release.

## Why BacSelect?

Public archives contain many complete bacterial genomes. Researchers often need
a much smaller set for benchmarking, method development or comparative
analysis.

The practical question is:

> We need a manageable set of bacterial genomes. Which ones?

Hand-picking familiar organisms is subjective. Random sampling is reproducible,
but heavily represented species can dominate. BacSelect is being developed as
a deterministic, diversity-seeking alternative within a clearly defined source
universe.

## Start here

- [Getting started](docs/index.md)
- [Scientific specification](docs/scientific-specification.md)
- [Selector-v1 validation](validation/selector-v1/design.md)
- [Public website](https://bacselect.github.io)

## Important limitation

BacSelect does not represent all bacterial life.

Its source universe reflects what has been sampled, sequenced, assembled to
completion, deposited and classified. BacSelect can reduce arbitrary selection
within that defined universe; it cannot remove biases already present in the
underlying data.

## Repository structure

- `src/bacselect/` - implementation
- `tests/` - automated tests
- `validation/` - prospective validation methods and evidence
- `docs/` - user and scientific documentation
- `envs/` - reproducible development environments

## Development state

The Python package is currently version `0.0.0`. It is not a public BacSelect
release and there is not yet a supported end-user command-line interface.
