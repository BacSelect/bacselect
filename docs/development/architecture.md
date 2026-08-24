# Code architecture

The repository deliberately separates reusable implementation, automated tests,
scientific validation and vendored external code.

## `src/bacselect/`

Reusable Python implementation.

Current modules include:

- `geometry.py` - feature-space transformations and geometry;
- `tie.py` - deterministic tie handling;
- `ops.py`, `sr.py`, `ag.py` - selector and diagnostic candidate logic;
- `metrics.py` - structural representation metrics;
- `random_baseline.py`, `random_compare.py` - species-balanced random controls;
- `correlation.py` - feature-correlation calculations;
- `ablation.py` - feature-removal analyses;
- `repeat_scale.py` - repeat-scale comparison calculations;
- `repeat_concordance.py` - repeat-engine concordance support;
- `provenance.py` - provenance utilities.

The existence of a candidate implementation does not mean that candidate has
been selected for BacSelect v1.

## `tests/`

Automated tests for the reusable implementation.

## `validation/`

Prospective scientific validation designs, executable validation workflows,
frozen outputs and interpretation records.

This directory is evidence, not merely temporary analysis code.

## `vendor/`

Pinned third-party or project-derived source required for a specific validation
workflow.

Vendored code should retain clear provenance and should not be mistaken for
native BacSelect implementation.

## `docs/`

User, scientific and developer documentation.

The formal scientific rules remain in
[`scientific-specification.md`](../scientific-specification.md).
