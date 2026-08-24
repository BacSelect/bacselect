# Genome architecture

BacSelect describes genomes using structural properties rather than organism
names, pathogen status or clinical importance.

The current development feature space includes properties of:

- genome length;
- GC content;
- chromosome and non-chromosomal replicons;
- the fraction of sequence outside the chromosome;
- repeated sequence;
- sequence shared between replicons.

These properties describe aspects of genome organisation that may matter when
testing genome-analysis methods.

## Why not use species names?

Species identity answers a different question.

Two genomes can belong to different species yet have similar structural
properties, while genomes within one species can differ in plasmids, repeats or
other architectural features.

BacSelect therefore treats taxonomy and structural diversity as separate
concepts.

The exact BacSelect v1 feature schema remains under validation.
