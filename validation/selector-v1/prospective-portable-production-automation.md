# Prospective portable production automation

## Status

This document freezes the infrastructure boundary for BacSelect monthly
production automation before production source acquisition is enabled.

The scheduler may be installed and tested before the first production
monthly source snapshot. Installation of the scheduler does not itself
authorize acquisition or publication of a BacSelect monthly release.

## Portability requirement

BacSelect is an independent public resource.

Production must remain operational without access to any current
institutional compute environment.

In particular, monthly production must not depend on:

- jynx;
- PHF Science compute or storage;
- Slurm;
- institution-specific mounted filesystems;
- institution-specific environment files;
- a self-hosted runner controlled by the user's current employer.

Those resources may be used for development or independent validation,
but they are not part of the production dependency chain.

## Production orchestration

The canonical monthly trigger is maintained in the BacSelect source
repository.

The scheduled trigger is:

- day: UTC day 01;
- time: 00:17 UTC;
- cadence: monthly.

The non-zero minute is deliberate because scheduled GitHub Actions
workflows are more susceptible to load-related delay at the start of an
hour.

The workflow must also support manual dispatch for validation and
recovery.

## Execution model

Production execution must use portable, publicly reproducible software
environments.

The initial orchestration target is a GitHub-hosted Linux runner.

Scientific stages that cannot reliably complete within one hosted-runner
job must be divided into deterministic, resumable jobs. The scientific
pipeline must not assume that all stages execute on the same host.

Future migration to another commodity compute provider must not require
a change in BacSelect scientific selection semantics.

## Persistent state

Transient runner storage and workflow caches are not authoritative
BacSelect scientific records.

Immutable release artefacts, checksums and provenance must be stored in
persistent public release infrastructure.

Upstream sequence data may be reacquired from its canonical public
source where allowed by the frozen release method.

Reusable derived evidence may be cached only where reuse is explicitly
permitted by the frozen scientific specification and its identity and
integrity requirements are satisfied.

## Fail-closed publication

A scheduled event does not imply that a release exists.

Source acquisition, downstream processing and publication are separate
gated states.

No monthly release may be published unless every required scientific,
integrity and provenance gate succeeds.

The website may show the next scheduled update time, but must not imply
that publication is guaranteed at that exact time.

## Initial automation state

The first checked-in monthly workflow is intentionally preflight-only.

It verifies:

- portable execution infrastructure;
- repository-defined installation on the hosted runner;
- the complete BacSelect test suite;
- availability of the frozen monthly release primitives;
- the UTC day-01 gate for scheduled runs.

It does not acquire the canonical monthly source snapshot and cannot
publish a release.

Production acquisition is enabled only after the complete portable
monthly pipeline and its publication gates have been frozen and tested.
