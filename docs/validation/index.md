# Validation

BacSelect is being validated prospectively before the first scientific release.

The aim is not simply to show that the code runs. The validation programme asks
whether the scientific design is reproducible, stable and supported by
pre-specified quantitative evidence.

## Selector-v1 questions

Current validation includes:

- candidate-selector comparison;
- comparison with species-balanced random panels;
- species-abundance diagnostics;
- feature-correlation analysis;
- leave-one-feature-out analysis;
- grouped feature ablation;
- repeat-scale sensitivity;
- input-order invariance;
- deterministic rebuild testing;
- update-stability testing.

Some analyses are complete. Others remain in progress.

## Why is the selector still open?

BacSelect has deliberately kept the selector decision unresolved while required
validation is incomplete.

An attractive result in one analysis is not enough to freeze the design.

## Where is the evidence?

Detailed prospective methods, frozen outputs and interpretation records are kept
under [`validation/selector-v1/`](../../validation/selector-v1/).

The [scientific specification](../scientific-specification.md) states which
questions must be resolved before BacSelect v1.0.
