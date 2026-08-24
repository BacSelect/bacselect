# Reproducibility

A BacSelect panel should be identifiable as a scientific result, not merely as a
list of accessions copied from a website.

## What must identify a release?

A published result is intended to record at least:

- BacSelect release identifier;
- frozen source-universe identity;
- selector version;
- architecture-schema version;
- requested panel size N;
- selected assembly accessions in deterministic order;
- checksums for release artefacts;
- software and environment provenance needed to verify the build.

## Why freeze the source universe?

Public genome archives change.

A reproducible panel must therefore record the exact source state from which it
was derived. Re-running the same selector against a later archive snapshot is a
new scientific result, not a rebuild of the old one.

## Deterministic rebuild

For a frozen release, rebuilding with the same inputs, scientific rules and
software version should reproduce the same ordered panel and release artefacts.

Deterministic rebuild testing is part of the pre-release validation programme.

## Fail closed

A monthly release candidate is intended to publish only when all mandatory
scientific, provenance and integrity checks pass.

If a check fails or an input is unresolved, the candidate is not published.
The previous validated release remains available.

## Portability

The long-term release workflow is intended not to depend on one institutional
HPC system.

The target is a release process that can be initiated from the public
repository using versioned software, public source data and reproducibly defined
compute environments.

That production release infrastructure has not yet been implemented.
