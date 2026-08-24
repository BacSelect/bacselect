# Choosing N

**N** is the number of genomes in a BacSelect panel.

There is no universally correct value. The useful value depends mainly on how
many genomes your downstream analysis can reasonably handle.

| N | Practical interpretation |
| ---: | --- |
| 10-20 | Very compact panel for quick tests or expensive workflows |
| 50-100 | Middle scale for broader benchmarking |
| 200-500 | Denser sampling when additional compute is practical |

These are practical descriptions, not biological thresholds.

## What changes as N increases?

Within one release, BacSelect is intended to use one ordered diversity ladder.

A panel of size 20 therefore contains the first 20 genomes in that ladder, a
panel of size 50 the first 50, and so on.

Increasing N adds genomes rather than replacing earlier selections from the same
release.

## What is the trade-off?

Larger panels sample the defined architecture space more densely, but require
more downstream compute, storage and analysis time.

BacSelect will report nearest-panel structural-distance summaries for supported
panel sizes so users can judge that trade-off directly.

See [Structural distance](concepts/distance-and-coverage.md).
