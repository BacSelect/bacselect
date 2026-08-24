# 0006: Fail closed when release validation is unresolved

## Status

Current release design.

## Context

Automated public-data workflows can encounter missing records, unexpected
metadata, changed inputs, failed computations or incomplete validation.

Publishing a partial result would make the release identity unreliable.

## Decision

A release candidate is published only when all mandatory scientific, provenance
and integrity gates pass.

Unresolved or failed checks block publication.

## Why

Keeping the previous validated release is safer and more interpretable than
publishing a partially verified replacement.

## Consequences

A nominal monthly trigger does not guarantee a monthly publication.

The previous validated release remains current until a new candidate passes all
required gates.
