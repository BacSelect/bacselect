# Getting started

BacSelect is being designed so that using a released panel does not require
Python or software-development experience.

## The basic idea

Suppose you need 50 bacterial genomes for a benchmark.

Public archives contain many thousands of complete bacterial genomes. Choosing
50 familiar organisms is easy, but subjective. Random sampling is reproducible,
but heavily represented species can dominate.

BacSelect is being developed to provide a deterministic alternative.

You choose:

> **N = 50**

A released BacSelect panel will provide 50 selected GenBank assembly accessions,
together with the release identity and provenance needed to reproduce the
selection.

## What you will receive

A released panel will include, at minimum:

- selected `GCA_` assembly accessions;
- genome metadata;
- BacSelect release identifier;
- selector version;
- architecture-schema version;
- checksums and provenance.

## What you do with the accessions

The accession list identifies the selected public genome assemblies. You can use
those accessions to retrieve the corresponding genome records from the public
archive using your preferred workflow.

BacSelect does not require users to adopt a particular downstream analysis
pipeline.

## What BacSelect is not

BacSelect is not:

- a taxonomy;
- a pathogen-priority list;
- a catalogue of clinically important bacteria;
- a claim to represent all bacterial life;
- a replacement for biologically specific controls.

It addresses a narrower question: how to choose a manageable, reproducible panel
that spans genome architecture within a defined public source universe.

## Can I download a panel now?

Not yet.

No scientific BacSelect panel has been released. Selector-v1 validation must be
completed before the first public panel is published.
