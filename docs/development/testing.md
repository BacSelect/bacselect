# Testing

BacSelect separates software tests from scientific validation.

Both are required, but they answer different questions.

## Automated tests

The `tests/` directory checks implementation behaviour such as:

- deterministic tie handling;
- geometry calculations;
- selector candidate implementations;
- structural coverage metrics;
- random-baseline calculations;
- correlation and ablation utilities;
- provenance handling;
- repeat-scale calculations;
- repeat-concordance processing.

Run the complete suite with:

```bash
python -m pytest
```

A passing unit-test suite means the tested code behaved as specified. It does
not, by itself, establish that a scientific design choice is appropriate.

## Scientific validation

The `validation/` directory contains prospective methods, production runners,
frozen evidence and interpretation records used to decide whether proposed
scientific choices should become part of BacSelect v1.

See [Validation](../validation/index.md).

## Why keep them separate?

A selector can be implemented perfectly and still be a poor scientific design.

Conversely, a scientifically sensible method is not reproducible if its
implementation is unstable or incorrect.

BacSelect therefore treats implementation correctness and scientific validation
as separate gates.
