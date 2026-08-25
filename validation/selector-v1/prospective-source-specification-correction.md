# Prospective source-specification correction

This note records two documentation corrections made before the first fresh
BacSelect source-universe query for the external selector-resolution
experiment.

## Assembly status

The previous public specification stated that NCBI Datasets
`--assembly-version current` should yield retained records with assembly status
`latest`.

The NCBI Datasets genome assembly report schema used by BacSelect defines the
relevant `assemblyInfo.assemblyStatus` value as `current`, with other enum
values including `previous`, `suppressed` and deprecated `retired`.

The specification is corrected to require `current`.

No fresh BacSelect source snapshot or selector-resolution outcome had been
generated before this correction.

## Final repeat scales

The source-universe section of the public scientific specification still
described the historical Project Finch 150/400 repeat coordinates.

BacSelect selector-v1 subsequently selected and froze the final repeat scales
300/2400.

The specification is corrected to the already frozen final 300/2400 feature
architecture. This is documentation alignment with existing frozen BacSelect
evidence, not a new feature-selection outcome.
