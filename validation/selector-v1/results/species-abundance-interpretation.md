# Selector-v1 species-abundance diagnostic

## Status

DESCRIPTIVE VALIDATION RESULT

Genome and species identities remain blinded.

This diagnostic reports only the three quantities pre-specified in the
selector-v1 design:

- number of distinct species selected;
- maximum number of selected genomes from one species;
- distribution of selected genomes per represented species.

No additional abundance statistic or selector decision criterion is
introduced.

## Results

| Selector | N | Distinct species | Maximum per species | Multiplicity distribution |
| :--- | ---: | ---: | ---: | :--- |
| OPS | 10 | 10 | 1 | 1x:10 |
| OPS | 20 | 20 | 1 | 1x:20 |
| OPS | 50 | 50 | 1 | 1x:50 |
| OPS | 100 | 100 | 1 | 1x:100 |
| OPS | 200 | 200 | 1 | 1x:200 |
| OPS | 500 | 500 | 1 | 1x:500 |
| SR | 10 | 10 | 1 | 1x:10 |
| SR | 20 | 20 | 1 | 1x:20 |
| SR | 50 | 50 | 1 | 1x:50 |
| SR | 100 | 100 | 1 | 1x:100 |
| SR | 200 | 200 | 1 | 1x:200 |
| SR | 500 | 499 | 2 | 1x:498,2x:1 |
| AG | 10 | 10 | 1 | 1x:10 |
| AG | 20 | 20 | 1 | 1x:20 |
| AG | 50 | 50 | 1 | 1x:50 |
| AG | 100 | 97 | 2 | 1x:94,2x:3 |
| AG | 200 | 179 | 6 | 1x:166,2x:9,3x:2,4x:1,6x:1 |
| AG | 500 | 408 | 16 | 1x:364,2x:26,3x:11,4x:3,5x:1,6x:1,12x:1,16x:1 |

## Interpretation

OPS behaves as defined: every selected genome represents a different species
at all evaluated panel sizes.

SR remains effectively one-per-species across the evaluated range. It selects
one genome from each of 200 species at N=200 and, at N=500, represents 499
species, with one species represented twice.

AG, which allows every eligible genome to compete directly without species
control, increasingly selects multiple genomes from the same species as panel
size grows. At N=100 it represents 97 species; at N=200, 179 species; and at
N=500, 408 species. The maximum within-species multiplicity rises from two at
N=100 to six at N=200 and sixteen at N=500.

The diagnostic therefore shows increasing species repetition under unrestricted
all-genome maximin selection, whereas OPS prevents repetition by construction
and SR shows almost none through N=500.

This result supports the need to control species-level candidate abundance in
the BacSelect selection design. It does not by itself identify which species
are repeated, establish why individual species are repeated, or resolve the
OPS-versus-SR selector decision.

The OPS-versus-SR decision remains **UNRESOLVED**.

Identity blinding remains in force.
