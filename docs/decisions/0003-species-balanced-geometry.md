# 0003: Control species abundance in feature geometry

## Status

Current selector-v1 validation design.

## Context

Public genome archives are unevenly sampled. Some species contribute many more
eligible complete assemblies than others.

If every genome contributes equal weight to empirical feature distributions,
archive abundance can dominate the geometry.

## Decision

Construct feature percentiles using species-balanced weights.

For a species with `n` eligible genomes, each genome contributes weight `1/n`.

## Why

This makes each species contribute the same total weight to the empirical
feature distribution while retaining within-species structural variation.

## Alternatives considered

A simple genome-weighted empirical distribution is easier to compute but
directly reflects archive abundance.

Selecting exactly one representative per species is a separate design question
and is not implied by species-balanced feature scaling.

## Consequences

Species balancing controls one known archive-abundance effect. It does not make
the underlying public genome universe unbiased.
