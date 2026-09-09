# Methods and software references

This page records scholarly and software references relevant to the methods
implemented or used by BacSelect. These references are distinct from the
citation for BacSelect itself or for a dated BacSelect data release.

## Diversity-seeking selection

The iterative BacSelect OPS selection step that chooses the candidate
maximising its minimum distance from the already selected set is related to
the classical farthest-first / maximin traversal described by:

Gonzalez TF. Clustering to minimize the maximum intercluster distance.
Theoretical Computer Science. 1985;38:293-306.
https://doi.org/10.1016/0304-3975(85)90224-5

BacSelect is not an implementation of the Gonzalez clustering method as a
whole. BacSelect additionally defines its own biological feature geometry,
species-representative restriction, deterministic initialisation, tie
handling, nested panel construction, and release framework.

## Circular sequence canonicalisation

BacSelect canonicalises circular replicon sequences using a linear-time
lexicographically minimal circular-rotation procedure. This belongs to the
classical lexicographically least circular substring problem described by:

Booth KS. Lexicographically least circular substrings.
Information Processing Letters. 1980;10(4-5):240-242.
https://doi.org/10.1016/0020-0190(80)90149-0

BacSelect combines circular-rotation canonicalisation with reverse-complement
canonicalisation to obtain a topology-aware representation for sequence
fingerprinting.

## NCBI Datasets

BacSelect uses NCBI Datasets as its assembly discovery and retrieval
interface.

O'Leary NA, Cox E, Holmes JB, Anderson WR, Falk R, Hem V, et al.
Exploring and retrieving sequence and metadata for species across the tree
of life with NCBI Datasets.
Scientific Data. 2024;11:732.
https://doi.org/10.1038/s41597-024-03571-y

## NCBI Taxonomy

BacSelect uses NCBI Taxonomy information as part of its frozen and monthly
taxonomy-resolution workflow.

Schoch CL, Ciufo S, Domrachev M, Hotton CL, Kannan S, Khovanskaya R, et al.
NCBI Taxonomy: a comprehensive update on curation, resources and tools.
Database. 2020;2020:baaa062.
https://doi.org/10.1093/database/baaa062

## libdivsufsort

The validated repeat-feature environment uses libdivsufsort 2.0.2, a
suffix-array construction library by Yuta Mori.

https://github.com/y-256/libdivsufsort

Licence and dependency information are recorded in
`THIRD_PARTY_NOTICES.md`.
