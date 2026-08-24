# Species balancing

Public genome archives are highly uneven.

Some bacterial species have many deposited complete genomes, while others have
few. If every genome contributes equally when feature distributions are built,
heavily sampled species can dominate the geometry.

BacSelect controls this during feature scaling.

If a species contains `n` eligible genomes, each genome contributes weight:

`1 / n`

The species as a whole therefore contributes total weight 1, regardless of how
many eligible genomes it contains.

## What species balancing means

It prevents archive abundance alone from dominating the empirical feature
distributions used by BacSelect.

## What it does not mean

It does not make the archive unbiased.

It also does not, by itself, require BacSelect to select exactly one genome per
species. The final species-representation rule remains a separate selector-v1
decision.
