# Project Finch validation foundation

This directory identifies the frozen Project Finch genome universe used for
prospective development and validation of BacSelect.

BacSelect does not modify these Project Finch artefacts and does not copy the
55,306-row source matrices into this repository.

The frozen validation foundation contains:

- 55,306 eligible complete bacterial genomes;
- 13,765 resolved species groups;
- 12 raw sequence-derived structural features per genome;
- a corresponding frozen Project Finch percentile feature matrix; and
- deterministic species-group assignments.

The raw feature matrix, percentile matrix, and species mapping contain exactly
the same 55,306 unique canonical GenBank assembly accessions in exactly the
same row order.

Independent Project Finch rebuilds of the three authoritative inputs were
byte-identical to their frozen counterparts.

## Important

This dataset is a validation foundation, not a BacSelect release.

BacSelect selector design and feature-schema decisions remain prospective.
Panel identities must not be used to choose or tune the selector before the
validation design is frozen.
