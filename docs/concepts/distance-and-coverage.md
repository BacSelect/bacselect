# Structural distance

BacSelect does not assign a single arbitrary percentage called "coverage".

Instead, it measures how far each eligible genome lies from its nearest selected
panel genome in the validated architecture feature space.

For a panel of size **N**:

1. take every eligible genome in the evaluation universe;
2. find its nearest selected panel genome;
3. calculate the structural distance between them.

Smaller distances mean the selected panel samples the defined architecture space
more densely.

## What BacSelect will report

At minimum:

- species-balanced median nearest-panel distance;
- species-balanced 95th-percentile nearest-panel distance;
- maximum nearest-panel distance across all eligible genomes.

The median and 95th percentile use species-balanced weighting so heavily
represented species do not dominate the summaries.

The maximum is the worst observed nearest-panel distance across the full
eligible universe.

## What this measures

These distances describe structural representation within the BacSelect source
universe.

They do not measure:

- taxonomic coverage;
- ecological coverage;
- pathogen coverage;
- clinical importance;
- evolutionary distance.

Exact distance definitions are given in the
[scientific specification](../scientific-specification.md).
