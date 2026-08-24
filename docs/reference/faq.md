# Frequently asked questions

## Does BacSelect represent all bacterial diversity?

No.

BacSelect operates within a defined public complete-genome universe. That
universe reflects upstream sampling, sequencing, assembly, deposition and
classification biases.

## Why not just choose one well-known genome from each species?

That answers a different question.

BacSelect is designed to span genome architecture. Familiarity, clinical
importance and organism identity are not intended ranking variables.

The final selector-v1 rule for species representation is still under
validation.

## Why not sample genomes at random?

Random sampling is useful and forms part of BacSelect validation.

However, a random sample can reflect archive abundance. BacSelect is being
developed as a deterministic diversity-seeking alternative with explicit
species-abundance control.

## Why use GenBank `GCA_` accessions?

BacSelect needs one canonical assembly identity for each source genome. The
proposed v1 design uses the GenBank assembly as that canonical source record.

See [Source universe](../concepts/source-universe.md).

## What does "coverage" mean in BacSelect?

BacSelect avoids treating coverage as an arbitrary percentage.

It measures the structural distance from each eligible genome to its nearest
selected panel genome.

See [Structural distance](../concepts/distance-and-coverage.md).

## Are larger panels always better?

They sample the defined architecture space more densely, but they also increase
downstream compute and analysis effort.

The useful N depends on the task.

## Will the same N always return the same genomes?

Within one frozen release and selector version, the result is intended to be
deterministic.

A later monthly release may differ because the eligible public source universe
has changed.

## Can I use BacSelect now?

Not yet for a scientific panel.

No BacSelect scientific release has been published. The current repository
contains development code and prospective validation evidence.
