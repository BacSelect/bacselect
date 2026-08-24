# Nested panels

BacSelect is intended to generate one deterministic ordered diversity ladder
for each release.

A panel of size **N** is then the first N genomes in that ladder.

For example:

```text
N=10   genomes 1-10
N=20   genomes 1-20
N=50   genomes 1-50
```

The N=10 panel is therefore contained within N=20, and N=20 within N=50.

## Why nested panels?

Nested panels make comparisons between panel sizes easier.

Increasing N adds genomes rather than replacing earlier selections from the
same release.

This lets a user increase panel size while retaining the genomes already
analysed.

## Current status

Nestedness is a required property of the intended BacSelect selector, but the
final selector-v1 species-representation design is still under validation.

Whichever design is frozen must preserve one deterministic ordered ladder
within each release.
