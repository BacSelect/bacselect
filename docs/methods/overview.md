# How BacSelect works

The intended release workflow has six stages.

## 1. Freeze the source universe

Retrieve and record the eligible public complete-genome universe for the
release.

## 2. Measure genome architecture

Calculate the frozen structural-feature schema for each eligible assembly.

## 3. Build species-balanced feature geometry

Transform raw feature values using species-balanced empirical distributions so
heavily represented species do not dominate feature scaling.

## 4. Build the diversity ladder

Apply the validated deterministic selector to the complete selector-defined
candidate set.

The final selector-v1 species-representation design is still under validation.

## 5. Measure structural representation

For each supported panel size, calculate nearest-panel structural distances
across the eligible evaluation universe.

## 6. Validate and publish

A release is published only if its required scientific, reproducibility and
provenance checks pass.

A failed or unresolved release remains unpublished.

For exact definitions, see the
[scientific specification](../scientific-specification.md).
