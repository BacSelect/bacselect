# BacSelect

**Bacterial genome diversity, at the scale you need.**

BacSelect is a reproducible system for selecting compact, nested panels of
complete bacterial genome assemblies that span genome architecture.

A user chooses the number of genomes, N. BacSelect returns a deterministic,
versioned panel from a defined universe of eligible complete bacterial genome
assemblies. For a given release, every smaller panel is an exact prefix of the
same ordered selection ladder.

## Current release

**BacSelect 2026.09** is the first dated monthly BacSelect release.

- **68,164** eligible complete bacterial genome assemblies
- **16,223** species groups
- **OPS** selector, version **1.0.0**
- supported preset panels: **N = 10, 20, 50, 100, 200, 500**
- custom panel sizes: **N = 10–500**
- deterministic nested panels from a single complete OPS ladder
- release-specific structural-coverage measurements across all 16,223 species
  groups
- immutable release artefacts with checksums and provenance

Current release, downloads and provenance:

https://bacselect.github.io

Dated public release artefacts are published through the BacSelect website;
this repository contains the scientific implementation, specifications,
validation evidence and automated tests.

## Citation

For analyses using a dated BacSelect panel, cite the **version-specific Zenodo
release corresponding to the panel used**.

For BacSelect 2026.09:

**White R. BacSelect 2026.09: bacterial genome diversity panels. Zenodo.
https://doi.org/10.5281/zenodo.22658842**

The stable BacSelect concept DOI is:

**https://doi.org/10.5281/zenodo.22658841**

Use the concept DOI when referring to BacSelect generally. For reproducible
analyses, cite the version-specific DOI for the exact BacSelect release used.

GitHub citation metadata are provided in `CITATION.cff`; its preferred citation
tracks the current dated BacSelect dataset release.

## Validated Selector v1 foundation

The Selector v1 validation foundation is distinct from the current monthly
release universe.

The frozen validation work used:

- **55,306** eligible complete bacterial genome assemblies
- **13,765** species groups
- **12** sequence-derived genome-architecture features
- species-abundance-controlled architecture geometry
- prospective selector comparison and resolution testing
- structural-coverage evaluation
- deterministic reproducibility and release-validation gates

Those values describe the validated Selector v1 foundation and should not be
interpreted as the size of the current BacSelect release universe.

## Release model

BacSelect releases are dated `YYYY.MM`.

Each release defines its own eligible genome universe, species groups,
selection ladder, preset panels, metadata, structural-coverage results and
provenance. As public genome archives change, later releases may therefore
contain different source-universe and species-group counts while retaining the
frozen Selector v1 methodology.

For any release and supported N, the BacSelect panel is the first N genomes of
that release's complete OPS ladder.

## Repository structure

- `docs/` — scientific specifications and frozen design documents
- `src/bacselect/` — BacSelect implementation
- `tests/` — automated scientific and reproducibility tests
- `validation/` — validation designs, analyses and evidence

## Website

https://bacselect.github.io

## Licence

BacSelect-authored software in this repository is released under the
[MIT License](LICENSE).

This licence does not alter the terms applying to third-party source data.
BacSelect does not claim ownership of or relicense underlying genome records
obtained from public archives.
