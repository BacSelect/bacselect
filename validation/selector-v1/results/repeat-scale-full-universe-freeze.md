# Repeat-scale full-universe production evidence freeze

This record freezes the validated BacSelect selector-v1 alternative-k repeat-scale
production dataset before any inspection of which repeat-scale pair is selected.

## Production identity

- BacSelect commit: `83516de6cd3713415e78502ba58db072fa6b38f9`
- Production first wave: Slurm array job `2500117`, batches 001-008
- Remaining production: Slurm array job `2500125`, batches 009-111
- Production batches: 111
- Production targets: 55,306
- k grid: 50, 75, 100, 150, 200, 300, 400, 600, 800, 1200, 1600, 2400, 3200
- Repeat feature families: non_unique_fraction, maximum_multiplicity, inter_replicon_shared_fraction

## Full-universe independent audit

- batches: 111 / 111
- batches passed: 111
- batches failed: 0
- manifest rows: 55,306 / 55,306
- result rows: 55,306 / 55,306
- candidate JSONs: 55,306 / 55,306
- source payload files hashed: 110,612 / 110,612
- independent 150/400 reference anchors: 55,306 / 55,306
- errors: 0
- warnings: 0
- exit status: 0
- all_pass: true

The production-file manifest contains 55,639 files and has SHA256:

`75fd427a28b712b1c76ebe93722d2c6baac1e3d1bccedf63a00de71bebea5b84`

No repeat-scale pair was selected before this production evidence was frozen.
