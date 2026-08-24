# 0005: Publish immutable versioned releases

## Status

Current release design.

## Context

Public genome archives change through new submissions, sequence updates,
suppression and classification changes.

A panel generated from a moving source universe cannot be reproduced reliably
unless the source state and result are versioned.

## Decision

BacSelect is designed around immutable scientific releases, intended on a
monthly cycle.

A published historical release is not rewritten when the public archive later
changes.

## Why

A release identifier should refer to one exact scientific result.

## Consequences

A later archive snapshot produces a new release rather than silently changing an
old one.

Analyses should record the BacSelect release alongside panel size and scientific
version information.
