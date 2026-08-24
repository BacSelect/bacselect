# Contributing to BacSelect

BacSelect is under prospective scientific development.

Contributions that improve correctness, reproducibility, testing,
documentation or portability are welcome.

## Before changing scientific behaviour

Changes to eligibility rules, feature definitions, species balancing, selector
behaviour, distance metrics or release semantics are scientific changes.

They should not be introduced only as implementation refactors.

A scientific change should include:

- the reason for the change;
- its relationship to the scientific specification;
- appropriate automated tests;
- any required prospective validation;
- updated documentation and decision records.

## Code changes

For normal development:

```bash
mamba create     -n bacselect-dev     --file envs/bacselect-dev-linux-64.lock

conda activate bacselect-dev

python -m pip install     --no-deps     --editable .

python -m pytest
```

Before committing, run:

```bash
git diff --check
python -m pytest
```

## Validation evidence

Do not rewrite frozen validation evidence to make later results appear
prospective.

If a method changes after evidence has been generated, preserve the historical
record and document the new validation boundary explicitly.

## Documentation

Public-facing documentation should distinguish clearly between:

- current validated behaviour;
- prospective design;
- unresolved decisions;
- future release plans.

Avoid claims that BacSelect represents all bacterial diversity.
