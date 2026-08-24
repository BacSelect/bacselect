# Development setup

These instructions are for contributors working on the BacSelect source code.
They are not required for ordinary users of future released panels.

## Requirements

- Git
- a Conda-compatible package manager such as Conda or Mamba
- Python 3.10 or later

## Reproduce the development environment

The repository contains an explicit Linux environment lock:

```bash
mamba create     -n bacselect-dev     --file envs/bacselect-dev-linux-64.lock

conda activate bacselect-dev
```

Install the local package without changing the locked dependency set:

```bash
python -m pip install     --no-deps     --editable .
```

## Run the tests

```bash
python -m pytest
```

See [Testing](testing.md) for the role of the test suite.

## Repeat-feature validation environment

Repeat-scale validation has a separate environment definition under `envs/`.

It exists because the repeat-feature workflow includes additional pinned
software beyond the core Python package.

Do not substitute that environment for the normal development environment
unless working specifically on repeat-feature validation.
