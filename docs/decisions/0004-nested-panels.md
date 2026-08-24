# 0004: Use nested panels within a release

## Status

Required property of the intended selector.

## Context

Users may want to compare analyses at several panel sizes.

If each N is selected independently, increasing panel size can replace genomes
rather than simply add them.

## Decision

Construct one deterministic ordered diversity ladder per release.

A panel of size N is the first N entries in that ladder.

## Why

Nestedness makes comparisons between panel sizes easier to interpret and lets a
user increase N without changing the smaller panel already analysed.

## Consequences

The final selector-v1 design must produce one deterministic complete ordering.

The unresolved species-representation decision must therefore be solved in a
way that preserves nestedness.
