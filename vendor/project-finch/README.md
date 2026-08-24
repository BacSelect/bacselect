# Vendored Project Finch repeat engine

BacSelect selector-v1 repeat-scale validation reuses the sequence-repeat
semantics that were previously validated for Project Finch Experiment 0.

The following files are vendored without modification from Project Finch
commit:

`904228199487575e183bc411a088fb435a531e0b`

## Vendored sources

`experiment-0/structural_features_fast.cpp`

SHA-256:

`bea979167a353c41e51bb96c83acebfb8e8136269d2902d99142c0780bf46925`

This is the validated production C++ implementation.

`experiment-0/structural_features.py`

SHA-256:

`c1e7388ba7db82d1b937a16e1a1be9e8c65d8779ce8691a2f0097cb5b6af6786`

This is the transparent Python semantic reference used for differential
validation.

## Build environment

The exact Project Finch feature environment was copied to:

`envs/bacselect-repeat-linux-64.lock`

Its SHA-256 is:

`aa6984b17e86f7d0627379e295fabed837cf7d43cc6a9fd80f32b7092ac5f64f`

The validated Project Finch production build used C++17, the conda compiler
toolchain and libdivsufsort.

The original Project Finch production executable had SHA-256:

`abb00cd36d9f6ebee91cb0c08992a751b6969766af5eb79e58f9f4f0e893cb48`

The unchanged vendored source reproduces this executable byte-for-byte when
compiled using the original `finch-features` environment and recorded
production command.

Executable identity is not required to remain byte-identical when the same
locked packages are installed under a differently named or located conda
environment because the build embeds the environment-specific library RPATH.

BacSelect therefore treats the original executable SHA-256 as Project Finch
provenance, not as a portable cross-environment build requirement.

For BacSelect production, the actual compiled executable SHA-256 is recorded
as run provenance. Scientific equivalence is additionally required through
source identity, environment-lock identity and differential validation
against the unchanged Python semantic reference.

## BacSelect use

BacSelect does not change the repeat semantics in these vendored files.

The repeat engine accepts arbitrary positive k values. Project Finch used
150 bp and 400 bp because those values were part of its sequencing-specific
experimental design.

BacSelect selector-v1 defines its candidate k values prospectively in
`validation/selector-v1/repeat-scale-method.md`.

Alternative-scale calculations must not proceed unless the BacSelect
reference-scale concordance gate reproduces the existing frozen 150-bp and
400-bp features for all 55,306 corrected eligible genomes.

## Source loading for reference-scale concordance

BacSelect also vendors without modification the Project Finch source loader
used for the selector-v1 reference-scale concordance gate.

`experiment-0/compute_structural_features.py`

SHA-256:

`e4d76a44731000dc8330d6f3289aca76ce6562329dd371f6f63ec090ab42db50`

`experiment-0/basic_structural_features.py`

SHA-256:

`30bc3f52fdf68cf7b6433262935b3ed2bb189b256672687bea56f3a4f4cc043a`

The loader verifies the audit-selected genomic FASTA, sequence-report file,
Primary Assembly component membership, component sequence hashes, lengths,
and recorded topology before a sequence is supplied to the repeat engine.

The concordance target universe is derived from the corrected 55,306-genome
BacSelect foundation rather than the original 55,420-genome Project Finch
structural-feature target set.
