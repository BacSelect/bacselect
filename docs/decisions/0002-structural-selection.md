# 0002: Select on genome architecture, not organism importance

## Status

Current BacSelect design principle.

## Context

A small bacterial genome panel can be assembled using many criteria: familiar
species, pathogen status, clinical importance, publication frequency, taxonomy
or structural genome properties.

Those criteria answer different questions.

## Decision

BacSelect uses genome-architecture properties as selection variables.

Organism identity, pathogen status, clinical priority and publication prominence
are not intended ranking variables.

## Why

The purpose of BacSelect is to build manageable panels spanning structural
genome properties for benchmarking and method evaluation.

Selecting familiar or important organisms would introduce a different,
use-case-specific objective.

## Consequences

A BacSelect panel is not a pathogen-priority panel and does not claim biological
importance for the selected genomes.

Users with a taxonomic, ecological or clinical target should apply criteria
appropriate to that question instead.
