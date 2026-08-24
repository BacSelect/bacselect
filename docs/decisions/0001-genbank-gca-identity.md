# 0001: Use GenBank assembly accessions as canonical source identities

## Status

Current BacSelect v1 design.

## Context

NCBI may expose a submitted GenBank assembly with a `GCA_` accession and a
paired RefSeq representation with a `GCF_` accession.

BacSelect needs one unambiguous canonical identity for each source assembly.

## Decision

Use the versioned GenBank `GCA_` assembly accession as the canonical BacSelect
assembly identifier.

## Why

The GenBank assembly is the submitted archive assembly and provides a direct
identity for the source record used by BacSelect.

A single canonical identifier also prevents a GenBank assembly and its paired
RefSeq representation from being treated as two independent source genomes.

## Consequences

Release artefacts must retain the exact accession version.

Paired RefSeq identifiers may be useful metadata, but they do not replace the
canonical `GCA_` identity.

Exact source-universe rules remain defined by the scientific specification.
